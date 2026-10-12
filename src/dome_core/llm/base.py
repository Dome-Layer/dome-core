from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class LLMOutputTruncatedError(ValueError):
    """The model stopped at the output token limit, so its answer is incomplete.

    A ValueError subclass so callers that already treat unparseable model output as a
    ValueError keep working; catch this first to handle truncation on its own.
    """

    def __init__(self, max_tokens: int) -> None:
        self.max_tokens = max_tokens
        super().__init__(f"LLM output was cut off at the {max_tokens}-token limit")


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system: Optional[str] = None) -> str: ...

    @abstractmethod
    async def generate_structured(
        self, prompt: str, schema: dict, system: Optional[str] = None
    ) -> dict: ...

    async def generate_vision(
        self,
        prompt: str,
        image: bytes,
        media_type: str = "image/png",
        system: Optional[str] = None,
    ) -> str:
        raise NotImplementedError(f"{type(self).__name__} does not support vision")
