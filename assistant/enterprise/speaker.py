# -*- coding: utf-8 -*-
"""音箱控制适配器：语音对话 → 控制音箱呼叫员工。

- ConsoleSpeaker（默认桩）：终端打印呼叫动作，离线验证流程
- 预留真机接入：小爱开放平台 / 天猫精灵技能 / 自研音箱 HTTP 接口，
  实现 SpeakerController 子类即可，企业大脑与技能层零改动。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .directory import Employee


class SpeakerController(ABC):
    @abstractmethod
    def call_employee(self, employee: Employee, from_person: str = "") -> dict:
        """通过音箱呼叫员工（响铃 + 屏显/播报来电人）。返回结构化结果供日志留痕。"""

    @abstractmethod
    def broadcast(self, text: str) -> dict:
        """通过音箱对外播报（如前台广播）。"""


class ConsoleSpeaker(SpeakerController):
    def call_employee(self, employee: Employee, from_person: str = "") -> dict:
        print(f"[音箱] 正在呼叫 {employee.name}（{employee.department}·分机 {employee.ext}）…")
        return {
            "ok": True,
            "action": "call_employee",
            "target": {"name": employee.name, "userid": employee.userid, "ext": employee.ext},
            "from": from_person,
        }

    def broadcast(self, text: str) -> dict:
        print(f"[音箱·广播] {text}")
        return {"ok": True, "action": "broadcast", "text": text}


def create_speaker(config: dict) -> SpeakerController:
    provider = config.get("enterprise", {}).get("speaker", {}).get("provider", "console")
    if provider == "console":
        return ConsoleSpeaker()
    raise NotImplementedError(
        f"音箱提供方 {provider} 未实现：请实现 SpeakerController 子类并注册到 create_speaker")
