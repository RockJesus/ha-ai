"""AI Task platform for HA AI.

Supports all four AI Task capabilities:
- GENERATE_DATA (chat completions)
- SUPPORT_ATTACHMENTS (images passed to the chat model)
- GENERATE_IMAGE (images endpoint or the keyless Pollinations endpoint)
- EVALUATE (JSON answer from the chat model)
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import mimetypes
import time
from pathlib import Path
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout

from homeassistant.components.ai_task import (
    AITaskEntity,
    AITaskEntityFeature,
    ChoiceAnswer,
    EvaluationTask,
    EvaluationTaskResult,
    GenDataTask,
    GenDataTaskResult,
    GenImageTask,
    GenImageTaskResult,
    NoulAnswer,
    ScoreAnswer,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
    PROVIDER_POLLINATIONS,
    PROVIDER_SILICONFLOW,
    PROVIDER_VOLCENGINE,
)

PARALLEL_UPDATES = 1
REQUEST_TIMEOUT = ClientTimeout(total=180)

DATA_SYSTEM_PROMPT = (
    "You are a helpful assistant inside Home Assistant. "
    "Answer concisely in the language of the request."
)

EVALUATE_SYSTEM_PROMPT = (
    "You evaluate questions about a Home Assistant smart home. "
    "Reply with a single JSON object mapping every question id to its answer. "
    'For type "noul" reply {"noul": <probability 0..1>}. '
    'For type "choice" reply {"choice": "<one of the criteria keys>", '
    '"probabilities": {"<criteria key>": <probability>}}. '
    'For type "score" reply {"score": <level index number>, '
    '"probabilities": [<probability per criterion in the given order>]}. '
    "Probabilities must sum to 1. Return JSON only, no prose and no code fences."
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AI Task entity from a config entry."""
    async_add_entities([HAAIEntity(entry)])


def _normalize_base_url(base_url: str | None) -> str:
    """Return an absolute base URL without a trailing slash.

    Users often type a bare host such as 'api.siliconflow.cn/v1'. aiohttp then
    treats it as a relative URL and raises InvalidUrlClientError, so the scheme
    has to be added before any request is made.
    """
    base_url = (base_url or "").strip().rstrip("/")
    if base_url and not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    return base_url


def _parse_size(size: str) -> tuple[int, int]:
    """Parse '1024x1024' into width and height."""
    try:
        width_str, height_str = size.lower().split("x")
        width, height = int(width_str), int(height_str)
    except (ValueError, AttributeError):
        return 1024, 1024
    if width <= 0 or height <= 0:
        return 1024, 1024
    return width, height


