# -*- coding: utf-8 -*-
from .base import BaseBrain, BrainReply
from .echo_brain import EchoBrain

__all__ = ["BaseBrain", "BrainReply", "EchoBrain"]


def create_brain(config: dict) -> BaseBrain:
    """按配置实例化大脑。"""
    provider = config["brain"]["provider"]
    system_prompt = config["brain"].get("system_prompt", "")
    if provider == "echo":
        return EchoBrain(system_prompt=system_prompt, config=config)
    if provider == "enterprise":
        from ..enterprise import create_enterprise_brain
        return create_enterprise_brain(config, system_prompt=system_prompt)
    if provider == "workbuddy":
        from .workbuddy_brain import WorkBuddyBrain
        return WorkBuddyBrain(system_prompt=system_prompt, config=config)
    raise ValueError(f"未知的大脑提供方: {provider}")
