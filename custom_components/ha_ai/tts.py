"""Text-to-speech platform for HA AI."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
from homeassistant.components import tts
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_TTS_MODEL,
    CONF_TTS_VOICE,
    DEFAULT_TIMEOUT,
    device_info,
    normalize_base_url,
    resolve_config,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

SUPPORTED_LANGUAGES = ["zh-CN", "en-US", "ja-JP", "ko-KR"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the text-to-speech entity."""
    config = resolve_config(entry)
    model = (config.get(CONF_TTS_MODEL) or "").strip()
    if not model:
        return

    async_add_entities([HAAITextToSpeechEntity(entry, config, model)])


class HAAITextToSpeechEntity(tts.TextToSpeechEntity):
    """Text-to-speech entity backed by an OpenAI-compatible endpoint."""

    _attr_has_entity_name = True
    _attr_supported_languages = SUPPORTED_LANGUAGES
    _attr_default_language = "zh-CN"
    _attr_supported_options = [tts.ATTR_VOICE]

    def __init__(
        self, entry: ConfigEntry, config: dict[str, Any], model: str
    ) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._base_url = normalize_base_url(config.get(CONF_BASE_URL))
        self._api_key = config.get(CONF_API_KEY) or ""
        self._model = model
        self._voice: str = (config.get(CONF_TTS_VOICE) or "").strip()

        self._attr_name = "文字转语音"
        self._attr_unique_id = f"{entry.entry_id}_tts"
        self._attr_device_info = device_info(entry, config)

    @property
    def default_options(self) -> Mapping[str, Any]:
        """Return the default options."""
        if self._voice:
            return {tts.ATTR_VOICE: self._voice}
        return {}

    @callback
    def async_get_supported_voices(self, language: str) -> list[tts.Voice] | None:
        """Return the voices this engine offers."""
        if not self._voice:
            return None
        return [tts.Voice(self._voice, self._voice)]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> tts.TtsAudioType:
        """Generate speech with the configured endpoint."""
        voice = options.get(tts.ATTR_VOICE) or self._voice
        payload: dict[str, Any] = {
            "model": self._model,
            "input": message,
            "response_format": "mp3",
        }
        if voice:
            payload["voice"] = voice

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"{self._base_url}/audio/speech",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status in (401, 403):
                    body = (await response.text())[:300]
                    self._entry.async_start_reauth(self.hass)
                    raise HomeAssistantError(
                        f"Provider rejected the API key ({response.status}): {body}"
                    )
                if response.status != 200:
                    body = (await response.text())[:300]
                    raise HomeAssistantError(
                        f"Speech generation failed ({response.status}): {body}"
                    )
                audio = await response.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(
                f"Speech generation request failed: {err}"
            ) from err

        if not audio:
            return None, None

        return "mp3", audio
