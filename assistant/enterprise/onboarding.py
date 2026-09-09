# -*- coding: utf-8 -*-
"""新员工入职培训技能：分步讲解 + 培训中随时提问（走知识库）+ 进度记忆。"""
from __future__ import annotations

from typing import Optional

from .knowledge import KnowledgeBase

STEPS = [
    {"title": "欢迎入职", "content": "欢迎加入！我是企业数字助理。接下来我带你过一遍入职必修课，说「下一个」进入下一节，随时可以直接提问。"},
    {"title": "入职当天流程", "content": "入职当天：先到人力资源部找 HRBP 报到（李华，分机 8003），签合同和保密协议，领工牌门禁卡，IT 当天开通企业微信、邮箱和 OA 账号，然后回部门对接导师。"},
    {"title": "考勤制度", "content": "标准工时 9 点到 18 点，可在 8:30-9:30 弹性到岗。请假走企业微信审批：1 天内直属上级批，3 天内部门总监批，3 天以上要总经理批。每月有 2 次补卡机会。"},
    {"title": "报销流程", "content": "报销在 OA 财务模块提交，上传发票照片，审批链是直属上级→部门总监→财务复核，报销款随次月工资发。注意发票要在 90 天内、抬头必须是公司全称。"},
    {"title": "常用工具与支持", "content": "会议室在企业微信预约；电脑故障找 IT 值班；工资每月 10 日发放。有任何问题随时问我，或找 HRBP 李华（分机 8003）。培训完毕，祝你入职顺利！"},
]


class OnboardingSkill:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self.active = False
        self.newbie_name = ""
        self.step = 0

    def start(self, name: str = "") -> str:
        self.active = True
        self.newbie_name = name
        self.step = 0
        prefix = f"{name}，" if name else ""
        return f"{prefix}{STEPS[0]['content']}"

    def handle(self, text: str) -> Optional[str]:
        """培训进行中处理用户输入。返回回复；返回 None 表示未处于培训态。"""
        if not self.active:
            return None
        if any(word in text for word in ("下一个", "下一节", "继续")):
            self.step += 1
            if self.step >= len(STEPS):
                self.active = False
                return "培训全部完成！转正前记得完成导师评价和转正述职。需要再看任何制度随时问我。"
            return f"【第 {self.step + 1}/{len(STEPS)} 节 · {STEPS[self.step]['title']}】{STEPS[self.step]['content']}"
        if any(word in text for word in ("结束", "退出培训", "先这样")):
            self.active = False
            return f"好的，培训先到第 {self.step + 1} 节，进度我记住了，下次说「继续入职培训」接着来。"
        # 培训中的提问 → 知识库
        answer = self.kb.answer(text)
        if answer:
            return answer
        return "这个问题培训材料里没有现成答案，我记下来了，会同步给 HR 跟进。你可以先说「下一个」继续课程。"

    @property
    def progress(self) -> str:
        return f"{min(self.step + 1, len(STEPS))}/{len(STEPS)}"
