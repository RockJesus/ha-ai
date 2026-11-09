# HA AI

一个 Home Assistant 的 AI 能力提供者：既补「AI 建议」页面需要的四类 `ai_task` 能力（数据生成、附件、图像生成、决策评估），也补「语音助手 → AI」页面需要的三项能力（对话代理、语音转文字、文字转语音）。支持 Pollinations（免 Key）、硅基流动、火山方舟 Seedream 与任意 OpenAI 兼容服务。

## 能力

| 能力 | 对应服务 | 实现方式 |
|---|---|---|
| 数据生成 | `ai_task.generate_data` | `POST {base_url}/chat/completions`，支持结构化 JSON |
| 附件 | — | 图片附件转 base64 传给文本模型 |
| 图像生成 | `ai_task.generate_image` | `POST {base_url}/images/generations`，或 Pollinations 免 Key 接口 |
| 决策评估 | `ai_task.evaluate` | 文本模型输出 JSON 概率 / 选项 / 评分 |

实体的能力位按配置动态注册：填了**文本模型**才启用数据生成、附件与决策；填了**图像模型**才启用图像生成。两个都填就是全能力。

### 语音与对话

| 能力 | 平台 | 实现方式 |
|---|---|---|
| 对话代理（可控制设备） | `conversation` | `POST {base_url}/chat/completions`，通过 Home Assistant 的 LLM API 把设备变成工具函数，模型返回 tool_calls 后由 HA 执行并循环 |
| 语音转文字 | `stt` | `POST {base_url}/audio/transcriptions`（OpenAI 兼容），16kHz/16bit/单声道 PCM WAV 直接可用 |
| 文字转语音 | `tts` | `POST {base_url}/audio/speech`，输出 mp3 |

三项都按条目内容自动创建，不需要单独添加集成：

- 条目里填了**文本模型** → 出现对话代理实体；在选项里勾选 `assist` API 后，它就能控制已公开给语音助手的设备。
- 条目里填了**语音转文字模型** → 出现 STT 引擎；硅基流动默认 `FunAudioLLM/SenseVoiceSmall`。
- 条目里填了**文字转语音模型** → 出现 TTS 引擎；硅基流动默认 `FunAudioLLM/CosyVoice2-0.5B`，默认音色 `FunAudioLLM/CosyVoice2-0.5B:alex`。

之后在「设置 → 语音助手 → 助手 → AI」里，把对话代理、语音转文字、文字转语音分别选中 HA AI 的实体即可。

## Provider

