# -*- coding: utf-8 -*-
"""感知适配器：唤醒词与视觉。桩实现用于 console 演示，接口签名与真机版一致。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional


class BaseWakeWord(ABC):
    """唤醒词检测接口。回调在检测到唤醒词时被调用。"""

    def __init__(self, keyword: str = "嘿阿鹭", sensitivity: float = 0.6):
        self.keyword = keyword
        self.sensitivity = sensitivity

    @abstractmethod
    def start(self, on_detected: Callable[[], None]) -> None:
        """开始监听（阻塞或后台线程均可）。"""

    def stop(self) -> None:
        """停止监听。"""


class ConsoleWakeWord(BaseWakeWord):
    """桩实现：console 模式下，用户输入唤醒词文本即触发。"""

    def start(self, on_detected: Callable[[], None]) -> None:
        raise NotImplementedError("console 模式下唤醒词由 main.py 的输入循环模拟")

    def stop(self) -> None:
        pass


class BaseVision(ABC):
    """视觉感知接口：人形检测 + 人脸身份识别。"""

    def __init__(self, camera_index: int = 0, min_face_confidence: float = 0.5):
        self.camera_index = camera_index
        self.min_face_confidence = min_face_confidence

    @abstractmethod
    def poll_person(self) -> Optional[str]:
        """非阻塞检查：画面中是否有可识别的人，返回 person_id 或 None。

        约定：本地推理、不落盘画面；陌生人返回 "unknown"。
        """


class ConsoleVision(BaseVision):
    """桩实现：console 模式无摄像头，永远返回 None（仅靠唤醒词触发）。"""

    def poll_person(self) -> Optional[str]:
        return None


def create_wake_word(config: dict) -> BaseWakeWord:
    cfg = config["sensing"]["wake_word"]
    provider = cfg["provider"]
    if provider == "console":
        return ConsoleWakeWord(cfg.get("keyword", "嘿阿鹭"), cfg.get("sensitivity", 0.6))
    if provider == "porcupine":
        raise NotImplementedError("安装 pvporcupine 后实现 PorcupineWakeWord")
    raise ValueError(f"未知唤醒词提供方: {provider}")


def create_vision(config: dict) -> BaseVision:
    cfg = config["sensing"]["vision"]
    provider = cfg["provider"]
    if provider == "console":
        return ConsoleVision(cfg.get("camera_index", 0), cfg.get("min_face_confidence", 0.5))
    if provider == "yolo_face":
        raise NotImplementedError("安装 ultralytics + insightface 后实现 YoloFaceVision")
    raise ValueError(f"未知视觉提供方: {provider}")