class HAAIEntity(AITaskEntity):
    """An AI Task entity backed by a remote HTTP API."""

    _attr_has_entity_name = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__()
        self._entry = entry
        data = {**entry.data, **entry.options}
        self._provider: str = data[CONF_PROVIDER]
        self._api_key: str = data.get(CONF_API_KEY, "")
        self._chat_model: str = (
            data.get(CONF_CHAT_MODEL) or DEFAULTS[self._provider]["chat_model"]
        )
        self._image_model: str = (
            data.get(CONF_IMAGE_MODEL)
            or data.get(CONF_LEGACY_MODEL)
            or DEFAULTS[self._provider]["image_model"]
        )
        # Older versions could store the image model in the chat slot; that is
        # not a usable chat model, treat it as unset.
        if self._chat_model and self._chat_model == self._image_model:
            self._chat_model = ""
        base_url = data.get(CONF_BASE_URL) or DEFAULTS[self._provider]["base_url"]
        self._base_url: str = _normalize_base_url(base_url)
        self._size: str = data.get(CONF_SIZE, DEFAULT_SIZE)
        self._width, self._height = _parse_size(self._size)

        features = AITaskEntityFeature(0)
        if self._image_model:
            features |= AITaskEntityFeature.GENERATE_IMAGE
        if self._chat_model:
            features |= (
                AITaskEntityFeature.GENERATE_DATA
                | AITaskEntityFeature.EVALUATE
                | AITaskEntityFeature.SUPPORT_ATTACHMENTS
            )
        self._attr_supported_features = features
        self._attr_unique_id = f"{entry.entry_id}_image"
        self._attr_name = f"AI Task {self._image_model or self._chat_model}"

    # ------------------------------------------------------------------
    # Data generation
    # ------------------------------------------------------------------
    async def _async_generate_data(
        self,
        task: GenDataTask,
        chat_log,
    ) -> GenDataTaskResult:
        """Generate structured or free-form data with the chat model."""
        if not self._chat_model:
            raise HomeAssistantError("No chat model is configured for this entry")

        instructions = (task.instructions or "").strip()
        if not instructions:
            raise HomeAssistantError("The task instructions are empty")

        system_prompt = DATA_SYSTEM_PROMPT
        response_format: dict[str, str] | None = None
        if task.structure is not None:
            system_prompt += (
                " Return only a valid JSON object matching the requested structure, "
                "without prose or code fences."
            )
            response_format = {"type": "json_object"}

        messages = [{"role": "system", "content": system_prompt}]
        messages.append(
            {
                "role": "user",
                "content": await self._build_user_content(
                    instructions, task.attachments
                ),
            }
        )

        text = await self._chat(messages, response_format)

        data: object = text
        if task.structure is not None:
            try:
                data = json.loads(_strip_code_fence(text))
            except json.JSONDecodeError as err:
                raise HomeAssistantError(
                    f"The model did not return valid JSON: {text[:200]}"
                ) from err

        return GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )

    # ------------------------------------------------------------------
    # Evaluation / decision
    # ------------------------------------------------------------------
    async def _async_evaluate(self, task: EvaluationTask) -> EvaluationTaskResult:
        """Answer the evaluation questions with the chat model."""
        if not self._chat_model:
            raise HomeAssistantError("No chat model is configured for this entry")

        questions = task.questions or {}
        if not questions:
            raise HomeAssistantError("The evaluation task has no questions")

        state = (
            json.dumps(task.state, ensure_ascii=False)
            if task.state is not None
            else "null"
        )
        question_text = _describe_questions(questions)
        user_text = (
            f"Current state:\n{state}\n\n"
            f"Questions:\n{question_text}\n\n"
            "Answer every question id."
        )

        messages = [
            {"role": "system", "content": EVALUATE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": await self._build_user_content(user_text, task.attachments),
            },
        ]

        text = await self._chat(messages, {"type": "json_object"}, max_tokens=4000)
        try:
            parsed = json.loads(_strip_code_fence(text))
        except json.JSONDecodeError as err:
            raise HomeAssistantError(
                f"The model did not return valid JSON: {text[:200]}"
            ) from err

        answers = {}
        for question_id, question in questions.items():
            raw = parsed.get(question_id)
            if raw is None:
                raw = parsed.get(str(question_id), {})
            if not isinstance(raw, dict):
                raw = {}
            answers[question_id] = _coerce_answer(question, raw)

        return EvaluationTaskResult(answers=answers)

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------
    async def _async_generate_image(
        self,
        task: GenImageTask,
        chat_log,
    ) -> GenImageTaskResult:
        """Generate an image based on the task instructions."""
        if not self._image_model:
            raise HomeAssistantError("No image model is configured for this entry")

        prompt = (task.instructions or "").strip()
        if not prompt:
            raise HomeAssistantError("The image prompt is empty")

        session = async_get_clientsession(self.hass)

        try:
            if self._provider == PROVIDER_POLLINATIONS:
                image_data, mime_type = await self._pollinations(session, prompt)
            else:
                image_data, mime_type = await self._images_api(session, prompt)
        except (ClientError, asyncio.TimeoutError, TimeoutError) as err:
            raise HomeAssistantError(f"Image request failed: {err}") from err

        real_width, real_height = _image_dimensions(image_data)

        return GenImageTaskResult(
            image_data=image_data,
            conversation_id=chat_log.conversation_id,
            mime_type=mime_type,
            width=real_width or self._width,
            height=real_height or self._height,
            model=self._image_model,
        )

    async def _pollinations(
        self, session: ClientSession, prompt: str
    ) -> tuple[bytes, str]:
        """Generate an image with the keyless Pollinations endpoint."""
        url = f"{self._base_url}/prompt/{quote(prompt, safe='')}"
        params = {
            "width": self._width,
            "height": self._height,
            "nologo": "true",
            "model": self._image_model or "flux",
            "seed": int(time.time()),
        }
        async with session.get(url, params=params, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HomeAssistantError(
                    f"Pollinations returned HTTP {resp.status}: {body[:200]}"
                )
            content = await resp.read()
            if not content:
                raise HomeAssistantError("Pollinations returned an empty image")
            return content, _normalize_mime(resp.content_type, url)

    async def _images_api(
        self, session: ClientSession, prompt: str
    ) -> tuple[bytes, str]:
        """Generate an image through an OpenAI-style images endpoint."""
        endpoint = f"{self._base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, object] = {
            "model": self._image_model,
            "prompt": prompt,
        }

        if self._provider == PROVIDER_SILICONFLOW:
            payload.update(
                {
                    "image_size": self._size,
                    "batch_size": 1,
                    "num_inference_steps": 20,
                    "guidance_scale": 7.5,
                    "prompt_enhancement": False,
                }
            )
        elif self._provider == PROVIDER_VOLCENGINE:
            payload.update(
                {
                    "size": self._size,
                    "response_format": "url",
                    "watermark": False,
                }
            )
        else:
            payload.update(
                {
                    "n": 1,
                    "size": self._size,
                    "response_format": "b64_json",
                }
            )

        async with session.post(
            endpoint, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
        ) as resp:
            status = resp.status
            text = await resp.text()

        if status != 200:
            raise HomeAssistantError(
                f"Image API returned HTTP {status}: {text[:300]}"
            )

        try:
            body = json.loads(text)
        except json.JSONDecodeError as err:
            raise HomeAssistantError(
                f"Image API returned invalid JSON: {text[:200]}"
            ) from err

        item = _first_image_item(body)
        b64 = item.get("b64_json") or item.get("b64") or body.get("b64_json")
        if b64:
            try:
                return base64.b64decode(b64), "image/png"
            except ValueError as err:
                raise HomeAssistantError("Invalid base64 image payload") from err

        image_url = item.get("url") or body.get("url")
        if not image_url:
            raise HomeAssistantError(
                f"Image API response has no image URL or base64 data: {text[:200]}"
            )

        async with session.get(image_url, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                raise HomeAssistantError(
                    f"Failed to download generated image: HTTP {resp.status}"
                )
            content = await resp.read()
            mime_type = _normalize_mime(resp.content_type, image_url)

        if not content:
            raise HomeAssistantError("Generated image is empty")

        return content, mime_type

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    async def _chat(
        self,
        messages: list[dict],
        response_format: dict[str, str] | None = None,
        max_tokens: int = 2000,
    ) -> str:
        """Call an OpenAI-style chat completions endpoint."""
        payload: dict[str, object] = {
            "model": self._chat_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        session = async_get_clientsession(self.hass)
        status, text = await self._post_chat(session, payload)

        # Some OpenAI-compatible providers reject response_format; retry without it.
        if (
            status == 400
            and response_format is not None
            and "response_format" in text
        ):
            payload.pop("response_format", None)
            status, text = await self._post_chat(session, payload)

        if status != 200:
            raise HomeAssistantError(
                f"Chat API returned HTTP {status}: {text[:300]}"
            )

        try:
            body = json.loads(text)
        except json.JSONDecodeError as err:
            raise HomeAssistantError(
                f"Chat API returned invalid JSON: {text[:200]}"
            ) from err

        choices = body.get("choices") or []
        if not choices:
            raise HomeAssistantError(
                f"Chat API returned no choices: {text[:200]}"
            )

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )
        if not content:
            raise HomeAssistantError(
                f"Chat API returned an empty message: {text[:200]}"
            )
        return content.strip()

    async def _post_chat(
        self, session: ClientSession, payload: dict[str, object]
    ) -> tuple[int, str]:
        """POST a chat completion request and return the status and body."""
        endpoint = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with session.post(
                endpoint, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
            ) as resp:
                return resp.status, await resp.text()
        except (ClientError, asyncio.TimeoutError, TimeoutError) as err:
            raise HomeAssistantError(f"Chat request failed: {err}") from err

    async def _build_user_content(
        self, text: str, attachments
    ) -> str | list[dict]:
        """Build user content, embedding image attachments when present."""
        if not attachments:
            return text

        parts: list[dict] = [{"type": "text", "text": text}]
        for attachment in attachments:
            mime_type = getattr(attachment, "mime_type", "") or ""
            if not mime_type.startswith("image/"):
                continue
            image_path = getattr(attachment, "path", None)
            if not image_path:
                continue
            encoded = await self.hass.async_add_executor_job(
                _read_b64, image_path
            )
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                }
            )
        if len(parts) == 1:
            return text
        return parts


