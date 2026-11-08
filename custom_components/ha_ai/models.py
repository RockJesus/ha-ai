"""Model catalogue discovery for HA AI.

The config and options flows use this module to build dropdowns from the
provider's own model list instead of asking the user to type a model id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DEFAULTS,
    PROVIDER_POLLINATIONS,
    normalize_base_url,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = ClientTimeout(total=20)

KIND_CHAT = "chat"
KIND_IMAGE = "image"
KIND_STT = "stt"
KIND_TTS = "tts"

# Keyword heuristics for OpenAI-compatible catalogues that do not describe what
# a model can do. Ordered: speech first (CosyVoice/SenseVoice), then images.
_STT_HINTS = (
    "sensevoice",
    "whisper",
    "paraformer",
    "transcribe",
    "transcription",
    "-stt",
)
_TTS_HINTS = ("cosyvoice", "text-to-speech", "-tts", "tts-")
_IMAGE_HINTS = (
    "image",
    "flux",
    "kolors",
    "seedream",
    "dall-e",
    "stable-diffusion",
    "sdxl",
    "imagen",
    "nano-banana",
    "qwen-image",
    "gpt-image",
    "seededit",
    "wanx",
)

POLLINATIONS_TEXT_MODELS = "https://text.pollinations.ai/models"
POLLINATIONS_IMAGE_MODELS = "https://image.pollinations.ai/models"


@dataclass(frozen=True)
class ModelOption:
    """One selectable model."""

    id: str
    name: str
    kind: str


@dataclass
class ModelCatalog:
    """Result of asking a provider for its models."""

    options: list[ModelOption] = field(default_factory=list)
    # invalid_auth | cannot_connect | unknown, None when the fetch succeeded.
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Return True when a usable model list was received."""
        return self.error is None and bool(self.options)

    def by_kind(self, kind: str) -> list[ModelOption]:
        """Return the models of one kind, sorted by display name."""
        return sorted(
            (option for option in self.options if option.kind == kind),
            key=lambda option: option.name.casefold(),
        )


def classify_model(model_id: str, output_modalities: list[str] | None = None) -> str:
    """Guess what a model can do from its id and declared output modalities."""
    lowered = model_id.casefold()
    if any(hint in lowered for hint in _STT_HINTS):
        return KIND_STT
    if any(hint in lowered for hint in _TTS_HINTS):
        return KIND_TTS
    if any(hint in lowered for hint in _IMAGE_HINTS):
        return KIND_IMAGE
    if output_modalities:
        outputs = {str(item).casefold() for item in output_modalities}
        if "image" in outputs:
            return KIND_IMAGE
        if "audio" in outputs:
            return KIND_TTS
    return KIND_CHAT


def _display_name(model_id: str, raw_name: Any = None) -> str:
    name = str(raw_name).strip() if raw_name else ""
    if not name or name == model_id:
        return model_id
    return f"{name} ({model_id})"


def _parse_openai_catalog(payload: Any) -> list[ModelOption]:
    """Parse the OpenAI style ``{"data": [{"id": ...}]}`` model list."""
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    options: list[ModelOption] = []
    for item in items:
        if isinstance(item, str):
            model_id, name, modalities = item, None, None
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("name") or "").strip()
            name = item.get("name")
            architecture = item.get("architecture")
            if isinstance(architecture, dict):
                modalities = (
                    architecture.get("output_modalities")
                    or architecture.get("modality")
                )
                if isinstance(modalities, str):
                    modalities = [
                        part.strip()
                        for part in modalities.split("->")[-1].split("+")
                    ]
            else:
                modalities = item.get("output_modalities")
        else:
            continue
        if not model_id:
            continue
        options.append(
            ModelOption(
                id=model_id,
                name=_display_name(model_id, name),
                kind=classify_model(
                    model_id, modalities if isinstance(modalities, list) else None
                ),
            )
        )
    return options


def _dedupe(options: list[ModelOption]) -> list[ModelOption]:
    seen: set[str] = set()
    result: list[ModelOption] = []
    for option in options:
        key = option.id.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(option)
    return result


async def _async_pollinations_catalog(
    session: ClientSession, base_url: str
) -> ModelCatalog:
    """Pollinations exposes separate text and image model endpoints."""
    catalog = ModelCatalog()
    text_url = (
        f"{base_url}/models"
        if base_url.startswith("https://text.")
        else POLLINATIONS_TEXT_MODELS
    )
    for url, forced in (
        (text_url, KIND_CHAT),
        (POLLINATIONS_IMAGE_MODELS, KIND_IMAGE),
    ):
        try:
            response = await session.get(url, timeout=REQUEST_TIMEOUT)
            payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Could not list Pollinations models at %s: %s", url, err)
            continue
        for option in _parse_openai_catalog(payload):
            catalog.options.append(
                ModelOption(id=option.id, name=option.name, kind=forced)
            )
    if not catalog.options:
        catalog.error = "cannot_connect"
    return catalog


async def async_fetch_catalog(
    hass: HomeAssistant,
    provider: str,
    base_url: str | None,
    api_key: str | None,
) -> ModelCatalog:
    """Fetch the provider's model list and group it into UI categories."""
    session = async_get_clientsession(hass)
    resolved_base = normalize_base_url(base_url) or normalize_base_url(
        DEFAULTS.get(provider, {}).get("base_url", "")
    )

    if provider == PROVIDER_POLLINATIONS:
        return await _async_pollinations_catalog(session, resolved_base)

    if not resolved_base:
        return ModelCatalog(error="cannot_connect")

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = await session.get(
            f"{resolved_base}/models", headers=headers, timeout=REQUEST_TIMEOUT
        )
        if response.status in (401, 403):
            return ModelCatalog(error="invalid_auth")
        response.raise_for_status()
        payload = await response.json(content_type=None)
    except (ClientError, TimeoutError, ValueError) as err:
        _LOGGER.debug("Model listing failed for %s: %s", resolved_base, err)
        return ModelCatalog(error="cannot_connect")

    options = _dedupe(_parse_openai_catalog(payload))
    if not options:
        return ModelCatalog(error="cannot_connect")
    return ModelCatalog(options=options)
