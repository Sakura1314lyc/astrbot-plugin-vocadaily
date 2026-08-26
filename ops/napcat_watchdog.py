#!/usr/bin/env python3
"""Monitor NapCat, QQ login, and OneBot; notify through PushPlus.

The monitor deliberately does not rely on Docker's running state alone. NapCat
4.18.x can remain alive after QQ reports ``KickedOffLine``, leaving AstrBot's
WebSocket connected while no new QQ events can arrive.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger("napcat-watchdog")

QQ_OFFLINE_MARKERS = (
    "[KickedOffLine]",
    "账号状态变更为离线",
    "你的用户身份已失效",
    "账号当前登录已失效",
    "[Core] [Login] Login Error",
)
QQ_ONLINE_MARKERS = (
    "[AdapterManager] OneBot11 适配器初始化完成",
    "接收 <-",
    "发送 ->",
)
ONEBOT_DOWN_MARKERS = (
    "反向WebSocket",
    "连接意外关闭",
    "连接错误 Error:",
)
ONEBOT_UP_MARKERS = ("aiocqhttp(OneBot v11) 适配器已连接",)


@dataclass
class WatchState:
    initialized: bool = False
    qq_online: bool | None = None
    onebot_connected: bool | None = None
    napcat_container_id: str = ""
    astrbot_container_id: str = ""
    overall: str = "unknown"
    reason: str = "尚未完成首次检查"
    outage_started: float = 0.0
    last_alert: float = 0.0
    last_check: float = 0.0
    unknown_started: float = 0.0


@dataclass(frozen=True)
class ContainerState:
    exists: bool
    running: bool
    container_id: str = ""


def _contains_all(text: str, markers: Iterable[str]) -> bool:
    return all(marker in text for marker in markers)


def apply_log_event(state: WatchState, source: str, message: str) -> None:
    """Apply one timestamp-ordered Docker log line to component state."""
    if source == "napcat":
        if any(marker in message for marker in QQ_OFFLINE_MARKERS):
            state.qq_online = False
        elif any(marker in message for marker in QQ_ONLINE_MARKERS):
            state.qq_online = True

        if _contains_all(message, ONEBOT_DOWN_MARKERS[:2]) or _contains_all(
            message, (ONEBOT_DOWN_MARKERS[0], ONEBOT_DOWN_MARKERS[2])
        ):
            state.onebot_connected = False
    elif source == "astrbot" and any(
        marker in message for marker in ONEBOT_UP_MARKERS
    ):
        state.onebot_connected = True


def evaluate_health(
    state: WatchState,
    napcat: ContainerState,
    astrbot: ContainerState,
) -> tuple[str, str]:
    if not napcat.exists:
        return "offline", "NapCat 容器不存在"
    if not napcat.running:
        return "offline", "NapCat 容器已停止"
    if not astrbot.exists:
        return "offline", "AstrBot 容器不存在"
    if not astrbot.running:
        return "offline", "AstrBot 容器已停止"
    if state.qq_online is False:
        return "offline", "QQ 登录已失效或被腾讯踢下线"
    if state.onebot_connected is False:
        return "offline", "NapCat 与 AstrBot 的 OneBot 连接已断开"
    if state.qq_online is True and state.onebot_connected is True:
        return "online", "QQ、NapCat、OneBot 与 AstrBot 均在线"
    return "unknown", "容器运行中，但尚未观察到完整登录和连接信号"


def parse_timestamped_line(line: str) -> tuple[float, str]:
    prefix, separator, message = line.partition(" ")
    if not separator:
        return 0.0, line
    try:
        timestamp = datetime.fromisoformat(prefix.replace("Z", "+00:00"))
    except ValueError:
        return 0.0, line
    return timestamp.timestamp(), message


class DockerMonitor:
    def __init__(self) -> None:
        self.napcat_name = os.getenv("NAPCAT_CONTAINER", "napcat")
        self.astrbot_name = os.getenv("ASTRBOT_CONTAINER", "astrbot")
        self.tail_lines = max(100, int(os.getenv("WATCHDOG_LOG_TAIL", "10000")))

    @staticmethod
    def _run(command: list[str], timeout: int = 20) -> str:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return completed.stdout

    def inspect(self, name: str) -> ContainerState:
        output = self._run(
            [
                "docker",
                "inspect",
                "--format",
                "{{.Id}}|{{.State.Running}}",
                name,
            ]
        ).strip()
        if "|" not in output:
            return ContainerState(False, False)
        container_id, running = output.split("|", 1)
        return ContainerState(True, running.strip().lower() == "true", container_id)

    def logs(self, name: str, since: float | None) -> list[str]:
        command = ["docker", "logs", "--timestamps"]
        if since:
            instant = datetime.fromtimestamp(since, tz=timezone.utc).isoformat()
            command.extend(["--since", instant])
        else:
            command.extend(["--tail", str(self.tail_lines)])
        command.append(name)
        return self._run(command).splitlines()

    def poll(self, state: WatchState, now: float) -> tuple[str, str]:
        napcat = self.inspect(self.napcat_name)
        astrbot = self.inspect(self.astrbot_name)

        container_changed = (
            napcat.container_id != state.napcat_container_id
            or astrbot.container_id != state.astrbot_container_id
        )
        if container_changed:
            state.qq_online = None
            state.onebot_connected = None

        since = None if container_changed or not state.last_check else state.last_check - 3
        events: list[tuple[float, int, str, str]] = []
        order = 0
        if napcat.exists:
            for line in self.logs(self.napcat_name, since):
                timestamp, message = parse_timestamped_line(line)
                events.append((timestamp, order, "napcat", message))
                order += 1
        if astrbot.exists:
            for line in self.logs(self.astrbot_name, since):
                timestamp, message = parse_timestamped_line(line)
                events.append((timestamp, order, "astrbot", message))
                order += 1
        for _, _, source, message in sorted(events):
            apply_log_event(state, source, message)

        state.napcat_container_id = napcat.container_id
        state.astrbot_container_id = astrbot.container_id
        state.last_check = now
        return evaluate_health(state, napcat, astrbot)


class PushPlusNotifier:
    def __init__(self) -> None:
        self.token = os.getenv("PUSHPLUS_TOKEN", "").strip()
        self.channel = os.getenv("PUSHPLUS_CHANNEL", "wechat").strip() or "wechat"
        self.endpoint = os.getenv(
            "PUSHPLUS_ENDPOINT", "https://www.pushplus.plus/send"
        ).strip()
        if not self.token:
            raise RuntimeError("PUSHPLUS_TOKEN 未配置")

    def send(self, title: str, content: str) -> None:
        payload = json.dumps(
            {
                "token": self.token,
                "title": title,
                "content": content,
                "template": "markdown",
                "channel": self.channel,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    result = json.loads(response.read().decode("utf-8"))
                if int(result.get("code", -1)) != 200:
                    raise RuntimeError(str(result.get("msg") or result))
                LOGGER.info("PushPlus 通知发送成功：%s", title)
                return
            except (OSError, ValueError, urllib.error.URLError, RuntimeError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise RuntimeError(f"PushPlus 通知发送失败：{last_error}")


def load_state(path: Path) -> WatchState:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        allowed = WatchState.__dataclass_fields__.keys()
        return WatchState(**{key: payload[key] for key in allowed if key in payload})
    except (OSError, ValueError, TypeError):
        return WatchState()


def save_state(path: Path, state: WatchState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary:
        json.dump(asdict(state), temporary, ensure_ascii=False, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} 小时 {minutes} 分钟"
    if minutes:
        return f"{minutes} 分钟 {secs} 秒"
    return f"{secs} 秒"


def notify_transition(
    notifier: PushPlusNotifier,
    state: WatchState,
    current: str,
    reason: str,
    now: float,
    reminder_seconds: int,
) -> None:
    label = os.getenv("WATCHDOG_SERVER_LABEL", "腾讯云 AstrBot")
    previous = state.overall
    local_time = datetime.fromtimestamp(now).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    if current == "offline" and previous != "offline":
        state.outage_started = now
        notifier.send(
            "⚠️ AstrBot / QQ 已掉线",
            f"**服务器：** {label}\n\n**时间：** {local_time}\n\n"
            f"**原因：** {reason}\n\n请检查 NapCat 登录状态。",
        )
        state.last_alert = now
    elif current == "offline" and now - state.last_alert >= reminder_seconds:
        notifier.send(
            "⏰ AstrBot / QQ 仍未恢复",
            f"**服务器：** {label}\n\n**时间：** {local_time}\n\n"
            f"**原因：** {reason}\n\n"
            f"**持续时间：** {format_duration(now - state.outage_started)}",
        )
        state.last_alert = now
    elif current == "online" and previous == "offline":
        notifier.send(
            "✅ AstrBot / QQ 已恢复",
            f"**服务器：** {label}\n\n**时间：** {local_time}\n\n"
            f"**状态：** {reason}\n\n"
            f"**中断时间：** {format_duration(now - state.outage_started)}",
        )
        state.outage_started = 0.0
        state.last_alert = now


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="检查一次后退出")
    parser.add_argument("--test", action="store_true", help="发送测试通知后退出")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=os.getenv("WATCHDOG_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    state_path = Path(
        os.getenv("WATCHDOG_STATE_FILE", "/var/lib/napcat-watchdog/state.json")
    )
    interval = max(5, int(os.getenv("WATCHDOG_INTERVAL", "15")))
    reminder = max(300, int(os.getenv("WATCHDOG_REMINDER", "21600")))
    unknown_grace = max(30, int(os.getenv("WATCHDOG_UNKNOWN_GRACE", "120")))
    notifier = PushPlusNotifier()
    monitor = DockerMonitor()
    state = load_state(state_path)

    now = time.time()
    current, reason = monitor.poll(state, now)
    if args.test:
        notifier.send(
            "✅ AstrBot 掉线监控已启用",
            f"当前检测结果：**{current}**\n\n{reason}\n\n"
            "以后 QQ、NapCat 或 OneBot 掉线时会自动通知。",
        )
        state.initialized = True
        state.overall = current
        state.reason = reason
        save_state(state_path, state)
        return 0

    stop_requested = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    while True:
        now = time.time()
        current, reason = monitor.poll(state, now)
        if current == "unknown":
            if not state.unknown_started:
                state.unknown_started = now
            if now - state.unknown_started >= unknown_grace:
                current = "offline"
                reason = "超过等待时间仍未观察到完整登录和 OneBot 连接信号"
        else:
            state.unknown_started = 0.0

        if state.initialized:
            try:
                notify_transition(notifier, state, current, reason, now, reminder)
            except RuntimeError:
                LOGGER.exception("发送状态通知失败")
        else:
            state.initialized = True

        if current != state.overall or reason != state.reason:
            LOGGER.info("状态：%s（%s）", current, reason)
        state.overall = current
        state.reason = reason
        save_state(state_path, state)

        if args.once or stop_requested:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
