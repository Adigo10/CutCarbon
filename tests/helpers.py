"""Shared helpers for API-level tests."""

import copy
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings


def make_supabase_token(
    email: str,
    *,
    sub: str | None = None,
    expires_in: int = 3600,
    aud: str | None = None,
    issuer: str | None = None,
    secret: str | None = None,
) -> str:
    """Mint an HS256 token shaped like a Supabase access token.

    The verifier's HS256 branch (app/auth/supabase.py) accepts it when signed with the
    test SUPABASE_JWT_SECRET and stamped with the expected audience/issuer — so tests
    exercise the real get_current_user + JIT-provisioning path without hitting Supabase.
    `sub` is derived deterministically from the email so repeated calls map to one user.
    """
    now = datetime.now(timezone.utc)
    claims = {
        "sub": sub or str(uuid.uuid5(uuid.NAMESPACE_URL, email)),
        "email": email,
        "role": "authenticated",
        "aud": aud or settings.SUPABASE_JWT_AUD,
        "iss": issuer or f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    return jwt.encode(claims, secret or settings.SUPABASE_JWT_SECRET, algorithm="HS256")


def auth_headers(email: str, **kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_supabase_token(email, **kwargs)}"}

SEEDED_SCENARIO_PAYLOAD = {
    "name": "APAC Summit Baseline",
    "event_name": "APAC Summit 2026",
    "location": "Singapore",
    "event_type": "conference",
    "attendees": 120,
    "event_days": 2,
    "mode": "basic",
    "travel_segments": [
        {
            "mode": "long_haul_flight",
            "travel_class": "economy",
            "attendees": 40,
            "distance_km": 6200,
            "label": "Long-haul delegates",
        }
    ],
    "venue_energy": {
        "grid_region": "singapore",
        "kwh_consumed": 2500,
        "renewable_pct": 10,
    },
    "accommodation": {
        "accommodation_type": "standard_hotel",
        "room_nights": 90,
    },
    "catering": {
        "catering_type": "vegetarian_meal",
        "meals": 240,
        "include_beverages": True,
        "include_alcohol": False,
        "coffee_tea_cups": 120,
    },
}


def register_user(client: TestClient, email: str = "reporter@example.com") -> dict[str, str]:
    """Return auth headers for `email`.

    There is no server-side registration under Supabase Auth — the profile row is
    JIT-provisioned on the first authenticated request made with these headers.
    """
    return auth_headers(email)


def create_scenario(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    payload = copy.deepcopy(SEEDED_SCENARIO_PAYLOAD)
    payload.update(overrides)
    response = client.post("/api/scenarios", json=payload, headers=headers)
    assert response.status_code == 200
    return response.json()


def create_seeded_scenario(client: TestClient, headers: dict[str, str]) -> str:
    scenario_id = create_scenario(client, headers)["scenario_id"]

    purchase_response = client.post(
        "/api/offsets",
        json={
            "scenario_id": scenario_id,
            "project_type": "renewable_energy",
            "registry": "gold_standard",
            "quantity_tco2e": 2.5,
            "price_per_tco2e_usd": 11.0,
            "vintage_year": 2025,
            "notes": "Seeded test purchase",
        },
        headers=headers,
    )
    assert purchase_response.status_code == 200
    purchase_id = purchase_response.json()["id"]

    retire_response = client.post(f"/api/offsets/{purchase_id}/retire", headers=headers)
    assert retire_response.status_code == 200

    return scenario_id
