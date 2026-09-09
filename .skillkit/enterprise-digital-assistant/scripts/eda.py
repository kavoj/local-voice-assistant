#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""企业数字助理 CLI（eda）——自包含单文件，离线可跑。

能力：制度问答(本地知识库) / 员工名录 / 呼叫指令卡 / 企业微信消息(stub|webhook) / 入职培训 / 意图解析
用法示例：
  eda ask "报销怎么走流程"
  eda find 李华
  eda dept 研发
  eda call 李华 --msg "来一下前台"
  eda send 张伟 "下午三点会议室过季度方案"        # stub 默认；--mode webhook 需 config
  eda onboard --name 王小明                        # 交互式入职培训
  eda intent "给张伟发消息明天开会"                # 意图解析（供大脑二次确认）

依赖：仅 Python 3.9+ 标准库。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = SKILL_ROOT / "knowledge"
DATA_FILE = SKILL_ROOT / "data" / "employees.json"
CONFIG_FILE = SKILL_ROOT / "config.json"

EXIT_WORDS = ("再见", "拜拜", "退出", "结束培训", "先这样")


# ---------- 知识库 ----------

def bigrams(text: str) -> set:
    cleaned = re.sub(r"[\s，。、：；！？\-#*（）()]", "", text)
    return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)} if len(cleaned) > 1 else {cleaned}


class KnowledgeBase:
    def __init__(self, kb_dir: Path = KB_DIR):
        self.kb_dir = Path(kb_dir)
        self.chunks: list[dict] = []

    def load(self) -> int:
        self.chunks = []
        if not self.kb_dir.exists():
            return 0
        for path in sorted(self.kb_dir.glob("*")):
            if path.suffix not in (".md", ".txt"):
                continue
            heading, current = "", []
            def flush():
                if current:
                    text = "\n".join(current).strip()
                    if text:
                        self.chunks.append({"text": text, "source": path.stem, "heading": heading})
                    current.clear()
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.rstrip()
                    if line.startswith("#"):
                        flush(); heading = line.lstrip("#").strip()
                    elif not line.strip():
                        flush()
                    else:
                        current.append(line)
            flush()
        return len(self.chunks)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if not self.chunks:
            return []
        q = bigrams(query)
        hits = []
        for c in self.chunks:
            overlap = len(q & bigrams(c["text"] + " " + c["heading"] + " " + c["source"]))
            if overlap:
                hits.append({**c, "score": round(overlap / (len(q) ** 0.5), 3)})
        hits.sort(key=lambda r: r["score"], reverse=True)
        return hits[:top_k]

    def answer(self, query: str) -> str | None:
        hits = self.search(query)
        if not hits or hits[0]["score"] < 0.5:
            return None
        top = hits[0]
        excerpt = max(top["text"].split("\n"), key=len)
        return f"{excerpt}（出处：《{top['source']}》{top['heading']}）"


# ---------- 员工名录 ----------

def load_employees() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def find_employee(query: str) -> dict | None:
    """双向匹配：查询即姓名（find 李华），或姓名出现在长句里（给张伟发消息…）。"""
    query = query.strip()
    for emp in load_employees():
        if emp["name"] == query or query in emp["name"] or emp["name"] in query:
            return emp
    return None


# ---------- 意图解析（供大脑二次确认 / 测试） ----------

def parse_intent(text: str) -> dict:
    """规则意图解析：call / wecom_send / onboarding / kb_qa / session_end / unknown"""
    if any(w in text for w in EXIT_WORDS):
        return {"intent": "session_end"}
    if re.search(r"(呼叫|打电话给|打电话找|call)", text, re.IGNORECASE):
        emp = find_employee(text) or {}
        return {"intent": "call", "name": emp.get("name", ""), "userid": emp.get("userid", "")}
    if re.search(r"(发(?:个|条)?(?:消息|信息|微信)|通知)", text):
        emp = find_employee(text) or {}
        content = text.split(emp["name"], 1)[1] if emp else ""
        content = re.sub(r"^(?:请|麻烦|帮我)?(?:发(?:个|条)?(?:消息|信息|微信)|通知)+[：:，, ]*", "", content).strip("，。, ：: ")
        return {"intent": "wecom_send", "name": emp.get("name", ""),
                "userid": emp.get("userid", ""), "content": content}
    if any(w in text for w in ("入职", "培训")):
        return {"intent": "onboarding"}
    return {"intent": "kb_qa"}


# ---------- 入职培训 ----------

