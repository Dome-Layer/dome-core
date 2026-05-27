from __future__ import annotations

import re

_INJECTION_TAG_PATTERN = re.compile(
    r"</?(?:system|user|assistant|instructions|prompt|process_description"
    r"|tool_use|tool_result|function_call|human|admin)\b[^>]*>",
    re.IGNORECASE,
)


def sanitize_user_text(text: str) -> str:
    """Strip XML-like tags that LLM providers interpret as prompt structure markers."""
    return _INJECTION_TAG_PATTERN.sub("", text)
