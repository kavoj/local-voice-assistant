# -*- coding: utf-8 -*-
"""本地语音助手入口。

用法：
  python -m assistant.main --mode console
    无硬件端到端演示：输入唤醒词「嘿阿鹭」开始会话；会话中直接键入要说的话；
    输入 exit / 退出 结束会话；会话外输入 q 退出程序。

  python -m assistant.main --mode demo
    全自动演示：模拟「摄像头看到人 → 主动问候 → 两轮对话 → 冷却 → 再次看到人被节流」，
    用于验证状态机与数据采集，不需要任何输入。
  python -m assistant.main --mode enterprise
    企业数字助理演示：新员工办理入职培训 → 知识问答 → 音箱呼叫员工 →
    企业微信发消息，全链路自动走一遍（企业微信/音箱为 stub 离线模式）。
"""
from __future__ import annotations

import argparse
import sys
import time

from .brain import create_brain
from .config import load_config
from .state_machine import Event, StateMachine
from .twin.recorder import TwinRecorder
from .voice import create_tts

WAKE_KEYWORD = "嘿阿鹭"
EXIT_WORDS = {"exit", "quit", "退出", "再见", "拜拜"}


def _run_conversation(brain, recorder: TwinRecorder, tts, greeting: str,
                      trigger: str, person_id: str, get_user_text) -> None:
    """一次完整会话：问候 → 多轮 → 结束。get_user_text() 返回用户输入，None 表示超时/结束。"""
    brain.start_session()
    recorder.begin_session(trigger=trigger, person_id=person_id)
    tts.speak(greeting)
    recorder.record_turn("assistant", greeting, intent="greeting", task_done=True,
                         trigger=trigger, person_id=person_id)

    while True:
        user_text = get_user_text()
        if user_text is None:
            break
        recorder.record_turn("user", user_text, trigger=trigger, person_id=person_id)
        reply = brain.ask(user_text)
        tts.speak(reply.text)
        recorder.record_turn(
            "assistant", reply.text, intent=reply.intent,
            action_taken=reply.action_taken, task_done=reply.task_done,
            trigger=trigger, person_id=person_id,
        )
        if reply.intent == "session_end":
            break

    recorder.end_session()
    brain.end_session()


