from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


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
