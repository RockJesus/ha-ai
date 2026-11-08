"""Config and options flow for HA AI."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_IMAGE_MODEL,
    CONF_LEGACY_MODEL,
    CONF_PROVIDER,
    CONF_SIZE,
    DEFAULT_SIZE,
    DEFAULTS,
    DOMAIN,
    PROVIDER_LABELS,
    PROVIDER_POLLINATIONS,
    PROVIDERS,
)


def _absolute_url(value: str | None) -> str:
    """Prefix a bare host with https:// so the stored base URL is absolute."""
    value = (value or "").strip().rstrip("/")
    if value and not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


def _provider_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value=key, label=PROVIDER_LABELS[key])
                for key in PROVIDERS
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _secret_selector() -> selector.TextSelector:
    return selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PROVIDER, default=PROVIDER_POLLINATIONS): _provider_selector(),
        vol.Optional(CONF_API_KEY, default=""): _secret_selector(),
        vol.Optional(CONF_BASE_URL, default=""): selector.TextSelector(),
        vol.Optional(CONF_CHAT_MODEL, default=""): selector.TextSelector(),
        vol.Optional(CONF_IMAGE_MODEL, default=""): selector.TextSelector(),
        vol.Optional(CONF_SIZE, default=DEFAULT_SIZE): selector.TextSelector(),
    }
)


def _options_schema(current: dict[str, Any]) -> vol.Schema:
    """Build the options schema prefilled with the current values."""
    return vol.Schema(
        {
            vol.Optional(CONF_API_KEY, default=current.get(CONF_API_KEY, "")): _secret_selector(),
            vol.Optional(
                CONF_BASE_URL, default=current.get(CONF_BASE_URL, "")
            ): selector.TextSelector(),
            vol.Optional(
                CONF_CHAT_MODEL, default=current.get(CONF_CHAT_MODEL, "")
            ): selector.TextSelector(),
            vol.Optional(
                CONF_IMAGE_MODEL,
                default=current.get(CONF_IMAGE_MODEL)
                or current.get(CONF_LEGACY_MODEL)
                or "",
            ): selector.TextSelector(),
            vol.Optional(
                CONF_SIZE, default=current.get(CONF_SIZE, DEFAULT_SIZE)
            ): selector.TextSelector(),
        }
    )


class HAAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA AI."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HAAIOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            provider = user_input[CONF_PROVIDER]
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            base_url = _absolute_url(user_input.get(CONF_BASE_URL))
            chat_model = (user_input.get(CONF_CHAT_MODEL) or "").strip()
            image_model = (user_input.get(CONF_IMAGE_MODEL) or "").strip()

            if provider != PROVIDER_POLLINATIONS and not api_key:
                errors["base"] = "api_key_required"
            else:
                resolved_chat = chat_model or DEFAULTS[provider]["chat_model"]
                resolved_image = image_model or DEFAULTS[provider]["image_model"]
                await self.async_set_unique_id(
                    f"{provider}_{resolved_chat}_{resolved_image}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=resolved_image or resolved_chat or PROVIDER_LABELS[provider],
                    data={
                        CONF_PROVIDER: provider,
                        CONF_API_KEY: api_key,
                        CONF_BASE_URL: base_url,
                        CONF_CHAT_MODEL: chat_model,
                        CONF_IMAGE_MODEL: image_model,
                        CONF_SIZE: (user_input.get(CONF_SIZE) or DEFAULT_SIZE).strip(),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class HAAIOptionsFlow(OptionsFlow):
    """Edit the endpoint, key and models without removing the entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            user_input[CONF_CHAT_MODEL] = (
                user_input.get(CONF_CHAT_MODEL) or ""
            ).strip()
            user_input[CONF_IMAGE_MODEL] = (
                user_input.get(CONF_IMAGE_MODEL) or ""
            ).strip()
            user_input[CONF_BASE_URL] = _absolute_url(user_input.get(CONF_BASE_URL))
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current),
            errors=errors,
        )
