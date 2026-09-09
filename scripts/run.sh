#!/usr/bin/env bash
# ============================================================
#  阿鹭 · 一条命令启动可视化语音台（macOS / Linux）
#
#  用法:
#    ./scripts/run.sh              # 自动准备环境并打开 HUD 界面
#    ./scripts/run.sh --demo       # 自动演示模式（用于录屏 / 验收界面）
#    PORT=9000 ./scripts/run.sh    # 指定端口
#    EDA_TTS_REAL=1 ./scripts/run.sh   # 用系统真人语音播报（mac say）
#
#  它会:
#    1. 检查 python3 (>=3.9) —— 没有则给出安装指引
#    2. 首次运行自动创建 .venv 并安装依赖（pyyaml）
#    3. 启动本地 HUD 服务并自动打开浏览器 —— 麦克风按钮即可说话
# ============================================================
set -e
cd "$(dirname "$0")/.."

# 1) Python 检查
PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "❌ 未找到 python3。请先安装："
  echo "   macOS:   brew install python@3.12"
  echo "   Ubuntu:  sudo apt install python3 python3-venv"
  echo "   Fedora:  sudo dnf install python3"
  exit 1
fi
MAJOR=$("$PY" -c 'import sys;print(sys.version_info.major)' 2>/dev/null || echo 0)
MINOR=$("$PY" -c 'import sys;print(sys.version_info.minor)' 2>/dev/null || echo 0)
if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 9 ]; }; then
  echo "❌ 需要 Python ≥ 3.9，当前为 $("$PY" --version 2>&1 | cut -d' ' -f2)"
  exit 1
fi

# 2) 虚拟环境 + 依赖（幂等）
if [ ! -d .venv ]; then
  echo "🔧 首次运行：创建虚拟环境 .venv …"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
if ! python -c "import yaml" >/dev/null 2>&1; then
  echo "🔧 安装依赖 pyyaml …"
  pip install -q -r requirements.txt
fi

# 3) 启动 HUD
PORT="${PORT:-8765}"
echo ""
echo "🦜 启动阿鹭 HUD → http://127.0.0.1:${PORT}"
echo "   浏览器会自动打开；若没有，手动访问上面的地址。"
echo "   按住 🎙 说话 · Ctrl-C 退出"
echo ""
if [ "$1" = "--demo" ] || [ "$1" = "-d" ]; then
  exec python -m assistant.hud --demo --port "$PORT"
fi
exec python -m assistant.hud --port "$PORT"