STEPS = [
    ("欢迎入职", "欢迎加入！我是企业数字助理。接下来带你过入职必修课，说「下一个」继续，随时可直接提问。"),
    ("入职当天流程", "入职当天：先到人力资源部找 HRBP 报到（李华，分机 8003），签合同和保密协议，领工牌门禁卡；IT 当天开通企业微信、邮箱和 OA；再回部门对接导师。"),
    ("考勤制度", "标准工时 9:00-18:00，午休 12:00-13:30，可 8:30-9:30 弹性到岗。请假走企业微信审批：1 天内直属上级、3 天内部门总监、3 天以上总经理；每月 2 次补卡。"),
    ("报销流程", "报销在 OA 财务模块提交并传发票照片，审批链：直属上级→部门总监→财务复核，随次月工资发放。发票需 90 天内、抬头为公司全称。差旅：高铁二等座/经济舱，住宿一线 500 元、其他 350 元/晚。"),
    ("常用工具与支持", "会议室在企业微信预约；电脑故障找 IT（3 楼）；工资每月 10 日发。有问题随时问我，或找 HRBP 李华（分机 8003）。祝你入职顺利！"),
]


def run_onboarding(name: str) -> None:
    kb = KnowledgeBase()
    kb.load()
    print(f"{name}，欢迎入职！让我带你完成入职必修课（共 {len(STEPS)} 节）。\n")
    for idx, (title, content) in enumerate(STEPS, 1):
        print(f"── 第 {idx}/{len(STEPS)} 节 · {title} ──\n{content}\n")
        while True:
            try:
                line = input("（输入「下一个」继续，或直接提问，exit 结束）> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n培训已暂停，进度可后续继续。")
                return
            if line.lower() in ("exit", "q") or any(w in line for w in EXIT_WORDS):
                print("培训结束，进度已记录。")
                return
            if any(w in line for w in ("下一个", "下一节", "继续")):
                break
            answer = kb.answer(line)
            print(("答：" + answer) if answer else "（知识库暂无此内容，已记录待 HR 补充）\n")


# ---------- 企业微信发送 ----------

def wecom_send(emp: dict, content: str, mode: str = "stub") -> dict:
    """mode: stub(默认,离线) | webhook(群机器人,需 config.webhook_key)"""
    if mode == "webhook":
        cfg = json.loads(CONFIG_FILE.read_text("utf-8")) if CONFIG_FILE.exists() else {}
        key = cfg.get("wecom", {}).get("webhook_key", "")
        if not key:
            return {"ok": False, "err": "config.json 缺少 wecom.webhook_key"}
        payload = {"msgtype": "text", "text": {"content": content}}
        req = urllib.request.Request(
            f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    payload = {"touser": emp.get("userid"), "msgtype": "text", "text": {"content": content}}
    print(f"[企业微信·{mode}] -> {emp.get('name')}({emp.get('userid')}): {content}")
    return {"ok": True, "mode": mode, "payload": payload}


# ---------- 主入口 ----------

def main() -> int:
    parser = argparse.ArgumentParser(prog="eda", description="企业数字助理 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ask = sub.add_parser("ask", help="企业知识库制度问答")
    p_ask.add_argument("question")

    sub.add_parser("find", help="按姓名查员工").add_argument("name")
    sub.add_parser("dept", help="按部门列员工").add_argument("department")

    p_call = sub.add_parser("call", help="输出呼叫指令卡")
    p_call.add_argument("name")
    p_call.add_argument("--msg", default="请到前台")

    p_send = sub.add_parser("send", help="发企业微信消息")
    p_send.add_argument("name")
    p_send.add_argument("content")
    p_send.add_argument("--mode", default="stub", choices=["stub", "webhook"])

    p_onboard = sub.add_parser("onboard", help="新员工入职培训（交互）")
    p_onboard.add_argument("--name", default="新同事")

    p_intent = sub.add_parser("intent", help="意图解析")
    p_intent.add_argument("text")

    args = parser.parse_args()

    if args.cmd == "ask":
        kb = KnowledgeBase(); n = kb.load()
        answer = kb.answer(args.question)
        print(answer if answer else f"（知识库共 {n} 个分块，未命中；可把制度文档放入 knowledge/ 目录）")
    elif args.cmd == "find":
        emp = find_employee(args.name)
        if emp:
            print(json.dumps(emp, ensure_ascii=False, indent=2))
        else:
            print(f"通讯录未找到「{args.name}」")
    elif args.cmd == "dept":
        emps = [e for e in load_employees() if args.department in e.get("department", "")]
        print(json.dumps(emps, ensure_ascii=False, indent=2))
    elif args.cmd == "call":
        emp = find_employee(args.name)
        if not emp:
            print(f"通讯录未找到「{args.name}」"); return 1
        print(f"[CALL] target={emp['name']} userid={emp['userid']} ext={emp['ext']} "
              f"dept={emp['department']} msg={args.msg}")
    elif args.cmd == "send":
        emp = find_employee(args.name)
        if not emp:
            print(f"通讯录未找到「{args.name}」"); return 1
        result = wecom_send(emp, args.content, args.mode)
        print("ok" if result.get("ok") else f"failed: {result}")
    elif args.cmd == "onboard":
        run_onboarding(args.name)
    elif args.cmd == "intent":
        print(json.dumps(parse_intent(args.text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
