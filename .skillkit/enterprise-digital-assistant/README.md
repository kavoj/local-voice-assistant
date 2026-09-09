# 企业数字助理 Enterprise Digital Assistant

**企业大厅/办公室里的数字助理**：制度问答、呼叫员工、企业微信发消息、新员工入职培训。
可打包成 WorkBuddy 技能，也可在电脑上作为独立 CLI 使用。

## 两种安装方式

### 方式 A · 装成 WorkBuddy 技能（推荐）

```bash
# 从技能包源码目录执行（或已直接拷贝到 ~/.workbuddy/skills/ 则无需操作）
cd <技能包目录>
./scripts/install.sh          # 自动拷贝到 ~/.workbuddy/skills/enterprise-digital-assistant
```

装好后，在任意 WorkBuddy 会话里直接说人话触发：
- 「报销怎么走流程」「出差住宿标准」→ 制度问答（答案带出处）
- 「呼叫李华」「把张伟叫来前台」→ 呼叫员工（真机音箱未接时输出呼叫指令卡）
- 「给张伟发消息下午三点开会」→ 经 wecom 连接器真实发送企业微信
- 「我是王小明，办理入职」→ 分步入职培训，可随时提问

### 方式 B · 装成电脑 CLI 应用

```bash
./scripts/install.sh          # 同时会装 eda 到 ~/local/bin 并生成双击启动器
export PATH="$HOME/local/bin:$PATH"   # 或追加到 ~/.zshrc
eda ask "报销怎么走流程"
eda find 李华
eda call 李华 --msg "来前台一下"
eda send 张伟 "下午三点会议室过季度方案"
eda onboard --name 王小明
```

或直接双击根目录的 `企业数字助理.command` 打开交互菜单。

## 目录

```
enterprise-digital-assistant/
├── SKILL.md              # WorkBuddy 技能定义（触发词+工作流+红线）
├── README.md
├── scripts/
│   ├── eda.py            # 自包含 CLI（Python3 标准库，零依赖）
│   ├── install.sh        # 双通道安装
│   └── 企业数字助理.command  # 双击启动器（install 后生成）
├── knowledge/*.md        # 企业知识库（放制度文档，即换即用）
├── data/employees.json   # 员工名录（userid 需与企业微信一致）
└── config.example.json   # 企业微信 webhook 配置模板（可选）
```

## 依赖

- Python 3.9+（macOS 自带 python3）
- 真实发送企业微信：WorkBuddy 已连接 wecom 连接器，或提供群机器人 webhook key

## 与 local-voice-assistant 项目的关系

本技能包是该项目的**企业数字助理能力**的独立发行版——把知识库、名录、培训、消息路由
打成零依赖单文件（eda.py）随技能分发，项目本体演进时同步更新本包。

## 隐私

- 知识库/名录只在本机；语音与摄像头数据不采集。
- 发送任何企业微信前先向用户复述确认。
