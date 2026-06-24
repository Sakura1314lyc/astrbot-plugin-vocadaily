import asyncio
import json
import logging
import os
import random
import time

import aiohttp
from astrbot.api.all import *

logger = logging.getLogger("astrbot")

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
BILI_FAV_API = "https://api.bilibili.com/x/v3/fav/resource/list"
BILI_VIDEO_BASE = "https://www.bilibili.com/video/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "plugin_config.json")


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------
def load_plugin_config() -> dict:
    """加载插件配置文件，不存在则返回空字典"""
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_plugin_config(config: dict) -> None:
    """持久化插件配置文件"""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# B站收藏夹数据获取器
# ---------------------------------------------------------------------------
class BiliFavFetcher:
    """
    从 B站公开收藏夹拉取视频列表，并在内存中缓存。
    使用方式：
        fetcher = BiliFavFetcher(media_id="8745208", cache_minutes=30)
        video = await fetcher.random_video()  # -> {"title": "...", "bvid": "..."}
    """

    def __init__(
        self,
        media_id: str,
        page_size: int = 20,
        cache_minutes: int = 30,
        timeout: int = 15,
    ):
        self.media_id = media_id
        self.page_size = page_size
        self.cache_minutes = cache_minutes
        self.timeout = timeout

        self._videos: list[dict] = []       # 内存缓存
        self._last_fetch: float = 0.0       # 上次拉取时间戳
        self._total_pages: int = 1          # 收藏夹总页数

    # ------------------------------------------------------------------
    # 底层 API 请求
    # ------------------------------------------------------------------
    async def _fetch_page(self, session: aiohttp.ClientSession, page: int) -> dict:
        """请求单页收藏夹数据，返回解析后的 JSON。"""
        params = {
            "media_id": self.media_id,
            "pn": page,
            "ps": self.page_size,
            "platform": "web",
        }
        headers = {
            "User-Agent": UA,
            "Referer": "https://www.bilibili.com/",
        }
        async with session.get(
            BILI_FAV_API, params=params, headers=headers, timeout=self.timeout
        ) as resp:
            return await resp.json()

    @staticmethod
    def _parse_video(item: dict) -> dict | None:
        """从 API 返回的单条数据中提取 title 和 bvid。"""
        title = item.get("title", "")
        bvid = item.get("bvid", "")
        # 跳过已失效视频
        if not title or not bvid:
            return None
        return {"title": title.strip(), "bvid": bvid}

    # ------------------------------------------------------------------
    # 拉取全部收藏夹
    # ------------------------------------------------------------------
    async def refresh_cache(self) -> None:
        """全量拉取收藏夹视频并写入缓存。"""
        async with aiohttp.ClientSession() as session:
            # ① 先拉第一页，获取总页数
            data = await self._fetch_page(session, 1)
            code = data.get("code", -1)
            if code != 0:
                raise RuntimeError(
                    f"B站 API 返回异常，code={code}, message={data.get('message', '')}"
                )

            info = data.get("data", {}).get("info", {})
            self._total_pages = max(1, int(info.get("page_count", 1)))

            # ② 解析第一页
            videos: list[dict] = []
            medias = data.get("data", {}).get("medias", []) or []
            for item in medias:
                v = self._parse_video(item)
                if v:
                    videos.append(v)

            # ③ 如有剩余页，并发拉取
            if self._total_pages > 1:
                tasks = []
                for p in range(2, self._total_pages + 1):
                    tasks.append(self._fetch_page(session, p))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        # 单页失败不中断整体，记录日志
                        logger.warning(f"[jrsq] 拉取收藏夹第页失败: {r}")
                        continue
                    if isinstance(r, dict):
                        medias = r.get("data", {}).get("medias", []) or []
                        for item in medias:
                            v = self._parse_video(item)
                            if v:
                                videos.append(v)

            self._videos = videos
            self._last_fetch = time.time()
            logger.info(f"[jrsq] 缓存已刷新，共 {len(self._videos)} 个视频")

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------
    def is_cache_stale(self) -> bool:
        """缓存是否过期。"""
        if not self._videos:
            return True
        elapsed = time.time() - self._last_fetch
        return elapsed > self.cache_minutes * 60

    async def random_video(self) -> dict | None:
        """随机返回一个视频，缓存过期时自动刷新。"""
        if self.is_cache_stale():
            await self.refresh_cache()
        if not self._videos:
            return None
        return random.choice(self._videos)

    async def get_video_count(self) -> int:
        """返回缓存中的视频总数。"""
        if self.is_cache_stale():
            await self.refresh_cache()
        return len(self._videos)


