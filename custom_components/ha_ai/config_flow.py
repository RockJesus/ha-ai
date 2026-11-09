"""Config and options flow for HA AI.

Both flows pull the model list from the provider and render dropdowns, so the
user never has to type a model id by hand. When a provider does not expose a
model catalogue (or the network is unreachable) the flow falls back to a
free-text form instead of blocking setup.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm, selector

from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_IMAGE_MODEL,
    CONF_LEGACY_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_PROVIDER,
    CONF_SIZE,
    CONF_STT_MODEL,
    CONF_TTS_MODEL,
    CONF_TTS_VOICE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_SIZE,
    DEFAULTS,
    DOMAIN,
    KEYLESS_PROVIDERS,
    PROVIDER_LABELS,
    PROVIDER_POLLINATIONS,
    PROVIDERS,
    normalize_base_url,
)
from .models import (
    KIND_CHAT,
    KIND_IMAGE,
    KIND_STT,
    KIND_TTS,
    ModelCatalog,
    ModelOption,
    async_fetch_catalog,
)

_LOGGER = logging.getLogger(__name__)

# Sentinel used inside dropdowns; empty strings are not valid select options.
USE_DEFAULT = "__ha_ai_default__"


# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------
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


CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_PROVIDER, default=PROVIDER_POLLINATIONS
        ): _provider_selector(),
        vol.Optional(CONF_API_KEY, default=""): _secret_selector(),
        vol.Optional(CONF_BASE_URL, default=""): selector.TextSelector(),
    }
)


def _model_selector(
    options: list[ModelOption], default_label: str, current: str | None
) -> selector.SelectSelector:
    """Build a dropdown whose first entry means 'use the provider default'."""
    entries = [selector.SelectOptionDict(value=USE_DEFAULT, label=default_label)]
    known = {option.id for option in options}
    if current and current not in known:
        entries.append(
            selector.SelectOptionDict(value=current, label=f"当前值 · {current}")
        )
    entries.extend(
        selector.SelectOptionDict(value=option.id, label=option.name)
        for option in options
    )
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=entries,
            mode=selector.SelectSelectorMode.DROPDOWN,
            sort=False,
        )
    )


def _default_label(provider: str, key: str, empty_label: str) -> str:
    value = DEFAULTS.get(provider, {}).get(key, "")
    if not value:
        return empty_label
    return f"使用默认 · {value}"


# Friendlier labels for the built-in APIs; unknown ids fall back to their name.
_LLM_API_LABELS = {
    "assist": "Device control（设备控制，安全）",
    "homeassistant": "Home Assistant（完全控制，管理员级）",
}


def _llm_api_selector(hass: HomeAssistant) -> selector.SelectSelector:
    """Return a checkbox list of the Home Assistant LLM APIs.

    Multiple + LIST renders as checkboxes in the frontend, which reads much
    better on mobile than the chip-style dropdown it replaced.
    """
    try:
        apis = llm.async_get_apis(hass)
    except Exception:  # noqa: BLE001 - discovery must never break the form
        apis = []
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(
                    value=api.id, label=_LLM_API_LABELS.get(api.id, api.name)
                )
                for api in apis
            ],
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
        )
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
def _catalog_schema(
    hass: HomeAssistant,
    provider: str,
    catalog: ModelCatalog,
    current: dict[str, Any],
    *,
    include_options: bool,
) -> vol.Schema:
    """Model pickers rendered as dropdowns plus the entry level settings."""
    schema: dict[Any, Any] = {
        vol.Optional(
            CONF_CHAT_MODEL,
            default=((current.get(CONF_CHAT_MODEL) or "").strip() or USE_DEFAULT),
        ): _model_selector(
            catalog.by_kind(KIND_CHAT),
            _default_label(provider, "chat_model", "不使用聊天模型（仅生图）"),
            current.get(CONF_CHAT_MODEL),
        ),
        vol.Optional(
            CONF_IMAGE_MODEL,
            default=(
                current.get(CONF_IMAGE_MODEL) or current.get(CONF_LEGACY_MODEL) or ""
            ).strip()
            or USE_DEFAULT,
        ): _model_selector(
            catalog.by_kind(KIND_IMAGE),
            _default_label(provider, "image_model", "不使用图像模型"),
            current.get(CONF_IMAGE_MODEL) or current.get(CONF_LEGACY_MODEL),
        ),
        vol.Optional(
            CONF_STT_MODEL,
            default=((current.get(CONF_STT_MODEL) or "").strip() or USE_DEFAULT),
        ): _model_selector(
            catalog.by_kind(KIND_STT),
            _default_label(provider, "stt_model", "不使用语音转文字"),
            current.get(CONF_STT_MODEL),
        ),
        vol.Optional(
            CONF_TTS_MODEL,
            default=((current.get(CONF_TTS_MODEL) or "").strip() or USE_DEFAULT),
        ): _model_selector(
            catalog.by_kind(KIND_TTS),
            _default_label(provider, "tts_model", "不使用文字转语音"),
            current.get(CONF_TTS_MODEL),
        ),
        vol.Optional(
            CONF_TTS_VOICE, default=(current.get(CONF_TTS_VOICE) or "").strip()
        ): selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.TEXT,
            )
        ),
        vol.Optional(
            CONF_SIZE, default=(current.get(CONF_SIZE) or DEFAULT_SIZE).strip()
        ): selector.TextSelector(),
    }

    if include_options:
        _add_credential_fields(schema, current)
        schema[
            vol.Optional(
                CONF_LLM_HASS_API, default=current.get(CONF_LLM_HASS_API) or ["assist"]
            )
        ] = _llm_api_selector(hass)
        schema[
            vol.Optional(CONF_PROMPT, default=current.get(CONF_PROMPT, ""))
        ] = selector.TextSelector(
            selector.TextSelectorConfig(
                multiline=True, type=selector.TextSelectorType.TEXT
            )
        )
    return vol.Schema(schema)


def _manual_schema(current: dict[str, Any], *, include_options: bool) -> vol.Schema:
    """Free-text fallback used when the provider has no model catalogue."""
    schema: dict[Any, Any] = {
        vol.Optional(
            CONF_CHAT_MODEL,
            default=((current.get(CONF_CHAT_MODEL) or "").strip() or USE_DEFAULT),
        ): selector.TextSelector(),
        vol.Optional(
            CONF_IMAGE_MODEL,
            default=(
                current.get(CONF_IMAGE_MODEL) or current.get(CONF_LEGACY_MODEL) or ""
            ).strip()
            or USE_DEFAULT,
        ): selector.TextSelector(),
        vol.Optional(
            CONF_STT_MODEL,
            default=((current.get(CONF_STT_MODEL) or "").strip() or USE_DEFAULT),
        ): selector.TextSelector(),
        vol.Optional(
            CONF_TTS_MODEL,
            default=((current.get(CONF_TTS_MODEL) or "").strip() or USE_DEFAULT),
        ): selector.TextSelector(),
        vol.Optional(
            CONF_TTS_VOICE, default=(current.get(CONF_TTS_VOICE) or "").strip()
        ): selector.TextSelector(),
        vol.Optional(
            CONF_SIZE, default=(current.get(CONF_SIZE) or DEFAULT_SIZE).strip()
        ): selector.TextSelector(),
    }
    if include_options:
        _add_credential_fields(schema, current)
        schema[
            vol.Optional(CONF_PROMPT, default=current.get(CONF_PROMPT, ""))
        ] = selector.TextSelector(
            selector.TextSelectorConfig(
                multiline=True, type=selector.TextSelectorType.TEXT
            )
        )
    return vol.Schema(schema)


def _add_credential_fields(schema: dict[Any, Any], current: dict[str, Any]) -> None:
    """Add the editable key and base URL to the options form."""
    schema[
        vol.Optional(CONF_API_KEY, default=current.get(CONF_API_KEY, ""))
    ] = _secret_selector()
    schema[
        vol.Optional(CONF_BASE_URL, default=current.get(CONF_BASE_URL, ""))
    ] = selector.TextSelector()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
_MODEL_KEYS = (
    CONF_CHAT_MODEL,
    CONF_IMAGE_MODEL,
    CONF_STT_MODEL,
    CONF_TTS_MODEL,
    CONF_TTS_VOICE,
)


def _clean_models(user_input: dict[str, Any]) -> dict[str, Any]:
    """Strip whitespace from every model field and the connection settings."""
    data = dict(user_input)
    for key in _MODEL_KEYS:
        value = (data.get(key) or "").strip()
        data[key] = "" if value == USE_DEFAULT else value
    data[CONF_SIZE] = (data.get(CONF_SIZE) or DEFAULT_SIZE).strip()
    if CONF_MAX_TOKENS in data:
        try:
            data[CONF_MAX_TOKENS] = int(data.get(CONF_MAX_TOKENS) or DEFAULT_MAX_TOKENS)
        except (TypeError, ValueError):
            data[CONF_MAX_TOKENS] = DEFAULT_MAX_TOKENS
    if CONF_API_KEY in data:
        data[CONF_API_KEY] = (data.get(CONF_API_KEY) or "").strip()
    if CONF_BASE_URL in data:
        data[CONF_BASE_URL] = normalize_base_url(data.get(CONF_BASE_URL))
    return data


def _entry_title(provider: str, data: dict[str, Any]) -> str:
    """Return a readable title: the chat model, else the image model."""
    for key in (CONF_CHAT_MODEL, CONF_IMAGE_MODEL):
        value = (data.get(key) or "").strip()
        if value:
            return value
    return PROVIDER_LABELS.get(provider, provider)


class HAAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA AI."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._credentials: dict[str, Any] = {}
        self._catalog: ModelCatalog | None = None
        self._fetch_error: str | None = None
        self._reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HAAIOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the provider credentials, then load the model list."""
        errors: dict[str, str] = {}

        if user_input is not None:
            provider = user_input[CONF_PROVIDER]
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            base_url = normalize_base_url(user_input.get(CONF_BASE_URL))

            if provider not in KEYLESS_PROVIDERS and not api_key:
                errors["base"] = "api_key_required"
            else:
                catalog = await async_fetch_catalog(
                    self.hass, provider, base_url, api_key
                )
                if catalog.error:
                    # Model ids must come from the provider, so a failed
                    # catalogue keeps the user on this step instead of falling
                    # back to typing a model id by hand.
                    errors["base"] = catalog.error
                else:
                    self._credentials = {
                        CONF_PROVIDER: provider,
                        CONF_API_KEY: api_key,
                        CONF_BASE_URL: base_url,
                    }
                    self._catalog = catalog
                    self._fetch_error = None
                    return await self.async_step_models()

            # Re-render the credential form while keeping what was typed.
            self._credentials = {
                CONF_PROVIDER: user_input.get(CONF_PROVIDER, PROVIDER_POLLINATIONS),
                CONF_API_KEY: user_input.get(CONF_API_KEY, ""),
                CONF_BASE_URL: user_input.get(CONF_BASE_URL, ""),
            }

        schema = CREDENTIALS_SCHEMA
        if self._credentials:
            schema = self.add_suggested_values_to_schema(schema, self._credentials)
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication when the provider rejects the stored key."""
        self._reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a fresh API key and prove it against the provider."""
        entry = self._reauth_entry
        assert entry is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            catalog = await async_fetch_catalog(
                self.hass,
                entry.data.get(CONF_PROVIDER, PROVIDER_POLLINATIONS),
                entry.data.get(CONF_BASE_URL),
                api_key,
            )
            if catalog.error == "invalid_auth":
                errors["base"] = "invalid_auth"
            elif catalog.error == "cannot_connect":
                errors["base"] = "cannot_connect"
            else:
                # The entry has an update listener, so let it reload instead of
                # reload-and-abort (report_usage on 2026.11, breaks 2026.12.0).
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_API_KEY: api_key}
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_API_KEY): _secret_selector()}
            ),
            errors=errors,
            description_placeholders={
                "provider": PROVIDER_LABELS.get(
                    entry.data.get(CONF_PROVIDER, ""),
                    entry.data.get(CONF_PROVIDER, ""),
                )
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change provider / key / base URL without deleting the entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        suggested = {
            CONF_PROVIDER: entry.data.get(CONF_PROVIDER, PROVIDER_POLLINATIONS),
            CONF_API_KEY: entry.data.get(CONF_API_KEY, ""),
            CONF_BASE_URL: entry.data.get(CONF_BASE_URL, ""),
        }

        if user_input is not None:
            provider = user_input[CONF_PROVIDER]
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            base_url = normalize_base_url(user_input.get(CONF_BASE_URL))
            suggested = {
                CONF_PROVIDER: provider,
                CONF_API_KEY: api_key,
                CONF_BASE_URL: base_url,
            }
            if provider not in KEYLESS_PROVIDERS and not api_key:
                errors["base"] = "api_key_required"
            else:
                catalog = await async_fetch_catalog(
                    self.hass, provider, base_url, api_key
                )
                if catalog.error == "invalid_auth":
                    errors["base"] = "invalid_auth"
                elif catalog.error == "cannot_connect":
                    errors["base"] = "cannot_connect"
                else:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            CONF_PROVIDER: provider,
                            CONF_API_KEY: api_key,
                            CONF_BASE_URL: base_url,
                        },
                    )
                    return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA, suggested
            ),
            errors=errors,
        )

    async def async_step_models(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick chat / image / speech models from the fetched catalogue."""
        assert self._catalog is not None
        provider = self._credentials[CONF_PROVIDER]

        if user_input is not None:
            return self._async_finish(user_input)

        try:
            schema = _catalog_schema(
                self.hass,
                provider,
                self._catalog,
                self._credentials,
                include_options=False,
            )
        except Exception:  # noqa: BLE001 - never block setup on a UI bug
            _LOGGER.exception("Could not render the model dropdowns")
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="models",
            data_schema=schema,
            description_placeholders={"count": str(len(self._catalog.options))},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Fallback: type the model ids when no catalogue is available."""
        if user_input is not None:
            return self._async_finish(user_input)

        return self.async_show_form(
            step_id="manual",
            data_schema=_manual_schema(self._credentials, include_options=False),
            errors={"base": self._fetch_error}
            if self._fetch_error in ("cannot_connect", "unknown")
            else {},
        )

    @callback
    def _async_finish(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Validate uniqueness and create the entry."""
        data = {**self._credentials, **_clean_models(user_input)}
        provider = data[CONF_PROVIDER]
        resolved_chat = data[CONF_CHAT_MODEL] or DEFAULTS[provider]["chat_model"]
        resolved_image = data[CONF_IMAGE_MODEL] or DEFAULTS[provider]["image_model"]
        self._async_abort_entries_match(
            {
                CONF_PROVIDER: provider,
                CONF_API_KEY: data[CONF_API_KEY],
                CONF_BASE_URL: data[CONF_BASE_URL],
                CONF_CHAT_MODEL: resolved_chat,
                CONF_IMAGE_MODEL: resolved_image,
            }
        )
        return self.async_create_entry(
            title=_entry_title(provider, data),
            data=data,
        )


def _settings_schema(
    hass: HomeAssistant, provider: str, current: dict[str, Any]
) -> vol.Schema:
    """Connection and agent settings; model ids live in the next step."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_API_KEY, default=current.get(CONF_API_KEY, "")
            ): _secret_selector(),
            vol.Optional(
                CONF_BASE_URL, default=current.get(CONF_BASE_URL, "")
            ): selector.TextSelector(),
            vol.Optional(
                CONF_SIZE, default=(current.get(CONF_SIZE) or DEFAULT_SIZE).strip()
            ): selector.TextSelector(),
            vol.Optional(
                CONF_LLM_HASS_API, default=current.get(CONF_LLM_HASS_API) or ["assist"]
            ): _llm_api_selector(hass),
            vol.Optional(
                CONF_PROMPT, default=(current.get(CONF_PROMPT) or "")
            ): selector.TemplateSelector(),
            vol.Optional(
                CONF_MAX_TOKENS,
                default=int(current.get(CONF_MAX_TOKENS) or DEFAULT_MAX_TOKENS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=256, max=8192, step=256, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )


class HAAIOptionsFlow(OptionsFlow):
    """Edit credentials, models and agent settings without removing the entry."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._settings: dict[str, Any] = {}
        self._catalog: ModelCatalog | None = None
        self._fetch_error: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the connection settings, then re-read the model list."""
        current = {**self.config_entry.data, **self.config_entry.options}
        provider = current.get(CONF_PROVIDER, PROVIDER_POLLINATIONS)

        if user_input is not None:
            # The init form does not carry the model fields; keep the values
            # already stored on the entry instead of blanking them.
            settings = {**current, **user_input}
            settings[CONF_API_KEY] = (settings.get(CONF_API_KEY) or "").strip()
            settings[CONF_BASE_URL] = (
                normalize_base_url(settings.get(CONF_BASE_URL)) or ""
            )
            settings[CONF_SIZE] = (settings.get(CONF_SIZE) or DEFAULT_SIZE).strip()
            try:
                settings[CONF_MAX_TOKENS] = int(
                    settings.get(CONF_MAX_TOKENS) or DEFAULT_MAX_TOKENS
                )
            except (TypeError, ValueError):
                settings[CONF_MAX_TOKENS] = DEFAULT_MAX_TOKENS
            settings[CONF_LLM_HASS_API] = settings.get(CONF_LLM_HASS_API) or []
            settings[CONF_PROMPT] = (settings.get(CONF_PROMPT) or "").strip()
            settings[CONF_PROVIDER] = provider

            catalog = await async_fetch_catalog(
                self.hass,
                provider,
                settings.get(CONF_BASE_URL),
                settings.get(CONF_API_KEY),
            )
            self._settings = settings
            self._catalog = catalog
            self._fetch_error = catalog.error
            if catalog.error:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_settings_schema(self.hass, provider, current),
                    errors={"base": catalog.error},
                )
            return await self.async_step_models()

        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(self.hass, provider, current),
            description_placeholders={
                "provider": PROVIDER_LABELS.get(provider, provider)
            },
        )

    async def async_step_models(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the models from the freshly fetched catalogue."""
        assert self._catalog is not None
        provider = self._settings[CONF_PROVIDER]

        if user_input is not None:
            return self.async_create_entry(
                data={**self._settings, **_clean_models(user_input)}
            )

        try:
            schema = _catalog_schema(
                self.hass,
                provider,
                self._catalog,
                self._settings,
                include_options=False,
            )
        except Exception:  # noqa: BLE001 - never block saving on a UI bug
            _LOGGER.exception("Could not render the model dropdowns")
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="models",
            data_schema=schema,
            description_placeholders={"count": str(len(self._catalog.options))},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Fallback: edit the model ids by hand."""
        if user_input is not None:
            return self.async_create_entry(
                data={**self._settings, **_clean_models(user_input)}
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=_manual_schema(self._settings, include_options=False),
            errors={"base": self._fetch_error}
            if self._fetch_error in ("cannot_connect", "unknown")
            else {},
        )
