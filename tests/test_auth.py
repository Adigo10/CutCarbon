import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.supabase import TokenError, verify_supabase_token

from helpers import auth_headers, make_supabase_token, register_user


def test_me_provisions_profile_from_token(client: TestClient):
    """First authenticated request JIT-provisions the profile; /me returns it."""
    headers = register_user(client, email="roundtrip@example.com")
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "roundtrip@example.com"
    uuid.UUID(body["id"])  # id is the Supabase auth UUID, serialized as a string


def test_me_provisioning_is_idempotent(client: TestClient):
    headers = register_user(client, email="idem@example.com")
    first = client.get("/api/auth/me", headers=headers).json()
    second = client.get("/api/auth/me", headers=headers).json()
    assert first["id"] == second["id"]
    assert first["email"] == second["email"]


def test_missing_token_rejected(client: TestClient):
    assert client.get("/api/auth/me").status_code == 401


def test_malformed_token_rejected(client: TestClient):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def test_wrong_issuer_rejected(client: TestClient):
    headers = auth_headers("wrongiss@example.com", issuer="https://evil.example.com/auth/v1")
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_wrong_audience_rejected(client: TestClient):
    headers = auth_headers("wrongaud@example.com", aud="anon")
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_expired_token_rejected(client: TestClient):
    headers = auth_headers("expired@example.com", expires_in=-10)
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_bad_signature_rejected(client: TestClient):
    headers = auth_headers("badsig@example.com", secret="a-totally-different-secret-value-1234567890")
    assert client.get("/api/auth/me", headers=headers).status_code == 401


# --- Verifier unit tests (no DB / no network; HS256 path) ---------------------

def test_verifier_accepts_valid_token():
    claims = asyncio.run(verify_supabase_token(make_supabase_token("verify@example.com")))
    assert claims["email"] == "verify@example.com"
    assert claims["sub"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"secret": "different-secret-abcdefghijklmnopqrstuvwxyz"},  # bad signature
        {"issuer": "https://evil.example.com/auth/v1"},            # wrong issuer
        {"aud": "anon"},                                           # wrong audience
        {"expires_in": -10},                                       # expired
    ],
)
def test_verifier_rejects_bad_tokens(kwargs):
    with pytest.raises(TokenError):
        asyncio.run(verify_supabase_token(make_supabase_token("bad@example.com", **kwargs)))
