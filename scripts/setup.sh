#!/usr/bin/env bash
# ============================================================
# macOS / Linux 一键部署入口（引导向导）
#   ./scripts/setup.sh                 # 交互引导
#   ./scripts/setup.sh --accept-defaults   # 全默认无人值守
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== local-voice-assistant 部署（macOS / Linux）=="
PYTHON="python3"
command -v "${PYTHON}" >/dev/null 2>&1 || PYTHON="python"

"${PYTHON}" scripts/quickstart.py "$@"
