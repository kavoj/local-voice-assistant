# 本地语音助手 · Local Voice Assistant

一个**可移植、可复刻**的本地语音助手项目：通过「唤醒词 / 摄像头识别到人」主动发起语音交互，
通过对话帮人完成日常工作，并在对话过程中沉淀**数字分身行为数据**（对话记录、任务执行、偏好习惯），
用于后续训练属于你自己的数字分身。

> 架构思路：**语音前端 + 大脑分层解耦**。本项目是语音前端 + 可插拔大脑接口；
> 大脑可以是内置回声大脑（离线可测），也可以对接 WorkBuddy 会话 / 任意 LLM。

## 快速开始（Windows / macOS / Linux 一键部署）

**要求：仅 Python 3.9+（可到 python.org 安装）。** 项目零第三方运行时依赖，向导全自动：

```bash
git clone https://github.com/kavoj/local-voice-assistant.git
cd local-voice-assistant

# macOS / Linux
./scripts/setup.sh                  # 交互引导：环境→依赖→配置→(可选)Obsidian 对接→试运行

# Windows（PowerShell）
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

向导会引导你完成：① 环境检测与虚拟环境 ② 依赖安装 ③ 生成配置
④ **（可选）对接 Obsidian 本地知识库**（详见 `docs/obsidian-guide.md`）⑤ 试运行验证。

安装完成后：

```bash
python -m assistant.main --mode console      # 打字对话（零硬件可跑）
python -m assistant.main --mode enterprise   # 企业数字助理全链路演示
EDA_TTS_REAL=1 python -m assistant.main --mode console   # 助手用系统语音开口说话（语音入门，见 docs/voice.md）
```

## 🎛 可视化语音台：一条命令跑起来（推荐先试这个）

把整个企业数字助理装进**浏览器界面**：状态光环 + 实时字幕 + 对话时间线 + 执行追踪，
麦克风按钮用浏览器原生中文语音识别（Chrome/Edge，无需任何额外依赖），回复自动朗读：

```bash
# macOS / Linux
./scripts/run.sh            # 首次自动建 .venv 装依赖 → 启动 → 自动打开浏览器

# Windows
scripts\run.bat

# 想看界面自动演示效果（录屏/验收用）
./scripts/run.sh --demo
```

打开后：**按住 🎙 说话**（或按住空格、或点左侧示例、或输入文字回车）——
「我是王小明，办理入职」「报销怎么走流程」「呼叫李华」「给张伟发消息下午三点开会」。
真实语音链路零安装依赖；交互界面即 `web/hud.html`，`file://` 直接双击也能看设计预览。

## 🖥 语音调度局域网电脑（节点代理）

在被控电脑上启动节点代理，就能用语音控制局域网内的机器：

```bash
# 被控电脑（mac/win/linux 通用，零依赖）
python -m assistant.remote.agent --port 8766 --token sanwu-demo
# 关机/重启指令默认拒绝；加 --allow-shutdown 才放开
```

主控机在 `data/enterprise/devices.json` 登记设备（name/aliases/host/port/token），然后对话：

- 「让会议室电脑锁屏」「让会议室电脑截图」「让会议室电脑播报：三点开会」
- 「让会议室电脑打开 http://…」「让会议室电脑执行脚本 probe.sh」「会议室电脑状态怎么样」
- 安全设计：token 鉴权、指令白名单、exec_script 仅限节点 `~/.eda-agent/scripts/` 白名单后缀、关机需显式开启

## 🎭 助理形象替换

新形象图覆盖 `assets/mascot/current.png`（支持 png/jpg/webp/gif），重启服务即换——
HUD 光环中心与安卓大屏 APK 同步生效，零代码改动（配置项 `hud.mascot_path`）。参考形象见 `assets/mascot/`。

## 📦 演示设备部署包（Windows / macOS 压缩包）

一条命令打出两个「拷走即用」的压缩包（含源码+种子数据+双击启动器+部署 README+形象图）：

```bash
python3 scripts/package_release.py          # 产出 dist/eda-voice-assistant-{macos,windows}.zip
```

macOS 解压双击 `启动语音助手.command`；Windows 先 `安装环境.bat` 再 `启动语音助手.bat`。
节点代理启动器同理（`启动节点代理.*`）。安卓大屏版见 `docs/任务说明书-安卓大屏APK部署.md`。

