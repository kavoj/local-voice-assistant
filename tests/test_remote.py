# -*- coding: utf-8 -*-
"""局域网远程控制单元测试：分发器路由 + 节点代理安全（全部离线，注入桩 sender）。"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistant.config import PROJECT_ROOT, _DEFAULTS, _deep_merge  # noqa: E402
from assistant.enterprise.agent import EnterpriseBrain  # noqa: E402
from assistant.remote.agent import build_commands  # noqa: E402
from assistant.remote.dispatch import RemoteDispatcher  # noqa: E402


def _fake_sender_factory(log):
    def sender(host, port, token, payload, timeout=5.0):
        log.append((host, port, token, payload))
        return {"ok": True, "detail": "stub"}
    return sender


class DispatcherTest(unittest.TestCase):
    def setUp(self):
        self.log = []
        self.config = _deep_merge(_DEFAULTS, {"remote": {"token": "tok"}})
        self.d = RemoteDispatcher(self.config, sender=_fake_sender_factory(self.log))

    def test_no_devices_returns_none(self):
        self.d.devices = []
        self.assertIsNone(self.d.match("随便聊聊天气"))

    def test_lock_command_routes(self):
        reply, action, done = self.d.match("让会议室电脑锁屏")
        self.assertTrue(done)
        self.assertIn("会议室电脑", reply)
        self.assertEqual(action, "remote.lock:会议室电脑")
        host, port, token, payload = self.log[-1]
        self.assertEqual((host, port, token), ("192.168.1.50", 8766, "change-me"))
        self.assertEqual(payload["command"], "lock")

    def test_alias_matching(self):
        _, action, done = self.d.match("会议室 截图")
        self.assertTrue(done)
        self.assertEqual(action, "remote.screenshot:会议室电脑")
        self.assertEqual(self.log[-1][3]["command"], "screenshot")

    def test_url_and_say_args(self):
        self.d.match("让会议室电脑打开 http://example.com")
        self.assertEqual(self.log[-1][3]["args"], {"url": "http://example.com"})
        self.d.match("让会议室电脑播报：开会了")
        self.assertEqual(self.log[-1][3]["args"], {"text": "开会了"})

    def test_device_mentioned_but_no_verb_falls_through(self):
        # 点了设备名但没有控制动词 → 交回主路由
        self.assertIsNone(self.d.match("会议室今天有安排吗"))

    def test_command_without_device_guides(self):
        reply, action, done = self.d.match("帮我锁屏")
        self.assertFalse(done)
        self.assertEqual(action, "remote.need_device")

    def test_status_check(self):
        reply, action, done = self.d.match("会议室电脑状态怎么样")
        self.assertTrue(done)
        self.assertEqual(action, "remote.status:会议室电脑")

    def test_unreachable_device(self):
        def broken(*a, **k):
            raise ConnectionError("refused")
        self.d.sender = broken
        reply, action, done = self.d.match("让会议室电脑锁屏")
        self.assertFalse(done)
        self.assertIn("没送达到", reply)


class AgentSafetyTest(unittest.TestCase):
    def setUp(self):
        self.commands = build_commands(allow_shutdown=False)

    def test_unknown_command_absent(self):
        self.assertNotIn("format_disk", self.commands)

    def test_exec_script_rejects_path_traversal(self):
        ok, detail = self.commands["exec_script"]({"script": "../../etc/passwd.sh"})
        self.assertFalse(ok)

    def test_exec_script_rejects_bad_suffix(self):
        ok, detail = self.commands["exec_script"]({"script": "evil.exe"})
        self.assertFalse(ok)

    def test_shutdown_denied_without_flag(self):
        ok, detail = self.commands["shutdown"]({})
        self.assertFalse(ok)
        self.assertIn("拒绝", detail)

    def test_shutdown_allowed_with_flag(self):
        commands = build_commands(allow_shutdown=True)
        # 只验证"允许进入执行"分支：关机在 CI 环境不可真执行，用 monkeypatch
        import assistant.remote.agent as agent_mod
        orig = agent_mod._make_shutdown
        calls = []
        agent_mod._make_shutdown = lambda allow: (lambda: calls.append(allow) or (True, "stub"))
        try:
            ok, detail = commands["shutdown"]({})
        finally:
            agent_mod._make_shutdown = orig
        self.assertTrue(ok)
        self.assertEqual(calls, [True])

    def test_open_url_rejects_garbage(self):
        ok, detail = self.commands["open_url"]({"url": "not a url with spaces"})
        self.assertFalse(ok)


class BrainRemoteRoutingTest(unittest.TestCase):
    def setUp(self):
        config = _deep_merge(_DEFAULTS, {})
        self.brain = EnterpriseBrain(config=config)
        self.sent = []

        def sender(host, port, token, payload, timeout=5.0):
            self.sent.append(payload)
            return {"ok": True, "detail": "stub"}
        self.brain.remote = RemoteDispatcher(
            _deep_merge(_DEFAULTS, {"remote": {"token": "tok"}}), sender=sender)

    def test_voice_command_routed_to_remote(self):
        reply = self.brain.ask("让会议室电脑锁屏")
        self.assertEqual(reply.intent, "remote_ctrl")
        self.assertTrue(reply.task_done)
        self.assertEqual(self.sent[-1]["command"], "lock")

    def test_non_control_still_knowledge(self):
        reply = self.brain.ask("报销怎么走流程")
        self.assertEqual(reply.intent, "kb_qa")


if __name__ == "__main__":
    unittest.main()