def _read_b64(path) -> str:
    """Read a file and return its base64 representation."""
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def _describe_questions(questions: dict) -> str:
    """Render evaluation questions as readable text."""
    lines = []
    for question_id, question in questions.items():
        question_type = question.get("type", "")
        line = (
            f"- id: {question_id}\n"
            f"  type: {question_type}\n"
            f"  instructions: {question.get('instructions', '')}"
        )
        if question_type in ("choice", "score"):
            line += "\n  criteria: " + json.dumps(
                question.get("criteria"), ensure_ascii=False
            )
        lines.append(line)
    return "\n".join(lines)


def _coerce_answer(question: dict, raw: dict):
    """Convert the model JSON into the matching answer dataclass."""
    question_type = question.get("type", "")

    if question_type == "noul":
        try:
            value = float(raw.get("noul", 0.5))
        except (TypeError, ValueError):
            value = 0.5
        return NoulAnswer(noul=min(max(value, 0.0), 1.0))

    if question_type == "choice":
        criteria = question.get("criteria") or {}
        probabilities = raw.get("probabilities")
        if not isinstance(probabilities, dict):
            probabilities = {}
        cleaned: dict[str, float] = {}
        for key in criteria:
            try:
                cleaned[key] = float(probabilities.get(key, 0.0))
            except (TypeError, ValueError):
                cleaned[key] = 0.0
        choice = raw.get("choice")
        if not isinstance(choice, str) or choice not in criteria:
            if cleaned:
                choice = max(cleaned, key=cleaned.get)
            else:
                choice = next(iter(criteria), "")
        return ChoiceAnswer(choice=str(choice), probabilities=cleaned)

    if question_type == "score":
        criteria = question.get("criteria") or []
        probabilities = raw.get("probabilities")
        if not isinstance(probabilities, list) or len(probabilities) != len(criteria):
            probabilities = [1.0 / len(criteria)] * len(criteria) if criteria else []
        try:
            cleaned_probs = [float(value) for value in probabilities]
        except (TypeError, ValueError):
            cleaned_probs = [1.0 / len(criteria)] * len(criteria) if criteria else []
        try:
            score = float(raw.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        return ScoreAnswer(score=score, probabilities=cleaned_probs)

    # Unknown question type: fall back to a neutral probability answer.
    return NoulAnswer(noul=0.5)


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding markdown code fence if the model added one."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _first_image_item(body: dict) -> dict:
    """Return the first image entry from common response shapes."""
    for key in ("data", "images", "output"):
        value = body.get(key)
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[0]
    if isinstance(body.get("data"), dict):
        return body["data"]
    return body


def _normalize_mime(content_type: str | None, url: str) -> str:
    """Normalize the MIME type of a downloaded image."""
    if content_type and content_type.startswith("image/"):
        return content_type.split(";")[0]
    guessed, _ = mimetypes.guess_type(url)
    if guessed and guessed.startswith("image/"):
        return guessed
    return "image/png"


def _image_dimensions(data: bytes) -> tuple[int | None, int | None]:
    """Return the real pixel dimensions of the generated image."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            return img.width, img.height
    except Exception:  # noqa: BLE001
        return None, None