## 三份必读文档

| 文档 | 内容 |
|------|------|
| `docs/voice.md` | **语音对话怎么实现**：零依赖开口 → whisper.cpp 流式 → 唤醒词+FunASR+edge-tts 三档落地 |
| `docs/obsidian-guide.md` | **Obsidian 本地知识库联动**：库目录即助手知识库，Obsidian 编辑即换即用 |
| `docs/enterprise-agent.md` | 企业数字助理（知识库/呼叫/企业微信/培训）能力设计 |
| `docs/architecture.md` | 分层架构与状态机设计 |
| `docs/digital-twin-data.md` | 数字分身数据采集与训练集规范 |

## 项目特性

- **可移植**：全部路径相对项目根目录，配置驱动（`config/settings.yaml`），零硬件也可运行（console 模式）
- **可复刻**：`git clone` + `pip install` + 一条命令即可在任意 Mac/Linux 上复现
- **主动交互**：状态机仲裁（待命 → 感知触发 → 主动问候 → 多轮对话 → 冷却），带冷却节流与防打扰
- **数字分身数据管线**：对话/行为数据本地 JSONL 落盘 → 清洗 → 导出微调训练集，知情同意开关内置

## 企业数字助理（对标 Jarvis 架构）

在个人助手之上，项目已扩展出**企业数字助理**形态（详见 `docs/enterprise-agent.md`）：

- **企业知识库**：`data/knowledge/` 放 markdown 制度文档（入职指南/考勤/报销/FAQ…），
  自动摄取分块，对话即答且**答案带出处**，零依赖全本地检索
- **音箱呼叫员工**：对话说「呼叫李华」→ 查员工名录 → 控制音箱呼叫（console 桩，预留小爱/天猫精灵/自研音箱）
- **语音调企业微信**：「给张伟发消息下午三点开会」→ 按 userid 精准发送
  （`stub` 离线演示 / `webhook` 群机器人 / `app` 自建应用三模式，凭证走配置）
- **新员工入职培训**：分步培训流程，培训中随时提问自动转知识库，进度可记忆

```bash
python -m assistant.main --mode enterprise   # 企业版全链路演示
```

### 一键打包为 WorkBuddy 技能 / 电脑 CLI

企业数字助理能力已封装为**独立技能包**（`local-voice-assistant/.skillkit/enterprise-digital-assistant/`），
可双通道安装：

```bash
cd local-voice-assistant/.skillkit/enterprise-digital-assistant
./scripts/install.sh   # ① 装入 ~/.workbuddy/skills/（WorkBuddy 新会话即触发）
                       # ② eda 命令进 ~/local/bin（终端即用）
                       # ③ 生成「企业数字助理.command」双击启动器
```

技能包自带零依赖 `eda.py` CLI 与知识库/名录资产，详见包内 README。

## 目录结构

```
local-voice-assistant/
├── README.md
├── docs/
│   ├── architecture.md        # 分层架构与状态机设计
│   ├── enterprise-agent.md    # 企业数字助理（知识库/呼叫/企业微信/培训）
│   ├── obsidian-guide.md      # Obsidian 本地知识库联动指南
│   ├── voice.md               # 语音对话三档落地指南
│   └── digital-twin-data.md   # 数字分身数据采集与训练集规范
├── config/
│   └── settings.example.yaml  # 配置模板（复制为 settings.yaml 使用）
├── assistant/
│   ├── main.py                # 守护进程入口（console / demo / enterprise）
│   ├── hud.py                 # HUD 可视化语音台（SSE 事件总线 + /ask + 自动演示，零依赖）
│   ├── config.py              # 配置加载
│   ├── state_machine.py       # 触发仲裁状态机
│   ├── brain/                 # 大脑接口 + 实现（echo / enterprise / workbuddy 预留）
│   ├── enterprise/            # 企业数字助理：知识库/名录/培训/企业微信/音箱
│   ├── sensing/ · voice/      # 感知与语音适配器（接口+桩，含 TTS 真人发声开关）
│   └── twin/                  # 数字分身：schema / recorder / export
├── web/
│   └── hud.html               # HUD 界面（单文件：光环/字幕/时间线/执行追踪/麦克风）
├── data/
│   ├── knowledge/             # 种子制度文档（markdown）
│   ├── enterprise/            # 员工名录样例
│   ├── sessions/ · datasets/  # 行为数据（JSONL，不入库 git）
├── scripts/
│   ├── setup.sh · setup.ps1   # macOS/Linux/Windows 一键部署入口
│   ├── quickstart.py          # 跨平台引导向导（环境→依赖→配置→Obsidian→试运行）
│   ├── run.sh · run.bat       # 🎛 一条命令启动可视化语音台
│   └── run_console.sh
├── tests/                     # 单元测试（21 项）
└── requirements.txt
```

