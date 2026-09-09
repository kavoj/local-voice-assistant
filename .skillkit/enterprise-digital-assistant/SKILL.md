---
name: enterprise-digital-assistant
description: >-
  企业数字助理（Enterprise Digital Assistant）：企业知识库制度问答、呼叫员工（音箱/分机）、
  给员工发企业微信消息、新员工入职培训、员工名录查询。当用户说出「呼叫/找一下员工」「给 X 发消息/发企业微信/通知 X」「新员工入职/办理入职/入职培训」「报销怎么走/考勤/请假/差旅标准/会议室怎么订/公司制度」等企业办公场景指令时使用。
  全部能力可离线运行（eda CLI），真实发送企业微信可对接 wecom 连接器（wecomcli-message）实现送达。
version: 1.0.0
agent_created: true
license: MIT
---

# 企业数字助理 Enterprise Digital Assistant

企业大厅/办公室里的语音数字助理能力包：**听得懂一句人话 → 查知识库 / 呼叫员工 / 调企业微信发消息 / 带新人培训**。
技能包自带本地知识库与员工名录，可离线运行；接上企业微信连接器即真实送达。

## 触发场景 → 动作

| 用户说（示例） | 意图 | 执行动作 |
|---|---|---|
| 「报销怎么走流程」「考勤迟到几次算」「出差住宿标准」 | 制度问答 | `eda ask "<问题>"`（本地知识库，答案带出处） |
| 「呼叫李华」「把王经理叫来」 | 呼叫员工 | `eda find 李华` 定位 → 输出呼叫指令（真机音箱未接时给呼叫卡片） |
| 「给张伟发消息下午三点开会」「通知全体员工明天停电」 | 发企业微信 | 走 **wecom 连接器**真实发送（见下）；未授权则 `eda send` stub |
| 「我是王小明，办理入职」「入职培训」 | 入职培训 | `eda onboard` 按 5 节必修课讲解，培训中提问转知识库 |
| 「李华是哪个部门的」「研发部有谁」 | 名录查询 | `eda find 李华` / `eda dept 研发` |

## 快速开始（eda CLI）

技能目录即 `{skill_dir}`（本 SKILL.md 所在文件夹）：

```bash
cd {skill_dir}

# 制度问答
python3 scripts/eda.py ask "报销怎么走流程"

# 名录定位（呼叫前先找人）
python3 scripts/eda.py find 李华

# 新员工入职培训（交互式，逐节讲解；Ctrl+C 退出）
python3 scripts/eda.py onboard --name 王小明

# 发送企业微信（stub 模式离线验证 payload；真发见下节）
python3 scripts/eda.py send 张伟 "下午三点会议室过季度方案"
```

## 真实发送企业微信（优先用连接器）

1. 若用户已授权 **wecom 连接器**（wecomcli-message）：按该连接器技能流程发送，
   userid 从 `eda find <姓名>` 或企业微信通讯录获取；
2. 未授权/离线环境：`eda send <姓名> "<内容>"` 以 stub 模式输出待发 payload，
   并提示用户「已准备好，接入企业微信后即可送达」。

## 呼叫员工（音箱/分机）

真机音箱未接入时，执行 `eda find <姓名>` 后以固定格式输出呼叫指令：

```
[CALL] target=张伟 userid=zhangwei ext=8004 dept=市场部 msg=请到前台
```

接入音箱厂商开放平台（小爱/天猫精灵/自研 HTTP 音箱）后，由平台侧把该指令转为真实呼叫。

## 知识库维护（即换即用）

- 目录 `knowledge/` 下放 markdown/txt，命名即主题（如 `报销流程.md`），
  重启即生效，无需任何配置——把公司制度文档丢进来即可。
- 答案强制标注出处《文件名·小节》，防止 AI 幻觉冒充制度。

## 员工名录维护

- 编辑 `data/employees.json`：`name / userid / department / title / ext / role`。
- userid 必须与企业微信通讯录一致，否则真实发送会失败。

## 隐私红线（必须遵守）

- 员工名录、知识库仅本地使用；摄像头/语音数据不采集、不上传。
- 发送企业微信前，把内容向用户复述一遍并得到确认（重要/群发尤其如此）。
- 涉及薪资、合同等敏感制度，若知识库未收录，明确回答「知识库没有」，不编造。
