import pytest
from fastapi.testclient import TestClient

from app.services.claims import find_banned_claims

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


def test_portfolio_states_compliant_compensation_instead_of_neutrality(client: TestClient):
    headers = register_user(client, email="claim-portfolio@example.com")
    scenario = create_scenario(client, headers)
    scenario_id = scenario["scenario_id"]
    purchase = _purchase(client, headers, scenario_id=scenario_id, qty=3.0)
    client.post(f"/api/offsets/{purchase['id']}/retire", headers=headers)

    summary = client.get(f"/api/offsets/portfolio?scenario_id={scenario_id}", headers=headers).json()
    total = scenario["emissions"]["total_tco2e"]
    # Only 3 tCO2e of the residual are retired — the statement must say so, and say
    # what is still outstanding, rather than reading as full compensation.
    assert summary["claim_statement"] == (
        f"{total:.3f} tCO2e measured, 0.0% reduced, 3.000 of {total:.3f} tCO2e residual "
        f"compensated outside the value chain via retired credits from Gold Standard; "
        f"{total - 3.0:.3f} tCO2e residual not yet compensated"
    )
    assert find_banned_claims(summary["claim_statement"]) == []

    # No scenario in scope means no measured total, so no statement is asserted.
    assert client.get("/api/offsets/portfolio", headers=headers).json()["claim_statement"] == ""


def test_purchase_notes_are_claim_sanitized_on_save(client: TestClient):
    headers = register_user(client, email="claim-notes@example.com")
    response = client.post(
        "/api/offsets",
        json={
            "project_type": "renewable_energy",
            "registry": "gold_standard",
            "quantity_tco2e": 1.0,
            "price_per_tco2e_usd": 10.0,
            "vintage_year": 2025,
            "notes": "These make the summit carbon neutral.",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert find_banned_claims(response.json()["notes"]) == []


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
