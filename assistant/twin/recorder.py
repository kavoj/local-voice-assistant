# -*- coding: utf-8 -*-
"""行为数据采集器：把每轮交互以 JSONL 追加写入 data/sessions/YYYY-MM-DD.jsonl。

红线：
- twin.consent_required 为 true 时，未获同意直接不采集；
- 只写本地文件，不做任何网络上传。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from ..config import resolve_path
from .schema import SessionRecord, TurnRecord, iso_now, new_session_id


class TwinRecorder:
    def __init__(self, config: dict, consent: bool = True):
        self.config = config
        # 配置要求知情同意时，以显式传入的 consent 为准；未同意则不采集。
        consent_required = config["twin"].get("consent_required", True)
        self.consent = bool(consent) if consent_required else True
        self.sessions_dir = resolve_path(config, "sessions_dir")
        self._lock = threading.Lock()
        self._current_session_id: str = new_session_id()
        self._turn_count = 0
        self._tasks_done = 0
        self._intents: dict = {}
        self._session_started_at = iso_now()

    @property
    def enabled(self) -> bool:
        return self.consent

    # ---- 会话级 -----------------------------------------------------------

    def begin_session(self, trigger: str, person_id: str = "unknown") -> str:
        self._current_session_id = new_session_id()
        self._turn_count = 0
        self._tasks_done = 0
        self._intents = {}
        self._session_started_at = iso_now()
        self._session_meta = {"trigger": trigger, "person_id": person_id}
        return self._current_session_id

    def record_turn(
        self,
        speaker: str,
        text: str,
        intent: str = "chat",
        action_taken: str = "",
        task_done: bool = False,
        trigger: str = "",
        person_id: str = "unknown",
    ) -> None:
        if not self.enabled:
            return
        record = TurnRecord(
            speaker=speaker,
            text=text,
            session_id=self._current_session_id,
            ts=iso_now(),
            trigger=trigger,
            intent=intent,
            action_taken=action_taken,
            task_done=task_done,
            person_id=person_id,
        )
        self._write(record.to_dict())
        if speaker == "assistant":
            self._turn_count += 1
            self._intents[intent] = self._intents.get(intent, 0) + 1
            if task_done:
                self._tasks_done += 1

    def end_session(self) -> None:
        if not self.enabled:
            return
        record = SessionRecord(
            session_id=self._current_session_id,
            started_at=self._session_started_at,
            ended_at=iso_now(),
            trigger=self._session_meta.get("trigger", ""),
            person_id=self._session_meta.get("person_id", "unknown"),
            turns=self._turn_count,
            tasks_done=self._tasks_done,
            intents=dict(self._intents),
        )
        self._write(record.to_dict())

    # ---- 内部 -------------------------------------------------------------

    def _session_file(self) -> Path:
        return self.sessions_dir / f"{iso_now()[:10]}.jsonl"

    def _write(self, obj: dict) -> None:
        with self._lock:
            with open(self._session_file(), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
