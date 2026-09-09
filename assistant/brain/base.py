# -*- coding: utf-8 -*-
"""大脑接口：把「用户说了什么」变成「助手怎么回、做了什么」。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrainReply:
    text: str                       # 给 TTS 播报的回复文本
    intent: str = "chat"            # 意图标签：schedule / query / message / chat ...
    action_taken: str = ""          # 大脑实际执行的动作摘要（工具调用等）
    task_done: bool = False         # 该轮任务是否完成


class BaseBrain(ABC):
    """所有大脑实现的统一接口。"""

    name: str = "base"

    def __init__(self, system_prompt: str = "", config: Optional[dict] = None):
        self.system_prompt = system_prompt
        self.config = config or {}
        self.history: list[dict] = []   # 会话内多轮上下文

    @abstractmethod
    def ask(self, text: str) -> BrainReply:
        """处理用户一轮输入，返回回复与行为元数据。"""

    def start_session(self) -> None:
        """新会话开始：清空轮级上下文，保留系统提示词。"""
        self.history = []

    def end_session(self) -> list[dict]:
        """会话结束：返回并清空历史（供 twin 采集器归档）。"""
        history = self.history
        self.history = []
        return history
