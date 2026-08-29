from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.services.claims import CLAIM_INTEGRITY_CAVEAT, find_banned_claims

from helpers import create_scenario, register_user

# Integrity evidence that makes a purchase claim-eligible (see app/services/offset_integrity.py).
CLAIM_EVIDENCE = {
    "ccp_approved": True,
    "methodology": "GS-VER Methodology for Grid-Connected Renewables v3",
    "retirement_serial": "GS1-1234-5678-9012",
    "retirement_date": "2026-03-01",
    "country": "IN",
}


def _purchase(client: TestClient, headers, scenario_id=None, qty=2.0, price=10.0, **extra):
    payload = {
        "scenario_id": scenario_id,
        "project_type": "renewable_energy",
        "registry": "gold_standard",
        "quantity_tco2e": qty,
        "price_per_tco2e_usd": price,
        "vintage_year": 2025,
    }
    payload.update(extra)
    response = client.post("/api/offsets", json=payload, headers=headers)
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
    # what is still outstanding, rather than reading as full compensation. The credit
    # carries no integrity evidence, so the statement is caveated (see Part D).
    assert summary["claim_statement"] == (
        f"{total:.3f} tCO2e measured, 0.0% reduced, 3.000 of {total:.3f} tCO2e residual "
        f"compensated outside the value chain via retired credits from Gold Standard; "
        f"{total - 3.0:.3f} tCO2e residual not yet compensated" + CLAIM_INTEGRITY_CAVEAT
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


def test_purchase_records_integrity_metadata_and_is_claim_eligible(client: TestClient):
    headers = register_user(client, email="integrity@example.com")
    purchase = _purchase(client, headers, vintage_year=2026, **CLAIM_EVIDENCE)

    assert purchase["ccp_approved"] is True
    assert purchase["article6_adjustment"] is None
    assert purchase["methodology"] == CLAIM_EVIDENCE["methodology"]
    assert purchase["retirement_serial"] == CLAIM_EVIDENCE["retirement_serial"]
    assert purchase["retirement_date"] == "2026-03-01"
    assert purchase["country"] == "IN"
    assert purchase["claim_eligible"] is True

    # It survives the round trip through the list endpoint too.
    listed = client.get("/api/offsets", headers=headers).json()
    assert [p["claim_eligible"] for p in listed] == [True]


def test_purchase_without_integrity_evidence_is_not_claim_eligible(client: TestClient):
    headers = register_user(client, email="no-evidence@example.com")

    bare = _purchase(client, headers)
    assert bare["claim_eligible"] is False
    assert bare["retirement_serial"] is None

    # A CCP label without registry retirement evidence is still not enough.
    partial = _purchase(client, headers, ccp_approved=True)
    assert partial["claim_eligible"] is False

    # Article 6.4 corresponding adjustment is the other accepted route.
    article6 = _purchase(
        client,
        headers,
        article6_adjustment=True,
        retirement_serial="A6-0001",
        retirement_date="2026-01-15",
    )
    assert article6["claim_eligible"] is True

    # Retiring keeps the flag (it is about evidence, not lifecycle state).
    retired = client.post(f"/api/offsets/{article6['id']}/retire", headers=headers).json()
    assert retired["claim_eligible"] is True


def test_vintage_older_than_the_linked_event_year_is_flagged_stale(client: TestClient):
    headers = register_user(client, email="vintage@example.com")
    scenario_id = create_scenario(client, headers)["scenario_id"]
    event_year = datetime.now(timezone.utc).year

    stale = _purchase(client, headers, scenario_id=scenario_id, vintage_year=event_year - 3)
    assert stale["vintage_stale"] is True

    current = _purchase(client, headers, scenario_id=scenario_id, vintage_year=event_year)
    assert current["vintage_stale"] is False

    # Unlinked purchases have no event year to compare against.
    unlinked = _purchase(client, headers, vintage_year=event_year - 3)
    assert unlinked["vintage_stale"] is False

    listed = {p["id"]: p["vintage_stale"] for p in client.get("/api/offsets", headers=headers).json()}
    assert listed[stale["id"]] is True
    assert listed[current["id"]] is False
    assert listed[unlinked["id"]] is False


def test_recommendations_expose_permanence_and_additionality_risk(client: TestClient):
    headers = register_user(client, email="risk@example.com")
    scenario = create_scenario(client, headers)

    recs = client.get(f"/api/offsets/recommend/{scenario['scenario_id']}", headers=headers).json()
    assert recs
    for rec in recs:
        assert rec["permanence"]
        assert rec["additionality_risk"]
        # The default mix carries no high-risk project type, so no warning fires.
        assert rec["risk_warning"] == ""
        assert rec["basis"] == "gross"


def test_recommendations_size_against_the_residual_net_of_reductions(client: TestClient):
    headers = register_user(client, email="residual@example.com")
    scenario = create_scenario(client, headers)
    total = scenario["emissions"]["total_tco2e"]

    gross = client.get(f"/api/offsets/recommend/{scenario['scenario_id']}", headers=headers).json()
    assert sum(r["recommended_qty_tco2e"] for r in gross) == pytest.approx(total, rel=0.01)
    assert {r["basis"] for r in gross} == {"gross"}
    assert all(r["residual_tco2e"] == pytest.approx(total, abs=0.001) for r in gross)

    net = client.get(
        f"/api/offsets/recommend/{scenario['scenario_id']}?reduction_pct=40",
        headers=headers,
    ).json()
    assert sum(r["recommended_qty_tco2e"] for r in net) == pytest.approx(total * 0.6, rel=0.01)
    assert {r["basis"] for r in net} == {"net_of_reductions"}
    assert all(r["residual_tco2e"] == pytest.approx(total * 0.6, abs=0.001) for r in net)

    # Out-of-range reductions are rejected rather than silently sized to nonsense.
    assert client.get(
        f"/api/offsets/recommend/{scenario['scenario_id']}?reduction_pct=140", headers=headers
    ).status_code == 422


def test_credit_sources_name_only_retired_registries(client: TestClient):
    headers = register_user(client, email="retired-only@example.com")
    scenario = create_scenario(client, headers)
    scenario_id = scenario["scenario_id"]

    _purchase(client, headers, scenario_id=scenario_id, qty=4.0)  # Gold Standard, NOT retired
    verra = _purchase(
        client, headers, scenario_id=scenario_id, qty=1.0, registry="verra_vcs", **CLAIM_EVIDENCE
    )
    client.post(f"/api/offsets/{verra['id']}/retire", headers=headers)

    summary = client.get(f"/api/offsets/portfolio?scenario_id={scenario_id}", headers=headers).json()
    # by_registry stays a portfolio breakdown of everything held...
    assert set(summary["by_registry"]) == {"gold_standard", "verra_vcs"}
    # ...but only the retired credit may be described as compensating the residual.
    assert "retired credits from Verra Vcs" in summary["claim_statement"]
    assert "Gold Standard" not in summary["claim_statement"]


def test_compensation_statement_is_caveated_when_backing_credits_lack_evidence(
    client: TestClient,
):
    headers = register_user(client, email="caveat@example.com")
    scenario = create_scenario(client, headers)
    scenario_id = scenario["scenario_id"]

    clean = _purchase(client, headers, scenario_id=scenario_id, qty=1.0, **CLAIM_EVIDENCE)
    client.post(f"/api/offsets/{clean['id']}/retire", headers=headers)
    summary = client.get(f"/api/offsets/portfolio?scenario_id={scenario_id}", headers=headers).json()
    assert CLAIM_INTEGRITY_CAVEAT.strip() not in summary["claim_statement"]

    # One non-eligible credit in the retired mix caveats the whole statement.
    bare = _purchase(client, headers, scenario_id=scenario_id, qty=1.0)
    client.post(f"/api/offsets/{bare['id']}/retire", headers=headers)
    summary = client.get(f"/api/offsets/portfolio?scenario_id={scenario_id}", headers=headers).json()
    assert summary["claim_statement"].endswith(CLAIM_INTEGRITY_CAVEAT.strip())
    assert find_banned_claims(summary["claim_statement"]) == []


def test_offsets_cross_user_isolation(client: TestClient):
    headers_a = register_user(client, email="offsets-a@example.com")
    headers_b = register_user(client, email="offsets-b@example.com")
    purchase = _purchase(client, headers_a)

    assert client.post(f"/api/offsets/{purchase['id']}/retire", headers=headers_b).status_code == 404
    assert client.delete(f"/api/offsets/{purchase['id']}", headers=headers_b).status_code == 404
    assert client.get("/api/offsets", headers=headers_b).json() == []
