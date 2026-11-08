"""Constants for the HA AI integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

DOMAIN = "ha_ai"

CONF_PROVIDER = "provider"
CONF_API_KEY = "api_key"
CONF_BASE_URL = "base_url"
CONF_CHAT_MODEL = "chat_model"
CONF_IMAGE_MODEL = "image_model"
CONF_SIZE = "size"
CONF_PROMPT = "prompt"
CONF_STT_MODEL = "stt_model"
CONF_TTS_MODEL = "tts_model"
CONF_TTS_VOICE = "tts_voice"
CONF_MAX_TOKENS = "max_tokens"

# Voice requests synthesize / transcribe short utterances, 120s is generous.
DEFAULT_TIMEOUT = 120

# Chat completions: keep the reservation small so per-request credit checks on
# gateways like OpenRouter do not reject the call.
DEFAULT_MAX_TOKENS = 2048

# Legacy key used before the integration supported chat models.
CONF_LEGACY_MODEL = "model"

DEFAULT_SIZE = "1024x1024"

PROVIDER_POLLINATIONS = "pollinations"
PROVIDER_SILICONFLOW = "siliconflow"
PROVIDER_VOLCENGINE = "volcengine"
PROVIDER_DASHSCOPE = "dashscope"
PROVIDER_ZHIPU = "zhipu"
PROVIDER_MOONSHOT = "moonshot"
PROVIDER_STEPFUN = "stepfun"
PROVIDER_MINIMAX = "minimax"
PROVIDER_HUNYUAN = "hunyuan"
PROVIDER_SPARK = "spark"
PROVIDER_BAICHUAN = "baichuan"
PROVIDER_OPENAI = "openai"
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_GEMINI = "gemini"
PROVIDER_GROQ = "groq"
PROVIDER_MISTRAL = "mistral"
PROVIDER_TOGETHER = "together"
PROVIDER_DEEPSEEK = "deepseek"
PROVIDER_XAI = "xai"
PROVIDER_FIREWORKS = "fireworks"
PROVIDER_CEREBRAS = "cerebras"
PROVIDER_OLLAMA = "ollama"
PROVIDER_LMSTUDIO = "lmstudio"
PROVIDER_CUSTOM = "openai_compatible"

# Grouped so the dropdown reads China -> overseas -> local -> custom.
PROVIDERS = [
    # 国内
    PROVIDER_POLLINATIONS,
    PROVIDER_SILICONFLOW,
    PROVIDER_VOLCENGINE,
    PROVIDER_DASHSCOPE,
    PROVIDER_ZHIPU,
    PROVIDER_MOONSHOT,
    PROVIDER_STEPFUN,
    PROVIDER_MINIMAX,
    PROVIDER_HUNYUAN,
    PROVIDER_SPARK,
    PROVIDER_BAICHUAN,
    # 海外
    PROVIDER_OPENAI,
    PROVIDER_OPENROUTER,
    PROVIDER_GEMINI,
    PROVIDER_GROQ,
    PROVIDER_MISTRAL,
    PROVIDER_TOGETHER,
    PROVIDER_DEEPSEEK,
    PROVIDER_XAI,
    PROVIDER_FIREWORKS,
    PROVIDER_CEREBRAS,
    # 本地
    PROVIDER_OLLAMA,
    PROVIDER_LMSTUDIO,
    # 自定义
    PROVIDER_CUSTOM,
]

# Providers that run without an API key (free endpoint or a local server).
KEYLESS_PROVIDERS = {
    PROVIDER_POLLINATIONS,
    PROVIDER_OLLAMA,
    PROVIDER_LMSTUDIO,
}

PROVIDER_LABELS = {
    PROVIDER_POLLINATIONS: "国内 · Pollinations（免费，无需 Key）",
    PROVIDER_SILICONFLOW: "国内 · 硅基流动 SiliconFlow",
    PROVIDER_VOLCENGINE: "国内 · 火山方舟 Ark（豆包 / Seedream）",
    PROVIDER_DASHSCOPE: "国内 · 阿里云百炼 DashScope（通义千问）",
    PROVIDER_ZHIPU: "国内 · 智谱 GLM",
    PROVIDER_MOONSHOT: "国内 · 月之暗面 Kimi",
    PROVIDER_STEPFUN: "国内 · 阶跃星辰 StepFun",
    PROVIDER_MINIMAX: "国内 · MiniMax",
    PROVIDER_HUNYUAN: "国内 · 腾讯混元",
    PROVIDER_SPARK: "国内 · 讯飞星火",
    PROVIDER_BAICHUAN: "国内 · 百川智能",
    PROVIDER_OPENAI: "海外 · OpenAI",
    PROVIDER_OPENROUTER: "海外 · OpenRouter（聚合，含国内模型）",
    PROVIDER_GEMINI: "海外 · Google Gemini（OpenAI 兼容）",
    PROVIDER_GROQ: "海外 · Groq",
    PROVIDER_MISTRAL: "海外 · Mistral",
    PROVIDER_TOGETHER: "海外 · Together AI",
    PROVIDER_DEEPSEEK: "海外 · DeepSeek 官方",
    PROVIDER_XAI: "海外 · xAI Grok",
    PROVIDER_FIREWORKS: "海外 · Fireworks AI",
    PROVIDER_CEREBRAS: "海外 · Cerebras",
    PROVIDER_OLLAMA: "本地 · Ollama（无需 Key）",
    PROVIDER_LMSTUDIO: "本地 · LM Studio（无需 Key）",
    PROVIDER_CUSTOM: "自定义 · OpenAI 兼容接口",
}

DEFAULTS: dict[str, dict[str, str]] = {
    PROVIDER_POLLINATIONS: {
        "base_url": "https://image.pollinations.ai",
        "chat_model": "",
        "image_model": "flux",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_SILICONFLOW: {
        "base_url": "https://api.siliconflow.cn/v1",
        "chat_model": "",
        "image_model": "Kwai-Kolors/Kolors",
        "stt_model": "FunAudioLLM/SenseVoiceSmall",
        "tts_model": "FunAudioLLM/CosyVoice2-0.5B",
        "tts_voice": "FunAudioLLM/CosyVoice2-0.5B:alex",
    },
    PROVIDER_VOLCENGINE: {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "chat_model": "",
        "image_model": "doubao-seedream-5-0-260128",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_DASHSCOPE: {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_ZHIPU: {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_MOONSHOT: {
        "base_url": "https://api.moonshot.cn/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_STEPFUN: {
        "base_url": "https://api.stepfun.com/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_MINIMAX: {
        "base_url": "https://api.minimaxi.com/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_HUNYUAN: {
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_SPARK: {
        "base_url": "https://spark-api-open.xf-yun.com/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_BAICHUAN: {
        "base_url": "https://api.baichuan-ai.com/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "whisper-1",
        "tts_model": "gpt-4o-mini-tts",
        "tts_voice": "alloy",
    },
    PROVIDER_OPENROUTER: {
        "base_url": "https://openrouter.ai/api/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_GEMINI: {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_GROQ: {
        "base_url": "https://api.groq.com/openai/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "whisper-large-v3",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_MISTRAL: {
        "base_url": "https://api.mistral.ai/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_TOGETHER: {
        "base_url": "https://api.together.xyz/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_DEEPSEEK: {
        "base_url": "https://api.deepseek.com/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_XAI: {
        "base_url": "https://api.x.ai/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_FIREWORKS: {
        "base_url": "https://api.fireworks.ai/inference/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_CEREBRAS: {
        "base_url": "https://api.cerebras.ai/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_OLLAMA: {
        "base_url": "http://localhost:11434/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_LMSTUDIO: {
        "base_url": "http://localhost:1234/v1",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
    PROVIDER_CUSTOM: {
        "base_url": "",
        "chat_model": "",
        "image_model": "",
        "stt_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
}

VOICE_KEYS = (
    CONF_CHAT_MODEL,
    CONF_IMAGE_MODEL,
    CONF_STT_MODEL,
    CONF_TTS_MODEL,
    CONF_TTS_VOICE,
)


def normalize_base_url(value: str | None) -> str:
    """Return an absolute base URL without a trailing slash."""
    value = (value or "").strip().rstrip("/")
    if value and not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


def resolve_config(entry: ConfigEntry) -> dict[str, Any]:
    """Merge data and options, falling back to the provider defaults."""
    config: dict[str, Any] = {**entry.data, **entry.options}
    defaults = DEFAULTS.get(config.get(CONF_PROVIDER, ""), {})
    for key in VOICE_KEYS:
        if not (config.get(key) or "").strip():
            config[key] = defaults.get(key, "")
    return config


MANUFACTURER = "RockJesus"
DOCUMENTATION_URL = "https://github.com/RockJesus/ha-ai"


def device_info(entry: ConfigEntry, config: dict[str, Any] | None = None) -> DeviceInfo:
    """Return the device that owns this entry's entities."""
    config = config if config is not None else resolve_config(entry)
    provider = config.get(CONF_PROVIDER, "")
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"HA AI · {entry.title}",
        manufacturer=MANUFACTURER,
        model=PROVIDER_LABELS.get(provider, provider) or None,
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=DOCUMENTATION_URL,
    )


def provider_error_hint(status: int, body: str) -> str:
    """Translate a failed provider response into a short Chinese hint."""
    lowered = (body or "").lower()
    if (
        status == 402
        or "30001" in (body or "")
        or "insufficient" in lowered
        or "balance" in lowered
        or "欠费" in (body or "")
    ):
        return "服务商账户余额或额度不足，请充值后重试，或先换用其他服务商/Key。"
    if status in (401, 403):
        return "API Key 无效或没有该模型的权限，请重新认证或更换 Key。"
    if status == 429:
        return "请求过于频繁或触发限流，请稍后再试。"
    if status == 404:
        return "该服务商没有这个模型或接口不存在，请在下拉里重新选择模型。"
    if status >= 500:
        return f"服务商暂时不可用（HTTP {status}），请稍后重试。"
    snippet = (body or "").strip().replace("\n", " ")[:120]
    if not snippet:
        return f"服务商返回错误（HTTP {status}）。"
    return f"服务商返回错误（HTTP {status}）：{snippet}"
