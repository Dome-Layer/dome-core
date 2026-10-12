import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("anthropic")

from dome_core.llm import LLMOutputTruncatedError  # noqa: E402
from dome_core.llm.claude import ClaudeProvider  # noqa: E402


def _provider(stop_reason: str, text: str = '{"ok": true}') -> ClaudeProvider:
    provider = ClaudeProvider(api_key="test", model="test-model", max_tokens=100)

    async def create(**kwargs):
        return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(text=text)])

    provider._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return provider


def test_generate_returns_text_when_complete():
    assert asyncio.run(_provider("end_turn").generate("hi")) == '{"ok": true}'


def test_generate_raises_when_cut_off_at_the_token_limit():
    with pytest.raises(LLMOutputTruncatedError) as info:
        asyncio.run(_provider("max_tokens", '{"fields": [').generate("hi"))
    assert info.value.max_tokens == 100
    assert "100-token limit" in str(info.value)


def test_generate_structured_reports_truncation_not_invalid_json():
    with pytest.raises(LLMOutputTruncatedError):
        asyncio.run(_provider("max_tokens", '{"fields": [').generate_structured("hi", schema={}))


def test_generate_vision_raises_when_cut_off():
    with pytest.raises(LLMOutputTruncatedError):
        asyncio.run(_provider("max_tokens").generate_vision("hi", b"\x89PNG", "image/png"))


def test_truncation_is_still_a_value_error_for_existing_callers():
    assert issubclass(LLMOutputTruncatedError, ValueError)
