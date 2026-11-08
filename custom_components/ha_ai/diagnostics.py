"""Diagnostics support for HA AI."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_PROMPT

TO_REDACT = {CONF_API_KEY, CONF_PROMPT, "password", "token"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted config entry diagnostics."""
    return {
        "title": entry.title,
        "state": entry.state.value,
        "version": entry.version,
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
    }
