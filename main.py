"""
astrbot-plugin-vocadaily — 每日术曲推荐插件

功能：
  - 从 B站收藏夹同步曲库到本地 SQLite 数据库
  - /jrsq          随机推荐一首术曲（发送视频 + 信息）
  - /jrsq list     查看曲库列表（分页）
  - /jrsq add      手动添加曲目（BV号）
  - /jrsq del      删除曲目
  - /jrsq search   按标题搜索
  - /jrsq favsync  从收藏夹同步新曲目
  - /jrsq count    查看曲库数量
  - 每天定时推送
"""

import asyncio
import json
import logging
import os

import aiohttp
import aiosqlite
from astrbot.api.all import *
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("astrbot")

# ============================================================================
# 常量
# ============================================================================
PLUGIN_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(PLUGIN_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "jrsq.db")
CONFIG_PATH = os.path.join(DATA_DIR, "plugin_config.json")

BILI_VIEW_API = "https://api.bilibili.com/x/web-interface/view"
BILI_PLAYURL_API = "https://api.bilibili.com/x/player/playurl"
BILI_FAV_API = "https://api.bilibili.com/x/v3/fav/resource/list"
BILI_VIDEO_BASE = "https://www.bilibili.com/video/"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

os.makedirs(DATA_DIR, exist_ok=True)


# ============================================================================
# 配置
# ============================================================================
def load_plugin_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)



