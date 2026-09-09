# -*- coding: utf-8 -*-
"""阿鹭 HUD —— 本地 Web 语音交互台（仅标准库，零第三方依赖）。

把「本地语音助手 / 企业数字助理」变成浏览器里的一块可视化操作台：

    麦克风（浏览器 Web Speech 中文识别）或键盘输入
      → POST /ask 交给大脑
      → SSE 实时推送：状态 / 用户字幕 / 回复文本 / 执行动作 / 采集统计
      → 界面光环变色、气泡时间线、动作追踪卡实时渲染
      → 回复朗读：浏览器 speechSynthesis；或设 EDA_TTS_REAL=1 用系统语音

用法：
    python -m assistant.hud                # 启动并自动打开浏览器
    python -m assistant.hud --demo         # 自动演示模式（每 1.6s 播一轮，供录屏/验收）
    python -m assistant.hud --port 9000 --no-browser

事件协议（SSE，每行一个 JSON）：
    {"type":"meta", ...}             连接欢迎：助手名/大脑/朗读模式/采集状态
    {"type":"state","phase":"listening|thinking|speaking|idle"}
    {"type":"user_text","text":"…","channel":"voice|text"}
    {"type":"assistant_text","text":"…","intent":"…","action_taken":"…","task_done":bool}
    {"type":"action","icon":"📞","title":"呼叫员工","detail":"…","action":"speaker.call:…","done":bool}
    {"type":"twin","on":bool,"turns":int,"done":int}
"""
from __future__ import annotations

import argparse
import json
import queue
import re
import sys
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .config import PROJECT_ROOT, load_config

HUD_HTML = PROJECT_ROOT / "web" / "hud.html"

# 动作意图 → (图标, 中文标题)
ACTION_META = {
    "call":         ("📞", "呼叫员工"),
    "wecom_send":   ("✉️", "发送企业微信"),
    "kb_qa":        ("📚", "知识库问答"),
    "onboarding":   ("🎓", "入职培训"),
    "session_end":  ("👋", "会话结束"),
    "unknown":      ("💬", "对话"),
}
_QUOTE_RE = re.compile(r"（出处：《(?P<source>[^》]+)》")


class EventBus:
    """线程安全事件总线：广播给所有订阅者，并为新订阅者回放最近事件。"""

    def __init__(self, history_size: int = 200):
        self._lock = threading.Lock()
        self._history: deque[dict] = deque(maxlen=history_size)
        self._subscribers: set[queue.Queue] = set()

    def publish(self, event: dict) -> None:
        event = dict(event)
        event.setdefault("ts", int(time.time() * 1000))
        with self._lock:
            self._history.append(event)
            for q in list(self._subscribers):
                q.put(event)

    def replay(self) -> list[dict]:
        with self._lock:
            return list(self._history)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subscribers.discard(q)