## 快速开始

```bash
# 1. 进入项目目录
cd local-voice-assistant

# 2. 创建虚拟环境并安装依赖（也可用 scripts/setup.sh）
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. 生成配置
cp config/settings.example.yaml config/settings.yaml

# 4. 跑测试
python -m unittest discover -s tests -v

# 5. console 模式端到端演示（无需麦克风/摄像头）
python -m assistant.main --mode console

# 在对话中输入任意文字，输入 exit 退出；
# 退出后 data/sessions/ 会留下行为数据，运行下面命令导出训练集：
python -m assistant.twin.export --date today
```

## 对接真实硬件 / WorkBuddy

各模块均为**接口 + 桩实现**，按以下顺序替换即可升级为真机版：

| 模块 | 桩实现（默认） | 生产选型建议 |
|------|----------------|--------------|
| 唤醒词 | `sensing/wake_word.py` ConsoleWakeWord | Porcupine（自定义「嘿阿鹭」）/ openWakeWord |
| 视觉感知 | `sensing/vision.py` ConsoleVision | YOLOv8n 人形 + InsightFace 人脸（本地推理） |
| ASR | `voice/asr.py` ConsoleASR | FunASR/Paraformer（中文优先）或 Whisper |
| TTS | `voice/tts.py` ConsoleTTS | edge-tts（免费）或 CosyVoice（本地） |
| 大脑 | `brain/echo_brain.py` EchoBrain | `brain/workbuddy_brain.py` 对接 WorkBuddy 会话/MCP |

对接 WorkBuddy：实现 `workbuddy_brain.py` 中的 `WorkBuddyBrain`，把 ASR 转写文本送入
WorkBuddy 会话、取回回复交 TTS 播报。长期记忆沿用 WorkBuddy 的记忆体系。

## 数字分身数据（核心差异化）

对话即数据。每一轮交互按统一 schema 记录（见 `docs/digital-twin-data.md`）：
**用户说了什么、助手做了什么、任务是否完成、用户的偏好表达**。
数据 100% 本地存储（`data/sessions/`），经 `assistant.twin.export` 清洗、去重、脱敏后
导出为标准 JSONL 微调数据集，用于训练「像你一样接活」的数字分身。

**知情同意开关**内置在配置中（`twin.consent_required`），默认开启——没有明确同意不采集。

## 隐私红线

- 摄像头画面仅本地推理，不留存、不外传
- 人脸特征仅本地存储，陌生人只问候不识别
- 行为数据默认本地落盘，导出前必须经过脱敏检查
- 家人/同事进入感知范围前，需提前告知并获得同意

## 路线图

- [x] M0 项目骨架 + 状态机 + echo 大脑
- [x] M-E1 企业版：知识库 + 员工名录 + 意图路由大脑 + 入职培训 + 企业微信/音箱适配器
- [x] M-H1 HUD 可视化语音台：一条命令启动 + 浏览器语音对话界面（光环/字幕/动作追踪/知情同意）
- [x] M-R1 可分发：三平台一键部署向导 + Obsidian 知识库联动 + 语音落地指南 + 企业数字助理技能包
- [ ] M1 真机听觉闭环：Porcupine 唤醒词 + FunASR + edge-tts
- [ ] M2 对接 WorkBuddy 大脑（会话上下文 + 记忆 + 工具执行）
- [ ] M-E2 企业微信 app 模式真实凭证接入 + 群通知广播
- [ ] M3 视觉主动交互：人形/人脸检测 + 主动问候 + 冷却节流
- [ ] M-E3 音箱真机接入（开放平台/HTTP）
- [ ] M4 数字分身训练管线：数据积累 → 导出 → 微调 → 分身上岗

## License

MIT © Xie Peijie（谢培杰）
