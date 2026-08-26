<p align="center">
  <img src="jrsq-avatar.png" alt="今日术曲" width="200">
</p>

# 今日术曲

[![AstrBot](https://img.shields.io/badge/AstrBot-4.19.2%2B-blue.svg)](https://github.com/AstrBotDevs/AstrBot)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

给 AstrBot 群聊点术曲用的插件。

在群里发 `/jrsq 千本樱`，机器人会先找曲名对得上的本家或官方投稿，把完整视频发出来，随后补一小段短评。没想好听什么就只发 `/jrsq`，也可以绑定群聊，让它每天中午自动送一首。

## 安装

在 AstrBot WebUI 的插件管理里填入仓库地址即可安装：

`https://github.com/Sakura1314lyc/astrbot-plugin-vocadaily`

想手动安装的话，把仓库克隆到插件目录：

```bash
cd data/plugins
git clone https://github.com/Sakura1314lyc/astrbot-plugin-vocadaily.git
```

然后重启 AstrBot，或者在 WebUI 里重载插件。依赖通常会自动安装；如果没装上，再进入插件目录执行 `pip install -r requirements.txt`。

## 常用指令

平时基本用这几条：

- `/jrsq 千本樱`：点一首指定的曲子
- `/jrsq BV1xxxxxxxxx`：已经知道投稿时，直接按 BV 号点播
- `/jrsq`：随机听一首
- `/jrsq bind`：把当前群加入每日推送（需要管理员权限）

不想再收每日推送时，用 `/jrsq unbind` 解绑。曲库同步、增删和状态查看等管理指令没有全塞在这里，发 `/jrsq help` 就能看到。

点名曲目后那段短评由 AstrBot 当前启用的大模型生成，默认不超过 100 字。短评会先检查投稿版本、题材风险和检索可信度，不会固定说好话；碰到翻唱、二创、AI 版本、争议或可能引起不适的内容时会直接说明。它可以通过 `review.enabled` 关闭，长度则由 `review.max_chars` 控制。随机推荐和每日推送不会额外发短评。

## 每日推送

在目标群里执行一次 `/jrsq bind` 就算绑定好了。默认每天 `12:00` 推送，时区是 `Asia/Shanghai`。

要换时间，修改 `data/plugin_config.json` 里的 `push.cron_hour` 和 `push.cron_minute`。候选曲目、视频大小、清晰度和缓存时间也在这份配置里，不用动代码。

## 搜索和视频发送

插件默认不要求登录 B站。它会先建立匿名访问会话；接口不可用时，再依次改走搜索网页和 yt-dlp。

点歌可以说得随意一点，比如 `/jrsq 想听你说月色真美`。插件会保留原句，同时拆出更像曲名的部分，用普通检索和“原曲 / 本家”检索一起召回候选，全部收齐后再判断，不会因为第一条标题很像就提前收工。排序时会综合曲名、别名、作者、标签、时长和本家标记，演唱会、MMD、翻唱、手书、谱面、短片等版本会被过滤或降权。已经知道投稿的话，直接发 BV 号或带 BV 号的链接最稳。

如果一直搜不到，或者投稿需要登录后才能看，可以在配置里填写 B站 Cookie，也可以指定 Netscape 格式的 Cookie 文件。

视频会先下载到 AstrBot 所在的机器，再作为视频消息发出去。机器要留出足够的磁盘空间，机器人侧也得允许发送相应大小的视频。缓存每小时检查一次，并按配置清理。

如果 AstrBot 和 NapCat 分别跑在两个 Docker 容器里，本地文件路径通常不互通。这种情况下把 `media.delivery_mode` 设为 `url`，再把 `media.public_base_url` 填成 NapCat 能访问的地址，例如 `http://astrbot:6200`。这个端口只要在两个容器共用的 Docker 网络里连通即可，不用开放到公网。实际媒体地址还会带上每次启动随机生成的访问令牌。

## NapCat 掉线监控

`ops/napcat_watchdog.py` 是给自建服务器准备的独立监控。它不只检查 Docker 容器是否运行，还会读取 NapCat 与 AstrBot 的日志，识别 QQ 被踢下线、OneBot 断连以及服务恢复。通知通过 PushPlus 发到微信，Token 应只保存在服务器的 `/etc/napcat-watchdog.env`，不要提交到仓库。

对应的 systemd 单元在 `ops/napcat-watchdog.service`。默认每 15 秒检查一次，掉线立即提醒，持续掉线时每 6 小时提醒一次，恢复后再发一条通知。

## 运行要求

- AstrBot `4.19.2+`
- Python `3.12+`
- 能正常访问 B站的网络环境
- 使用 URL 投递时，协议端能访问配置的媒体服务地址

## 其他

这个插件最初就是写给自己群里用的。使用时请遵守 B站和聊天平台的服务条款，也请尊重作品版权，不要拿它传播受限制的内容。

碰到 bug，可以直接提 [Issue](https://github.com/Sakura1314lyc/astrbot-plugin-vocadaily/issues)。

## License

MIT © sakura
