# -*- coding: utf-8 -*-
"""企业数字助理包：工厂函数与统一出口。"""
from __future__ import annotations

from ..brain.base import BaseBrain
from .agent import EnterpriseBrain
from .directory import Employee, EmployeeDirectory
from .knowledge import KnowledgeBase
from .onboarding import OnboardingSkill
from .speaker import ConsoleSpeaker, SpeakerController, create_speaker
from .wecom import WeComClient

__all__ = [
    "EnterpriseBrain", "KnowledgeBase", "EmployeeDirectory", "Employee",
    "OnboardingSkill", "WeComClient", "SpeakerController", "ConsoleSpeaker",
    "create_speaker", "create_enterprise_brain",
]


def create_enterprise_brain(config: dict, system_prompt: str = "") -> EnterpriseBrain:
    """组装企业大脑：知识库 + 名录 + 培训技能 + 企业微信 + 音箱。"""
    brain = EnterpriseBrain(system_prompt=system_prompt, config=config)
    brain.speaker = create_speaker(config)
    return brain