| Provider | 默认 Base URL | 默认图像模型 | 文本模型 | Key |
|---|---|---|---|---|
| Pollinations | `https://image.pollinations.ai` | `flux` | 不支持 | 不需要 |
| SiliconFlow | `https://api.siliconflow.cn/v1` | `Kwai-Kolors/Kolors` | 需自己填 | 需要（实名后图像免费） |
| Volcengine Ark | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-seedream-5-0-260128` | 需自己填 | 需要 |
| OpenAI-compatible | 自定义 | 自定义 | 自定义 | 视服务而定 |

文本模型填对应平台的模型 ID 即可（例如硅基流动模型广场里的 `Qwen/...`、火山方舟的 `doubao-...`）。留空则只做图像。

## 安装

1. 把 `custom_components/ha_ai` 整个目录放进 HA 的 `config/custom_components/`。
2. 重启 Home Assistant。
3. 「设置 → 设备与服务 → 添加集成」搜索 **HA AI**，选服务商、填 Key 与模型。
4. 「设置 → AI → AI 建议」三个下拉都能选到这个实体（能力对齐的才会出现在对应下拉）。

## 说明

- 实体的自身状态记录最近一次任务的执行时间，方便在 UI 上看是否跑过。
- 图像结果交给 HA 的 `image` 媒体目录保存。
- 请求超时 180 秒；图像尺寸以 Pillow 读到的真实像素回填。
- 若某些 OpenAI 兼容服务不接受 `response_format`，会自动去掉该参数重试一次。

## 更新日志

### v1.2.4
- 修复 v1.2.3 中网页搜索选项未真正加载（缺少导入导致对话请求 500）的问题。

### v1.2.3
- 选项新增「网页搜索」（仅 OpenRouter 生效）：关闭 / 插件（已弃用）/ 自动 / Model native / Exa / Firecrawl / Parallel / Perplexity，默认关闭。启用后按所选引擎在请求里带上 `openrouter:web_search` 服务端工具（插件模式走旧 `web` 插件），对话代理与 AI 任务生成文本都会用上，图片生成不受影响；其他服务商会自动忽略该选项。
- 搜索会在 OpenRouter 侧产生额外费用，按需开启。

### v1.2.2
- 选项表单里的「允许对话代理使用的 Home Assistant API」由原来的下拉 + 添加标签式多选，改为**可勾选的复选框列表**：Device control（设备控制）与 Home Assistant（完全控制）两项直接勾选，手机上更好点。
- 选项名称同步补上中文说明，默认仍只勾选 `assist`，保存逻辑与实体创建规则不变。
- 重新认证 / 重新配置的收尾改用 `async_update_entry` + `async_abort`（原先的 `async_update_reload_and_abort` 从 HA 2026.11 起会记录使用告警），由已有 update listener 负责重载。

### v1.2.1
- 中文错误提示扩展到 AI 任务（ai_task：生成文本/图片）与对话代理（conversation）：余额不足、Key 无效、限流、模型不存在、服务商不可用、连接失败、超时都返回中文原因，不再是英文原始报错。

### v1.2.0
- 语音失败原因改用 ERROR 级别写入日志（默认 logger 配置下 WARNING 可能不落 system_log），便于在「设置 → 日志」里直接看到中文原因。

### v1.1.9
- 语音转文字 / 语音合成失败时给出中文原因：余额或额度不足、Key 无效、限流、模型不存在、服务商不可用；STT 实体还会把最近一次失败原因写入属性 `last_error`，方便在开发者工具里直接看到。

### v1.1.8
- 目录拉取失败时不再自动跳到「手动填写模型」，而是留在当前步骤提示「连接失败 / 认证失败」，避免用户被迫手填模型 ID（模型始终来自服务商 `/models` 下拉）。

### v1.1.7
- 修复 v1.1.6 只注册了 24 个服务商常量、下拉里仍只有 4 个的遗漏。

### v1.1.6
- 服务商从 4 个扩到 24 个，覆盖国内与海外主流 OpenAI 兼容接口，模型列表全部走 `/models` 下拉：

| 分组 | 服务商 | 默认 Base URL |
|---|---|---|
| 国内 | 硅基流动、火山方舟、阿里云百炼、智谱 GLM、月之暗面 Kimi、阶跃星辰、MiniMax、腾讯混元、讯飞星火、百川、Pollinations | 各自官方兼容地址 |
| 海外 | OpenAI、OpenRouter、Google Gemini（OpenAI 兼容）、Groq、Mistral、Together AI、DeepSeek、xAI、Fireworks、Cerebras | 各自官方兼容地址 |
| 本地 | Ollama、LM Studio | `http://localhost:11434/v1`、`http://localhost:1234/v1` |
| 自定义 | 任意 OpenAI 兼容接口 | 手填 |

- Ollama / LM Studio / Pollinations 选为「无需 Key」，其余服务商仍要求 Key 并用 `/models` 当场校验，Key 错会直接提示「认证失败」。
- OpenAI 条目默认带上 `whisper-1` 转写与 `gpt-4o-mini-tts` 合成，Groq 默认 `whisper-large-v3`。
- 说明：Anthropic Claude 使用私有协议、Perplexity 没有 `/models`，两者都不能按 OpenAI 兼容方式直接接入，故未列入；Azure OpenAI 需要按部署名调用，请用「自定义」并填自己的 endpoint。

### v1.1.5
- 修复对话代理实体在初始化阶段就调用 LLM API 列表、此时 `self.hass` 还是空导致整个 conversation 平台启动失败（实体显示「已恢复 / 不可用」）的问题：改为实体加入后再过滤 LLM API。

### v1.1.4
- 修复选项里「提示词」为空时，模板选择器收到 null 会报 `template value is None`、导致整个选项流程保存失败的问题（空值现在按空字符串处理，对话代理仍然回落到 HA 内置指令）。

### v1.1.3
- 重新配置时如果填了自定义 Base URL（Pollinations），会先探测该地址的 `/models`，不可达直接报「无法连接」，避免把不可用的地址写进条目。

### v1.1.2
- 新增「重新认证」流程：服务商返回 401/403 时 HA 会直接弹出重新输入 API Key 的窗口，模型、设备和实体全部保留（对齐官方 OpenAI 集成的 reauth 行为）。
- 新增「重新配置」流程：可以在条目页改服务商 / API Key / Base URL，提交前先用模型目录验证，成功后自动重载。
- 对话代理补齐官方做法：未填提示词时自动使用 HA 内置指令；自动过滤已失效的 LLM API 选项；`max_tokens` 可在选项里调节（256–8192，默认 2048）。
- 语音转文字 / 文字转语音 / AI 任务遇到 401 也会触发重新认证，而不是只报一句 HTTP 错误。

### v1.1.1
- 修复编辑已有条目时，选项流程首步会把已保存的模型字段清空的问题（现在沿用条目里的原值）。

### v1.1.0
- 下拉的「使用默认」改用内部哨兵值，避免空字符串在某些 HA 版本里被选择器拒绝；保存时再还原为空值（等价于使用服务商默认）。
- 模型下拉渲染异常时记录日志并自动退回手动填写，不会再把整个配置流程打断。

