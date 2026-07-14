<p align="center">
  <img src="shuqu-avatar.png" alt="今日术曲" width="200">
</p>

# 今日术曲

[![AstrBot](https://img.shields.io/badge/AstrBot-4.19.2%2B-blue.svg)](https://github.com/AstrBotDevs/AstrBot)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一个给 AstrBot 群聊用的术曲推荐插件。

群友发一句 `/jrsq 千本樱`，机器人会去 B站找合适的投稿，把完整视频下载后发到群里。没想好听什么时只发 `/jrsq`，也可以让它每天定时往群里送一首。

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
- `/jrsq`：随机听一首
- `/jrsq bind`：把当前群加入每日推送（需要管理员权限）

取消每日推送用 `/jrsq unbind`。曲库同步、增删和状态查看等管理指令，可以直接发 `/jrsq help` 查看。

插件也兼容旧命令 `/shuqu`。

## 每日推送

在目标群里执行一次 `/jrsq bind` 就会完成绑定。默认每天 `12:00` 推送，时区为 `Asia/Shanghai`。

想换时间，可以修改 `data/plugin_config.json` 里的 `push.cron_hour` 和 `push.cron_minute`。同一份配置中也能调整候选曲目、视频大小、清晰度和缓存时间，不需要改代码。

## B站相关

插件默认不要求登录。如果遇到搜索结果为空、频繁触发风控，或者需要访问登录后可见的内容，可以在配置中填写 B站 Cookie，或指定 Netscape 格式的 Cookie 文件。

视频会先下载到 AstrBot 所在机器，再作为视频消息发送。请预留足够的磁盘空间，并确认机器人侧允许发送相应大小的视频；缓存会按配置定期清理。

## 运行要求

- AstrBot `4.19.2+`
- Python `3.10+`
- 能正常访问 B站的网络环境

如果 AstrBot 和 NapCat/OneBot 不在同一台机器上，需要让协议端能够访问插件生成的视频文件。

## 说明

这个插件主要是为了自用群聊写的。使用时请遵守 B站和聊天平台的服务条款，也请尊重作品版权，不要用它传播受限制的内容。

遇到问题可以直接提 [Issue](https://github.com/Sakura1314lyc/astrbot-plugin-vocadaily/issues)。

## License

MIT © sakura
