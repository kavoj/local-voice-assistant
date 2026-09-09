# -*- coding: utf-8 -*-
"""配置加载：读取 config/settings.yaml，缺省时回落到 settings.example.yaml。"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_DEFAULTS = {
    "app": {"name": "阿鹭", "mode": "console"},
    "sensing": {
        "wake_word": {"provider": "console", "keyword": "嘿阿鹭", "sensitivity": 0.6},
        "vision": {"provider": "console", "camera_index": 0, "min_face_confidence": 0.5},
    },
    "voice": {
        "asr": {"provider": "console", "model": "paraformer-zh"},
        "tts": {"provider": "console", "voice": "zh-CN-XiaoxiaoNeural"},
        "vad": {"silence_timeout_seconds": 30},
    },
    "brain": {"provider": "echo", "system_prompt": "你是阿鹭。"},
    "twin": {
        "consent_required": True,
        "cooldown_seconds": 300,
        "redact_patterns": [],
    },
    "paths": {
        "sessions_dir": "data/sessions",
        "datasets_dir": "data/datasets",
    },
    "enterprise": {
        "employees_path": "data/enterprise/employees.json",
        "knowledge_dir": "data/knowledge",
        "wecom": {"mode": "stub", "webhook_key": "", "corpid": "", "secret": "", "agentid": ""},
        "speaker": {"provider": "console"},
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict:
    """加载配置文件（settings.yaml 优先，其次 example，最后纯默认值）。"""
    candidates = [
        PROJECT_ROOT / "config" / "settings.yaml",
        PROJECT_ROOT / "config" / "settings.example.yaml",
    ]
    file_cfg: dict = {}
    for path in candidates:
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                file_cfg = yaml.safe_load(fh) or {}
            break
    return _deep_merge(_DEFAULTS, file_cfg)


def resolve_path(config: dict, key: str) -> Path:
    """把配置里的相对路径解析为基于项目根目录的绝对路径。"""
    path = Path(config["paths"][key])
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path
