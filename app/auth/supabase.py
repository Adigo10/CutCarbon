"""Verification of Supabase-issued access tokens.

Supabase mints the JWTs; FastAPI only *verifies* them. Newer projects sign with
asymmetric keys (RS256/ES256) published at a JWKS endpoint; older projects (and our
tests) use a shared HS256 secret. Both paths are supported here.
"""
import time

import httpx
from jose import jwt
from jose.exceptions import JWTError

from app.config import settings


class TokenError(Exception):
    """Raised when a token is missing, malformed, or fails verification."""


# Simple in-process JWKS cache: {kid: jwk_dict}, refreshed on TTL or unknown kid.
_jwks_cache: dict = {"keys_by_kid": {}, "fetched_at": 0.0}


def _jwks_url() -> str:
    if settings.SUPABASE_JWKS_URL:
        return settings.SUPABASE_JWKS_URL
    base = settings.SUPABASE_URL.rstrip("/")
    return f"{base}/auth/v1/.well-known/jwks.json"


def _issuer() -> str:
    return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"


async def _load_jwks(force: bool = False) -> dict:
    now = time.monotonic()
    fresh = (now - _jwks_cache["fetched_at"]) < settings.SUPABASE_JWKS_CACHE_TTL
    if _jwks_cache["keys_by_kid"] and fresh and not force:
        return _jwks_cache["keys_by_kid"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_jwks_url())
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        # Keys rarely rotate: serve the last-known-good set through a transient JWKS
        # outage so a blip degrades to "can't verify new kids" rather than a hard 500.
        if _jwks_cache["keys_by_kid"]:
            return _jwks_cache["keys_by_kid"]
        raise TokenError("unable to fetch Supabase JWKS")

    keys_by_kid = {k.get("kid"): k for k in data.get("keys", [])}
    _jwks_cache["keys_by_kid"] = keys_by_kid
    _jwks_cache["fetched_at"] = now
    return keys_by_kid


async def verify_supabase_token(token: str) -> dict:
    """Verify a Supabase access token and return its claims.

    Checks the signature (JWKS for RS256/ES256, shared secret for HS256), plus the
    audience and issuer, and requires `sub` + `email`. Raises TokenError on any failure.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise TokenError("malformed token") from exc

    alg = header.get("alg")
    common = {"audience": settings.SUPABASE_JWT_AUD, "issuer": _issuer()}

    if alg == "HS256":
        if not settings.SUPABASE_JWT_SECRET:
            raise TokenError("HS256 token but SUPABASE_JWT_SECRET is not configured")
        key = settings.SUPABASE_JWT_SECRET
        algorithms = ["HS256"]
    elif alg in ("RS256", "ES256"):
        kid = header.get("kid")
        keys = await _load_jwks()
        key = keys.get(kid)
        if key is None:  # unknown kid → keys may have rotated; refetch once
            keys = await _load_jwks(force=True)
            key = keys.get(kid)
        if key is None:
            raise TokenError("no matching JWKS key for token kid")
        algorithms = [alg]
    else:
        raise TokenError(f"unsupported token algorithm: {alg!r}")

    try:
        claims = jwt.decode(token, key, algorithms=algorithms, **common)
    except JWTError as exc:
        raise TokenError(str(exc)) from exc

    if not claims.get("sub") or not claims.get("email"):
        raise TokenError("token missing required sub/email claims")
    return claims
