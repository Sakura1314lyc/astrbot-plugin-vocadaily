# 🎵 astrbot-plugin-vocadaily

[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-blue.svg)](https://github.com/Soulter/AstrBot)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 🎧 为 [AstrBot](https://github.com/Soulter/AstrBot) 打造的每日术曲（Vocaloid）推荐插件。
> 每天自动为你和你的群友推送一首精选术曲，支持 B 站视频链接直达。

## ✨ 核心功能

* **🕒 定时推送**：默认每天中午 12:00 自动推送今日推荐术曲（支持自定义 Cron 表达式）。
* **💬 指令唤醒**：随时通过发送 `/jrsq` 指令主动获取一首随机推荐。
* **📺 B站解析**：完美输出 Bilibili 视频的标题与链接，适配各平台的卡片解析。

## 📦 安装方法

### 方法一：通过 AstrBot 插件市场安装（推荐）
在 AstrBot 的控制台或交互界面中，直接搜索 `vocadaily` 并一键安装。

### 方法二：手动克隆安装
1. 进入 AstrBot 的插件目录：
   ```bash
   cd data/plugins