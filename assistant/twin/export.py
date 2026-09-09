# -*- coding: utf-8 -*-
"""训练集导出：data/sessions/*.jsonl → data/datasets/twin-YYYYMMDD.jsonl

流程：读取 → 组配 (user, assistant) 轮对 → 过滤 → 去重 → 脱敏 → messages JSONL。

用法：
  python -m assistant.twin.export --date today
  python -m assistant.twin.export --date 2026-09-01
  python -m assistant.twin.export --all
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Optional

from ..config import PROJECT_ROOT, load_config, resolve_path

MIN_TEXT_LEN = 4  # 过短文本视为无意义


def _redact(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        text = re.sub(pattern, "[已脱敏]", text)
    return text


def load_turns(sessions_dir: Path, date: Optional[str] = None) -> list[dict]:
    """读取指定日期（或全部）会话文件中的 turn 记录。"""
    if date == "today":
        files = [sessions_dir / f"{time.strftime('%Y-%m-%d')}.jsonl"]
    elif date:
        files = [sessions_dir / f"{date}.jsonl"]
    else:
        files = sorted(sessions_dir.glob("*.jsonl"))
    turns: list[dict] = []
    for path in files:
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("record_type") == "turn":
                    turns.append(obj)
    return turns


def pair_turns(turns: list[dict]) -> list[dict]:
    """把连续的 user/assistant 轮配成对话对（user 在前）。"""
    pairs: list[dict] = []
    pending_user: Optional[dict] = None
    for turn in turns:
        if turn["speaker"] == "user":
            pending_user = turn
        elif turn["speaker"] == "assistant" and pending_user is not None:
            if turn.get("session_id") == pending_user.get("session_id"):
                pairs.append({"user": pending_user, "assistant": turn})
            pending_user = None
    return pairs


def build_dataset(pairs: list[dict], system_prompt: str, redact_patterns: list[str]) -> list[dict]:
    samples: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for pair in pairs:
        user_text = _redact(pair["user"]["text"].strip(), redact_patterns)
        asst_text = _redact(pair["assistant"]["text"].strip(), redact_patterns)
        if len(user_text) < MIN_TEXT_LEN or len(asst_text) < MIN_TEXT_LEN:
            continue
        if not pair["assistant"].get("task_done", False):
            continue  # 只导出任务完成的轮次：宁缺毋滥
        key = (user_text, asst_text)
        if key in seen:
            continue
        seen.add(key)
        samples.append({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": asst_text},
            ],
            "meta": {
                "intent": pair["assistant"].get("intent", "chat"),
                "action_taken": pair["assistant"].get("action_taken", ""),
                "session_id": pair["assistant"].get("session_id", ""),
                "ts": pair["assistant"].get("ts", ""),
            },
        })
    return samples


def export(date: Optional[str] = None, export_all: bool = False) -> Path:
    config = load_config()
    sessions_dir = resolve_path(config, "sessions_dir")
    datasets_dir = resolve_path(config, "datasets_dir")

    turns = load_turns(sessions_dir, date=None if export_all else (date or "today"))
    pairs = pair_turns(turns)
    system_prompt = (
        f"你是{config['app'].get('name', '助手')}（数字分身），"
        "语言风格与决策习惯与主人一致，简洁务实，先干活后解释。"
    )
    samples = build_dataset(pairs, system_prompt, config["twin"].get("redact_patterns", []))

    date_tag = time.strftime("%Y%m%d") if (export_all or not date or date == "today") else date.replace("-", "")
    out_path = datasets_dir / f"twin-{date_tag}.jsonl"
    with open(out_path, "w", encoding="utf-8") as fh:
        for sample in samples:
            fh.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"[export] 读入轮次 {len(turns)}，配对 {len(pairs)}，导出样本 {len(samples)}")
    print(f"[export] 训练集已写入: {out_path.relative_to(PROJECT_ROOT)}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="导出数字分身训练集")
    parser.add_argument("--date", default=None, help="日期 YYYY-MM-DD 或 today")
    parser.add_argument("--all", action="store_true", help="导出全部会话数据")
    args = parser.parse_args()
    export(date=args.date, export_all=args.all)


if __name__ == "__main__":
    main()
