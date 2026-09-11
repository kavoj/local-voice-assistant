# -*- coding: utf-8 -*-
"""节点代理：跑在局域网被控电脑上，接收助理下发的白名单指令。

零依赖（纯标准库），跨平台 macOS / Windows / Linux。启动：

    python3 -m assistant.remote.agent --port 8766 --token change-me

安全设计：
- token 鉴权（请求体携带），不匹配一律 403
- 指令白名单（COMMANDS），未知指令拒绝
- exec_script 仅允许执行代理目录 scripts/ 白名单后缀内的脚本
- 关机/重启需 --allow-shutdown 显式开启
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = Path.home() / ".eda-agent" / "scripts"
SHOTS_DIR = Path.home() / ".eda-agent" / "screenshots"

# ---- 平台执行器 -------------------------------------------------------------


def _run(cmd: list[str], timeout: float = 15.0) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode == 0, (proc.stdout or proc.stderr or "").strip()[:200]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)[:200]


def _ps1(script: str) -> list[str]:
    return ["powershell", "-NoProfile", "-Command", script]


def do_lock():
    system = platform.system()
    if system == "Darwin":
        return _run(["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"])
    if system == "Windows":
        return _run(["rundll32.exe", "user32.dll,LockWorkStation"])
    return _run(["loginctl", "lock-session"])


def do_sleep():
    system = platform.system()
    if system == "Darwin":
        return _run(["pmset", "sleepnow"])
    if system == "Windows":
        return _run(["rundll32.exe", "powrprof.dll,SetSuspendState 0,1,0"])
    return _run(["systemctl", "suspend"])


def _make_shutdown(allow: bool):
    def do_shutdown():
        if not allow:
            return False, "代理未开启 --allow-shutdown，拒绝关机指令"
        system = platform.system()
        if system == "Darwin":
            return _run(["osascript", "-e", 'tell app "System Events" to shut down'])
        if system == "Windows":
            return _run(["shutdown", "/s", "/t", "5"])
        return _run(["systemctl", "poweroff"])
    return do_shutdown


def _make_reboot(allow: bool):
    def do_reboot():
        if not allow:
            return False, "代理未开启 --allow-shutdown，拒绝重启指令"
        system = platform.system()
        if system == "Darwin":
            return _run(["osascript", "-e", 'tell app "System Events" to restart'])
        if system == "Windows":
            return _run(["shutdown", "/r", "/t", "5"])
        return _run(["systemctl", "reboot"])
    return do_reboot


def do_screenshot():
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    import time
    path = SHOTS_DIR / f"shot-{time.strftime('%Y%m%d-%H%M%S')}.png"
    system = platform.system()
    if system == "Darwin":
        ok, out = _run(["screencapture", "-x", str(path)])
    elif system == "Windows":
        ok, out = _run(_ps1(
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
            "$bmp=New-Object Drawing.Bitmap $b.Width,$b.Height;"
            "$g=[Drawing.Graphics]::FromImage($bmp);"
            "$g.CopyFromScreen($b.Location,[Drawing.Point]::Empty,$b.Size);"
            f"$bmp.Save('{path}');$g.Dispose();$bmp.Dispose()"))
    else:
        ok, out = _run(["import", "-window", "root", str(path)])
    return ok, f"{path.name}" if ok else out


def do_volume(args: dict):
    level = max(0, min(100, int(args.get("level", 50))))
    system = platform.system()
    if system == "Darwin":
        return _run(["osascript", "-e", f"set volume output volume {level}"])
    if system == "Windows":
        # 依赖系统自带 COM 接口的近似实现（精确控制可装 nircmd）
        key = int(level * 65535 / 100)
        return _run(_ps1(
            "Add-Type '(bool,int,uint,uint)SetVol(){MessageBox.Show(\"\");return default;}' -ErrorAction SilentlyContinue;"
            f"$w=New-Object -ComObject WScript.Shell; $null=$w.SendKeys([char]174); '{level}%'"))
    return _run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"])


def do_mute():
    system = platform.system()
    if system == "Darwin":
        return _run(["osascript", "-e", "set volume with output muted"])
    if system == "Windows":
        return _run(_ps1("$w=New-Object -ComObject WScript.Shell; $null=$w.SendKeys([char]173); 'muted'"))
    return _run(["amixer", "-D", "pulse", "sset", "Master", "toggle"])


def do_say(args: dict):
    text = str(args.get("text", ""))[:300]
    system = platform.system()
    if system == "Darwin":
        return _run(["say", "-v", "Tingting", text])
    if system == "Windows":
        quoted = text.replace("'", "''")
        return _run(_ps1(f"(New-Object -ComObject SAPI.SpVoice).Speak('{quoted}')"))
    return _run(["espeak", text])


def do_open_url(args: dict):
    url = str(args.get("url", "")).strip()
    if not re_url(url):
        return False, f"非法地址: {url[:60]}"
    system = platform.system()
    if system == "Darwin":
        return _run(["open", url])
    if system == "Windows":
        return _run(["cmd", "/c", "start", "", url])
    return _run(["xdg-open", url])


def re_url(url: str) -> bool:
    import re
    return bool(re.match(r"^(https?://|file://)?[A-Za-z0-9.\-]+(\.[A-Za-z]{2,})?", url)) and " " not in url


def do_exec_script(args: dict):
    name = str(args.get("script", "")).strip()
    if Path(name).name != name or not name.endswith((".sh", ".bat", ".ps1", ".py")):
        return False, "仅允许执行 scripts/ 目录下 .sh/.bat/.ps1/.py 脚本（不带路径）"
    target = SCRIPTS_DIR / name
    if not target.exists():
        return False, f"脚本不存在: {name}（放到 {SCRIPTS_DIR}）"
    if name.endswith(".py"):
        return _run([sys.executable, str(target)], timeout=120)
    target.chmod(0o755)
    return _run([str(target)], timeout=120)


# ---- 指令表 -----------------------------------------------------------------

def build_commands(allow_shutdown: bool) -> dict:
    return {
        "ping": lambda args: (True, platform.node()),
        "lock": lambda args: do_lock(),
        "sleep": lambda args: do_sleep(),
        "shutdown": lambda args: _make_shutdown(allow_shutdown)(),
        "reboot": lambda args: _make_reboot(allow_shutdown)(),
        "screenshot": lambda args: do_screenshot(),
        "volume": do_volume,
        "mute": lambda args: do_mute(),
        "say": do_say,
        "open_url": do_open_url,
        "exec_script": do_exec_script,
    }


# ---- HTTP 服务 ---------------------------------------------------------------


class AgentHandler(BaseHTTPRequestHandler):
    token = ""
    commands: dict = {}

    def log_message(self, fmt, *args):  # 静默访问日志
        pass

    def _json(self, code: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "host": platform.node(), "system": platform.system()})
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/cmd":
            return self._json(404, {"ok": False, "error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (json.JSONDecodeError, ValueError):
            return self._json(400, {"ok": False, "error": "bad json"})
        if payload.get("token") != self.token:
            return self._json(403, {"ok": False, "error": "token 不匹配"})
        command = payload.get("command", "")
        fn = self.commands.get(command)
        if fn is None:
            return self._json(200, {"ok": False, "error": f"未知指令: {command}"})
        try:
            ok, detail = fn(payload.get("args") or {})
        except Exception as exc:  # 执行器兜底
            return self._json(200, {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"})
        self._json(200, {"ok": bool(ok), "detail": detail})


def main() -> None:
    parser = argparse.ArgumentParser(description="EDA 节点代理（被控电脑端）")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--token", default="", help="鉴权 token；与助理端 devices.json 一致")
    parser.add_argument("--allow-shutdown", action="store_true", help="允许关机/重启指令")
    args = parser.parse_args()

    AgentHandler.token = args.token
    AgentHandler.commands = build_commands(args.allow_shutdown)
    server = ThreadingHTTPServer((args.host, args.port), AgentHandler)
    print(f"[eda-agent] {platform.node()}({platform.system()}) 监听 {args.host}:{args.port}，"
          f"token={'已配置' if args.token else '未配置(危险)'}，关机权限={'开' if args.allow_shutdown else '关'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[eda-agent] 退出")


if __name__ == "__main__":
    main()
