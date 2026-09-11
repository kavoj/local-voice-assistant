#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包双平台演示设备部署包。

产出（dist/ 下）：
    eda-voice-assistant-macos.zip    macOS：双击「启动语音助手.command」即用
    eda-voice-assistant-windows.zip  Windows：先「安装环境.bat」，再「启动语音助手.bat」

包内含：完整源码 + 种子数据 + 一键启动/节点代理启动器 + 演示设备部署 README + 形象图。
用法： python3 scripts/package_release.py   （可选 --token 自定义节点代理默认 token）
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

COPY_ITEMS = [  # 相对 ROOT 的文件/目录
    "assistant",
    "web",
    "config/settings.example.yaml",
    "data/knowledge",
    "data/enterprise/employees.json",
    "assets/mascot/current.png",
    "requirements.txt",
    "LICENSE",
]
SKIP_DIRS = {"__pycache__", ".venv", ".git", ".workbuddy", ".skillkit",
             "android", "__MACOSX", "node_modules", "screenshots"}

README = """# 企业数字助理 · 演示设备部署包（{osname}）

两分钟上手：解压本目录到任意位置，按角色二选一。

## 角色 A · 主控演示机（跑语音助手的大脑 + 界面）

{launch_main}

- 自动：检查 Python3 → 建 venv → 装依赖 → 启动 HUD（局域网可访问，端口 8765）
- 浏览器打开 http://127.0.0.1:8765 即可对话；局域网其他设备访问 http://本机IP:8765
- 首次配置知识库/员工名录：编辑 `config/settings.yaml`（模板见 settings.example.yaml）

## 角色 B · 被控节点（局域网里被语音调度的电脑）

{launch_agent}

- 节点默认端口 8766、token 默认 `{token}`（改 token 需同步主控机 devices.json）
- 主控机在 `data/enterprise/devices.json` 登记这台设备（name/aliases/host/port/token），
  然后对话就能说：「让会议室电脑锁屏」「让会议室电脑截图」「让会议室电脑播报：三点开会」
- 危险指令（关机/重启）默认拒绝，节点启动时加 `--allow-shutdown` 才放开

## 形象替换

把新形象图命名为 `current.png`（支持 png/jpg/webp/gif）覆盖 `assets/mascot/current.png`，
重启服务即换形象——界面光环中心与安卓大屏 APK 同步生效，无需改任何代码。

## 常见问题

- 双击 .command 提示"无法打开"：系统设置 → 隐私与安全性 → 仍要打开
- 节点收不到指令：确认主控机与节点互 ping 通、端口 8766 未被防火墙拦截、token 一致
- 麦克风不识别：浏览器需 Chrome/Edge；或用 `EDA_TTS_REAL=1` 由服务端系统语音播报
- 首次运行没生成 .venv：手动 `python3 -m venv .venv && .venv/bin/pip install pyyaml`（Windows 用 `.venv\\Scripts\\pip`）
"""


