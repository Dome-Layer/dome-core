import uuid

import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dome_core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware

# ── SecurityHeadersMiddleware ────────────────────────────────────────────────


def _security_app(environment: str) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, environment=environment)

    @app.get("/test")
    def _():
        return {"ok": True}

    return app


def test_security_headers_production():
    client = TestClient(_security_app("production"))
    resp = client.get("/test")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" in resp.headers


def test_no_hsts_in_development():
    client = TestClient(_security_app("development"))
    resp = client.get("/test")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" not in resp.headers


# ── RequestIDMiddleware ──────────────────────────────────────────────────────


def _request_id_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    def _():
        return {"ok": True}

    @app.get("/context")
    def _context():
        ctx = structlog.contextvars.get_contextvars()
        return {"request_id": ctx.get("request_id")}

    return app


def test_request_id_generated_when_absent():
    client = TestClient(_request_id_app())
    resp = client.get("/test")
    rid = resp.headers["X-Request-Id"]
    uuid.UUID(rid, version=4)


def test_request_id_propagated_when_present():
    client = TestClient(_request_id_app())
    resp = client.get("/test", headers={"X-Request-Id": "my-custom-id"})
    assert resp.headers["X-Request-Id"] == "my-custom-id"


def test_request_id_in_structlog_context():
    client = TestClient(_request_id_app())
    resp = client.get("/context")
    body = resp.json()
    assert body["request_id"] == resp.headers["X-Request-Id"]


def test_request_id_cleared_between_requests():
    client = TestClient(_request_id_app())
    r1 = client.get("/test")
    r2 = client.get("/test")
    assert r1.headers["X-Request-Id"] != r2.headers["X-Request-Id"]


def test_combined_middleware_stack():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, environment="production")
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    def _():
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/test")
    assert "X-Request-Id" in resp.headers
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
