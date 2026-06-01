"""Local JWT verification for the DOME portfolio (DA-005).

Supabase issues short-lived **ES256** access tokens signed with an asymmetric key
whose *public* half is published at ``{SUPABASE_URL}/auth/v1/.well-known/jwks.json``.
Verifying the signature locally against that public key removes the per-request
``supabase.auth.get_user`` network round-trip (latency + single point of failure +
auth-rate-limit ceiling) and creates an offline-capable path: the JWKS can be
fetched-and-cached, or bundled as a static document for an air-gapped deployment.

Public surface:
  * :class:`Principal` — the verified caller.
  * :func:`verify_jwt` — local verify with an optional network fallback.
  * :func:`make_require_user` — the single FastAPI dependency new repos should use.
  * :func:`make_supabase_fallback` — wraps the legacy ``get_user`` as a fallback.

Failure policy: a genuinely invalid token (bad signature, expired, wrong
audience/issuer, malformed) always raises :class:`AuthError` and is **never**
forwarded to the fallback. The fallback fires only on *infrastructure* failure
(JWKS unreachable, signing key not found, no source configured) so a transient
JWKS outage degrades to the old behaviour rather than locking everyone out.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Callable

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient
from pydantic import BaseModel, Field

DEFAULT_AUDIENCE = "authenticated"
_JWKS_PATH = "/auth/v1/.well-known/jwks.json"
_ISSUER_PATH = "/auth/v1"
_DEFAULT_ALGORITHMS = ["ES256"]

NetworkFallback = Callable[[str], "Principal"]


class Principal(BaseModel):
    """An authenticated caller derived from a verified access token."""

    user_id: str
    email: str | None = None
    claims: dict[str, Any] = Field(default_factory=dict)


class AuthError(Exception):
    """A token could not be verified (bad signature, expired, bad claims, or
    local verification failed with no usable fallback)."""


# ── JWKS client cache ─────────────────────────────────────────────────────────
# One PyJWKClient per JWKS URL, reused across requests so the fetched key set
# (and its short-lived cache) is shared. PyJWKClient is internally thread-safe
# for reads; we guard creation only.
_jwks_clients: dict[str, PyJWKClient] = {}
_jwks_lock = threading.Lock()


def _strip(url: str) -> str:
    return url.rstrip("/")


def jwks_url_from_supabase(supabase_url: str) -> str:
    """Derive the public JWKS URL from a Supabase project URL."""
    return _strip(supabase_url) + _JWKS_PATH


def issuer_from_supabase(supabase_url: str) -> str:
    """Derive the expected ``iss`` claim from a Supabase project URL."""
    return _strip(supabase_url) + _ISSUER_PATH


def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    client = _jwks_clients.get(jwks_url)
    if client is None:
        with _jwks_lock:
            client = _jwks_clients.get(jwks_url)
            if client is None:
                client = PyJWKClient(jwks_url, cache_keys=True, lifespan=600)
                _jwks_clients[jwks_url] = client
    return client


def reset_jwks_cache() -> None:
    """Clear the cached JWKS clients (useful in tests)."""
    with _jwks_lock:
        _jwks_clients.clear()


def _principal_from_claims(claims: dict[str, Any]) -> Principal:
    sub = claims.get("sub")
    if not sub:
        raise AuthError("token missing 'sub' claim")
    return Principal(user_id=str(sub), email=claims.get("email"), claims=claims)


def _signing_key_from_static_jwks(token: str, jwks: dict[str, Any] | str) -> Any:
    """Return the cryptographic key matching the token's ``kid`` from a static
    JWKS document (no network). Raises on a missing match so the caller can fall
    back."""
    jwk_set = jwt.PyJWKSet.from_dict(jwks if isinstance(jwks, dict) else json.loads(jwks))
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    for key in jwk_set.keys:
        if kid is None or key.key_id == kid:
            return key.key
    raise LookupError(f"no JWK matching kid {kid!r} in static JWKS")


def verify_jwt(
    token: str,
    *,
    supabase_url: str | None = None,
    jwks_url: str | None = None,
    jwks: dict[str, Any] | str | None = None,
    audience: str | None = DEFAULT_AUDIENCE,
    issuer: str | None = None,
    verify_iss: bool = False,
    leeway: int = 10,
    algorithms: list[str] | None = None,
    network_fallback: NetworkFallback | None = None,
) -> Principal:
    """Verify a Supabase access token locally and return a :class:`Principal`.

    Signing-key resolution (first available wins):
      1. ``jwks`` — a static JWKS dict/JSON string (no network; air-gapped path).
      2. ``jwks_url`` — fetched and cached via ``PyJWKClient``.
      3. ``supabase_url`` — JWKS URL (and issuer) derived from it.

    ``audience`` defaults to Supabase's ``"authenticated"``; pass ``None`` to skip
    the audience check. Issuer is checked only when ``verify_iss`` is true (the
    issuer is derived from ``supabase_url`` if not given explicitly).

    On an *infrastructure* failure ``network_fallback`` is invoked if provided;
    an invalid/expired token always raises :class:`AuthError`.
    """
    algs = algorithms or _DEFAULT_ALGORITHMS
    if issuer is None and supabase_url:
        issuer = issuer_from_supabase(supabase_url)

    # 1) Resolve the signing key. Malformed tokens raise AuthError; any other
    #    failure here is "infrastructure" and is eligible for the fallback.
    try:
        if jwks is not None:
            signing_key = _signing_key_from_static_jwks(token, jwks)
        else:
            url = jwks_url or (jwks_url_from_supabase(supabase_url) if supabase_url else None)
            if not url:
                raise RuntimeError("no JWKS source configured (set jwks, jwks_url or supabase_url)")
            signing_key = _get_jwks_client(url).get_signing_key_from_jwt(token).key
    except jwt.DecodeError as exc:
        raise AuthError(f"malformed token header: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — JWKS unreachable / no kid / misconfig
        return _fallback_or_raise(token, network_fallback, repr(exc))

    # 2) Verify signature + claims locally. A bad token never reaches the fallback.
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key,
            algorithms=algs,
            audience=audience,
            issuer=issuer if verify_iss else None,
            leeway=leeway,
            options={"verify_aud": audience is not None, "verify_iss": verify_iss},
        )
    except jwt.InvalidTokenError as exc:
        raise AuthError(str(exc)) from exc

    return _principal_from_claims(claims)


def _fallback_or_raise(
    token: str, network_fallback: NetworkFallback | None, reason: str
) -> Principal:
    if network_fallback is not None:
        try:
            return network_fallback(token)
        except AuthError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AuthError(f"local verify and network fallback both failed: {exc}") from exc
    raise AuthError(f"unable to verify token locally: {reason}")


def make_supabase_fallback(client_getter: Callable[[], Any]) -> NetworkFallback:
    """Build a :data:`NetworkFallback` that validates a token via the legacy
    ``supabase.auth.get_user`` call. ``client_getter`` returns a Supabase client
    (or ``None`` when auth is not configured)."""

    def _fallback(token: str) -> Principal:
        client = client_getter()
        if client is None:
            raise AuthError("auth backend unavailable")
        resp = client.auth.get_user(token)
        user = getattr(resp, "user", None)
        if user is None:
            raise AuthError("invalid or expired token")
        return Principal(user_id=str(user.id), email=getattr(user, "email", None), claims={})

    return _fallback


def make_require_user(
    *,
    supabase_url_getter: Callable[[], str | None],
    jwks: dict[str, Any] | str | None = None,
    audience: str | None = DEFAULT_AUDIENCE,
    verify_iss: bool = False,
    optional: bool = False,
    dev_bypass_user: str | None = None,
    network_fallback_getter: Callable[[], NetworkFallback | None] | None = None,
) -> Callable[[Request], Principal | None]:
    """Build the single FastAPI auth dependency new DOME repos should consume.

    Returns a dependency that yields a verified :class:`Principal`. With
    ``optional=True`` a missing/blank Authorization header yields ``None`` (but a
    *present* invalid token still 401s — never silently demoted to anonymous).
    ``dev_bypass_user`` short-circuits to a fixed principal for local dev only.
    """

    def dependency(request: Request) -> Principal | None:
        if dev_bypass_user:
            return Principal(user_id=dev_bypass_user, claims={"dev_bypass": True})

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            if optional:
                return None
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

        token = auth_header.removeprefix("Bearer ").strip()
        fallback = network_fallback_getter() if network_fallback_getter else None
        try:
            return verify_jwt(
                token,
                supabase_url=supabase_url_getter(),
                jwks=jwks,
                audience=audience,
                verify_iss=verify_iss,
                network_fallback=fallback,
            )
        except AuthError as exc:
            raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc

    return dependency
