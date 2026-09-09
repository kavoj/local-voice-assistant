# 语音对话：从文字到真人口语，三档落地

## 架构回顾：语音 = 耳朵(ASR) + 嘴(TTS)，大脑不变

```
麦克风 ──唤醒词/VAD──▶ ASR 转写(耳朵) ──文本──▶ EnterpriseBrain(大脑) ──回复──▶ TTS 播报(嘴) ──▶ 音箱
```

console 模式就是这条链路的**纯文本版**：你打字 = ASR 结果，终端打印 = TTS 结果。
所以「实现语音对话效果」= 把两个桩（`assistant/voice/` 里的 ASR/TTS）换成真实现，
大脑与整套技能（知识库/呼叫/企业微信/培训）一行都不用改。

## 档位 0 · 最快听声（1 分钟，零依赖）——助手先会"说话"

系统自带语音即可让助手开口（TTS 真机开关已内置）：

```bash
# macOS / Windows / Linux 通用：
EDA_TTS_REAL=1 python -m assistant.main --mode console   # 回复将真人朗读
# macOS 中文音色默认 Tingting；Windows 用系统 SAPI 中文语音
```

输入仍靠打字——这是"先让嘴动起来"，验证对话节奏与话术。

## 档位 1 · 最省事的真语音（建议先跑这条）——Whisper 命令行流式转写

用 [whisper.cpp](https://github.com/ggerganov/whisper.cpp)（单二进制，Windows/macOS/Linux 都有 release），
`stream` 工具实时把麦克风语音转成文本行，**把文本行直接喂给本项目 console**：

```bash
# 1) 下载 whisper.cpp release + 中文小模型(ggml-base/medium)
# 2) 流式转写并进入本项目会话
./stream -m ggml-base.bin -l zh -t 4 | EDA_TTS_REAL=1 python -m assistant.main --mode console
```

- 优点：不需要 Python 音频依赖、跨平台、实时；`-l zh` 识别中文
- 缺点：唤醒词需手动（或让 stream 常驻 + 本项目状态机监听）

## 档位 2 · 产品级闭环（M1 路线）——唤醒词 + 本地 ASR + 自然 TTS

按项目预留的适配器接口实现即可，配置切换提供方，其余零改动：

```yaml
# config/settings.yaml
voice:
  asr:  { provider: "funasr", model: "paraformer-zh" }   # 或 whisper
  tts:  { provider: "edge-tts", voice: "zh-CN-XiaoxiaoNeural" }  # 或 cosyvoice(离线)
sensing:
  wake_word: { provider: "porcupine", keyword: "嘿阿鹭" }
```

### 需要补的两个适配器（模板）

```python
# assistant/voice/__init__.py 中注册后的实现示意
class FunASRASR(BaseASR):
    """耳：FunASR Paraformer 中文实时识别（pip install funasr modelscope）"""
    def __init__(self):
        from funasr import AutoModel
        self.model = AutoModel(model="paraformer-zh", vad_model="fsmn-vad")

    def transcribe(self, audio) -> str:
        return self.model.generate(input=audio, batch_size_s=60)[0]["text"]


class EdgeTTS(BaseTTS):
    """嘴：微软 Edge 免费语音（pip install edge-tts；需联网）"""
    def __init__(self, voice="zh-CN-XiaoxiaoNeural"):
        import edge_tts
        self.voice = voice

    def speak(self, text: str) -> None:
        import asyncio, edge_tts
        asyncio.run(edge_tts.Communicate(text, self.voice).save("reply.mp3"))
        # 随后调用系统播放器播报 reply.mp3（macOS: afplay，Windows: start，Linux: aplay）
```

在 `assistant/voice/__init__.py` 的 `create_asr / create_tts` 工厂中放开分支即可生效。
调用链（含回声抑制、打断处理、唤醒后对话窗口）参考 `docs/architecture.md` 状态机。

## 产品化要点（从 demo 到真机）

| 环节 | 必做 |
|------|------|
| 唤醒 | Porcupine 自定义唤醒词（麦克风常驻低功耗）；或用视觉/按键代替 |
| 收音 | VAD 静音检测结束一句话（FunASR fsmn-vad / WebRTC VAD） |
| 打断 | 播报中检测到人声 → 立即停 TTS 进聆听态（Barge-in） |
| 回声消除 | 硬件全双工或 AEC 库，否则会自己唤醒自己 |
| 播报节奏 | TTS 阻塞式播报后再收音，保持一问一答节奏 |
| 降级 | 语音链路故障自动回 console，保证核心能力不中断 |

## 尽快听到效果的最小清单

1. `EDA_TTS_REAL=1 python -m assistant.main --mode enterprise`（先听音色与话术）
2. 装 whisper.cpp + 中文模型，stream 管道进 console（听+答闭环，约 10 分钟）
3. 把 ask/呼叫/发消息等意图换成人话说一遍，调话术
4. 需要真机常驻再走档位 2 的 FunASR/Porcupine/edge-tts

> 当前 GitHub 仓库不含语音模型与唤醒词引擎的二进制（体积与许可原因），
> 全部为「接口 + 桩 + 模板代码」，按上表接入即可，不锁死任何一家供应商。
