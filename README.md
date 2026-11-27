<p align="center">
  <img src="custom_components/ha_ai/brand/logo.png" width="160" alt="HA AI">
</p>

<h1 align="center">HA AI</h1>

<p align="center">
  <strong>一个条目，把任意 OpenAI 兼容服务接进 Home Assistant</strong><br>
  AI 建议 · 对话代理 · 语音转写 · 语音合成
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=RockJesus&amp;repository=ha-ai&amp;category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open in HACS">
  </a>
</p>

<p align="center">
  <sub>已收录于 HACS 默认仓库 · 点击上方按钮可直接打开</sub>
</p>

<p align="center">
  <a href="https://github.com/RockJesus/ha-ai/releases"><img src="https://img.shields.io/github/v/release/RockJesus/ha-ai?label=release&style=flat-square&color=41BDF5" alt="Release"></a>
  <a href="https://github.com/hacs/default"><img src="https://img.shields.io/badge/HACS-Default-41BDF5?style=flat-square&logo=homeassistant&logoColor=white" alt="HACS Default"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2026.11%2B-41BDF5?style=flat-square&logo=homeassistant&logoColor=white" alt="Home Assistant 2026.11+">
  <img src="https://img.shields.io/badge/API-OpenAI%20compatible-2EA44F?style=flat-square" alt="OpenAI compatible">
  <a href="https://github.com/RockJesus/ha-ai/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RockJesus/ha-ai?style=flat-square&color=2EA44F" alt="MIT License"></a>
</p>

---

## 为什么用它

- **不绑定厂商**：内置 24 个预设，覆盖国内、海外和本地部署；任何 OpenAI 兼容服务都能用「自定义」接入。
- **一个条目，四类实体**：`ai_task`、`conversation`、`stt`、`tts` 按你填的模型动态创建，只做一件事或全部打开都可以。
- **出错说人话**：余额不足、Key 无效、限流、模型不存在、连接失败、超时都会给出中文原因。

## 能力

| 平台 | 能做什么 | 请求 |
|:--|:--|:--|
| `ai_task` | 生成文本 / 结构化 JSON、读取图片附件、生成图像、决策评估 | `POST {base_url}/chat/completions`、`/images/generations`；Pollinations 走免 Key 接口 |
| `conversation` | 对话代理，可控制 Home Assistant 设备 | `chat/completions` + HA LLM API 工具调用，最多 10 轮 |
| `stt` | 语音转文字 | `POST {base_url}/audio/transcriptions` |
| `tts` | 文字转语音，输出 mp3 | `POST {base_url}/audio/speech` |

对话代理会把 Home Assistant 已公开的实体变成工具函数；模型返回 `tool_calls` 后由 HA 执行，再把结果回传给模型。选项里勾选 `assist` 即具备设备控制能力，不勾选则只聊天。

## 安装

> **HA AI 已进入 HACS 默认仓库。** 点页面顶部的「Open in HACS」，或打开 HACS → 集成 → 搜索 **HA AI**，安装后重启 Home Assistant。

1. 「设置 → 设备与服务 → 添加集成」搜索 **HA AI**。
2. 选择服务商，填 API Key；Base URL 留空即使用该服务商的预设地址。
3. 下一步从服务商 `/models` 返回的列表里下拉选模型，不需要手填模型 ID。

<details>
<summary>手动安装 / 自定义仓库</summary>

**自定义仓库**

HACS → 集成 → 右上角菜单 → 自定义仓库，添加 `https://github.com/RockJesus/ha-ai`，类别选「集成」，然后重新搜索安装。

**手动安装**

把 `custom_components/ha_ai` 整个目录放进 HA 的 `config/custom_components/`，重启 Home Assistant。

</details>

## 服务商

内置 24 个预设，其余服务用「自定义 · OpenAI 兼容」手填地址。

| 服务商 | 默认 Base URL | 默认图像模型 | Key |
|:--|:--|:--|:--|
| Pollinations | `https://image.pollinations.ai` | `flux` | 不需要 |
| 硅基流动 SiliconFlow | `https://api.siliconflow.cn/v1` | `Kwai-Kolors/Kolors` | 需要（实名后图像免费） |
| 火山方舟 Ark | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-seedream-5-0-260128` | 需要 |
| OpenRouter | `https://openrouter.ai/api/v1` | 自定义 | 需要 |
| OpenAI / Gemini / Groq / Mistral / DeepSeek / xAI 等 | 各自官方兼容地址 | 自定义 | 需要 |
| Ollama / LM Studio | `http://localhost:11434/v1`、`http://localhost:1234/v1` | 自定义 | 不需要 |
| 自定义 · OpenAI 兼容 | 手填 | 手填 | 视服务而定 |

> Anthropic Claude 使用私有协议，Perplexity 没有 `/models`，两者不能按 OpenAI 兼容方式直接接入，请改用各自原生集成。

## 语音助手

1. 「设置 → 语音助手 → 助手 → AI」新建或编辑助手。
2. 对话代理选 `conversation.ha_ai_...`。
3. 语音转文字选 `stt.ha_ai_...`，例如 `FunAudioLLM/SenseVoiceSmall`。
4. 文字转语音选 `tts.ha_ai_...`，例如 `FunAudioLLM/CosyVoice2-0.5B`；音色默认 `FunAudioLLM/CosyVoice2-0.5B:alex`。

硅基流动的语音模型需要单独在条目里填写；Pollinations 只提供文本与图像，没有语音能力。

## 网页搜索

选项里的「网页搜索」只对 **OpenRouter** 生效，其他服务商自动忽略。

| 选项 | 行为 |
|:--|:--|
| 关闭（默认） | 不发送任何搜索参数 |
| 自动 / Model native / Exa / Firecrawl / Parallel / Perplexity | 带上 `openrouter:web_search` 服务端工具，由模型决定是否搜索，可多次搜索 |
| 插件（已弃用） | 旧的 `web` 插件，每次请求必定搜索一次 |

搜索会在 OpenRouter 侧产生额外费用，即使使用免费模型也一样；不需要时切回「关闭」。

## 说明

- 每个配置条目创建一台设备（`HA AI · <模型名>`），四类实体统一挂在该设备下。
- 实体状态记录最近一次任务的执行时间，方便判断是否跑过。
- 生成的图片交给 HA 的 `image` 媒体目录保存。
- 请求超时 180 秒；图像尺寸以真实像素回填。
- 服务商不接受 `response_format` 时，会自动去掉该参数重试一次。
- 服务商返回 401/403 会触发「重新认证」，模型、设备与实体全部保留。
- 余额不足、Key 无效、限流、模型不存在、连接失败、超时都会给出中文原因；STT 最近一次失败原因同时写入实体属性 `last_error`。
- 诊断信息中的 API Key 与提示词自动脱敏。

---

<p align="center">
  <a href="https://github.com/RockJesus/ha-ai/releases">Releases</a> ·
  <a href="https://github.com/RockJesus/ha-ai/issues">问题反馈</a> ·
  <a href="https://github.com/RockJesus/ha-ai/blob/main/LICENSE">MIT License</a>
</p>
