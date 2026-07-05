from fastapi.testclient import TestClient

from app.rate_limit import limiter

from helpers import register_user


def test_register_login_me_roundtrip(client: TestClient):
    headers = register_user(client, email="roundtrip@example.com")

    login = client.post(
        "/api/auth/login",
        json={"email": "roundtrip@example.com", "password": "super-secret"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["access_token"]
    assert body["user"]["email"] == "roundtrip@example.com"

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "roundtrip@example.com"


def test_duplicate_email_rejected(client: TestClient):
    register_user(client, email="dupe@example.com")
    response = client.post(
        "/api/auth/register",
        json={"email": "dupe@example.com", "password": "super-secret"},
    )
    assert response.status_code == 400


def test_invalid_email_rejected(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "super-secret"},
    )
    assert response.status_code == 422


def test_short_password_rejected(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "seven77"},
    )
    assert response.status_code == 422


def test_wrong_password_rejected(client: TestClient):
    register_user(client, email="locked@example.com")
    response = client.post(
        "/api/auth/login",
        json={"email": "locked@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_form_token_endpoint_works_for_swagger(client: TestClient):
    register_user(client, email="swagger@example.com")
    response = client.post(
        "/api/auth/token",
        data={"username": "swagger@example.com", "password": "super-secret"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200


def test_register_rate_limited(client: TestClient):
    """5/minute per IP on register — the 6th request in a burst gets 429."""
    limiter.enabled = True
    try:
        statuses = [
            client.post(
                "/api/auth/register",
                json={"email": f"burst{i}@example.com", "password": "super-secret"},
            ).status_code
            for i in range(6)
        ]
    finally:
        limiter.enabled = False
        limiter.reset()

    assert statuses[-1] == 429
    assert all(code == 201 for code in statuses[:5])
