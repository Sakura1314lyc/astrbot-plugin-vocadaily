<p align="center">
  <img src="shuqu-avatar.png" alt="今日术曲" width="200">
</p>

# 今日术曲

[![AstrBot](https://img.shields.io/badge/AstrBot-4.19.2%2B-blue.svg)](https://github.com/AstrBotDevs/AstrBot)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一个给 AstrBot 群聊用的术曲推荐插件。

群友发一句 `/jrsq 千本樱`，机器人会优先寻找曲名相符的本家或官方投稿，把完整视频发到群里，再紧跟一段自己的术曲短评。没想好听什么时只发 `/jrsq`，也可以让它每天定时往群里送一首。

## 安装

可以在 AstrBot WebUI 的插件管理中，使用本仓库地址安装：

`https://github.com/Sakura1314lyc/astrbot-plugin-vocadaily`

也可以手动放进插件目录：

```bash
cd data/plugins
git clone https://github.com/Sakura1314lyc/astrbot-plugin-vocadaily.git
```

安装后重启 AstrBot，或在 WebUI 中重载插件。依赖通常会自动安装；如果没有，再进入插件目录执行 `pip install -r requirements.txt`。

## 怎么用

平时最常用的是这三个：

- `/jrsq 千本樱`：点一首指定的曲子
- `/jrsq BV1xxxxxxxxx`：已经知道投稿时，直接按 BV 号点播
- `/jrsq`：随机听一首
- `/jrsq bind`：把当前群加入每日推送（需要管理员权限）

取消每日推送用 `/jrsq unbind`。曲库同步、增删和状态查看等管理指令，可以直接发 `/jrsq help` 查看。

插件也兼容旧命令 `/shuqu`。

点名曲目后的短评由 AstrBot 当前启用的大模型生成，默认不超过 100 字。可以通过 `review.enabled` 关闭，或用 `review.max_chars` 调整长度；随机推荐和每日推送不会额外发送短评。

## 每日推送

在目标群里执行一次 `/jrsq bind` 就会完成绑定。默认每天 `12:00` 推送，时区为 `Asia/Shanghai`。

想换时间，可以修改 `data/plugin_config.json` 里的 `push.cron_hour` 和 `push.cron_minute`。同一份配置中也能调整候选曲目、视频大小、清晰度和缓存时间，不需要改代码。

## B站相关

插件默认不要求登录。搜索接口触发风控时会自动改走搜索网页，仍失败才交给 yt-dlp；结果会再按曲名、作者、标签和投稿类型排序，尽量避开翻唱、教程、音游谱面、翻跳和游戏版 MV。已经知道投稿时，直接发送 BV 号或带 BV 号的链接最稳。

如果持续搜不到内容，或者需要访问登录后可见的投稿，可以在配置中填写 B站 Cookie，或指定 Netscape 格式的 Cookie 文件。

视频会先下载到 AstrBot 所在机器，再作为视频消息发送。请预留足够的磁盘空间，并确认机器人侧允许发送相应大小的视频；缓存会每小时检查并按配置清理。

如果 AstrBot 和 NapCat 分别运行在 Docker 容器里，本地文件路径通常不能直接互通。此时把 `media.delivery_mode` 设为 `url`，并把 `media.public_base_url` 设成协议端可访问的地址，例如 `http://astrbot:6200`。端口只需在两个容器共用的 Docker 网络中连通，不必暴露到公网；实际媒体地址还带有每次启动随机生成的访问令牌。

## 运行要求

- AstrBot `4.19.2+`
- Python `3.12+`
- 能正常访问 B站的网络环境
- 使用 URL 投递时，协议端能访问配置的媒体服务地址

## 说明

这个插件主要是为了自用群聊写的。使用时请遵守 B站和聊天平台的服务条款，也请尊重作品版权，不要用它传播受限制的内容。

遇到问题可以直接提 [Issue](https://github.com/Sakura1314lyc/astrbot-plugin-vocadaily/issues)。

## License

MIT © sakura
