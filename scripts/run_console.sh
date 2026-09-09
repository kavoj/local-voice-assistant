#!/usr/bin/env bash
# console 模式启动
cd "$(dirname "$0")/.."
[ -d .venv ] && source .venv/bin/activate
python -m assistant.main --mode console