# ---------------------------------------------------------------------------
# 插件主体
# ---------------------------------------------------------------------------
@register("jrsq", "sakura", "每日术曲推荐 — 从B站收藏夹随机推送术曲视频", "2.0.0")
class JRSQPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        # ---------- 读取配置 ----------
        cfg = load_plugin_config()
        bili_cfg = cfg.get("bilibili", {})
        push_cfg = cfg.get("push", {})

        media_id = bili_cfg.get("media_id", "8745208")
        page_size = bili_cfg.get("page_size", 20)
        cache_minutes = bili_cfg.get("cache_minutes", 30)
        timeout = bili_cfg.get("timeout_seconds", 15)

        self.fetcher = BiliFavFetcher(
            media_id=str(media_id),
            page_size=int(page_size),
            cache_minutes=int(cache_minutes),
            timeout=int(timeout),
        )

        # ---------- 推送配置 ----------
        self.target_groups = push_cfg.get("target_groups", [])
        cron_hour = push_cfg.get("cron_hour", 12)
        cron_minute = push_cfg.get("cron_minute", 0)

        # ---------- 定时器 ----------
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(
            self.scheduled_push, "cron", hour=cron_hour, minute=cron_minute
        )
        self.scheduler.start()

    # ==================================================================
    # 数据层
    # ==================================================================
    async def get_shuju_data(self) -> str:
        """从 B站收藏夹随机获取一首术曲，拼接为消息文本。"""
        try:
            video = await self.fetcher.random_video()
        except Exception as e:
            logger.error(f"[jrsq] 获取视频失败: {e}", exc_info=True)
            return f"😢 获取术曲失败了，请稍后再试。\n({e})"

        if video is None:
            return "😢 收藏夹里还没有视频，请联系管理员添加曲目。"

        return (
            f"🎵 今日术曲推荐：\n"
            f"{video['title']}\n"
            f"🔗 视频链接：{BILI_VIDEO_BASE}{video['bvid']}"
        )

    # ==================================================================
    # 指令层
    # ==================================================================
    @filter.command("jrsq")
    async def handle_jrsq_command(self, event: AstrMessageEvent):
        """处理 /jrsq 指令 — 手动触发每日术曲"""
        result_msg = await self.get_shuju_data()
        yield event.plain_result(result_msg)

    @filter.command("jrsq_refresh")
    async def handle_refresh_command(self, event: AstrMessageEvent):
        """处理 /jrsq_refresh 指令 — 手动刷新缓存"""
        try:
            await self.fetcher.refresh_cache()
            cnt = len(self.fetcher._videos)
            yield event.plain_result(f"✅ 缓存已刷新，共 {cnt} 首曲目。")
        except Exception as e:
            yield event.plain_result(f"😢 缓存刷新失败: {e}")

    @filter.command("jrsq_count")
    async def handle_count_command(self, event: AstrMessageEvent):
        """处理 /jrsq_count 指令 — 查看当前缓存的曲目数"""
        try:
            cnt = await self.fetcher.get_video_count()
            yield event.plain_result(f"📊 当前缓存曲目数: {cnt}")
        except Exception as e:
            yield event.plain_result(f"😢 查询失败: {e}")

    # ==================================================================
    # 定时推送
    # ==================================================================
    async def scheduled_push(self):
        """每天定时推送到配置的群聊。"""
        result_msg = await self.get_shuju_data()

        if not self.target_groups:
            logger.warning("[jrsq] 未配置目标群组，跳过定时推送。")
            return

        for group_id in self.target_groups:
            try:
                gid = str(group_id).strip()
                if not gid:
                    continue
                await self.context.send_message(
                    target=gid,
                    message=MessageChain([Plain(result_msg)]),
                )
                await asyncio.sleep(1)  # 群间间隔，避免风控
            except Exception as e:
                logger.error(f"[jrsq] 推送到群 {group_id} 失败: {e}")
