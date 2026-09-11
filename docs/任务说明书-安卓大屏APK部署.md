# 任务说明书 · 安卓大屏 APK 部署（企业数字助理）

> 交接文档：本文档自包含，按顺序执行即可完成。遇到问题先看 §8 常见坑，再联系老谢。
> 仓库：https://github.com/kavoj/local-voice-assistant （工程在 `android/` 目录）

---

## 1. 目标与成果物

把「企业数字助理」的可视化语音台（HUD）打包成安卓 APK，安装到**安卓大屏**（会议平板 / 广告机 / 触摸一体机，Android 7.0+），实现：

- 大屏全屏显示语音助手界面（待命光环 / 对话时间线 / 执行追踪卡）
- 触摸点选意图 + 按住麦克风说话（走系统语音识别）
- 与同网段电脑上的 Python 后端通信（知识库问答 / 呼叫员工 / 企业微信 / 入职培训）

**交付物清单（完成后回传）**
1. `app-debug.apk`（构建产物）
2. 大屏实拍照片或录屏 1 段（界面 + 一次完整语音问答）
3. 填写完毕的《验收清单》（§7）
4. 遇到的问题与解决记录（如有）

## 2. 方案说明（为什么这样做）

架构是「**薄壳 + 局域网后端**」：

```
安卓大屏 (APK, WebView 薄壳)          电脑 / 小主机 (Python 后端)
┌─────────────────────────┐   HTTP   ┌──────────────────────────┐
│ HUD 界面 + 系统 TTS/ASR  │ ───────> │ assistant/hud.py          │
│ config.json 指定后端地址 │  <────── │ 知识库·名录·企业微信·培训  │
└─────────────────────────┘   SSE    └──────────────────────────┘
```

- APK 只负责界面与语音采集播报（约 3–5MB），改知识库/逻辑只改电脑端，**不用重装 APK**
- 后端零依赖（纯 Python 标准库），任何能装 Python 3.9+ 的电脑都能跑
- `config.json` 里 `server_url` 留空 = 离线演示模式（不连后端也能展示界面和演示脚本）

## 3. 需要准备

| 项 | 要求 |
|---|---|
| 构建机 | macOS / Windows / Linux 任一，磁盘 ≥ 10GB 可用 |
| JDK | 17（必须 17，AGP 8.x 要求） |
| Android SDK | 通过命令行工具安装 platform 34 + build-tools |
| Gradle | 8.7+（建议生成 wrapper 后不再依赖本机版本） |
| 后端机 | 公司同网段任一电脑，Python 3.9+，Python 包 pyyaml |
| 大屏 | Android 7.0+，允许安装未知来源应用，横屏 |
| 网络 | 大屏与后端机同一局域网，端口 8765 可互通 |

## 4. 步骤一 · 构建机环境安装

### 4.1 JDK 17

```bash
# macOS（brew）
brew install --cask temurin@17
sudo ln -sfn /Library/Java/JavaVirtualMachines/temurin-17.jdk /Library/Java/JavaVirtualMachines/current
export JAVA_HOME=$(/usr/libexec/java_home -v 17)

# Windows（PowerShell，管理员）
winget install EclipseAdoptium.Temurin.17.JDK
# Linux (Ubuntu/Debian)
sudo apt install -y openjdk-17-jdk
```

验证：`java -version` 输出 17.x。

### 4.2 Android SDK 命令行工具

