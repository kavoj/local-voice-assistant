# -*- coding: utf-8 -*-
"""企业数字助理大脑：意图路由 + Agent 技能集（知识问答/呼叫/发消息/入职培训）。

意图规则零依赖（关键词+正则），保证可移植可测试；接 LLM 后可替换为模型意图分类，
技能层（kb/onboarding/wecom/speaker）不变。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..brain.base import BaseBrain, BrainReply
from ..config import PROJECT_ROOT
from .directory import EmployeeDirectory
from .knowledge import KnowledgeBase
from .onboarding import OnboardingSkill
from .speaker import SpeakerController
from .wecom import WeComClient

_NAME = r"([\u4e00-\u9fa5]{2,4})"


class EnterpriseBrain(BaseBrain):
    name = "enterprise"

    def __init__(self, system_prompt: str = "", config: Optional[dict] = None):
        super().__init__(system_prompt, config)
        ent_cfg = config.get("enterprise", {}) if config else {}

        employees_path = Path(ent_cfg.get("employees_path", "data/enterprise/employees.json"))
        knowledge_dir = Path(ent_cfg.get("knowledge_dir", "data/knowledge"))
        if not employees_path.is_absolute():
            employees_path = PROJECT_ROOT / employees_path
        if not knowledge_dir.is_absolute():
            knowledge_dir = PROJECT_ROOT / knowledge_dir

        self.directory = EmployeeDirectory(employees_path)
        self.kb = KnowledgeBase(knowledge_dir)
        self.kb.load()
        self.onboarding = OnboardingSkill(self.kb)
        self.wecom = WeComClient(config or {})
        self.speaker = None  # 延迟注入（create_enterprise_brain 注入），便于测试替换

    # ---- 主入口 -----------------------------------------------------------

    def ask(self, text: str) -> BrainReply:
        stripped = text.strip()
        self.history.append({"role": "user", "content": stripped})

        # 0) 结束会话
        if any(word in stripped for word in ("再见", "拜拜", "退出", "先这样")):
            return self._emit("好，有事随时叫我，再见！", intent="session_end",
                              action="end_session", task_done=True)

        # 1) 培训进行中：交给 OnboardingSkill
        if self.onboarding.active:
            reply_text = self.onboarding.handle(stripped)
            if reply_text is not None:
                return self._emit(reply_text, intent="onboarding",
                                  action=f"onboarding.progress:{self.onboarding.progress}",
                                  task_done=True)
            # onboarding.handle 返回 None 说明已不在培训态，继续走正常路由

        # 1) 呼叫员工
        if re.search(r"(呼叫|打电话给|打电话找|call)", stripped, re.IGNORECASE):
            return self._route_call(stripped)

        # 2) 发企业微信消息
        if re.search(r"(发(?:个|条)?(?:消息|信息|微信)|通知)", stripped):
            return self._route_message(stripped)

        # 3) 入职培训
        if any(word in stripped for word in ("入职", "新员工培训", "培训")):
            name_match = re.search(rf"(?:我是|新员工)?{_NAME}(?:，|,)?(?:需要|想)?(?:办理)?入职", stripped)
            newbee = name_match.group(1) if name_match else ""
            reply_text = self.onboarding.start(newbee)
            return self._emit(reply_text, intent="onboarding", action="onboarding.start", task_done=True)

        # 4) 兜底：企业知识库问答
        answer = self.kb.answer(stripped)
        if answer:
            return self._emit(answer, intent="kb_qa", action="kb.search", task_done=True)

        return self._emit(
            "这个我不确定，先记下来同步给相应同事跟进。你也可以换个问法试试。",
            intent="unknown", action="fallback",
        )

    # ---- 路由实现 ----------------------------------------------------------

    def _extract_employee(self, text: str):
        """从文本中反查通讯录员工：全名包含匹配，比正则切人名可靠。"""
        for emp in self.directory.employees:
            if emp.name in text:
                return emp
        return None

    def _route_call(self, text: str) -> BrainReply:
        emp = self._extract_employee(text)
        if not emp:
            return self._emit("通讯录里没找到这个人，要我把 TA 加进名录吗？",
                              intent="call", action="call.not_found")
        if self.speaker is None:
            return self._emit("音箱还没接上，先记下这条呼叫请求。",
                              intent="call", action="call.no_speaker")
        result = self.speaker.call_employee(emp)
        return self._emit(
            f"好的，正在通过音箱呼叫{emp.name}（{emp.department}·分机 {emp.ext}），请稍等。",
            intent="call", action=f"speaker.call:{emp.userid}", task_done=bool(result.get("ok")),
        )

    _LEADING_VERB = re.compile(r"^(?:请|麻烦|帮我)?(?:给)?(?:TA|他|她)?(?:发(?:个|条)?(?:消息|信息|微信)|通知)+[：:，, ]*")

    def _route_message(self, text: str) -> BrainReply:
        emp = self._extract_employee(text)
        if not emp:
            return self._emit("通讯录里没找到收件人，请确认姓名后再说一遍。",
                              intent="wecom_send", action="wecom.not_found")
        # 收件人名字之后的文本即为内容
        content = text.split(emp.name, 1)[1].strip()
        content = self._LEADING_VERB.sub("", content).strip("，。, ：: ")
        if not content:
            return self._emit(f"要给{emp.name}发什么内容？说完我马上发。",
                              intent="wecom_send", action="wecom.pending_content")
        result = self.wecom.send_text(emp.userid, content)
        status = "已发出" if result.get("ok") else "发送失败"
        return self._emit(
            f"好，已通过企业微信给{emp.name}（{emp.department}）发消息：「{content}」，{status}。",
            intent="wecom_send", action=f"wecom.send_text:{emp.userid}({result.get('mode')})",
            task_done=bool(result.get("ok")),
        )

    # ---- 辅助 --------------------------------------------------------------

    def _emit(self, text: str, intent: str, action: str, task_done: bool = False) -> BrainReply:
        self.history.append({"role": "assistant", "content": text})
        return BrainReply(text=text, intent=intent, action_taken=action, task_done=task_done)
