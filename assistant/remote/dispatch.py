# -*- coding: utf-8 -*-
"""RemoteDispatcher：把自然语言控制指令分发到局域网设备。

设备名录 data/enterprise/devices.json：
    [{"name": "会议室电脑", "aliases": ["会议室"], "host": "192.168.1.50",
      "port": 8766, "token": "change-me"}]

指令表（可按需扩充，需与 agent.py 的 COMMANDS 对应）：
    锁屏 lock / 休眠 sleep / 关机 shutdown / 重启 reboot / 截图 screenshot /
    打开 open_url / 音量 volume / 静音 mute / 播报 say / 状态 status

match(text) 返回 (回复话术, action留痕, 是否完成) 或 None（不含设备控制意图时交回主路由）。
零依赖：HTTP 用标准库 urllib。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional
from urllib import request as _urlrequest

from ..config import PROJECT_ROOT

# 话术关键词 -> (指令, 参数提取函数)；顺序即匹配优先级
_COMMAND_TABLE = [
    (r"锁屏|锁定屏幕", "lock", None),
    (r"休眠|睡眠", "sleep", None),
    (r"关机", "shutdown", None),
    (r"重启", "reboot", None),
    (r"截(?:图|屏)|屏幕截图", "screenshot", None),
    (r"音量调?(?:到|至|大|小)?\s*(\d{1,3})", "volume", lambda m: {"level": int(m.group(1))}),
    (r"静音", "mute", None),
    (r"(?:播报|说|喊)\s*[：:，,]?\s*(.+)", "say", lambda m: {"text": m.group(1)}),
    (r"打开\s*(https?://\S+|[a-z0-9.\-]+\.[a-z]{2,}\S*)", "open_url", lambda m: {"url": m.group(1)}),
    (r"(?:运行|执行)\s*(?:脚本)?\s*([A-Za-z0-9_\-]+\.(?:sh|bat|ps1|py))", "exec_script",
     lambda m: {"script": m.group(1)}),
]

_ONLINE_WORDS = ("状态", "在线", "活着吗", "还在吗")

# 强控制动词：没点名设备也值得引导（「打开」等泛动词不在此列）
_STRONG_VERBS = {"lock", "sleep", "shutdown", "reboot", "screenshot",
                 "mute", "volume", "exec_script"}


# 局域网直连：绕过系统/环境代理（公司网络常配 http_proxy，会把内网请求也劫走）
_OPENER = _urlrequest.build_opener(_urlrequest.ProxyHandler({}))


def _default_sender(host: str, port: int, token: str, payload: dict, timeout: float = 5.0) -> dict:
    """默认 HTTP 下发；测试时替换为桩。"""
    url = f"http://{host}:{port}/cmd"
    data = json.dumps({**payload, "token": token}).encode("utf-8")
    req = _urlrequest.Request(url, data=data, headers={"Content-Type": "application/json"})
    with _OPENER.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class RemoteDispatcher:
    def __init__(self, config: dict, sender: Optional[Callable] = None):
        self.sender = sender or _default_sender
        cfg = config.get("remote", {}) if config else {}
        devices_path = Path(cfg.get("devices_path", "data/enterprise/devices.json"))
        if not devices_path.is_absolute():
            devices_path = PROJECT_ROOT / devices_path
        self.token = cfg.get("token", "")
        self.devices: list[dict] = []
        if devices_path.exists():
            try:
                self.devices = json.loads(devices_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.devices = []

    # ---- 匹配入口 ----------------------------------------------------------

    def match(self, text: str) -> Optional[tuple[str, str, bool]]:
        """返回 (回复, action, done)；无设备控制意图返回 None。"""
        if not self.devices:
            return None
        device = self._find_device(text)
        if device is None:
            hit = self._find_command(text)
            # 强控制动词没点名设备 → 引导点名（「打开」太泛，不算强动词，避免误抢路由）
            if hit and (hit[0] in _STRONG_VERBS or re.search(r"(电脑|设备|主机)", text)):
                return ("局域网里有多台设备，请说清楚控制哪一台，比如「让会议室电脑锁屏」。",
                        "remote.need_device", False)
            return None

        # 查询在线状态
        if any(w in text for w in _ONLINE_WORDS) or re.search(rf"{device['name']}(状态|在线)", text):
            ok = self._ping(device)
            return (f"{device['name']}{'在线，一切正常' if ok else '不在线，检查一下设备或代理是否启动'}。",
                    f"remote.status:{device['name']}", ok)

        hit = self._find_command(text)
        if hit is None:
            return None  # 点了设备名但没有控制动词 → 交给主路由
        verb, args = hit
        return self._dispatch(device, verb, args)

    # ---- 内部 --------------------------------------------------------------

    def _find_device(self, text: str) -> Optional[dict]:
        for dev in self.devices:
            names = [dev.get("name", "")] + list(dev.get("aliases", []))
            for n in names:
                if n and n in text:
                    return dev
        return None

    @staticmethod
    def _find_command(text: str) -> Optional[tuple[str, Optional[dict]]]:
        for pattern, verb, extractor in _COMMAND_TABLE:
            m = re.search(pattern, text)
            if m:
                return verb, extractor(m) if extractor else None
        return None

    def _dispatch(self, device: dict, verb: str, args: Optional[dict]) -> tuple[str, str, bool]:
        payload = {"command": verb, "args": args or {}}
        try:
            result = self.sender(device["host"], int(device.get("port", 8766)),
                                 device.get("token", self.token), payload)
        except Exception as exc:  # 网络不通/超时/拒绝
            return (f"指令没送达到{device['name']}（{exc.__class__.__name__}），"
                    f"检查设备是否开机、代理是否在跑。", f"remote.{verb}:{device['name']}.fail", False)
        if result.get("ok"):
            detail = result.get("detail", "")
            extra = f"（{detail}）" if detail else ""
            return (f"已让{device['name']}{_VERB_CN.get(verb, verb)}{extra}。",
                    f"remote.{verb}:{device['name']}", True)
        reason = result.get("error", "设备拒绝了该指令")
        return (f"{device['name']}没能完成{_VERB_CN.get(verb, verb)}：{reason}。",
                f"remote.{verb}:{device['name']}.deny", False)

    def _ping(self, device: dict) -> bool:
        try:
            result = self.sender(device["host"], int(device.get("port", 8766)),
                                 device.get("token", self.token), {"command": "ping", "args": {}})
            return bool(result.get("ok"))
        except Exception:
            return False


_VERB_CN = {
    "lock": "锁屏了", "sleep": "进入休眠了", "shutdown": "关机了", "reboot": "重启了",
    "screenshot": "截图了", "volume": "调整音量了", "mute": "静音了",
    "say": "播报了内容", "open_url": "打开网址了", "exec_script": "执行脚本了",
}
