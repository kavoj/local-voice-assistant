# 企业数字助理（Enterprise Agent）设计

对标参考：企业数字助理 Agent（Jarvis）总体架构——「听得懂 · 看得见 · 答得准 · 办得成 · 能协同」。
本项目沿用心智模型：**语音前端 + 仲裁状态机 + 可插拔大脑**，企业版把大脑升级为
`EnterpriseBrain`（意图路由 + Agent 技能集 + 企业知识库）。

## 能力映射（参考图 → 本项目实现）

| 参考图能力 | 本项目实现 | 状态 |
|-----------|-----------|------|
| 企业知识库 / RAG | `assistant/enterprise/knowledge.py` + `data/knowledge/`（文档摄取、分块、零依赖检索） | ✅ M-E1 |
| 员工信息库 | `data/enterprise/employees.json` + `directory.py`（按姓名找 userid/分机） | ✅ M-E1 |
| 通知/协作战能：呼叫员工 | `speaker.py` SpeakerController（console 桩；预留小爱/天猫精灵开放平台） | ✅ 桩 / M-E3 真机 |
| 通知/协作战能：发企业微信 | `wecom.py` WeComClient（stub / 群机器人 webhook / 自建应用 app 三模式） | ✅ 三模式 |
| HR 智能体：新员工入职培训 | `onboarding.py` 分步培训流程 + 知识库随时问答 | ✅ |
| 办公智能体：知识问答 | EnterpriseBrain 兜底走知识库检索，答案带出处 | ✅ |
| 意图理解 / 任务规划 | EnterpriseBrain 规则意图路由（零依赖），可替换为 LLM 意图分类 | ✅ |
| 记忆与上下文 | 沿用 brain.history + twin 行为数据管线（分身数据同步沉淀） | ✅ |

## 意图路由（EnterpriseBrain）

```
用户语音 → ASR 文本 → 意图规则匹配：
  1) 入职/培训    → OnboardingSkill（分步讲解，培训中可随时提问，走知识库）
  2) 呼叫 <姓名>  → SpeakerController.call_employee(名录查分机/userid)
  3) 给 <姓名> 发消息/通知 <内容> → WeComClient.send_text(userid, 内容)
  4) 其他         → KnowledgeBase.search(检索企业知识库) → 无命中则兜底话术
```

意图规则先用零依赖关键词+正则（可移植、可测试）；接 LLM 大脑后可无缝替换为
模型意图分类，技能层不变。

## 企业微信三种模式（config: enterprise.wecom.mode）

| 模式 | 用途 | 依赖 |
|------|------|------|
| `stub`（默认） | 演示/测试：只构造 payload 打印，不联网 | 无 |
| `webhook` | 群机器人：往企业微信群推送通知 | webhook key |
| `app` | 自建应用：按 userid 精准发给对应员工 | corpid + secret + agentid |

## 音箱呼叫（config: enterprise.speaker.provider）

- `console`（默认桩）：终端打印呼叫动作，验证流程
- 预留：小爱开放平台 / 天猫精灵精灵技能 / 自研 Linux 音箱（HTTP 接口）——实现
  `SpeakerController` 子类即可接入，技能层零改动

## 数据与隐私

- 员工名录、知识库均为本地文件（`data/` 内，不入 git）
- 通过企业微信发送的内容会进入公司通讯录体系，发送前在 `action_taken` 留痕，同步进 twin 行为数据
- 知识库答案强制带来源标注，避免 AI 幻觉冒充制度