### v1.0.9
- 模型不再手填：配置流程会先校验 API Key，再从服务商拉取真实模型列表，文本 / 图像 / 语音转文字 / 文字转语音全部改为下拉选择，并标注模型名与 ID。
- 每个下拉第一项是「使用默认」，跟随服务商预设；当前配置的模型如果不在列表里，会自动作为「当前值」出现在下拉里，不会丢配置。
- 服务商没有模型清单或网络不通时，自动退回原来的手填表单，不再阻断添加。
- 选项流程也改成两步：先改地址 / Key / 提示词，保存时重新拉取模型列表，再用下拉换模型。
- 新增诊断信息（`diagnostics.py`），API Key 与提示词自动脱敏。

### v1.0.8
- 品牌图换成新版 HAI 连笔字标：H 的横笔直接延伸成 A 的左斜笔，A 为钝角三角，I 为独立竖笔，字标 “HA AI” 居中排在字形下方。图标仍是深空蓝 `#12233F` 圆角底 + 反白字形，`logo.png` / `dark_logo.png` 为 238×256，`@2x` 为 476×512，全部透明 PNG、裁剪到最紧。

### v1.0.7
- 加入品牌图：`custom_components/ha_ai/brand/` 放 `icon.png`（256×256）/ `icon@2x.png`（512×512）/ `logo.png`（594×256）/ `logo@2x.png`（1187×512），外加深色主题用的 `dark_logo.png` 与 `dark_logo@2x.png`。HA 2026.3 起本地 `brand/` 目录自动优先于 brands CDN，集成卡片、设备页和语音助手列表直接显示新标志。
- 标志为 H、A、I 三字母共笔构成的正方形字标：字形笔等宽、硬切方角、共享基线，白底黑色横版组合中标出现在右侧；图标为深空蓝圆角底 + 反白字形。无第三方素材、无官方品牌图。

### v1.0.6
- 每个配置条目现在会先创建一台设备（`HA AI · <模型名>`，型号为服务商名），`ai_task` / `conversation` / `stt` / `tts` 四类实体统一挂在该设备下，设备页可直接看到能力归属。
- 实体改用设备+实体两级命名（如 `HA AI · deepseek/deepseek-v4.1-flash` 下的「对话代理」），unique_id 与 entity_id 保持不变。

### v1.0.5
- 对话代理请求补上 `max_tokens`（2048）：OpenRouter 这类网关会按未声明的上限（131072）预扣额度，余额不多时直接返回 `402 requires more credits`。

### v1.0.4
- 修复历史条目把图像模型写进文本模型槽位（如 flux / Kolors / Seedream）时误创建对话代理实体的问题：文本模型与图像模型同名视为未配置。
- 对话代理未保存过 LLM API 选项时默认使用 `assist`，新装条目开箱即可控制设备；显式清空则不具备控制能力。
- `ai_task` 实体同步按该规则判定能力位，避免图像模型被当成文本模型。

### v1.0.3
- 新增 `conversation` 对话代理：走 OpenAI 兼容的 `chat/completions`，并通过 Home Assistant 的 LLM API 获得设备工具，模型发起 `tool_calls` 后由 HA 执行并继续对话（最多 10 轮）；在选项里勾选 `assist` API 即具备控制设备能力。
- 新增 `stt` 语音转文字平台：`/audio/transcriptions`，兼容语音卫星下发的 16kHz/16bit/单声道 PCM WAV（自动补 WAV 头）。
- 新增 `tts` 文字转语音平台：`/audio/speech`，输出 mp3，支持 `voice` 选项与默认音色。
- 选项表单新增语音转文字模型、文字转语音模型、音色、可用 LLM API（多选，默认 `assist`）与系统提示词；三类语音/AI 实体按填写内容自动创建。
- 硅基流动内置语音默认值：`FunAudioLLM/SenseVoiceSmall` / `FunAudioLLM/CosyVoice2-0.5B`（实测 3.5 秒合成、转写回读一致）。

### v1.0.2
- 修复 Base URL 未带协议（例如直接填 `api.siliconflow.cn/v1`）时所有请求都抛 `InvalidUrlClientError`、图像生成 0.2 秒即失败的问题：现在保存与运行时都会自动补 `https://`。

### v1.0.2
- 配置表单与选项表单里的 Base URL、文本模型、图像模型全部改为选填：留空即使用该服务商的默认地址与默认模型，不再校验 `base_url_required` / `model_required`。
- 运行时同步兜底：条目里存的是空值时，按 provider 的 `DEFAULTS` 取默认地址与默认模型，老条目/清空后的条目不会因此失去能力。
- 修正中文翻译里的标题与表单文案。
