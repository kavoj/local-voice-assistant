# -*- coding: utf-8 -*-
"""HUD 可视化语音台测试：事件总线 / 大脑问答路由 / HTTP+SSE 服务。"""
from __future__ import annotations

import http.client
import json
import queue
import threading
import unittest
from http.server import ThreadingHTTPServer

from assistant.config import load_config
from assistant.hud import EventBus, HudApp, HudHandler


class TestEventBus(unittest.TestCase):
    def test_publish_replay_and_subscribe(self):
        bus = EventBus(history_size=5)
        q = bus.subscribe()
        bus.publish({"type": "state", "phase": "thinking"})
        bus.publish({"type": "user_text", "text": "你好"})

        # 订阅者收到全部事件
        self.assertEqual(q.get(timeout=1)["type"], "state")
        self.assertEqual(q.get(timeout=1)["type"], "user_text")

        # 新订阅者回放历史
        bus.unsubscribe(q)
        q2 = bus.subscribe()
        replay = bus.replay()
        self.assertEqual([e["type"] for e in replay], ["state", "user_text"])
        bus.unsubscribe(q2)

    def test_history_capped(self):
        bus = EventBus(history_size=3)
        for i in range(5):
            bus.publish({"type": "t", "i": i})
        replay = bus.replay()
        self.assertEqual(len(replay), 3)
        self.assertEqual(replay[-1]["i"], 4)


class TestHudApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = HudApp(load_config())

    def test_ask_call_employee(self):
        r = self.app.ask("呼叫李华")
        self.assertTrue(r["ok"])
        self.assertEqual(r["intent"], "call")
        events = self.app.bus.replay()
        texts = [e for e in events if e["type"] == "assistant_text"]
        self.assertIn("呼叫", texts[-1]["text"])
        actions = [e for e in events if e["type"] == "action"]
        self.assertTrue(actions[-1]["action"].startswith("speaker.call"))

    def test_ask_kb_qa_with_source(self):
        r = self.app.ask("报销怎么走流程")
        self.assertEqual(r["intent"], "kb_qa")
        actions = [e for e in self.app.bus.replay() if e["type"] == "action"]
        self.assertEqual(actions[-1]["source"], "报销流程")

    def test_ask_wecom(self):
        r = self.app.ask("给张伟发消息下午三点开会")
        self.assertEqual(r["intent"], "wecom_send")
        self.assertIn("zhangwei", r["action_taken"])

    def test_consent_toggle(self):
        self.app.set_consent(False)
        self.assertFalse(self.app.recorder.enabled)
        self.app.set_consent(True)
        self.assertTrue(self.app.recorder.enabled)


class TestHudHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = HudApp(load_config())
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), HudHandler)
        cls.server.app = cls.app  # type: ignore[attr-defined]
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"} if body else {}
        data = json.dumps(body).encode() if body is not None else None
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        payload = resp.read()
        conn.close()
        return resp.status, json.loads(payload)

    def test_health(self):
        status, j = self._request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertTrue(j["ok"])

    def test_ask_route(self):
        status, j = self._request("POST", "/ask",
                                  {"text": "呼叫李华", "channel": "voice"})
        self.assertEqual(status, 200)
        self.assertEqual(j["intent"], "call")

    def test_consent_route(self):
        status, j = self._request("POST", "/consent", {"on": False})
        self.assertEqual(status, 200)
        self.assertFalse(j["on"])
        self._request("POST", "/consent", {"on": True})

    def test_events_sse_replays_meta(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/events")
        resp = conn.getresponse()
        self.assertEqual(resp.getheader("Content-Type", "").split(";")[0],
                         "text/event-stream")
        line = resp.readline().decode("utf-8").strip()
        conn.close()
        self.assertTrue(line.startswith("data: "))
        event = json.loads(line[len("data: "):])
        self.assertEqual(event["type"], "meta")


if __name__ == "__main__":
    unittest.main()
