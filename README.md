<p align="center">
  <img src="shuqu-avatar.png" alt="今日术曲头像" width="240">
</p>

# astrbot-plugin-vocadaily

[![AstrBot](https://img.shields.io/badge/AstrBot-4.19.2%2B-blue.svg)](https://github.com/AstrBotDevs/AstrBot)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AstrBot 每日术曲视频推送插件。

核心功能是 `/jrsq`：机器人自动到 B站搜索术曲，下载完整 MP4，再通过 AstrBot 的 `Video` 消息段把整个视频发送到群里。

## 核心功能

- `/jrsq <术曲名>`：自动搜索 B站、下载并发送完整视频
- `/jrsq`：从曲库随机推荐；曲库为空时从可配置的每日曲目池抽取
- 精确匹配曲名，优先官方、本家、原曲与原创投稿，过滤翻唱、手书、恐怖、合集等非原曲候选
- 每天定时向已绑定的群推送一首完整术曲视频
- 可从 B站公开收藏夹同步本地曲库
- B站 JSON 搜索遇到 412 风控时自动改用搜索网页解析
- 优先获取带声音的单文件 MP4；需要时可通过 ffmpeg 合并音视频
- 限制视频分辨率、时长和大小，并自动清理缓存
- 下载或视频准备失败时只记录错误，不用链接冒充视频结果

网易云功能默认关闭，不影响 `/jrsq` 的 B站视频主流程。

## 指令

| 指令 | 说明 | 示例 |
|---|---|---|
| `/jrsq <曲名>` | 从 B站查找并发送完整视频 | `/jrsq 千本樱` |
| `/jrsq` | 随机推荐；空曲库时自动联网搜索 | `/jrsq` |
| `/jrsq random` | 从本地曲库随机发送视频 | `/jrsq random` |
| `/jrsq list [页]` | 分页查看本地曲库 | `/jrsq list 2` |
| `/jrsq search <词>` | 搜索本地曲库 | `/jrsq search 初音` |
| `/jrsq add <BV号或链接>` | 添加 B站视频到曲库 | `/jrsq add BV1xx411c7m9` |
| `/jrsq del <ID>` | 删除曲库条目 | `/jrsq del 3` |
| `/jrsq sync` | 同步配置的 B站收藏夹 | `/jrsq sync` |
| `/jrsq count` | 查看曲库数量 | `/jrsq count` |
| `/jrsq bind` | 管理员绑定当前群的每日推送 | `/jrsq bind` |
| `/jrsq unbind` | 管理员解绑当前群 | `/jrsq unbind` |
| `/jrsq status` | 查看视频、缓存和推送状态 | `/jrsq status` |
| `/jrsq help` | 查看帮助 | `/jrsq help` |

兼容别名 `/shuqu`，但项目主命令是 `/jrsq`。

## 安装

```bash
cd data/plugins
git clone https://github.com/Sakura1314lyc/astrbot-plugin-vocadaily.git
cd astrbot-plugin-vocadaily
pip install -r requirements.txt
```

重启 AstrBot 或在 WebUI 中重载插件。

插件要求 AstrBot `4.19.2+`，B站搜索与下载依赖 `yt-dlp`。建议安装 `ffmpeg`，用于合并 B站提供的 DASH 音视频流；没有 ffmpeg 时，插件会优先请求游客可用的带声音单文件 MP4。

## 基础配置

配置文件：`data/plugin_config.json`。

```json
{
  "bilibili": {
    "enabled": true,
    "media_id": "8745208",
    "page_size": 20,
    "search_count": 10,
    "search_suffix": "VOCALOID 原曲 MV",
    "default_query": "术曲",
    "apex_host_fallback": true,
    "search_min_score": 100,
    "cookie": "",
    "cookies_file": ""
  },
  "netease": {
    "enabled": false,
    "search_count": 5,
    "cookie": "",
    "send_mode": "file"
  },
  "media": {
    "source_order": ["bilibili"],
    "video_height": 360,
    "max_duration_seconds": 900,
    "max_file_size_mb": 100,
    "cache_hours": 24,
    "ffmpeg_location": "",
    "proxy": ""
  },
  "push": {
    "enabled": true,
    "cron_hour": 12,
    "cron_minute": 0,
    "timezone": "Asia/Shanghai",
    "fallback_search_query": "术曲",
    "daily_queries": ["千本樱", "天ノ弱", "メルト", "深海少女", "ロキ"],
    "target_umos": []
  }
}
```

### B站配置

| 字段 | 说明 |
|---|---|
| `media_id` | 用于同步曲库的公开收藏夹 ID；只使用搜索功能时可留空 |
| `search_count` | 每次搜索检查的 B站候选数量 |
| `search_suffix` | 自动添加到用户曲名后的搜索限定词 |
| `default_query` | `/jrsq` 在曲库为空时使用的联网搜索词 |
| `apex_host_fallback` | 子域名 TLS 被重置时，通过 `bilibili.com` 顶级域名路由 API、搜索页和视频 CDN |
| `search_min_score` | 原曲候选最低可信分；默认 `100`，越高越严格 |
| `cookie` | 可选 B站 Cookie，用于登录可见内容并降低风控概率 |
| `cookies_file` | 可选 Netscape 格式 Cookie 文件路径 |

收藏夹 URL 形如：

```text
https://space.bilibili.com/用户ID/favlist?fid=收藏夹ID
```

将 `fid=` 后的数字填入 `media_id`，然后执行 `/jrsq sync`。

### 视频配置

| 字段 | 说明 |
|---|---|
| `video_height` | 视频最高高度，群聊建议 360 或 480 |
| `max_duration_seconds` | 最大视频时长；`0` 表示不限 |
| `max_file_size_mb` | 最大下载和发送大小 |
| `cache_hours` | 视频缓存保留时间 |
| `ffmpeg_location` | ffmpeg 可执行文件或目录；已加入 PATH 时留空 |
| `proxy` | yt-dlp 代理，例如 `http://127.0.0.1:7890` |

视频缓存在 `data/media_cache/`，过期文件会在插件启动时清理。

## 每日自动推送

AstrBot 主动发送消息需要完整的 UMO，不能只填写裸群号。UMO 类似：

```text
aiocqhttp:GroupMessage:123456789
```

在目标群里使用 AstrBot 管理员账号执行：

```text
/jrsq bind
```

插件会自动把当前群的 UMO 写入 `push.target_umos`。取消推送使用 `/jrsq unbind`。

每天到达配置时间后：

1. 曲库有内容：随机选取一条 B站视频记录。
2. 曲库为空：从 `daily_queries` 随机抽取一个明确曲名，再按曲名精确匹配并优先下载官方/本家投稿。
3. 下载完整视频，使用标准 Windows `file:///C:/...` URI 构造独立的 AstrBot `Video` 消息。
4. 向所有绑定群发送视频。
5. 视频准备失败：本次不发送，不降级成链接。

## 为什么先下载再发送

B站临时播放地址通常要求正确的 Referer、Cookie 等请求头。直接把临时 URL 交给聊天平台，平台再次下载时容易出现 403。

插件会先把 MP4 下载到 AstrBot 所在机器，再让 AstrBot 发送本地视频文件，因此群里收到的是完整视频消息。

如果 OneBot/NapCat 和 AstrBot 不在同一台机器，需要让协议端能够访问 `data/media_cache/`，或按照平台适配器文档配置共享路径。

## 可选网易云扩展

网易云默认关闭。只有确实需要音频兜底时，才将：

```json
"netease": { "enabled": true }
```

并把 `media.source_order` 改成 `["bilibili", "netease"]`。这不会改变 `/jrsq <曲名>` 优先获取 B站完整视频的行为。

## 项目结构

```text
astrbot-plugin-vocadaily/
├── main.py
├── manifest.json
├── requirements.txt
├── shuqu-avatar.png
├── jsrqmiku.png
├── README.md
└── data/
    ├── plugin_config.json
    ├── jrsq.db
    └── media_cache/
```

## 注意

本插件只用于个人学习和自有群聊。请遵守 B站及消息平台的服务条款，不要绕过付费、版权或地区限制传播受保护内容。

## License

MIT (c) sakura
