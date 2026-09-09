# 数字分身行为数据：采集与训练集规范

## 目标

让助手在「帮人干活」的同时，把**这个人如何干活**沉淀为结构化数据：
说话风格、任务模式、决策偏好、常用工具与联系人——最终训练出一个行为风格一致的数字分身。

## 数据 schema（assistant/twin/schema.py）

### TurnRecord（每轮对话）

| 字段 | 类型 | 说明 |
|------|------|------|
| ts | str | ISO 8601 时间戳 |
| session_id | str | 会话 ID |
| speaker | str | `user` / `assistant` |
| text | str | 转写文本（assistant 侧为最终回复） |
| trigger | str | 该会话触发方式：`wake_word` / `person_detected` |
| intent | str | 意图标签（可由大脑标注：日程/查询/消息/闲聊…） |
| action_taken | str | 大脑执行的动作摘要（工具调用、文件读写等） |
| task_done | bool | 该轮任务是否完成 |
| person_id | str | 触发者身份（本地人脸 ID，陌生人记 `unknown`） |

### SessionRecord（每会话）

会话级摘要：起止时间、触发方式、轮数、完成任务数、涉及的意图分布。

## 落盘方式

- 路径：`data/sessions/YYYY-MM-DD.jsonl`（每日一个文件，追加写）
- 格式：每行一个 JSON 对象（TurnRecord 或 SessionRecord，以 `record_type` 区分）
- 权限：`data/sessions/` 在 `.gitignore` 中，永不入库

## 导出训练集（assistant/twin.export）

```bash
python -m assistant.twin.export --date today          # 导出今天
python -m assistant.twin.export --date 2026-09-01     # 导出指定日期
python -m assistant.twin.export --all                 # 导出全部
```

导出流程：
1. **过滤**：丢弃 `task_done=false` 且无教学价值的轮次；丢弃过短无意义文本
2. **去重**：相同 (instruction, response) 去重
3. **脱敏**：按配置 `twin.redact_patterns` 正则替换手机号/邮箱/身份证等
4. **格式**：输出 OpenAI/LLaMA 微调通用的 messages JSONL：

```json
{"messages": [
  {"role": "system", "content": "你是<用户>的数字分身，语言风格与决策习惯与其一致。"},
  {"role": "user", "content": "<用户原话>"},
  {"role": "assistant", "content": "<助手当时的高质量回复>"}
]}
```

输出到 `data/datasets/twin-YYYYMMDD.jsonl`。

## 数据质量原则

- 宁缺毋滥：只导出用户当时认可/任务成功的轮次，垃圾数据会教坏分身
- 隐私优先：`twin.consent_required` 默认 `true`，未同意不采集；导出前必过脱敏
- 本地闭环：采集、存储、导出、训练全流程可离线完成
