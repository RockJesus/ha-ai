"""Constants for the HA AI integration."""

from __future__ import annotations

DOMAIN = "ha_ai"

CONF_PROVIDER = "provider"
CONF_API_KEY = "api_key"
CONF_BASE_URL = "base_url"
CONF_CHAT_MODEL = "chat_model"
CONF_IMAGE_MODEL = "image_model"
CONF_SIZE = "size"

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
    },
    PROVIDER_SILICONFLOW: {
        "base_url": "https://api.siliconflow.cn/v1",
        "chat_model": "",
        "image_model": "Kwai-Kolors/Kolors",
    },
    PROVIDER_VOLCENGINE: {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "chat_model": "",
        "image_model": "doubao-seedream-5-0-260128",
    },
    PROVIDER_OPENAI: {
        "base_url": "",
        "chat_model": "",
        "image_model": "",
    },
}
