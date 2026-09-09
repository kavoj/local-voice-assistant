# -*- coding: utf-8 -*-
"""企业微信客户端：stub / 群机器人 webhook / 自建应用 app 三模式。

- stub（默认）：只构造 payload 并打印，离线可测，保证可移植复刻
- webhook：企业微信群机器人，往群推通知（POST qyapi.weixin.qq.com/cgi-bin/webhook/send）
- app：自建应用，按 userid 精准发给对应员工（gettoken → message/send）

凭证一律来自 config，不写死在代码里。
"""
from __future__ import annotations

import json
import urllib.request
from typing import Optional


class WeComClient:
    def __init__(self, config: dict):
        wecom = config.get("enterprise", {}).get("wecom", {})
        self.mode = wecom.get("mode", "stub")
        self.webhook_key = wecom.get("webhook_key", "")
        self.corpid = wecom.get("corpid", "")
        self.secret = wecom.get("secret", "")
        self.agentid = wecom.get("agentid", "")
        self._token: Optional[str] = None

    # ---- 对外 -------------------------------------------------------------

    def send_text(self, userid: str, content: str) -> dict:
        """给指定员工发文本消息。返回 {ok, mode, payload/response}。"""
        if self.mode == "app":
            payload = {
                "touser": userid,
                "msgtype": "text",
                "agentid": self.agentid,
                "text": {"content": content},
            }
            response = self._app_send(payload)
            return {"ok": bool(response.get("errcode") == 0), "mode": "app",
                    "payload": payload, "response": response}
        if self.mode == "webhook":
            payload = {"msgtype": "text", "text": {"content": f"@{userid} {content}"}}
            response = self._webhook_send(payload)
            return {"ok": bool(response.get("errcode") == 0), "mode": "webhook",
                    "payload": payload, "response": response}
        # stub
        payload = {"touser": userid, "msgtype": "text", "text": {"content": content}}
        print(f"[企业微信·stub] -> {userid}: {content}")
        return {"ok": True, "mode": "stub", "payload": payload}

    def broadcast(self, content: str) -> dict:
        """全员/群通知（webhook 群机器人天然是群发；stub/app 走 @all）。"""
        if self.mode == "webhook":
            return self.send_text("所有人", content)
        payload = {"touser": "@all", "msgtype": "text", "text": {"content": content}}
        if self.mode == "app":
            response = self._app_send(payload)
            return {"ok": bool(response.get("errcode") == 0), "mode": "app",
                    "payload": payload, "response": response}
        print(f"[企业微信·stub] -> @all: {content}")
        return {"ok": True, "mode": "stub", "payload": payload}

    # ---- HTTP（仅非 stub 模式用到） ----------------------------------------

    def _post(self, url: str, data: dict) -> dict:
        req = urllib.request.Request(
            url, data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _webhook_send(self, payload: dict) -> dict:
        if not self.webhook_key:
            return {"errcode": -1, "errmsg": "missing webhook_key"}
        url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={self.webhook_key}"
        return self._post(url, payload)

    def _get_token(self) -> str:
        if self._token:
            return self._token
        if not (self.corpid and self.secret):
            raise ValueError("app 模式需要配置 enterprise.wecom.corpid / secret")
        url = (f"https://qyapi.weixin.qq.com/cgi-bin/gettoken"
               f"?corpid={self.corpid}&corpsecret={self.secret}")
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self._token = data["access_token"]
        return self._token

    def _app_send(self, payload: dict) -> dict:
        try:
            token = self._get_token()
        except Exception as exc:  # 网络异常时返回结构化错误，不中断会话
            return {"errcode": -1, "errmsg": str(exc)}
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        return self._post(url, payload)
