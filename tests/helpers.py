"""Shared helpers for API-level tests."""

import copy

from fastapi.testclient import TestClient

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
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "super-secret"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


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