def _copy_item(src: Path, stage_dir: Path) -> None:
    """按相对项目根的路径复制到打包目录（保持原有层级，不额外嵌套）。"""
    target = stage_dir / src.relative_to(ROOT)
    if src.is_dir():
        shutil.copytree(src, target,
                        ignore=shutil.ignore_patterns(*SKIP_DIRS, "*.pyc"))
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def _write(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(0o755)


def stage(target: str, token: str) -> Path:
    stage_dir = DIST / f"stage-{target}"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    for item in COPY_ITEMS:
        src = ROOT / item
        if not src.exists():
            print(f"  ! 跳过不存在的条目: {item}")
            continue
        _copy_item(src, stage_dir)

    # 种子设备名录：内置默认 token，开箱即联调
    devices = [{"name": "会议室电脑", "aliases": ["会议室"], "host": "192.168.1.50",
                "port": 8766, "token": token,
                "_说明": "改成实际被控电脑 IP；name/aliases 用于语音点名，可加多台"}]
    _write(stage_dir / "data/enterprise/devices.json",
           __import__("json").dumps(devices, ensure_ascii=False, indent=2))

    if target == "macos":
        launch_main = MAC_RUN
        launch_agent = MAC_AGENT.replace("{token}", token)
    else:
        launch_main = WIN_ENV + "\n\n```bat\n" + WIN_RUN + "\n```"
        launch_agent = "```bat\n" + WIN_AGENT.replace("{token}", token) + "\n```"

    readme = (README
              .replace("{osname}", "macOS" if target == "macos" else "Windows")
              .replace("{launch_main}", launch_main)
              .replace("{launch_agent}", launch_agent)
              .replace("{token}", token))
    if target == "macos":
        _write(stage_dir / "启动语音助手.command", MAC_RUN, executable=True)
        _write(stage_dir / "启动节点代理.command", MAC_AGENT.replace("{token}", token), executable=True)
    else:
        _write(stage_dir / "安装环境.bat", WIN_ENV)
        _write(stage_dir / "启动语音助手.bat", WIN_RUN)
        _write(stage_dir / "启动节点代理.bat", WIN_AGENT.replace("{token}", token))
    _write(stage_dir / "README-演示设备部署.md", readme)
    return stage_dir


def zip_dir(stage_dir: Path, out_name: str, top_name: str) -> Path:
    out = DIST / out_name
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        # 把包内容放进同名顶层目录，解压不散落
        for path in sorted(stage_dir.rglob("*")):
            rel = path.relative_to(stage_dir)
            arc = f"{top_name}/{rel}"
            if path.is_dir():
                zf.mkdir(arc)
            else:
                zf.write(path, arc)
                if path.stat().st_mode & 0o111:  # 保留可执行位
                    info = zf.getinfo(arc)
                    info.external_attr = 0o755 << 16
    return out


MAC_RUN = """#!/usr/bin/env bash
# 企业数字助理 · 主控演示机启动（macOS）
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "请先安装 Python3: https://www.python.org/downloads/"; read -n1; exit 1; }
[ -d .venv ] || { python3 -m venv .venv && ./.venv/bin/pip install -q pyyaml; }
export EDA_TTS_REAL=1
echo "[EDA] 启动中… 浏览器访问 http://127.0.0.1:8765"
exec ./.venv/bin/python -m assistant.hud --host 0.0.0.0 --port 8765
"""

MAC_AGENT = """#!/usr/bin/env bash
# EDA 节点代理 · 被控电脑端（macOS）
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "请先安装 Python3"; read -n1; exit 1; }
[ -d .venv ] || { python3 -m venv .venv && ./.venv/bin/pip install -q pyyaml; }
echo "[EDA-agent] 节点启动：端口 8766，token={token}"
exec ./.venv/bin/python -m assistant.remote.agent --port 8766 --token {token}
"""

WIN_ENV = """@echo off
chcp 65001 >nul
title EDA 环境安装
cd /d %~dp0
where python >nul 2>nul || (echo [EDA] 未检测到 Python，请先安装: https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .venv (
  echo [EDA] 首次安装：创建虚拟环境并装依赖…
  python -m venv .venv || (echo venv 创建失败 & pause & exit /b 1)
  .venv\\Scripts\\pip install -q pyyaml || (echo 依赖安装失败，检查网络 & pause & exit /b 1)
)
echo [EDA] 环境就绪。请双击「启动语音助手.bat」
pause
"""

WIN_RUN = """@echo off
chcp 65001 >nul
title 企业数字助理
cd /d %~dp0
where python >nul 2>nul || (echo [EDA] 请先运行「安装环境.bat」 & pause & exit /b 1)
if not exist .venv (echo [EDA] 请先运行「安装环境.bat」 & pause & exit /b 1)
set EDA_TTS_REAL=1
echo [EDA] 启动中… 浏览器访问 http://127.0.0.1:8765
.venv\\Scripts\\python -m assistant.hud --host 0.0.0.0 --port 8765
pause
"""

WIN_AGENT = """@echo off
chcp 65001 >nul
title EDA 节点代理
cd /d %~dp0
where python >nul 2>nul || (echo [EDA] 请先运行「安装环境.bat」 & pause & exit /b 1)
if not exist .venv (echo [EDA] 请先运行「安装环境.bat」 & pause & exit /b 1)
echo [EDA-agent] 节点启动：端口 8766，token={token}
.venv\\Scripts\\python -m assistant.remote.agent --port 8766 --token {token}
pause
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="打包演示设备部署包")
    parser.add_argument("--token", default="sanwu-demo", help="包内节点代理默认 token")
    args = parser.parse_args()

    DIST.mkdir(parents=True, exist_ok=True)
    outputs = []
    for target in ("macos", "windows"):
        print(f"[pack] 组装 {target} …")
        stage_dir = stage(target, args.token)
        out = zip_dir(stage_dir, f"eda-voice-assistant-{target}.zip",
                      f"eda-voice-assistant-{target}")
        outputs.append(out)
        shutil.rmtree(stage_dir)
        print(f"       -> {out.name}  {out.stat().st_size/1024/1024:.1f} MB")
    print("[pack] 完成：")
    for out in outputs:
        print(f"  {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
