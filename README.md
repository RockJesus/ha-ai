<p align="center">
  <img src="custom_components/ha_ai/brand/logo.png" width="150" alt="HA AI">
</p>

<h1 align="center">HA AI</h1>

<p align="center">把任意 OpenAI 兼容服务接进 Home Assistant，补齐 AI 建议与语音助手需要的能力。</p>

<p align="center">
  <a href="https://github.com/RockJesus/ha-ai/releases"><img src="https://img.shields.io/github/v/release/RockJesus/ha-ai?label=release&style=flat-square" alt="Release"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2026.11-41BDF5?style=flat-square&logo=homeassistant&logoColor=white" alt="Home Assistant">
  <img src="https://img.shields.io/badge/API-OpenAI%20compatible-2EA44F?style=flat-square" alt="OpenAI compatible">
</p>

---

## 简介

HA AI 是一个「能力提供者」型集成，不绑定单一厂商。填入一个 Base URL、一个 Key、若干模型 ID，就能同时得到：

- **AI 建议页面**需要的 `ai_task`：生成数据、读附件、生成图像、决策评估
- **语音助手 → AI 页面**需要的 `conversation` / `stt` / `tts`：对话、语音转文字、文字转语音

实体按配置动态创建：填了文本模型才有对话与数据能力，填了图像模型才有生图能力，语音模型同理。一个条目可以只做一件事，也可以全部打开。

## 能力

| 平台 | 能力 | 接口 |
|---|---|---|
| `ai_task` | 生成文本 / 结构化 JSON | `POST {base_url}/chat/completions` |
| `ai_task` | 图片附件 | 图片转 base64 交给文本模型 |
| `ai_task` | 生成图像 | `POST {base_url}/images/generations`；Pollinations 走免 Key 接口 |
| `ai_task` | 决策评估 | 文本模型输出 JSON 概率 / 选项 / 评分 |
| `conversation` | 对话代理，可控制设备 | `chat/completions` + HA LLM API 工具调用（最多 10 轮） |
| `stt` | 语音转文字 | `POST {base_url}/audio/transcriptions` |
| `tts` | 文字转语音 | `POST {base_url}/audio/speech`，输出 mp3 |

对话代理把 Home Assistant 已公开的实体变成工具函数，模型返回 `tool_calls` 后由 HA 执行并把结果回传。选项里勾选 `assist` 即具备设备控制能力；不勾选则只聊天。

## 安装

**通过 HACS（推荐）**

1. HACS → 集成 → 搜索 **HA AI** 并安装，重启 Home Assistant
2. 如果暂时搜不到（默认仓库收录后即可直接搜索），再用自定义仓库：HACS → 集成 → 右上角菜单 → 自定义仓库，添加 `https://github.com/RockJesus/ha-ai`，类别选「集成」，然后重新搜索安装

**手动安装**

把 `custom_components/ha_ai` 整个目录放进 HA 的 `config/custom_components/`，重启 Home Assistant。

**添加条目**

「设置 → 设备与服务 → 添加集成」搜索 **HA AI**，选择服务商、填 Key，下一步从服务商 `/models` 返回的列表里下拉选模型。模型始终来自下拉，不需要手填 ID。

## 服务商

内置 24 个预设，覆盖国内、海外与本地部署；其余服务用「自定义 · OpenAI 兼容」手填地址。

| 服务商 | 默认 Base URL | 默认图像模型 | Key |
|---|---|---|---|
| Pollinations | `https://image.pollinations.ai` | `flux` | 不需要 |
| 硅基流动 SiliconFlow | `https://api.siliconflow.cn/v1` | `Kwai-Kolors/Kolors` | 需要（实名后图像免费） |
| 火山方舟 Ark | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-seedream-5-0-260128` | 需要 |
| OpenRouter | `https://openrouter.ai/api/v1` | 自定义 | 需要 |
| OpenAI / Gemini / Groq / Mistral / DeepSeek / xAI 等 | 各自官方兼容地址 | 自定义 | 需要 |
| Ollama / LM Studio | `http://localhost:11434/v1`、`http://localhost:1234/v1` | 自定义 | 不需要 |
| 自定义 · OpenAI 兼容 | 手填 | 手填 | 视服务而定 |

> Anthropic Claude 使用私有协议，Perplexity 没有 `/models`，两者不能按 OpenAI 兼容方式直接接入，请改用各自原生集成。

## 语音助手

1. 「设置 → 语音助手 → 助手 → AI」新建或编辑助手
2. 对话代理选 `conversation.ha_ai_...`
3. 语音转文字选 `stt.ha_ai_...`（如 `FunAudioLLM/SenseVoiceSmall`）
4. 文字转语音选 `tts.ha_ai_...`（如 `FunAudioLLM/CosyVoice2-0.5B`），音色默认 `FunAudioLLM/CosyVoice2-0.5B:alex`

硅基流动的语音模型需要单独在条目里填写；Pollinations 只提供文本与图像，没有语音能力。

## 网页搜索

选项里的「网页搜索」只对 **OpenRouter** 生效，其他服务商自动忽略。

| 选项 | 行为 |
|---|---|
| 关闭（默认） | 不发送任何搜索参数 |
| 自动 / Model native / Exa / Firecrawl / Parallel / Perplexity | 带上 `openrouter:web_search` 服务端工具，由模型决定是否搜索、可多次搜索 |
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