class HudApp:
    """组装 HUD 应用：大脑 + 行为采集 + 事件总线，串行处理每轮对话。"""

    def __init__(self, config: dict):
        self.config = config
        self.bus = EventBus()
        self._turn_lock = threading.Lock()

        # 大脑：默认企业数字助理；config hud.brain=echo 时可切换为回声大脑
        brain_cfg = config.get("hud", {}).get("brain", "enterprise")
        if brain_cfg == "enterprise":
            from .enterprise import create_enterprise_brain
            self.brain = create_enterprise_brain(
                config, system_prompt=config["brain"].get("system_prompt", ""))
            self.brain_name = "企业数字助理"
        else:
            from .brain import create_brain
            self.brain = create_brain(config)
            self.brain_name = "回声大脑"

        # 行为采集（数字分身）
        from .twin.recorder import TwinRecorder
        self.recorder = TwinRecorder(config, consent=True)
        self.recorder.begin_session(trigger="hud_ui", person_id="staff_web")

        # 朗读模式：EDA_TTS_REAL=1 → 系统真人语音（后端播报）；否则交给浏览器 speechSynthesis
        import os
        self.tts_real = os.environ.get("EDA_TTS_REAL") == "1"
        if self.tts_real:
            from .voice import create_tts
            self.tts = create_tts(config)

        # 立即广播欢迎元信息
        self.bus.publish({
            "type": "meta",
            "name": config["app"].get("name", "阿鹭"),
            "brain": self.brain_name,
            "tts_mode": "system" if self.tts_real else "browser",
            "twin_on": self.recorder.enabled,
        })

    # ---- 对外接口 ----------------------------------------------------------

    def ask(self, text: str, channel: str = "text") -> dict:
        """处理一轮对话（串行锁，保证多线程下会话上下文一致）。"""
        text = (text or "").strip()
        if not text:
            return {"ok": False, "reason": "empty"}
        with self._turn_lock:
            self.bus.publish({"type": "state", "phase": "thinking"})
            self.recorder.record_turn("user", text, intent="chat",
                                      trigger=channel or "text", person_id="staff_web")
            self.bus.publish({"type": "user_text", "text": text, "channel": channel or "text"})

            reply = self.brain.ask(text)

            self.bus.publish({
                "type": "assistant_text",
                "text": reply.text,
                "intent": reply.intent,
                "action_taken": reply.action_taken,
                "task_done": reply.task_done,
            })
            self._publish_action(reply)
            self.recorder.record_turn("assistant", reply.text, intent=reply.intent,
                                      action_taken=reply.action_taken, task_done=reply.task_done,
                                      trigger=channel or "text", person_id="staff_web")
            self._publish_twin_stats()

            # 会话收尾意图 → 重置上下文（下一轮是全新的开始，如培训完成后再接待下一位）
            if reply.intent == "session_end":
                self.brain.start_session()

            if self.tts_real and reply.text:
                self.bus.publish({"type": "state", "phase": "speaking"})
                threading.Thread(target=self._speak, args=(reply.text,), daemon=True).start()
            else:
                self.bus.publish({"type": "state", "phase": "idle"})

            return {"ok": True, "intent": reply.intent, "text": reply.text,
                    "action_taken": reply.action_taken}

    def set_consent(self, on: bool) -> dict:
        """切换数字分身行为采集（知情同意开关）。"""
        self.recorder.consent = bool(on)
        self._publish_twin_stats()
        return {"ok": True, "on": self.recorder.enabled}

    def twin_stats(self) -> dict:
        return {"on": self.recorder.enabled,
                "turns": self.recorder._turn_count,
                "done": self.recorder._tasks_done}

    # ---- 内部 --------------------------------------------------------------

    def _speak(self, text: str) -> None:
        try:
            self.tts.speak(text)
        finally:
            self.bus.publish({"type": "state", "phase": "idle"})

    def _publish_action(self, reply) -> None:
        icon, title = ACTION_META.get(reply.intent, ("💬", "对话"))
        detail = reply.text
        m = _QUOTE_RE.search(detail)
        source = m.group("source") if m else ""
        detail = _QUOTE_RE.sub("", detail).strip("，。 ")[:56]
        self.bus.publish({
            "type": "action",
            "icon": icon, "title": title,
            "detail": detail, "source": source,
            "action": reply.action_taken,
            "done": reply.task_done,
            "intent": reply.intent,
        })

    def _publish_twin_stats(self) -> None:
        self.bus.publish({"type": "twin", **self.twin_stats()})

    # ---- 演示 --------------------------------------------------------------

    def run_demo(self, interval: float = 1.6) -> None:
        """自动播一轮典型场景（新员工入职 → 培训 → 知识问答 → 呼叫 → 发消息）。"""
        script = [
            ("我是王小明，需要办理入职", "voice"),
            ("下一个", "voice"),
            ("差旅住宿标准是多少", "voice"),
            ("下一个", "voice"),
            ("下一个", "voice"),
            ("下一个", "voice"),
            ("下一个", "voice"),
            ("报销怎么走流程", "voice"),
            ("呼叫李华", "voice"),
            ("给张伟发消息下午三点会议室过一下季度方案", "voice"),
            ("再见", "voice"),
        ]
        print(f"[demo] 自动演示开始（每 {interval}s 一轮），Ctrl-C 停止。")
        try:
            for text, channel in script:
                time.sleep(interval)
                print(f"[demo] > {text}")
                self.ask(text, channel=channel)
        except KeyboardInterrupt:
            print("\n[demo] 已停止。")