def run_console(config: dict) -> None:
    tts = create_tts(config)
    brain = create_brain(config)
    recorder = TwinRecorder(config, consent=True)
    sm = StateMachine(cooldown_seconds=config["twin"].get("cooldown_seconds", 300))
    name = config["app"].get("name", "助手")

    print(f"== {name} console 模式 ==")
    print(f"输入「{WAKE_KEYWORD}」唤醒；会话中直接说话；exit 结束会话；q 退出程序。")

    while True:
        try:
            line = input(f"[待命] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.lower() == "q":
            break
        if not line:
            continue

        if WAKE_KEYWORD in line:
            result = sm.handle_event(Event.WAKE_WORD, person_id="laosie")
        else:
            print("（未唤醒。试试先说唤醒词。）")
            continue

        if result["action"] != "start_session":
            print(f"（忽略：{result['reason']}）")
            continue

        session = result["session"]

        def get_user_text():
            try:
                text = input("[对话] > ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if not text:
                return None
            if text.lower() in EXIT_WORDS or text in EXIT_WORDS:
                return text
            return text

        _run_conversation(brain, recorder, tts, result["greeting"],
                          trigger="wake_word", person_id=session.person_id,
                          get_user_text=get_user_text)
        sm.handle_event(Event.SESSION_END)

    print(" Bye. 行为数据已落盘 data/sessions/，用 python -m assistant.twin.export 导出训练集。")


def run_demo(config: dict) -> None:
    """全自动演示：主动交互 + 冷却节流 + 数据采集全链路。"""
    tts = create_tts(config)
    brain = create_brain(config)
    recorder = TwinRecorder(config, consent=True)
    sm = StateMachine(cooldown_seconds=300)

    print("== 演示：摄像头识别到人，助手主动搭话 ==")
    result = sm.handle_event(Event.PERSON_DETECTED, person_id="laosie")
    session = result["session"]

    demo_inputs = iter(["帮我看看今天有什么安排", "顺便记一下明天十点跟信泰开会", "再见"])

    def get_user_text():
        time.sleep(0.2)
        text = next(demo_inputs, None)
        if text is None:
            return None
        print(f"[对话] > {text}")
        return text

    _run_conversation(brain, recorder, tts, result["greeting"],
                      trigger="person_detected", person_id=session.person_id,
                      get_user_text=get_user_text)
    sm.handle_event(Event.SESSION_END)

    print("\n== 演示：5 分钟冷却期内再次识别到同一人 → 节流忽略 ==")
    result = sm.handle_event(Event.PERSON_DETECTED, person_id="laosie")
    print(f"仲裁结果: {result}")

    print("\n== 演示结束。查看行为数据：data/sessions/，导出训练集：python -m assistant.twin.export --date today ==")


def run_enterprise_demo(config: dict) -> None:
    """企业数字助理演示：入职培训 / 知识问答 / 音箱呼叫 / 企业微信发消息。"""
    from .enterprise import create_enterprise_brain

    tts = create_tts(config)
    brain = create_enterprise_brain(config, system_prompt=config["brain"].get("system_prompt", ""))
    recorder = TwinRecorder(config, consent=True)
    sm = StateMachine(cooldown_seconds=config["twin"].get("cooldown_seconds", 300))

    # 前台场景：摄像头识别到新员工走进大厅
    result = sm.handle_event(Event.PERSON_DETECTED, person_id="guest_wang")
    session = result["session"]

    script = iter([
        "我是王小明，需要办理入职",          # → 入职培训
        "下一个",                            # → 下一节
        "差旅住宿标准是多少",                # → 培训中提问，走知识库
        "下一个", "下一个", "下一个", "下一个",
        "报销怎么走流程",                    # → 知识问答
        "呼叫李华",                          # → 音箱呼叫
        "给张伟发消息下午三点会议室过一下季度方案",  # → 企业微信
        "再见",
    ])

    def get_user_text():
        time.sleep(0.15)
        text = next(script, None)
        if text is None:
            return None
        print(f"[对话] > {text}")
        return text

    brain.start_session()
    recorder.begin_session(trigger="person_detected", person_id=session.person_id)
    tts.speak(result["greeting"])
    recorder.record_turn("assistant", result["greeting"], intent="greeting",
                         task_done=True, trigger="person_detected", person_id=session.person_id)
    while True:
        user_text = get_user_text()
        if user_text is None:
            break
        recorder.record_turn("user", user_text, trigger="person_detected",
                             person_id=session.person_id)
        reply = brain.ask(user_text)
        tts.speak(reply.text)
        recorder.record_turn("assistant", reply.text, intent=reply.intent,
                             action_taken=reply.action_taken, task_done=reply.task_done,
                             trigger="person_detected", person_id=session.person_id)
        if reply.intent == "session_end":
            break
    recorder.end_session()
    sm.handle_event(Event.SESSION_END)

    print("\n== 本轮意图与动作留痕（同步沉淀进数字分身数据）==")
    for record_type in ("turn",):
        pass
    for line in open(sorted(recorder.sessions_dir.glob("*.jsonl"))[-1], encoding="utf-8"):
        obj = __import__("json").loads(line)
        if obj.get("speaker") == "assistant" and obj.get("action_taken"):
            print(f"  [{obj['intent']}] {obj['action_taken']}  done={obj['task_done']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="本地语音助手")
    parser.add_argument("--mode", default=None, choices=["console", "demo", "enterprise"],
                        help="运行模式，默认取配置文件 app.mode")
    args = parser.parse_args()

    config = load_config()
    mode = args.mode or config["app"].get("mode", "console")
    if mode == "demo":
        run_demo(config)
    elif mode == "enterprise":
        run_enterprise_demo(config)
    else:
        run_console(config)


if __name__ == "__main__":
    sys.exit(main())
