# -*- coding: utf-8 -*-
"""状态机单元测试：覆盖主动交互的节流与冷却核心逻辑。"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistant.state_machine import Event, State, StateMachine  # noqa: E402


class StateMachineTest(unittest.TestCase):
    def setUp(self):
        self.sm = StateMachine(cooldown_seconds=300)

    def test_wake_word_starts_session(self):
        result = self.sm.handle_event(Event.WAKE_WORD, person_id="laosie")
        self.assertEqual(result["action"], "start_session")
        self.assertEqual(result["session"].trigger, "wake_word")
        self.assertEqual(self.sm.state, State.ENGAGED)
        self.assertTrue(result["greeting"])

    def test_person_detected_starts_proactive_session(self):
        result = self.sm.handle_event(Event.PERSON_DETECTED, person_id="laosie")
        self.assertEqual(result["action"], "start_session")
        self.assertEqual(result["session"].trigger, "person_detected")

    def test_cooldown_blocks_repeat_greeting(self):
        self.sm.handle_event(Event.PERSON_DETECTED, person_id="laosie")
        self.sm.handle_event(Event.SESSION_END)
        result = self.sm.handle_event(Event.PERSON_DETECTED, person_id="laosie")
        self.assertEqual(result["action"], "ignore")
        self.assertEqual(result["reason"], "cooldown")

    def test_cooldown_expires(self):
        self.sm.handle_event(Event.PERSON_DETECTED, person_id="laosie")
        self.sm.handle_event(Event.SESSION_END)
        # 把冷却名单里的过期时间拨回 300 秒前
        entry = self.sm._cooldowns["laosie"]
        entry.until -= 301
        result = self.sm.handle_event(Event.PERSON_DETECTED, person_id="laosie")
        self.assertEqual(result["action"], "start_session")

    def test_wake_word_bypasses_cooldown(self):
        self.sm.handle_event(Event.PERSON_DETECTED, person_id="laosie")
        self.sm.handle_event(Event.SESSION_END)
        result = self.sm.handle_event(Event.WAKE_WORD, person_id="laosie")
        self.assertEqual(result["action"], "start_session")

    def test_session_end_persists(self):
        self.sm.handle_event(Event.PERSON_DETECTED, person_id="laosie")
        result = self.sm.handle_event(Event.SESSION_END)
        self.assertEqual(result["action"], "end_session")
        self.assertEqual(self.sm.state, State.IDLE)
        self.assertIsNone(self.sm.session)

    def test_different_person_not_affected_by_cooldown(self):
        self.sm.handle_event(Event.PERSON_DETECTED, person_id="laosie")
        self.sm.handle_event(Event.SESSION_END)
        result = self.sm.handle_event(Event.PERSON_DETECTED, person_id="guest")
        self.assertEqual(result["action"], "start_session")

    def test_timeout_ends_session(self):
        self.sm.handle_event(Event.WAKE_WORD, person_id="laosie")
        result = self.sm.handle_event(Event.TURN_TIMEOUT)
        self.assertEqual(result["action"], "end_session")
        self.assertEqual(result["reason"], "turn_timeout")


if __name__ == "__main__":
    unittest.main()
