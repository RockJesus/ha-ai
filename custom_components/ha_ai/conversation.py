"""Conversation agent for HA AI.

Talks to any OpenAI-compatible chat completions endpoint and can control the
Home Assistant devices that are exposed to the selected LLM API.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

import aiohttp
import probatio

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_PROMPT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    normalize_base_url,
    resolve_config,
)

_LOGGER = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 10

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the conversation entity."""
    config = resolve_config(entry)
    chat_model = config.get(CONF_CHAT_MODEL) or ""
    if not chat_model:
        return

    async_add_entities([HAAIConversationEntity(entry, config)])


class HAAIConversationEntity(conversation.ConversationEntity):
    """HA AI conversation agent."""

    _attr_has_entity_name = False

    def __init__(self, entry: ConfigEntry, config: dict[str, Any]) -> None:
        """Initialize the agent."""
        self._config = config
        self._chat_model: str = config[CONF_CHAT_MODEL]
        self._base_url = normalize_base_url(config.get(CONF_BASE_URL))
        self._api_key: str = config.get(CONF_API_KEY) or ""
        self._llm_hass_api: list[str] = config.get(CONF_LLM_HASS_API) or []
        self._prompt: str | None = config.get(CONF_PROMPT) or None

        self._attr_name = f"HA AI: {self._chat_model}"
        self._attr_unique_id = f"{entry.entry_id}_conversation"

        if self._llm_hass_api:
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Call the configured chat completions endpoint."""
        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                self._llm_hass_api or None,
                self._prompt,
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        try:
            await self._async_handle_chat_log(chat_log)
        except HomeAssistantError as err:
            _LOGGER.error("Error talking to %s: %s", self._chat_model, err)
            raise

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _async_handle_chat_log(self, chat_log: conversation.ChatLog) -> None:
        """Run the model, execute its tool calls and repeat until it answers."""
        for _iteration in range(MAX_TOOL_ITERATIONS):
            message = await self._async_chat(chat_log)

            tool_calls = self._build_tool_calls(message.get("tool_calls") or [])
            content = conversation.AssistantContent(
                agent_id=self.entity_id,
                content=message.get("content") or None,
                tool_calls=tool_calls or None,
            )

            async for _result in chat_log.async_add_assistant_content(content):
                pass

            if not chat_log.unresponded_tool_results:
                return

        _LOGGER.warning(
            "Stopped after %s tool iterations for %s", MAX_TOOL_ITERATIONS, self.entity_id
        )

    @staticmethod
    def _build_tool_calls(raw_calls: list[dict[str, Any]]) -> list[llm.ToolInput]:
        """Convert OpenAI tool calls into HA tool inputs."""
        tool_calls: list[llm.ToolInput] = []
        for raw in raw_calls:
            function = raw.get("function") or {}
            name = function.get("name")
            if not name:
                continue

            arguments = function.get("arguments") or "{}"
            try:
                tool_args = json.loads(arguments) if isinstance(arguments, str) else arguments
            except json.JSONDecodeError:
                _LOGGER.warning("Invalid tool arguments for %s: %s", name, arguments)
                tool_args = {}
            if not isinstance(tool_args, dict):
                tool_args = {"value": tool_args}

            kwargs: dict[str, Any] = {"tool_name": name, "tool_args": tool_args}
            if raw.get("id"):
                kwargs["id"] = raw["id"]
            tool_calls.append(llm.ToolInput(**kwargs))
        return tool_calls

    async def _async_chat(self, chat_log: conversation.ChatLog) -> dict[str, Any]:
        """Send the chat log to the endpoint and return the assistant message."""
        payload: dict[str, Any] = {
            "model": self._chat_model,
            "messages": _convert_content(chat_log.content),
            "stream": False,
        }

        if chat_log.llm_api and chat_log.llm_api.tools:
            payload["tools"] = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]
            payload["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status != 200:
                    body = (await response.text())[:300]
                    raise HomeAssistantError(
                        f"Chat completions failed ({response.status}): {body}"
                    )
                data = await response.json()
        except aiohttp.ClientError as err:
            raise HomeAssistantError(f"Chat completions request failed: {err}") from err
        except TimeoutError as err:
            raise HomeAssistantError("Chat completions request timed out") from err

        try:
            return data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as err:
            raise HomeAssistantError(f"Unexpected chat completions response: {data}") from err


def _format_tool(
    tool: llm.Tool, custom_serializer: Any | None
) -> dict[str, Any]:
    """Convert an HA tool into an OpenAI function tool."""
    schema = probatio.to_openapi(
        tool.parameters, custom_serializer=custom_serializer, openapi_version="3.1.0"
    )
    if not schema.get("properties") and schema.get("type") != "object":
        schema = {"type": "object", "properties": {}}

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema,
        },
    }


def _convert_content(
    chat_content: list[conversation.Content],
) -> list[dict[str, Any]]:
    """Convert the HA chat log into OpenAI chat messages."""
    messages: list[dict[str, Any]] = []

    for content in chat_content:
        if isinstance(content, conversation.SystemContent):
            messages.append({"role": "system", "content": content.content})

        elif isinstance(content, conversation.UserContent):
            messages.append({"role": "user", "content": content.content})

        elif isinstance(content, conversation.AssistantContent):
            message: dict[str, Any] = {"role": "assistant"}
            if content.content:
                message["content"] = content.content
            else:
                message["content"] = None
            if content.tool_calls:
                message["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.tool_name,
                            "arguments": json.dumps(call.tool_args, ensure_ascii=False),
                        },
                    }
                    for call in content.tool_calls
                ]
            messages.append(message)

        elif isinstance(content, conversation.ToolResultContent):
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": content.tool_call_id,
                    "content": json.dumps(
                        {
                            "data": content.result.data,
                            "error": content.result.error,
                        },
                        ensure_ascii=False,
                    ),
                }
            )

    return messages
