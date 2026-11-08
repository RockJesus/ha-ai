# HA AI

一个 Home Assistant `ai_task` 提供者：把「AI 建议」页面需要的四类能力（数据生成、附件、图像生成、决策评估）一次补齐，支持 Pollinations（免 Key）、硅基流动、火山方舟 Seedream 与任意 OpenAI 兼容服务。

## 能力

| 能力 | 对应服务 | 实现方式 |
|---|---|---|
| 数据生成 | `ai_task.generate_data` | `POST {base_url}/chat/completions`，支持结构化 JSON |
| 附件 | — | 图片附件转 base64 传给文本模型 |
| 图像生成 | `ai_task.generate_image` | `POST {base_url}/images/generations`，或 Pollinations 免 Key 接口 |
| 决策评估 | `ai_task.evaluate` | 文本模型输出 JSON 概率 / 选项 / 评分 |

实体的能力位按配置动态注册：填了**文本模型**才启用数据生成、附件与决策；填了**图像模型**才启用图像生成。两个都填就是全能力。

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

### v1.0.1
- 修复 Base URL 未带协议（例如直接填 `api.siliconflow.cn/v1`）时所有请求都抛 `InvalidUrlClientError`、图像生成 0.2 秒即失败的问题：现在保存与运行时都会自动补 `https://`。
