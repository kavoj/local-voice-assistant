# -*- coding: utf-8 -*-
"""企业大脑与知识库单元测试（全部离线，stub 模式）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistant.config import load_config
from assistant.enterprise import (  # noqa: E402
    EnterpriseBrain, KnowledgeBase, create_speaker,
)
from assistant.enterprise.directory import EmployeeDirectory  # noqa: E402
from assistant.enterprise.speaker import ConsoleSpeaker  # noqa: E402
from assistant.enterprise.wecom import WeComClient  # noqa: E402


def make_brain() -> EnterpriseBrain:
    config = load_config()
    brain = EnterpriseBrain(config=config)
    brain.speaker = ConsoleSpeaker()
    return brain


class KnowledgeBaseTest(unittest.TestCase):
    def setUp(self):
        from assistant.config import PROJECT_ROOT
        self.kb = KnowledgeBase(PROJECT_ROOT / "data" / "knowledge")
        self.n = self.kb.load()

    def test_load_chunks(self):
        self.assertGreater(self.n, 10)  # 5 份种子文档应分出足够多块

    def test_search_baoxiao(self):
        hits = self.kb.search("报销怎么走流程")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["source"], "报销流程")

    def test_answer_kaoqin(self):
        answer = self.kb.answer("上班时间是几点 弹性打卡")
        self.assertIsNotNone(answer)
        self.assertIn("出处", answer)


class DirectoryTest(unittest.TestCase):
    def test_find_by_name(self):
        from assistant.config import PROJECT_ROOT
        d = EmployeeDirectory(PROJECT_ROOT / "data" / "enterprise" / "employees.json")
        emp = d.find("王小明")
        self.assertEqual(emp.userid, "wangxiaoming")
        self.assertEqual(emp.ext, "8002")
        self.assertIsNone(d.find("不存在的人"))


class EnterpriseBrainTest(unittest.TestCase):
    def setUp(self):
        self.brain = make_brain()

    def test_call_employee(self):
        reply = self.brain.ask("呼叫王小明")
        self.assertEqual(reply.intent, "call")
        self.assertTrue(reply.task_done)
        self.assertIn("8002", reply.text)
        self.assertIn("speaker.call:wangxiaoming", reply.action_taken)

    def test_call_not_found(self):
        reply = self.brain.ask("呼叫赵六")
        self.assertIn("没找到", reply.text)
        self.assertFalse(reply.task_done)

    def test_wecom_send(self):
        reply = self.brain.ask("给李华发消息明天上午十点面试一名候选人")
        self.assertEqual(reply.intent, "wecom_send")
        self.assertTrue(reply.task_done)
        self.assertIn("wecom.send_text:lihua", reply.action_taken)

    def test_wecom_notify_order(self):
        reply = self.brain.ask("通知张伟下午三点市场部例会取消")
        self.assertEqual(reply.intent, "wecom_send")
        self.assertIn("zhangwei", reply.action_taken)

    def test_wecom_payload_stub(self):
        client = WeComClient({"enterprise": {"wecom": {"mode": "stub"}}})
        result = client.send_text("lihua", "测试内容")
        self.assertTrue(result["ok"])
        self.assertEqual(result["payload"]["touser"], "lihua")
        self.assertEqual(result["payload"]["text"]["content"], "测试内容")

    def test_onboarding_flow(self):
        r1 = self.brain.ask("我是王小明，需要办理入职")
        self.assertEqual(r1.intent, "onboarding")
        self.assertIn("王小明", r1.text)
        r2 = self.brain.ask("下一个")
        self.assertIn("入职当天流程", r2.text)
        self.assertIn("onboarding.progress", r2.action_taken)
        # 培训中提问走知识库
        r3 = self.brain.ask("差旅住宿标准是多少")
        self.assertEqual(r3.intent, "onboarding")
        self.assertIn("出处", r3.text)
        r4 = self.brain.ask("下一个")
        r5 = self.brain.ask("下一个")
        r6 = self.brain.ask("下一个")
        r7 = self.brain.ask("下一个")  # 走完 5 节
        self.assertIn("培训全部完成", r7.text)

    def test_kb_qa_fallback(self):
        reply = self.brain.ask("会议室怎么预定")
        self.assertEqual(reply.intent, "kb_qa")
        self.assertTrue(reply.task_done)

    def test_unknown_fallback(self):
        reply = self.brain.ask("量子力学的薛定谔方程是什么")
        self.assertEqual(reply.intent, "unknown")


class SpeakerTest(unittest.TestCase):
    def test_console_speaker_result(self):
        from assistant.config import PROJECT_ROOT
        d = EmployeeDirectory(PROJECT_ROOT / "data" / "enterprise" / "employees.json")
        speaker = create_speaker({"enterprise": {"speaker": {"provider": "console"}}})
        result = speaker.call_employee(d.find("张伟"), from_person="laosie")
        self.assertTrue(result["ok"])
        self.assertEqual(result["target"]["ext"], "8004")


if __name__ == "__main__":
    unittest.main()
