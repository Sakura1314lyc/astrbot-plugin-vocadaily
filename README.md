# 🎵 astrbot-plugin-vocadaily

[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-blue.svg)](https://github.com/Soulter/AstrBot)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 🎧 为 [AstrBot](https://github.com/Soulter/AstrBot) 打造的每日术曲（Vocaloid）推荐插件。
> 从 B站收藏夹同步曲库，每天为你推送一首术曲 **视频**（非链接）。

## ✨ 功能

- **📺 视频直发** — 自动获取 B站视频流，以视频消息发送（非文字链接），失败自动降级
- **🕒 定时推送** — 每天中午 12:00 自动推送（可在配置中调整时间）
- **💬 指令唤醒** — 随时用指令获取随机术曲
- **🗄️ 本地曲库** — SQLite 数据库存储曲目元数据（标题/BV号/UP主/时长）
- **🔄 收藏夹同步** — 一键从 B站公开收藏夹批量导入曲库
- **🔍 曲库管理** — 支持添加/删除/搜索/列表查看曲目

## 📋 指令列表

| 指令 | 说明 | 示例 |
|------|------|------|
| `/jrsq` | 随机推荐一首术曲（视频消息） | `/jrsq` |
| `/jrsq list [页]` | 分页查看曲库（每页10条） | `/jrsq list` `/jrsq list 2` |
| `/jrsq add <BV号>` | 从 B站添加曲目 | `/jrsq add BV1xx411c7m9` |
| `/jrsq del <ID>` | 按 ID 删除曲目 | `/jrsq del 3` |
| `/jrsq search <词>` | 按标题搜索 | `/jrsq search 深海` |
| `/jrsq favsync` | 从收藏夹同步新曲目 | `/jrsq favsync` |
| `/jrsq count` | 查看曲库总数 | `/jrsq count` |

## ⚙️ 配置

配置文件位于 `data/plugin_config.json`：

```json
{
  "bilibili": {
    "media_id": "8745208",
    "page_size": 20,
    "cache_minutes": 30,
    "timeout_seconds": 15
  },
  "push": {
    "cron_hour": 12,
    "cron_minute": 0,
    "target_groups": ["群号1", "群号2"]
  }
}
```

| 字段 | 说明 |
|------|------|
| `bilibili.media_id` | B站收藏夹 ID（⚠️ 必改，在收藏夹页 URL 中获取） |
| `bilibili.page_size` | 每次 API 请求拉取的视频数 |
| `push.cron_hour` / `cron_minute` | 定时推送时间（24小时制） |
| `push.target_groups` | 需要推送的群聊 ID 列表 |

### 获取 media_id

1. 在浏览器打开你的 B站收藏夹
2. URL 格式为 `https://space.bilibili.com/xxxx/favlist?fid=你的media_id`
3. 将 `fid=` 后面的数字填入配置

## 📦 手动安装

1. 进入 AstrBot 插件目录：
   ```bash
   cd data/plugins
   ```

2. 克隆仓库：
   ```bash
   git clone https://github.com/Sakura1314lyc/astrbot-plugin-vocadaily.git
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 修改 `data/plugin_config.json` 中的 `media_id` 和 `target_groups`

5. 重启 AstrBot 或热加载插件

6. 首次使用先运行 `/jrsq favsync` 同步曲库

## 🏗️ 项目结构

```
astrbot-plugin-vocadaily/
├── main.py                # 插件主程序
├── manifest.json          # 插件元信息
├── requirements.txt       # Python 依赖
├── README.md
└── data/
    ├── plugin_config.json # 插件配置
    └── jrsq.db            # SQLite 曲库（运行后自动生成）
```

## 📄 License

MIT © sakura
