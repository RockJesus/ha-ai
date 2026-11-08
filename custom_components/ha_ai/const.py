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
PROVIDER_OPENAI = "openai_compatible"

PROVIDERS = [
    PROVIDER_POLLINATIONS,
    PROVIDER_SILICONFLOW,
    PROVIDER_VOLCENGINE,
    PROVIDER_OPENAI,
]

PROVIDER_LABELS = {
    PROVIDER_POLLINATIONS: "Pollinations (free, no key)",
    PROVIDER_SILICONFLOW: "SiliconFlow (Kolors, free after verification)",
    PROVIDER_VOLCENGINE: "Volcengine Ark (Seedream)",
    PROVIDER_OPENAI: "OpenAI-compatible (custom)",
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
    PROVIDER_OPENAI: {
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
