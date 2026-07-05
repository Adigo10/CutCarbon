import pytest
from fastapi.testclient import TestClient

from helpers import create_scenario, register_user


def _purchase(client: TestClient, headers, scenario_id=None, qty=2.0, price=10.0):
    response = client.post(
        "/api/offsets",
        json={
            "scenario_id": scenario_id,
            "project_type": "renewable_energy",
            "registry": "gold_standard",
            "quantity_tco2e": qty,
            "price_per_tco2e_usd": price,
            "vintage_year": 2025,
        },
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def test_purchase_retire_cancel_lifecycle(client: TestClient):
    headers = register_user(client, email="lifecycle@example.com")

    purchase = _purchase(client, headers)
    assert purchase["status"] == "purchased"
    assert purchase["total_cost_usd"] == pytest.approx(20.0)

    retired = client.post(f"/api/offsets/{purchase['id']}/retire", headers=headers)
    assert retired.status_code == 200
    assert retired.json()["status"] == "retired"
    assert retired.json()["retired_at"]

    # Retiring twice and cancelling a retired credit are both rejected.
    assert client.post(f"/api/offsets/{purchase['id']}/retire", headers=headers).status_code == 400
    assert client.delete(f"/api/offsets/{purchase['id']}", headers=headers).status_code == 400

    second = _purchase(client, headers)
    cancelled = client.delete(f"/api/offsets/{second['id']}", headers=headers)
    assert cancelled.status_code == 200


def test_portfolio_summary_math(client: TestClient):
    headers = register_user(client, email="portfolio@example.com")
    scenario_id = create_scenario(client, headers)["scenario_id"]

    first = _purchase(client, headers, scenario_id=scenario_id, qty=3.0, price=10.0)
    _purchase(client, headers, scenario_id=scenario_id, qty=2.0, price=20.0)
    cancelled = _purchase(client, headers, scenario_id=scenario_id, qty=5.0, price=1.0)

    client.post(f"/api/offsets/{first['id']}/retire", headers=headers)
    client.delete(f"/api/offsets/{cancelled['id']}", headers=headers)

    summary = client.get(f"/api/offsets/portfolio?scenario_id={scenario_id}", headers=headers).json()
    assert summary["total_purchased_tco2e"] == pytest.approx(5.0)  # cancelled excluded
    assert summary["total_retired_tco2e"] == pytest.approx(3.0)
    assert summary["total_cost_usd"] == pytest.approx(3 * 10 + 2 * 20)
    assert summary["coverage_pct"] is not None


def test_recommendations_full_coverage_without_budget(client: TestClient):
    headers = register_user(client, email="recommend@example.com")
    scenario = create_scenario(client, headers)
    residual = scenario["emissions"]["total_tco2e"]

    recs = client.get(f"/api/offsets/recommend/{scenario['scenario_id']}", headers=headers).json()
    assert recs
    total_qty = sum(r["recommended_qty_tco2e"] for r in recs)
    assert total_qty == pytest.approx(residual, rel=0.01)


def test_recommendations_scale_to_budget(client: TestClient):
    headers = register_user(client, email="budget@example.com")
    scenario = create_scenario(client, headers)

    unconstrained = client.get(
        f"/api/offsets/recommend/{scenario['scenario_id']}", headers=headers
    ).json()
    full_cost = sum(r["estimated_cost_usd"] for r in unconstrained)
    budget = full_cost / 3

    recs = client.get(
        f"/api/offsets/recommend/{scenario['scenario_id']}?budget_usd={budget}", headers=headers
    ).json()
    total_cost = sum(r["estimated_cost_usd"] for r in recs)
    assert total_cost <= budget * 1.01
    assert total_cost == pytest.approx(budget, rel=0.05)
    # Mix preserved: same project ordering, proportionally scaled quantities.
    assert [r["project_type"] for r in recs] == [r["project_type"] for r in unconstrained]


def test_offsets_cross_user_isolation(client: TestClient):
    headers_a = register_user(client, email="offsets-a@example.com")
    headers_b = register_user(client, email="offsets-b@example.com")
    purchase = _purchase(client, headers_a)

    assert client.post(f"/api/offsets/{purchase['id']}/retire", headers=headers_b).status_code == 404
    assert client.delete(f"/api/offsets/{purchase['id']}", headers=headers_b).status_code == 404
    assert client.get("/api/offsets", headers=headers_b).json() == []