```bash
# macOS / Linux
mkdir -p ~/android-sdk/cmdline-tools
cd ~/android-sdk/cmdline-tools
# 下载地址以 https://developer.android.com/studio#command-line-tools-only 页面最新链接为准
curl -LO https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip
unzip commandlinetools-*.zip && mv cmdline-tools latest
export ANDROID_HOME=~/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH

# 接受许可并安装组件（约 1–2GB，需耐心）
yes | sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

Windows 同理：下载 `commandlinetools-win-*.zip`，解压后用 `sdkmanager.bat`，环境变量在「系统设置 → 环境变量」配 `ANDROID_HOME`。

### 4.3 Gradle 并生成 wrapper

```bash
brew install gradle          # macOS；Windows: choco install gradle 或官网下载解压
cd android/                  # 仓库里的 android 目录
gradle wrapper --gradle-version 8.7   # 生成 ./gradlew，以后构建不再依赖本机 gradle
```

## 5. 步骤二 · 构建 APK

```bash
cd android/
./gradlew assembleDebug          # Windows: gradlew.bat assembleDebug
# 成功后产物：
#   app/build/outputs/apk/debug/app-debug.apk
```

**换图标（可选）**：把 `ic_launcher.png`（192×192）放到
`app/src/main/res/mipmap-xxxhdpi/`，并把 Manifest 里
`android:icon="@android:drawable/sym_def_app_icon"` 改为 `@mipmap/ic_launcher`。
（本项目已备好形象设计图，见仓库 `assets/mascot/`，可用它裁切）

## 6. 步骤三 · 后端启动与大屏安装

### 6.1 电脑端启动后端

```bash
git clone https://github.com/kavoj/local-voice-assistant.git
cd local-voice-assistant
python3 -m venv .venv && source .venv/bin/activate
pip install pyyaml
python3 -m assistant.hud --host 0.0.0.0 --port 8765 --no-browser
# 记下这台电脑的局域网 IP（mac: ipconfig getifaddr en0；win: ipconfig）
```

> 防火墙需放行 8765 端口入站。

### 6.2 配置 APK 后端地址

编辑 `android/app/src/main/assets/config.json`，把 `server_url` 改为后端实际地址，
然后**重新构建一次**（§5）：

```json
{ "server_url": "http://192.168.1.100:8765/" }
```

### 6.3 安装到大屏

任选其一：
- **USB + adb**：大屏开开发者模式/USB调试 → `adb install app-debug.apk`
- **U 盘侧载**：拷 APK 进 U 盘 → 大屏文件管理器打开 → 允许「未知来源」→ 安装

装好后首次打开会弹麦克风权限，选**允许**。

### 6.4 验证联调

1. 大屏界面加载出三栏 HUD（左光环 / 中时间线 / 右追踪卡）
2. 点快捷意图「报销怎么走」→ 界面出现带《出处》的回答
3. 按住麦克风说话「呼叫李华」→ 大屏放语音 → 电脑端日志出现 `speaker.call` action
4. 电脑端发消息测试：`python3 scripts/eda.py send 张伟 "大屏联调测试"`

## 7. 验收清单（逐项打勾后回传）

- [ ] APK 安装成功，图标与名称「三五数字助理」正确
- [ ] 横屏全屏，无状态栏/导航栏，屏幕常亮不熄屏
- [ ] 大屏断电重启后自动进入助理界面（开机自启）
- [ ] 快捷意图点击有响应，回答带知识库出处
- [ ] 按住麦克风说话可识别中文并得到回答（走系统语音）
- [ ] 助手回答有语音播报（系统 TTS）
- [ ] 「呼叫员工」动作在电脑端日志留痕
- [ ] 大屏与后端机断网时，界面不崩溃（离线提示/演示模式）
- [ ] 连续运行 2 小时无闪退、无内存暴涨

## 8. 常见坑

| 现象 | 原因与解法 |
|---|---|
| 构建报 `Unsupported class file major version` | JDK 不是 17。`java -version` 确认，必要时切 JAVA_HOME |
| `SDK location not found` | 没设 `ANDROID_HOME`；或在 `android/` 下新建 `local.properties` 写 `sdk.dir=/Users/你/android-sdk` |
| 大屏打开白屏 | 后端没起 / IP 不通。大屏浏览器先试访问 `http://后端IP:8765`；防火墙放行 8765 |
| 大屏加载报「明文流量被禁」 | 本工程 Manifest 已开 `usesCleartextTraffic`，若仍报说明装的是旧包，重装 |
| 按说话无反应 | ① 麦克风权限未授予（系统设置里补）② 大屏是安卓 5/6 无系统识别服务 → 用界面点选交互，或联系老谢接第三方语音 SDK |
| 语音识别报错码 6/7/8 | 系统语音服务未安装（国产大屏常见）。文本输入可用，语音需接讯飞/百度 SDK——把这个现象记进回传问题清单 |
| adb 找不到设备 | 大屏设置里开「USB 调试」；部分广告机需在工程模式开 ADB |

## 9. 边界与注意事项

- 本壳**不含** Python 运行时：知识库、企业微信、员工数据全部在电脑端，大屏不做数据落盘
- `config.json` 里的地址如含敏感内网信息，构建包不要外传
- 正式对外分发需配 release 签名（`build.gradle` 里加 `signingConfigs`），当前 debug 包仅内部使用
- 完全单机版（Python 打进 APK、无需电脑）规划为下一里程碑，接口已预留

— 完 —
