# -*- coding: utf-8 -*-
"""触发仲裁状态机：待命 → 感知触发 → 主动问候 → 多轮对话 → 冷却 → 待命。

核心职责：决定助手「什么时候开口、什么时候闭嘴」。
- 唤醒词触发（用户主动）：不受冷却限制，直接响应。
- 摄像头看到人（助手主动）：必须通过冷却节流，同一人短时间内不重复打扰。
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class State(str, Enum):
    IDLE = "idle"          # 待命，低功耗监听
    ENGAGED = "engaged"    # 会话进行中


class Event(str, Enum):
    WAKE_WORD = "wake_word"              # 听到唤醒词
    PERSON_DETECTED = "person_detected"  # 摄像头识别到人（携带 person_id）
    PERSON_GONE = "person_gone"          # 人离开了
    TURN_TIMEOUT = "turn_timeout"        # 对话中长时间无声
    SESSION_END = "session_end"          # 用户主动结束 / 任务完成


@dataclass
class CooldownEntry:
    person_id: str
    until: float  # epoch 秒


@dataclass
class Session:
    session_id: str
    person_id: str
    trigger: str           # wake_word / person_detected
    started_at: float
    meta: dict = field(default_factory=dict)


class StateMachine:
    """触发仲裁状态机。与硬件无关，纯逻辑，可单测。"""

    def __init__(self, cooldown_seconds: int = 300, greeting_pool: Optional[list] = None):
        self.cooldown_seconds = cooldown_seconds
        self.state = State.IDLE
        self.session: Optional[Session] = None
        self._cooldowns: dict[str, CooldownEntry] = {}
        self.greeting_pool = greeting_pool or [
            "你好，需要我帮忙吗？",
            "回来了？有什么要安排的尽管说。",
            "我在，说吧。",
        ]
        self._greeting_idx = 0

    # ---- 对外主接口 -------------------------------------------------------

    def handle_event(self, event: Event, person_id: str = "unknown") -> dict:
        """处理事件，返回动作指令 dict。

        返回形如：
          {"action": "start_session", "greeting": str, "session": Session}
          {"action": "end_session", "session": Session}
          {"action": "ignore", "reason": str}
        """
        handler = {
            Event.WAKE_WORD: self._on_wake_word,
            Event.PERSON_DETECTED: self._on_person_detected,
            Event.PERSON_GONE: self._on_person_gone,
            Event.TURN_TIMEOUT: self._on_turn_timeout,
            Event.SESSION_END: self._on_session_end,
        }[event]
        return handler(person_id)

    # ---- 事件处理 ---------------------------------------------------------

    def _on_wake_word(self, person_id: str) -> dict:
        # 唤醒词是用户主动行为，不受冷却限制；已在会话中则忽略重复唤醒。
        if self.state is State.ENGAGED:
            return {"action": "ignore", "reason": "already_engaged"}
        return self._start_session(person_id, trigger="wake_word")

    def _on_person_detected(self, person_id: str) -> dict:
        if self.state is State.ENGAGED:
            return {"action": "ignore", "reason": "already_engaged"}
        if self._in_cooldown(person_id):
            return {"action": "ignore", "reason": "cooldown"}
        return self._start_session(person_id, trigger="person_detected")

    def _on_person_gone(self, person_id: str) -> dict:
        if self.state is State.ENGAGED and self.session and self.session.person_id == person_id:
            return self._end_session(reason="person_gone")
        return {"action": "ignore", "reason": "no_matching_session"}

    def _on_turn_timeout(self, person_id: str = "unknown") -> dict:
        if self.state is State.ENGAGED:
            return self._end_session(reason="turn_timeout")
        return {"action": "ignore", "reason": "not_engaged"}

    def _on_session_end(self, person_id: str = "unknown") -> dict:
        if self.state is State.ENGAGED:
            return self._end_session(reason="session_end")
        return {"action": "ignore", "reason": "not_engaged"}

    # ---- 内部辅助 ---------------------------------------------------------

    def _start_session(self, person_id: str, trigger: str) -> dict:
        self.state = State.ENGAGED
        self.session = Session(
            session_id=uuid.uuid4().hex[:12],
            person_id=person_id,
            trigger=trigger,
            started_at=time.time(),
        )
        greeting = self.greeting_pool[self._greeting_idx % len(self.greeting_pool)]
        self._greeting_idx += 1
        return {"action": "start_session", "greeting": greeting, "session": self.session}

    def _end_session(self, reason: str) -> dict:
        session = self.session
        self.state = State.IDLE
        self.session = None
        if session and session.trigger == "person_detected":
            # 主动搭话的会话结束后进入冷却；唤醒词触发的无需冷却（用户随时可来）。
            self._cooldowns[session.person_id] = CooldownEntry(
                person_id=session.person_id,
                until=time.time() + self.cooldown_seconds,
            )
        return {"action": "end_session", "session": session, "reason": reason}

    def _in_cooldown(self, person_id: str) -> bool:
        entry = self._cooldowns.get(person_id)
        if entry and time.time() < entry.until:
            return True
        return False
