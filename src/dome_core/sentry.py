from __future__ import annotations

import os

import sentry_sdk


def init_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", os.getenv("ENVIRONMENT", "development")),
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=_before_send,
    )


def _before_send(event, hint):  # type: ignore[no-untyped-def]
    request = event.get("request", {})
    if "/health" in request.get("url", ""):
        return None

    if "exc_info" in hint:
        exc = hint["exc_info"][1]
        from fastapi import HTTPException

        if isinstance(exc, HTTPException) and exc.status_code in (401, 403, 404, 429):
            return None

    return event
