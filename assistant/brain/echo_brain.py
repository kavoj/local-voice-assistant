# -*- coding: utf-8 -*-
"""回声大脑：离线演示用。零依赖、可复现，用于验证整条链路与数据采集。"""
from __future__ import annotations

from .base import BaseBrain, BrainReply

_EXIT_WORDS = {"exit", "quit", "退出", "再见", "拜拜"}

_FAQ = [
    (("你是谁", "你叫什么"), "我是阿鹭，本地语音助手。现在跑的是演示大脑，接上 WorkBuddy 我就能真干活了。"),
    (("你能做什么", "能干什么"), "目前我能记录对话、攒数字分身数据。真机版可以管日程、发消息、查资料。"),
    (("今天", "日期"), "我的时钟在你机器上，真接大脑后我会在回复里带上实时日期。"),
]


class EchoBrain(BaseBrain):
    name = "echo"

    def ask(self, text: str) -> BrainReply:
        stripped = text.strip()
        self.history.append({"role": "user", "content": stripped})

        if any(word in stripped for word in _EXIT_WORDS):
            reply = BrainReply(
                text="好，先到这，数据我记下了。再见。",
                intent="session_end",
                action_taken="end_session",
                task_done=True,
            )
        else:
            reply = None
            for keywords, answer in _FAQ:
                if any(k in stripped for k in keywords):
                    reply = BrainReply(text=answer, intent="query", task_done=True)
                    break
            if reply is None:
                reply = BrainReply(
                    text=f"收到：「{stripped}」。演示大脑先记下来，接上 WorkBuddy 后我就能处理这类事情。",
                    intent="chat",
                )

        self.history.append({"role": "assistant", "content": reply.text})
        return reply
