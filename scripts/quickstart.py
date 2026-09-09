#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台一键部署引导向导（Windows / macOS / Linux）。

职责：环境检查 → 创建虚拟环境 → 安装依赖 → 生成配置 → （可选）对接 Obsidian 知识库 → 试运行。
全程问答式；无人值守场景可用 --accept-defaults 走默认路径，--skip-deps 跳过依赖安装（调试用）。

用法：
  python3 scripts/quickstart.py                 # 交互式引导
  python3 scripts/quickstart.py --accept-defaults   # 默认值直接跑
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = ROOT / ".venv"
REQ_FILE = ROOT / "requirements.txt"
CONFIG_EXAMPLE = ROOT / "config" / "settings.example.yaml"
CONFIG_FILE = ROOT / "config" / "settings.yaml"
SEED_KB = ROOT / "data" / "knowledge"


def banner(text: str) -> None:
    print("\n" + "=" * 62)
    print("  " + text)
    print("=" * 62)


def ask(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{question}{suffix}: ").strip()
    return value or default


def check_python() -> Path | None:
    """找可用的 python3（>=3.9）。Windows 依次试 py -3 / python3 / python。"""
    candidates: list[list[str]] = []
    if sys.platform == "win32":
        candidates = [["py", "-3"], ["python3"], ["python"]]
    else:
        candidates = [["python3"], ["python"]]
    for cand in candidates:
        try:
            out = subprocess.run(cand + ["--version"], capture_output=True, text=True, timeout=15)
            version = (out.stdout or out.stderr).strip()
            if out.returncode == 0 and version:
                import re
                m = re.search(r"(\d+)\.(\d+)", version)
                if m and (int(m.group(1)), int(m.group(2))) >= (3, 9):
                    return shutil.which(cand[0])
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def make_venv(python: Path) -> bool:
    banner("步骤 1/4 · 创建虚拟环境")
    if VENV_DIR.exists():
        print("已存在 .venv，跳过创建。")
        return True
    print(f"使用 {python} 创建 {VENV_DIR} …")
    try:
        subprocess.run([str(python), "-m", "venv", str(VENV_DIR)], check=True, timeout=180)
        return True
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"创建失败：{exc}\n将回退为直接使用系统 Python。")
        return False


def venv_python() -> Path:
    bin_dir = VENV_DIR / ("Scripts" if sys.platform == "win32" else "bin")
    py = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
    return py if py.exists() else Path(sys.executable)


def install_deps() -> bool:
    banner("步骤 2/4 · 安装依赖")
    py = venv_python()
    try:
        subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"],
                       check=False, capture_output=True)
        subprocess.run([str(py), "-m", "pip", "install", "-r", str(REQ_FILE)],
                       check=True, timeout=600)
        print("依赖安装完成。")
        return True
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"依赖安装失败：{exc}\n请检查网络后重试，或手动执行 pip install -r requirements.txt")
        return False


def gen_config() -> Path:
    banner("步骤 3/4 · 生成配置")
    if CONFIG_FILE.exists():
        print(f"已存在 {CONFIG_FILE.relative_to(ROOT)}，保留现有配置。")
        return CONFIG_FILE
    shutil.copy(CONFIG_EXAMPLE, CONFIG_FILE)
    print(f"已从模板生成 {CONFIG_FILE.relative_to(ROOT)}，后续可自行编辑。")
    return CONFIG_FILE


def obsidian_step(interactive: bool = True) -> None:
    banner("（可选）对接 Obsidian 本地知识库")
    vault = ""
    if interactive:
        vault = ask("你的 Obsidian 库目录（留空跳过；如 ~/Documents/Obsidian/企业知识库）", "")
    if not vault:
        print("跳过 Obsidian 对接。你也可以之后用 docs/obsidian-guide.md 手动配置。")
        return
    vault_path = Path(vault).expanduser()
    if not vault_path.is_absolute():
        vault_path = ROOT / vault_path
    kb_vault = vault_path / "00-数字助理知识库"
    try:
        kb_vault.mkdir(parents=True, exist_ok=True)
        # 把种子制度文档拷进 vault，供 Obsidian 编辑、助手即换即用
        if SEED_KB.exists():
            for doc in SEED_KB.glob("*"):
                if doc.suffix in (".md", ".txt"):
                    shutil.copy(doc, kb_vault / doc.name)
        _write_knowledge_dir(str(kb_vault))
        print(f"✓ 已对接。知识库：{kb_vault}")
        print("  以后在 Obsidian 里新建/编辑 markdown 制度文档，助手下次启动即生效。")
    except OSError as exc:
        print(f"对接失败：{exc}（可稍后按 docs/obsidian-guide.md 手动处理）")


def _write_knowledge_dir(vault_kb: str) -> None:
    """把 enterprise.knowledge_dir 指向 vault 目录（YAML 简单替换）。"""
    import re
    text = CONFIG_FILE.read_text("utf-8")
    text = re.sub(r"(knowledge_dir:\s*).*", rf"\1{json_dquote(vault_kb)}", text, count=1)
    CONFIG_FILE.write_text(text, "utf-8")


def json_dquote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def run_check() -> None:
    banner("步骤 4/4 · 试运行验证")
    py = venv_python()
    tests = subprocess.run([str(py), "-m", "unittest", "discover", "-s", "tests"],
                           capture_output=True, text=True, cwd=str(ROOT))
    if tests.returncode == 0:
        print("单元测试全部通过 ✓")
    else:
        print("单元测试异常：\n" + tests.stdout[-800:] + tests.stderr[-500:])
    if ask("立即跑一个企业版演示看看效果？", "y").lower() in ("y", "yes", ""):
        subprocess.run([str(py), "-m", "assistant.main", "--mode", "enterprise"], cwd=str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="local-voice-assistant 一键部署")
    parser.add_argument("--accept-defaults", action="store_true", help="全默认无人值守")
    parser.add_argument("--skip-deps", action="store_true", help="跳过依赖安装（调试用）")
    args = parser.parse_args()

    print(f"""
┌────────────────────────────────────────────┐
│  本地语音助手 · 企业数字助理 一键部署引导    │
│  平台: {platform.system()} {platform.release():<18}  │
└────────────────────────────────────────────┘""")

    if not args.accept_defaults:
        input("按回车开始（Ctrl+C 随时取消）…")

    python = check_python()
    if python is None:
        print("未找到 Python 3.9+，请先安装：https://www.python.org/downloads/")
        return 1
    print(f"✓ Python: {python}")

    make_venv(Path(python))
    if not args.skip_deps and not install_deps():
        return 1
    gen_config()
    obsidian_step(interactive=not args.accept_defaults)
    if args.accept_defaults:
        # 无人值守：只跑测试，不阻塞演示
        py = venv_python()
        subprocess.run([str(py), "-m", "unittest", "discover", "-s", "tests"], cwd=str(ROOT))
    else:
        run_check()

    banner("部署完成")
    print("· 交互模式（打字说话）      : python -m assistant.main --mode console")
    print("· 企业数字助理演示          : python -m assistant.main --mode enterprise")
    print("· 语音对话接入指南          : docs/voice.md")
    print("· Obsidian 知识库联动指南   : docs/obsidian-guide.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
