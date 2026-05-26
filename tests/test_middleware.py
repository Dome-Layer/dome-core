import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dome_core.middleware import SecurityHeadersMiddleware


@pytest.fixture
def app_production():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, environment="production")

    @app.get("/test")
    def _():
        return {"ok": True}

    return app


@pytest.fixture
def app_development():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, environment="development")

    @app.get("/test")
    def _():
        return {"ok": True}

    return app


def test_security_headers_production(app_production):
    client = TestClient(app_production)
    resp = client.get("/test")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" in resp.headers


def test_no_hsts_in_development(app_development):
    client = TestClient(app_development)
    resp = client.get("/test")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" not in resp.headers