# ============================================================================
# 数据库层
# ============================================================================
class SongDB:
    """本地 SQLite 曲库"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init(self) -> None:
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS songs (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    bvid     TEXT    NOT NULL UNIQUE,
                    cid      INTEGER NOT NULL,
                    title    TEXT    NOT NULL,
                    author   TEXT    DEFAULT '',
                    cover    TEXT    DEFAULT '',
                    duration INTEGER DEFAULT 0,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    # ---- 增删改查 ----

    async def add(self, bvid: str, cid: int, title: str,
                  author: str = "", cover: str = "", duration: int = 0) -> bool:
        """添加曲目，已存在则返回 False"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO songs (bvid, cid, title, author, cover, duration) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (bvid, cid, title, author, cover, duration),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def delete(self, song_id: int) -> bool:
        """按 ID 删除"""
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("DELETE FROM songs WHERE id = ?", (song_id,))
            await db.commit()
            return cur.rowcount > 0

    async def random(self) -> dict | None:
        """随机返回一首"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM songs ORDER BY RANDOM() LIMIT 1")
            row = await cur.fetchone()
            return dict(row) if row else None

    async def list_all(self, page: int = 1, per_page: int = 10) -> tuple[list[dict], int]:
        """分页列表，返回 (条目列表, 总条数)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # 总数
            cur = await db.execute("SELECT COUNT(*) FROM songs")
            total = (await cur.fetchone())[0]
            # 分页
            offset = (page - 1) * per_page
            cur = await db.execute(
                "SELECT * FROM songs ORDER BY id DESC LIMIT ? OFFSET ?",
                (per_page, offset),
            )
            rows = [dict(r) for r in await cur.fetchall()]
            return rows, total

    async def search(self, keyword: str, limit: int = 20) -> list[dict]:
        """按标题模糊搜索"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM songs WHERE title LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{keyword}%", limit),
            )
            return [dict(r) for r in await cur.fetchall()]

    async def count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM songs")
            return (await cur.fetchone())[0]

    async def has_bvid(self, bvid: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT 1 FROM songs WHERE bvid = ?", (bvid,))
            return await cur.fetchone() is not None

    async def get_all_bvids(self) -> set[str]:
        """获取所有已存 BV 号（用于收藏夹同步去重）"""
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT bvid FROM songs")
            return {r[0] for r in await cur.fetchall()}


# ============================================================================
# B站 API 工具
# ============================================================================
class BiliAPI:
    """封装 B站公开 API 调用（复用 session 减少连接开销）"""

    HEADERS = {
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
    }

    _session: aiohttp.ClientSession | None = None

    @classmethod
    async def _get_session(cls) -> aiohttp.ClientSession:
        """获取或创建共享 session，避免每次请求都建立新连接"""
        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            cls._session = aiohttp.ClientSession(timeout=timeout, headers=cls.HEADERS)
        return cls._session

    @classmethod
    async def close_session(cls) -> None:
        """关闭共享 session（插件卸载时调用）"""
        if cls._session and not cls._session.closed:
            await cls._session.close()

    @classmethod
    async def get_video_info(cls, bvid: str) -> dict | None:
        """通过 BV 号获取视频信息 (cid, title, author, cover, duration)"""
        s = await cls._get_session()
        async with s.get(BILI_VIEW_API, params={"bvid": bvid}) as resp:
            data = await resp.json()
            if data.get("code") != 0:
                return None
            d = data["data"]
            return {
                "bvid": bvid,
                "cid": d.get("cid", 0),
                "title": d.get("title", ""),
                "author": d.get("owner", {}).get("name", ""),
                "cover": d.get("pic", ""),
                "duration": d.get("duration", 0),
            }

    @classmethod
    async def get_play_url(cls, bvid: str, cid: int) -> str | None:
        """获取可下载的视频直链（MP4）。失败返回 None。"""
        s = await cls._get_session()
        async with s.get(
            BILI_PLAYURL_API,
            params={"bvid": bvid, "cid": cid, "qn": 80, "fnval": 1},
        ) as resp:
            data = await resp.json()
            if data.get("code") != 0:
                return None
            durl = data.get("data", {}).get("durl", [])
            if durl:
                return durl[0].get("url")
            return None

    @classmethod
    async def _fetch_fav_page(cls, media_id: str, page: int, page_size: int) -> list[dict]:
        """拉取收藏夹单页（内部方法，使用共享 session）"""
        s = await cls._get_session()
        params = {"media_id": media_id, "pn": page, "ps": page_size, "platform": "web"}
        async with s.get(BILI_FAV_API, params=params) as resp:
            data = await resp.json()
            if data.get("code") != 0:
                return []
            medias = data.get("data", {}).get("medias") or []
            results = []
            for item in medias:
                bvid = item.get("bvid", "")
                title = item.get("title", "").strip()
                if bvid and title:
                    results.append({"bvid": bvid, "title": title})
            return results

    @classmethod
    async def fetch_fav_all(cls, media_id: str, page_size: int = 20) -> list[dict]:
        """拉取整个收藏夹，返回 [{bvid, title}, ...]"""
        s = await cls._get_session()
        params = {"media_id": media_id, "pn": 1, "ps": page_size, "platform": "web"}
        async with s.get(BILI_FAV_API, params=params) as resp:
            data = await resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"收藏夹 API 错误: code={data.get('code')}")

        info = data.get("data", {}).get("info", {})
        total_pages = max(1, int(info.get("page_count", 1)))

        # 收集第一页
        all_videos: list[dict] = []
        medias = data.get("data", {}).get("medias") or []
        for item in medias:
            bvid = item.get("bvid", "")
            title = item.get("title", "").strip()
            if bvid and title:
                all_videos.append({"bvid": bvid, "title": title})

        # 剩余页并发
        if total_pages > 1:
            tasks = [
                cls._fetch_fav_page(media_id, p, page_size)
                for p in range(2, total_pages + 1)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    all_videos.extend(r)

        return all_videos


# ============================================================================
# 插件主体
# ============================================================================
@register("jrsq", "sakura", "每日术曲推荐 — B站术曲随机推送（视频消息）", "3.0.0")
class JRSQPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        self.db = SongDB(DB_PATH)

        # ---- 读取配置 ----
        cfg = load_plugin_config()
        bili_cfg = cfg.get("bilibili", {})
        push_cfg = cfg.get("push", {})

        self.media_id = str(bili_cfg.get("media_id", "8745208"))
        self.page_size = int(bili_cfg.get("page_size", 20))
        self.target_groups = push_cfg.get("target_groups", [])
        cron_hour = push_cfg.get("cron_hour", 12)
        cron_minute = push_cfg.get("cron_minute", 0)

        # ---- 定时器 ----
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(
            self.scheduled_push, "cron", hour=cron_hour, minute=cron_minute
        )
        self.scheduler.start()

    async def initialize(self) -> None:
        """插件激活时初始化数据库"""
        await self.db.init()
        logger.info(f"[jrsq] 数据库已初始化，当前曲库 {await self.db.count()} 首")

    async def terminate(self) -> None:
        """插件卸载时清理资源"""
        self.scheduler.shutdown(wait=False)
        await BiliAPI.close_session()

    # ==================================================================
    # 核心：随机推荐（返回视频）
    # ==================================================================
    async def _build_video_message(self, song: dict) -> MessageChain:
        """
        根据曲目信息构建消息链：
          - 文本：🎵 标题 + 作者
          - 视频：从 B站直链下载的 MP4
        失败时降级为纯文本 + 链接。
        """
        text = (
            f"🎵 今日术曲推荐：\n"
            f"{song['title']}\n"
            f"👤 UP主：{song.get('author', '未知')}"
        )

        try:
            play_url = await BiliAPI.get_play_url(song["bvid"], song["cid"])
        except Exception:
            play_url = None

        if play_url:
            try:
                return MessageChain([
                    Plain(text),
                    Video.fromURL(play_url),
                ])
            except Exception as e:
                logger.warning(f"[jrsq] 视频发送失败，降级为链接: {e}")

        # 降级
        return MessageChain([
            Plain(text + f"\n🔗 {BILI_VIDEO_BASE}{song['bvid']}"),
            Plain("\n⚠️ 视频直链获取失败，请点击链接观看"),
        ])

    # ==================================================================
    # 指令：/jrsq
    # ==================================================================
    @filter.command("jrsq")
    async def cmd_random(self, event: AstrMessageEvent):
        """随机推荐一首术曲"""
        try:
            song = await self.db.random()
            if song is None:
                yield event.plain_result("😢 曲库为空，请先用 /jrsq favsync 同步或 /jrsq add 添加曲目。")
                return

            msg = await self._build_video_message(song)
            yield event.chain_result([msg])
        except Exception as e:
            logger.error(f"[jrsq] 随机推荐异常: {e}", exc_info=True)
            yield event.plain_result(f"😢 出了点问题: {e}")

    # ==================================================================
    # 指令：/jrsq list [页码]
    # ==================================================================
    @filter.command("jrsq list")
    async def cmd_list(self, event: AstrMessageEvent):
        """查看曲库列表（分页，每页 10 条）"""
        try:
            msg = event.message_str.strip()
            page = 1
            # 尝试提取页码，如 "/jrsq list 2"
            parts = msg.split()
            if len(parts) >= 3:
                try:
                    page = max(1, int(parts[2]))
                except ValueError:
                    pass

            songs, total = await self.db.list_all(page=page, per_page=10)
            if not songs:
                yield event.plain_result("😢 曲库为空。")
                return

            total_pages = (total + 9) // 10
            lines = [f"📋 曲库列表 ({total}首) [第{page}/{total_pages}页]"]
            for s in songs:
                dur = s.get("duration", 0)
                dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else "??:??"
                lines.append(
                    f"  [{s['id']}] {s['title']}  |  {dur_str}  |  {s['bvid']}"
                )
            if page < total_pages:
                lines.append(f"👉 输入 /jrsq list {page + 1} 查看下一页")

            yield event.plain_result("\n".join(lines))
        except Exception as e:
            yield event.plain_result(f"😢 查询失败: {e}")

    # ==================================================================
    # 指令：/jrsq add <BV号>
    # ==================================================================
    @filter.command("jrsq add")
    async def cmd_add(self, event: AstrMessageEvent):
        """从 B站添加曲目，用法: /jrsq add BV1xx411c7m9"""
        try:
            parts = event.message_str.strip().split()
            if len(parts) < 3:
                yield event.plain_result("⚠️ 用法: /jrsq add <BV号>")
                return

            bvid = parts[2].strip()
            if bvid.startswith("http"):
                # 用户可能粘贴了完整链接
                if "BV" in bvid:
                    bvid = bvid[bvid.index("BV"):]
                bvid = bvid.split("?")[0].split("/")[-1]

            if not bvid.startswith("BV"):
                yield event.plain_result("⚠️ 请输入有效的 BV 号（以 BV 开头）")
                return

            # 检查是否已存在
            if await self.db.has_bvid(bvid):
                yield event.plain_result(f"⚠️ {bvid} 已在曲库中。")
                return

            # 从 B站 获取详情
            yield event.plain_result(f"🔍 正在获取 {bvid} 的信息...")

            info = await BiliAPI.get_video_info(bvid)
            if info is None:
                yield event.plain_result(f"😢 无法获取 {bvid} 的信息，请检查 BV 号是否正确。")
                return

            await self.db.add(**info)
            yield event.plain_result(
                f"✅ 已添加: {info['title']}\n"
                f"   UP主: {info['author']}  |  {info['duration'] // 60}:{info['duration'] % 60:02d}"
            )
        except Exception as e:
            yield event.plain_result(f"😢 添加失败: {e}")

    # ==================================================================
    # 指令：/jrsq del <ID>
    # ==================================================================
    @filter.command("jrsq del")
    async def cmd_delete(self, event: AstrMessageEvent):
        """删除曲目，用法: /jrsq del 3"""
        try:
            parts = event.message_str.strip().split()
            if len(parts) < 3:
                yield event.plain_result("⚠️ 用法: /jrsq del <曲目ID>\n先用 /jrsq list 查看 ID")
                return

            song_id = int(parts[2])
            ok = await self.db.delete(song_id)
            if ok:
                yield event.plain_result(f"✅ 已删除曲目 ID={song_id}")
            else:
                yield event.plain_result(f"😢 未找到 ID={song_id} 的曲目。")
        except ValueError:
            yield event.plain_result("⚠️ ID 必须是数字，请用 /jrsq list 查看。")
        except Exception as e:
            yield event.plain_result(f"😢 删除失败: {e}")

    # ==================================================================
    # 指令：/jrsq search <关键词>
    # ==================================================================
    @filter.command("jrsq search")
    async def cmd_search(self, event: AstrMessageEvent):
        """搜索曲目，用法: /jrsq search 深海"""
        try:
            msg = event.message_str.strip()
            keyword = " ".join(msg.split()[2:]) if len(msg.split()) > 2 else ""
            if not keyword:
                yield event.plain_result("⚠️ 用法: /jrsq search <关键词>")
                return

            songs = await self.db.search(keyword)
            if not songs:
                yield event.plain_result(f"😢 未找到包含「{keyword}」的曲目。")
                return

            lines = [f"🔍 搜索「{keyword}」结果 ({len(songs)}首):"]
            for s in songs:
                dur = s.get("duration", 0)
                dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else "??:??"
                lines.append(f"  [{s['id']}] {s['title']}  |  {dur_str}  |  {s['bvid']}")
            yield event.plain_result("\n".join(lines))
        except Exception as e:
            yield event.plain_result(f"😢 搜索失败: {e}")

    # ==================================================================
    # 指令：/jrsq favsync
    # ==================================================================
    @filter.command("jrsq favsync")
    async def cmd_favsync(self, event: AstrMessageEvent):
        """从 B站收藏夹同步新曲目到本地数据库"""
        try:
            yield event.plain_result(f"🔄 正在从收藏夹 (media_id={self.media_id}) 同步...")

            # 拉取收藏夹全部视频
            fav_videos = await BiliAPI.fetch_fav_all(self.media_id, self.page_size)
            if not fav_videos:
                yield event.plain_result(
                    "😢 收藏夹为空或无法访问，请检查 media_id 是否正确。\n"
                    "提示: 在 B站收藏夹页面 URL 中可找到 media_id"
                )
                return

            # 去重
            existing = await self.db.get_all_bvids()
            new_count = 0
            skip_count = 0
            fail_count = 0

            for v in fav_videos:
                if v["bvid"] in existing:
                    skip_count += 1
                    continue
                # 获取完整信息后写入
                try:
                    info = await BiliAPI.get_video_info(v["bvid"])
                    if info:
                        await self.db.add(**info)
                        new_count += 1
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1

            total = await self.db.count()
            yield event.plain_result(
                f"✅ 同步完成！\n"
                f"   📥 新增: {new_count} 首\n"
                f"   ⏭️ 已存在: {skip_count} 首\n"
                f"   ❌ 失败: {fail_count} 首\n"
                f"   📊 曲库总计: {total} 首"
            )
        except Exception as e:
            logger.error(f"[jrsq] 同步失败: {e}", exc_info=True)
            yield event.plain_result(f"😢 同步失败: {e}")

    # ==================================================================
    # 指令：/jrsq count
    # ==================================================================
    @filter.command("jrsq count")
    async def cmd_count(self, event: AstrMessageEvent):
        """查看曲库曲目数"""
        try:
            cnt = await self.db.count()
            yield event.plain_result(f"📊 曲库共有 {cnt} 首术曲。")
        except Exception as e:
            yield event.plain_result(f"😢 查询失败: {e}")

    # ==================================================================
    # 定时推送
    # ==================================================================
    async def scheduled_push(self):
        """每天定时推送"""
        song = await self.db.random()
        if song is None:
            logger.warning("[jrsq] 曲库为空，跳过定时推送。")
            return

        msg = await self._build_video_message(song)

        for group_id in self.target_groups:
            try:
                gid = str(group_id).strip()
                if not gid:
                    continue
                await self.context.send_message(target=gid, message=msg)
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.error(f"[jrsq] 推送到群 {group_id} 失败: {e}")
