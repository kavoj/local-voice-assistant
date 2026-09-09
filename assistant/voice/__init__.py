# -*- coding: utf-8 -*-
"""语音适配器：ASR 与 TTS。桩实现用于 console 演示，接口签名与真机版一致。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseASR(ABC):
    """语音识别接口：音频帧流转写为文本。"""

    @abstractmethod
    def transcribe(self, audio) -> str:
        """audio: 真机版为 PCM/numpy 帧；console 桩版不使用。"""


class ConsoleASR(BaseASR):
    """桩实现：console 模式下用户键入的文字即「转写结果」。"""

    def transcribe(self, audio) -> str:
        return ""


class BaseTTS(ABC):
    """语音合成接口：文本转语音并播报。"""

    @abstractmethod
    def speak(self, text: str) -> None:
        """合成并播报。真机版阻塞至播报完成，保证对话节奏。"""


class ConsoleTTS(BaseTTS):
    """桩实现：打印到终端。

    设置环境变量 EDA_TTS_REAL=1 后，会用系统语音真人口播（零额外依赖）：
      macOS   → say（中文可指定 -v Tingting）
      Windows → PowerShell SAPI（Microsoft Huihui 等）
      Linux   → 有 espeak-ng 则用，否则回落打印
    可作为「语音对话效果」的最快验证；正式链路见 docs/voice.md 的 ASR/TTS 适配器。
    """

    def speak(self, text: str) -> None:
        import os as _os
        if _os.environ.get("EDA_TTS_REAL") == "1":
            if self._speak_system(text):
                return
        print(f"[TTS] {text}")

    @staticmethod
    def _speak_system(text: str) -> bool:
        import platform as _platform
        import shutil as _shutil
        import subprocess as _sp
        system = _platform.system()
        try:
            if system == "Darwin":
                _sp.run(["say", "-v", "Tingting", text], check=False)
            elif system == "Windows":
                quoted = text.replace('"', '""')
                _sp.run(["powershell", "-NoProfile", "-Command",
                         "(New-Object -ComObject SAPI.SpVoice).Speak('" + quoted + "')"],
                        check=False)
            elif _shutil.which("espeak-ng"):
                _sp.run(["espeak-ng", text], check=False)
            elif _shutil.which("espeak"):
                _sp.run(["espeak", text], check=False)
            else:
                return False
            return True
        except OSError:
            return False


def create_asr(config: dict) -> BaseASR:
    provider = config["voice"]["asr"]["provider"]
    if provider == "console":
        return ConsoleASR()
    if provider in ("funasr", "whisper"):
        raise NotImplementedError(f"安装对应依赖后实现 {provider} 的 ASR 适配器")
    raise ValueError(f"未知 ASR 提供方: {provider}")


def create_tts(config: dict) -> BaseTTS:
    provider = config["voice"]["tts"]["provider"]
    if provider == "console":
        return ConsoleTTS()
    if provider in ("edge-tts", "cosyvoice"):
        raise NotImplementedError(f"安装对应依赖后实现 {provider} 的 TTS 适配器")
    raise ValueError(f"未知 TTS 提供方: {provider}")
