from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

from dome_core.logging import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


def is_retryable(exc: Exception) -> bool:
    try:
        import anthropic
    except ImportError:
        return False
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in (529, 500, 502, 503, 504)
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    return False


async def with_retry(
    coro_fn: Callable[..., Coroutine[Any, Any, Any]],
    *args: Any,
    max_retries: int = MAX_RETRIES,
    base_delay: float = RETRY_BASE_DELAY,
    **kwargs: Any,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as exc:
            if not is_retryable(exc):
                raise
            last_exc = exc
            delay = base_delay * (2**attempt)
            logger.warning(
                "llm_retrying",
                attempt=attempt + 1,
                max_retries=max_retries,
                delay=delay,
                error=str(exc),
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]
