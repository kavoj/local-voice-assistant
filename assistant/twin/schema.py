# -*- coding: utf-8 -*-
"""数字分身数据 schema：TurnRecord / SessionRecord。字段规范见 docs/digital-twin-data.md"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

RECORD_TURN = "turn"
RECORD_SESSION = "session"


@dataclass
class TurnRecord:
    """一轮对话（用户一句 + 助手一句）。"""

    speaker: str                    # user / assistant
    text: str
    session_id: str
    ts: str                         # ISO 8601
    trigger: str = ""               # wake_word / person_detected
    intent: str = "chat"
    action_taken: str = ""
    task_done: bool = False
    person_id: str = "unknown"
    record_type: str = RECORD_TURN

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionRecord:
    """会话级摘要，会话结束时写入。"""

    session_id: str
    started_at: str                 # ISO 8601
    ended_at: str
    trigger: str
    person_id: str
    turns: int = 0
    tasks_done: int = 0
    intents: dict = field(default_factory=dict)   # 意图分布 {"query": 2, ...}
    record_type: str = RECORD_SESSION

    def to_dict(self) -> dict:
        return asdict(self)


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