class HudHandler(BaseHTTPRequestHandler):
    """HTTP + SSE 处理器。server 属性注入 app 实例。"""

    server_version = "AluHUD/0.1"

    # ---- 工具 --------------------------------------------------------------

    @property
    def app(self) -> HudApp:
        return self.server.app  # type: ignore[attr-defined]

    def _send_json(self, obj: dict, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _log(self, *args):  # 关闭每请求默认日志噪音，仅错误时打印
        pass

    # ---- 路由 --------------------------------------------------------------

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json({"ok": True, "name": self.app.config["app"].get("name", "阿鹭")})
        elif path == "/events":
            self._stream_events()
        elif path in ("/", "/index.html"):
            self._serve_page()
        else:
            self._send_json({"ok": False, "reason": f"no route: {path}"}, 404)

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json({"ok": False, "reason": "bad json"}, 400)
            return
        if path == "/ask":
            result = self.app.ask(payload.get("text", ""), channel=payload.get("channel", "text"))
            status = 200 if result.get("ok") else 400
            self._send_json(result, status)
        elif path == "/consent":
            self._send_json(self.app.set_consent(bool(payload.get("on", True))))
        else:
            self._send_json({"ok": False, "reason": f"no route: {path}"}, 404)

    # ---- 实现 --------------------------------------------------------------

    def _serve_page(self) -> None:
        if not HUD_HTML.exists():
            body = "web/hud.html 不存在——请确认在项目根目录运行。".encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = HUD_HTML.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _stream_events(self) -> None:
        """SSE：连接即回放近期事件，之后持续推送（15s 心跳保活）。"""
        q = self.app.bus.subscribe()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            for event in self.app.bus.replay():
                self._write_sse(event)
            while True:
                try:
                    event = q.get(timeout=15)
                    self._write_sse(event)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.app.bus.unsubscribe(q)

    def _write_sse(self, event: dict) -> None:
        data = json.dumps(event, ensure_ascii=False)
        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
        self.wfile.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="阿鹭 HUD · 本地 Web 语音交互台")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--demo", action="store_true", help="自动演示模式")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--interval", type=float, default=1.6, help="demo 轮间隔秒")
    args = parser.parse_args()

    config = load_config()
    hud_cfg = config.get("hud", {})
    host = args.host or hud_cfg.get("host", "127.0.0.1")
    port = args.port or int(hud_cfg.get("port", 8765))

    app = HudApp(config)
    server = ThreadingHTTPServer((host, port), HudHandler)
    server.app = app  # type: ignore[attr-defined]
    name = config["app"].get("name", "阿鹭")

    print(f"\n  🦜 {name} · HUD 已启动")
    print(f"  界面地址 : http://{host}:{port}")
    print(f"  大脑     : {app.brain_name}")
    print(f"  朗读模式 : {'系统真人语音(EDA_TTS_REAL)' if app.tts_real else '浏览器语音'}")
    print(f"  采集开关 : {'开' if app.recorder.enabled else '关（未同意不采集）'}")
    print(f"  按 Ctrl-C 退出\n")

    if not args.no_browser and not args.demo:
        threading.Timer(0.6, lambda: webbrowser.open(f"http://{host}:{port}")).start()

    try:
        if args.demo:
            threading.Thread(target=app.run_demo, args=(args.interval,), daemon=True).start()
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n Bye. 行为数据已落盘 data/sessions/（导出训练集: python -m assistant.twin.export --date today）")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
