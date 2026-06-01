"""Tests for dome_core.auth — local ES256 JWT verification (DA-005).

Keys are minted locally so the suite never touches the network: an EC P-256
key pair is generated, its public half exported as a JWK, and tokens are signed
with the private half. The JWKS is passed to ``verify_jwt`` as a static
document (also exercising the air-gapped path).
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jwt.algorithms import ECAlgorithm

from dome_core.auth import (
    AuthError,
    Principal,
    issuer_from_supabase,
    jwks_url_from_supabase,
    make_require_user,
    make_supabase_fallback,
    reset_jwks_cache,
    verify_jwt,
)

KID = "test-kid-1"
SUPABASE_URL = "https://proj.supabase.co"
ISSUER = issuer_from_supabase(SUPABASE_URL)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    reset_jwks_cache()


@pytest.fixture(scope="module")
def keypair() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(scope="module")
def jwks(keypair: ec.EllipticCurvePrivateKey) -> dict[str, Any]:
    jwk = json.loads(ECAlgorithm.to_jwk(keypair.public_key()))
    jwk.update({"kid": KID, "alg": "ES256", "use": "sig"})
    return {"keys": [jwk]}


def _make_token(
    keypair: ec.EllipticCurvePrivateKey,
    *,
    sub: str = "user-123",
    email: str = "a@b.com",
    aud: str = "authenticated",
    iss: str = ISSUER,
    expires_in: int = 3600,
    kid: str = KID,
) -> str:
    now = dt.datetime.now(tz=dt.timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": now + dt.timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, keypair, algorithm="ES256", headers={"kid": kid})


# ── happy path ────────────────────────────────────────────────────────────────


def test_valid_token_returns_principal(keypair, jwks):
    token = _make_token(keypair)
    p = verify_jwt(token, jwks=jwks)
    assert isinstance(p, Principal)
    assert p.user_id == "user-123"
    assert p.email == "a@b.com"
    assert p.claims["aud"] == "authenticated"


def test_valid_token_via_static_jwks_string(keypair, jwks):
    token = _make_token(keypair)
    p = verify_jwt(token, jwks=json.dumps(jwks))
    assert p.user_id == "user-123"


def test_issuer_checked_when_enabled(keypair, jwks):
    token = _make_token(keypair, iss="https://evil.example/auth/v1")
    with pytest.raises(AuthError):
        verify_jwt(token, jwks=jwks, supabase_url=SUPABASE_URL, verify_iss=True)
    # same token passes when issuer verification is off (default)
    assert verify_jwt(token, jwks=jwks).user_id == "user-123"


# ── invalid tokens must raise AuthError and NOT hit the fallback ───────────────


def _counting_fallback() -> tuple[Any, dict[str, int]]:
    calls = {"n": 0}

    def _fb(token: str) -> Principal:
        calls["n"] += 1
        return Principal(user_id="fallback-user")

    return _fb, calls


def test_expired_token_raises_and_skips_fallback(keypair, jwks):
    token = _make_token(keypair, expires_in=-10)
    fb, calls = _counting_fallback()
    with pytest.raises(AuthError):
        verify_jwt(token, jwks=jwks, network_fallback=fb)
    assert calls["n"] == 0  # an invalid token is never sent to the fallback


def test_bad_signature_raises(keypair, jwks):
    other = ec.generate_private_key(ec.SECP256R1())
    token = _make_token(other)  # signed by a different key, same kid
    with pytest.raises(AuthError):
        verify_jwt(token, jwks=jwks)


def test_wrong_audience_raises(keypair, jwks):
    token = _make_token(keypair, aud="anon")
    with pytest.raises(AuthError):
        verify_jwt(token, jwks=jwks)


def test_audience_none_skips_check(keypair, jwks):
    token = _make_token(keypair, aud="anon")
    assert verify_jwt(token, jwks=jwks, audience=None).user_id == "user-123"


def test_malformed_token_raises(jwks):
    with pytest.raises(AuthError):
        verify_jwt("not.a.jwt", jwks=jwks)


def test_missing_sub_raises(keypair):
    jwk = json.loads(ECAlgorithm.to_jwk(keypair.public_key()))
    jwk.update({"kid": KID, "alg": "ES256", "use": "sig"})
    now = dt.datetime.now(tz=dt.timezone.utc)
    token = jwt.encode(
        {"email": "a@b.com", "aud": "authenticated", "exp": now + dt.timedelta(hours=1)},
        keypair,
        algorithm="ES256",
        headers={"kid": KID},
    )
    with pytest.raises(AuthError):
        verify_jwt(token, jwks={"keys": [jwk]})


# ── infrastructure failures use the fallback ───────────────────────────────────


def test_unknown_kid_uses_fallback(keypair, jwks):
    token = _make_token(keypair, kid="some-other-kid")
    fb, calls = _counting_fallback()
    p = verify_jwt(token, jwks=jwks, network_fallback=fb)
    assert calls["n"] == 1
    assert p.user_id == "fallback-user"


def test_no_source_uses_fallback(keypair):
    token = _make_token(keypair)
    fb, calls = _counting_fallback()
    p = verify_jwt(token, network_fallback=fb)
    assert calls["n"] == 1
    assert p.user_id == "fallback-user"


def test_no_source_no_fallback_raises(keypair):
    token = _make_token(keypair)
    with pytest.raises(AuthError):
        verify_jwt(token)


def test_fallback_raising_autherror_propagates(keypair):
    token = _make_token(keypair)

    def _fb(_: str) -> Principal:
        raise AuthError("invalid or expired token")

    with pytest.raises(AuthError):
        verify_jwt(token, network_fallback=_fb)


# ── make_supabase_fallback ─────────────────────────────────────────────────────


class _FakeUser:
    id = "supa-user"
    email = "x@y.com"


class _FakeResp:
    user = _FakeUser()


class _FakeAuth:
    def get_user(self, token: str) -> _FakeResp:
        return _FakeResp()


class _FakeClient:
    auth = _FakeAuth()


def test_supabase_fallback_maps_user():
    fb = make_supabase_fallback(lambda: _FakeClient())
    p = fb("tok")
    assert p.user_id == "supa-user"
    assert p.email == "x@y.com"


def test_supabase_fallback_none_client_raises():
    fb = make_supabase_fallback(lambda: None)
    with pytest.raises(AuthError):
        fb("tok")


# ── make_require_user FastAPI dependency ───────────────────────────────────────


def _app(**kwargs: Any) -> FastAPI:
    dep = make_require_user(supabase_url_getter=lambda: None, **kwargs)
    app = FastAPI()

    @app.get("/me")
    def me(principal: Any = Depends(dep)) -> dict[str, Any]:
        return {"user_id": principal.user_id if principal else None}

    return app


def test_require_user_valid(keypair, jwks):
    client = TestClient(_app(jwks=jwks))
    token = _make_token(keypair)
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "user-123"


def test_require_user_missing_header_401(jwks):
    client = TestClient(_app(jwks=jwks))
    assert client.get("/me").status_code == 401


def test_require_user_optional_missing_header_returns_none(jwks):
    client = TestClient(_app(jwks=jwks, optional=True))
    resp = client.get("/me")
    assert resp.status_code == 200
    assert resp.json()["user_id"] is None


def test_require_user_optional_present_but_invalid_401(jwks):
    # a present-but-invalid token must NOT be silently demoted to anonymous
    client = TestClient(_app(jwks=jwks, optional=True))
    resp = client.get("/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_require_user_dev_bypass(jwks):
    client = TestClient(_app(jwks=jwks, dev_bypass_user="00000000-0000-0000-0000-000000000000"))
    resp = client.get("/me")  # no header needed
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "00000000-0000-0000-0000-000000000000"


def test_jwks_url_and_issuer_helpers():
    assert jwks_url_from_supabase("https://p.supabase.co/") == (
        "https://p.supabase.co/auth/v1/.well-known/jwks.json"
    )
    assert issuer_from_supabase("https://p.supabase.co") == "https://p.supabase.co/auth/v1"
