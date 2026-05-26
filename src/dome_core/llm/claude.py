from __future__ import annotations

import base64
from typing import Optional

import anthropic

from dome_core.json_utils import parse_json_response
from dome_core.llm.base import LLMProvider
from dome_core.llm.retry import with_retry
from dome_core.logging import get_logger

logger = get_logger(__name__)

_JSON_INSTRUCTION = "\n\nRespond ONLY with valid JSON. No markdown, no code fences, no explanation."
_CLAUDE_BASE64_LIMIT = 5 * 1024 * 1024


class ClaudeProvider(LLMProvider):
    def __init__(self, *, api_key: str, model: str, max_tokens: int = 16384) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def generate(self, prompt: str, system: Optional[str] = None) -> str:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = await with_retry(self._client.messages.create, **kwargs)
        return response.content[0].text

    async def generate_structured(
        self, prompt: str, schema: dict, system: Optional[str] = None
    ) -> dict:
        schema_hint = "\n\nOutput schema — use these exact field names:\n"
        import json

        schema_hint += json.dumps(schema, indent=2)
        sys_prompt = (system or "") + _JSON_INSTRUCTION
        text = await self.generate(prompt + schema_hint, system=sys_prompt)
        return parse_json_response(text)

    async def generate_vision(
        self,
        prompt: str,
        image: bytes,
        media_type: str = "image/png",
        system: Optional[str] = None,
    ) -> str:
        image_b64 = base64.standard_b64encode(image).decode("utf-8")
        if len(image_b64) > _CLAUDE_BASE64_LIMIT:
            size_mb = len(image_b64) / 1024 / 1024
            raise ValueError(
                f"Image is too large to process ({size_mb:.1f} MB encoded, 5 MB limit). "
                "Try a lower-resolution image or a text-based PDF."
            )
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        kwargs: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        response = await with_retry(self._client.messages.create, **kwargs)
        return response.content[0].text
