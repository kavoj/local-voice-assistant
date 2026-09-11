# -*- coding: utf-8 -*-
"""局域网远程控制：语音指令 → 目标电脑执行。

- dispatch.py：RemoteDispatcher，把「让会议室电脑锁屏」这类话术路由到设备并下发
- agent.py：节点代理，跑在被控电脑上（零依赖标准库，token 鉴权，白名单指令）
"""
from .dispatch import RemoteDispatcher

__all__ = ["RemoteDispatcher"]
