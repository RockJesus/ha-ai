"""Speech-to-text platform for HA AI."""

from __future__ import annotations

import io
import logging
import wave
from collections.abc import AsyncIterable
from typing import Any

import aiohttp
from homeassistant.components import stt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_PROMPT,
    CONF_STT_MODEL,
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
    """Set up the speech-to-text entity."""
    config = resolve_config(entry)
    model = (config.get(CONF_STT_MODEL) or "").strip()
    if not model:
        return

    async_add_entities([HAAISpeechToTextEntity(entry, config, model)])


class HAAISpeechToTextEntity(stt.SpeechToTextEntity):
    """Speech-to-text entity backed by an OpenAI-compatible endpoint."""

    _attr_has_entity_name = True

    def __init__(
        self, entry: ConfigEntry, config: dict[str, Any], model: str
    ) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._base_url = normalize_base_url(config.get(CONF_BASE_URL))
        self._api_key = config.get(CONF_API_KEY) or ""
        self._prompt = config.get(CONF_PROMPT) or ""
        self._model = model

        self._attr_name = "语音转文字"
        self._attr_unique_id = f"{entry.entry_id}_stt"
        self._attr_device_info = device_info(entry, config)

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        return [stt.AudioFormats.WAV, stt.AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM, stt.AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bit rates."""
        return [
            stt.AudioBitRates.BITRATE_8,
            stt.AudioBitRates.BITRATE_16,
            stt.AudioBitRates.BITRATE_24,
            stt.AudioBitRates.BITRATE_32,
        ]

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [
            stt.AudioSampleRates.SAMPLERATE_8000,
            stt.AudioSampleRates.SAMPLERATE_11000,
            stt.AudioSampleRates.SAMPLERATE_16000,
            stt.AudioSampleRates.SAMPLERATE_18900,
            stt.AudioSampleRates.SAMPLERATE_22000,
            stt.AudioSampleRates.SAMPLERATE_32000,
            stt.AudioSampleRates.SAMPLERATE_37800,
            stt.AudioSampleRates.SAMPLERATE_44100,
            stt.AudioSampleRates.SAMPLERATE_48000,
        ]

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        return [stt.AudioChannels.CHANNEL_MONO, stt.AudioChannels.CHANNEL_STEREO]

    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Send the recorded audio to the transcription endpoint."""
        audio_bytes = bytearray()
        async for chunk in stream:
            audio_bytes.extend(chunk)

        audio_data = bytes(audio_bytes)
        if metadata.format == stt.AudioFormats.WAV:
            # Voice satellites stream raw PCM frames without a container header.
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(metadata.channel.value)
                wav_file.setsampwidth(metadata.bit_rate.value // 8)
                wav_file.setframerate(metadata.sample_rate.value)
                wav_file.writeframes(audio_data)
            audio_data = wav_buffer.getvalue()

        form = aiohttp.FormData()
        form.add_field("model", self._model)
        form.add_field(
            "file",
            audio_data,
            filename=f"audio.{metadata.format.value}",
            content_type=f"audio/{metadata.format.value}",
        )
        if self._prompt:
            form.add_field("prompt", self._prompt)

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"{self._base_url}/audio/transcriptions",
                data=form,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status in (401, 403):
                    body = (await response.text())[:300]
                    self._entry.async_start_reauth(self.hass)
                    _LOGGER.error(
                        "Transcription rejected the API key (%s): %s",
                        response.status,
                        body,
                    )
                    return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
                if response.status != 200:
                    body = (await response.text())[:300]
                    _LOGGER.error(
                        "Transcription failed (%s): %s", response.status, body
                    )
                    return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
                data = await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Error during transcription: %s", err)
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        text = (data.get("text") or "").strip()
        if not text:
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        return stt.SpeechResult(text, stt.SpeechResultState.SUCCESS)
