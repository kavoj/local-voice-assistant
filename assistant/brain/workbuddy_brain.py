# -*- coding: utf-8 -*-
"""WorkBuddy 大脑（M2 预留）：把 ASR 转写文本送入 WorkBuddy 会话，取回回复。

对接思路（实现 ask() 即可启用）：
1. 会话通道：通过 WorkBuddy 开放的会话接口/CLI 无头模式，发送转写文本并取回回复；
2. 记忆与工具：长期记忆、日程、消息等能力全部留在 WorkBuddy 侧，
   语音前端只做「耳朵和嘴」，不重复造轮子；
3. 行为标注：把 WorkBuddy 侧的工具调用摘要填入 BrainReply.action_taken，
   让 twin 采集器能记录「数字分身该学会做什么」，而不只是「说了什么」。
"""
from __future__ import annotations

from .base import BaseBrain, BrainReply


class WorkBuddyBrain(BaseBrain):
    name = "workbuddy"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        raise NotImplementedError(
            "WorkBuddyBrain 尚未对接。请实现 ask()："
            "调用 WorkBuddy 会话接口发送 text，取回回复后封装为 BrainReply 返回。"
        )

    def ask(self, text: str) -> BrainReply:
        raise NotImplementedError
