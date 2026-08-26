import unittest

from ops.napcat_watchdog import (
    ContainerState,
    WatchState,
    apply_log_event,
    evaluate_health,
    notify_transition,
    parse_timestamped_line,
)

RUNNING = ContainerState(True, True, "container-id")


class RecordingNotifier:
    def __init__(self):
        self.messages = []

    def send(self, title, content):
        self.messages.append((title, content))


class NapCatWatchdogTests(unittest.TestCase):
    def test_kicked_offline_wins_while_websocket_stays_connected(self):
        state = WatchState(qq_online=True, onebot_connected=True)

        apply_log_event(
            state,
            "napcat",
            "叩群娘 | [KickedOffLine] [下线通知] 你的账号当前登录已失效",
        )

        self.assertFalse(state.qq_online)
        self.assertTrue(state.onebot_connected)
        self.assertEqual(evaluate_health(state, RUNNING, RUNNING)[0], "offline")

    def test_message_activity_and_adapter_connection_restore_health(self):
        state = WatchState(qq_online=False, onebot_connected=False)

        apply_log_event(state, "napcat", "叩群娘 | 接收 <- 群聊 测试")
        apply_log_event(
            state,
            "astrbot",
            "aiocqhttp(OneBot v11) 适配器已连接。",
        )

        self.assertEqual(
            evaluate_health(state, RUNNING, RUNNING),
            ("online", "QQ、NapCat、OneBot 与 AstrBot 均在线"),
        )

    def test_reverse_websocket_error_marks_link_down(self):
        state = WatchState(qq_online=True, onebot_connected=True)

        apply_log_event(
            state,
            "napcat",
            "[OneBot] [WebSocket Client] 反向WebSocket 连接错误 Error: refused",
        )

        self.assertFalse(state.onebot_connected)

    def test_stopped_container_is_offline(self):
        state = WatchState(qq_online=True, onebot_connected=True)

        status, reason = evaluate_health(
            state, ContainerState(True, False, "napcat"), RUNNING
        )

        self.assertEqual(status, "offline")
        self.assertIn("NapCat", reason)

    def test_timestamp_parser_handles_docker_rfc3339(self):
        timestamp, message = parse_timestamped_line(
            "2026-08-26T01:04:14.123456789Z hello"
        )

        self.assertGreater(timestamp, 0)
        self.assertEqual(message, "hello")

    def test_notifications_are_transition_based_and_rate_limited(self):
        notifier = RecordingNotifier()
        state = WatchState(initialized=True, overall="online")

        now = 1_800_000_000
        notify_transition(notifier, state, "offline", "QQ 掉线", now, 3600)
        state.overall = "offline"
        notify_transition(notifier, state, "offline", "QQ 掉线", now + 100, 3600)
        notify_transition(notifier, state, "online", "已恢复", now + 200, 3600)

        self.assertEqual(len(notifier.messages), 2)
        self.assertIn("已掉线", notifier.messages[0][0])
        self.assertIn("已恢复", notifier.messages[1][0])


if __name__ == "__main__":
    unittest.main()
