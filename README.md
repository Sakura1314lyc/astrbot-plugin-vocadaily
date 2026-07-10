<p align="center">
  <img src="shuqu-avatar.png" alt="今日术曲头像" width="240">
</p>

# astrbot-plugin-vocadaily

[![AstrBot](https://img.shields.io/badge/AstrBot-4.25%2B-blue.svg)](https://github.com/AstrBotDevs/AstrBot)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AstrBot 每日术曲插件。可以按曲名从 B站搜索并下载视频，再由 AstrBot 以视频消息发送到当前群；B站失败时可自动转到网易云，发送试听音频文件或歌曲链接。插件同时保留 B站收藏夹曲库、随机推荐和定时群推送。

## 功能

- `/shuqu 千本樱`：按名称搜索，默认按照“B站 → 网易云”的顺序获取
- B站视频由 `yt-dlp` 下载到本地缓存，再使用 AstrBot `Video` 消息段发送
- `/shuqu bili 曲名` 和 `/shuqu wy 曲名`：指定来源
- 网易云支持音频文件、WAV 语音或链接三种模式
- 从公开 B站收藏夹同步本地 SQLite 曲库
- 从本地曲库随机发送视频、搜索、分页、添加和删除
- 管理员可在群内一键绑定每日定时推送，无需手写群号
- 视频获取失败会返回原站链接和明确错误，不会静默失败
- 自动限制视频分辨率、时长、文件大小，并定期清理媒体缓存
- 兼容旧入口 `/jrsq`

## 指令

| 指令 | 说明 | 示例 |
|---|---|---|
| `/shuqu <曲名>` | B站优先搜索，失败自动转网易云 | `/shuqu 世界第一公主殿下` |
| `/shuqu bili <曲名>` | 只从 B站拉取视频 | `/shuqu bili 千本樱` |
| `/shuqu wy <曲名>` | 只从网易云拉取音频 | `/shuqu wy 神っぽいな` |
| `/shuqu random` | 从收藏夹曲库随机发送 B站视频 | `/shuqu random` |
| `/shuqu list [页]` | 分页查看本地曲库 | `/shuqu list 2` |
| `/shuqu search <词>` | 只搜索本地曲库，不联网 | `/shuqu search 初音` |
| `/shuqu add <BV号或链接>` | 添加一个 B站视频到曲库 | `/shuqu add BV1xx411c7m9` |
| `/shuqu del <ID>` | 按曲库 ID 删除 | `/shuqu del 3` |
| `/shuqu sync` | 同步配置的 B站收藏夹 | `/shuqu sync` |
| `/shuqu count` | 查看本地曲库数量 | `/shuqu count` |
| `/shuqu bind` | 管理员绑定当前群的每日推送 | `/shuqu bind` |
| `/shuqu unbind` | 管理员解绑当前群 | `/shuqu unbind` |
| `/shuqu status` | 查看来源、缓存和推送状态 | `/shuqu status` |
| `/shuqu help` | 显示插件帮助 | `/shuqu help` |

以上命令均可将 `/shuqu` 换成 `/jrsq`。

## 安装

在 AstrBot 的插件目录中克隆并安装依赖：

```bash
cd data/plugins
git clone https://github.com/Sakura1314lyc/astrbot-plugin-vocadaily.git
cd astrbot-plugin-vocadaily
pip install -r requirements.txt
```

然后重启 AstrBot 或在 WebUI 中重载插件。

插件需要 AstrBot `4.25.0+`。B站视频搜索和下载依赖 `yt-dlp`。只有在以下场景需要额外安装 `ffmpeg`：

- B站只提供音视频分离的 DASH 流，需要合并为 MP4；
- 将 `netease.send_mode` 设置成 `record`，需要把网易云音频转成 AstrBot 文档要求的 WAV。

建议服务器安装 `ffmpeg`。如果它不在系统 `PATH` 中，可在配置的 `media.ffmpeg_location` 填可执行文件或所在目录。

## 配置

配置文件为 `data/plugin_config.json`：

```json
{
  "bilibili": {
    "enabled": true,
    "media_id": "8745208",
    "page_size": 20,
    "search_count": 5,
    "search_suffix": "VOCALOID",
    "cookie": "",
    "cookies_file": ""
  },
  "netease": {
    "enabled": true,
    "search_count": 5,
    "cookie": "",
    "send_mode": "file"
  },
  "media": {
    "source_order": ["bilibili", "netease"],
    "video_height": 480,
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
    "target_umos": []
  }
}
```

### B站

| 字段 | 说明 |
|---|---|
| `enabled` | 是否允许 B站搜索和下载 |
| `media_id` | 要同步的收藏夹 ID；只按名称搜索时可以留空 |
| `page_size` | 收藏夹每页读取数量 |
| `search_count` | 每次名称搜索读取的候选数，插件发送第一个满足限制的结果 |
| `search_suffix` | 自动附加到搜索词后的限定词；默认 `VOCALOID`，可改成 `术曲` 或留空 |
| `cookie` | 可选的完整 Cookie 请求头，用于登录可见内容和降低风控概率 |
| `cookies_file` | 可选的 Netscape 格式 Cookie 文件路径；相对路径从插件目录开始 |

收藏夹页面 URL 形如：

```text
https://space.bilibili.com/用户ID/favlist?fid=收藏夹ID
```

将 `fid=` 后的数字填到 `media_id`。收藏夹必须公开，私密收藏夹需要配置有效 Cookie。

### 网易云

`send_mode` 支持：

- `file`：默认，下载公开试听 MP3 并作为文件消息发送；不要求 ffmpeg。
- `record`：转成 WAV 后作为语音消息发送；要求 ffmpeg，且 WAV 文件通常更大。
- `link`：只发送歌曲信息和网易云链接，不下载音频。

部分付费、VIP、无版权或区域受限歌曲没有公开试听地址。遇到这种情况插件会返回歌曲链接；配置 Cookie 也不保证能够突破版权限制。

### 媒体限制

| 字段 | 说明 |
|---|---|
| `source_order` | `/shuqu 曲名` 的来源尝试顺序，可改成只包含一个来源 |
| `video_height` | B站下载的目标最高高度，群聊建议 360 或 480 |
| `max_duration_seconds` | 最大时长；设为 `0` 表示不限制 |
| `max_file_size_mb` | 下载和发送的最大文件大小 |
| `cache_hours` | 本地媒体缓存保留小时数 |
| `ffmpeg_location` | ffmpeg 可执行文件或目录；已加入 PATH 时留空 |
| `proxy` | yt-dlp 使用的代理，例如 `http://127.0.0.1:7890` |

缓存位于 `data/media_cache/`，过期文件会在插件启动时自动清理。

## 定时推送

不要只在配置里填写裸群号。AstrBot 主动消息需要 UMO（Unified Message Origin），格式类似：

```text
aiocqhttp:GroupMessage:123456789
```

最简单且不容易填错的方式：在目标群里用 AstrBot 管理员账号发送：

```text
/shuqu bind
```

插件会把当前会话的完整 UMO 写入 `push.target_umos`。发送 `/shuqu unbind` 可解绑。也可以先在群里执行 AstrBot 自带的 `/sid`，再手动复制 UMO 到配置中。

修改 `cron_hour`、`cron_minute` 或 `timezone` 后需要重载插件。

## 媒体发送说明

插件先把 B站视频下载到 AstrBot 所在机器，再构造 `Video.fromFileSystem(...)` 消息。这能避免 B站临时直链因缺少 Referer/Cookie 而被消息平台下载时报 403。

本地媒体能否成功发送仍取决于具体平台适配器：

- OneBot/NapCat 与 AstrBot 不在同一台机器时，需要正确共享或映射本地文件路径；
- 部分平台不支持视频、文件或主动消息；
- QQ 等平台还会限制文件大小、编码格式和上传频率。

若适配器不接受本地文件，请让协议端与 AstrBot 共享 `data/media_cache/`，或按适配器文档设置路径映射。

## 项目结构

```text
astrbot-plugin-vocadaily/
├── main.py
├── manifest.json
├── requirements.txt
├── shuqu-avatar.png       # 项目头像
├── jsrqmiku.png
├── README.md
└── data/
    ├── plugin_config.json
    ├── jrsq.db
    └── media_cache/       # 自动生成，不提交到 Git
```

## 注意

本插件只用于个人学习和自有群聊。请遵守 B站、网易云音乐及消息平台的服务条款，不要绕过付费、版权、地区限制或批量传播受保护内容。

## License

MIT (c) sakura
