"""Immutable report snapshots + engine versioning.

Covers: ENGINE_VERSION stamped into the factors snapshot, the write-on-export
report_snapshots row, listing/retrieval with ownership enforcement, canonical
sha256 stability, the PDF provenance footer, and the factor-drift serializer field.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.models.database import ScenarioDB
from app.models.schemas import EventScenarioInput
from app.routers.exports import (
    _provenance_footer_text,
    canonical_payload_json,
    payload_sha256,
)
from app.services.emissions_engine import EF, ENGINE_VERSION, build_factors_snapshot
from app.services.scenario_serializer import serialize_scenario

from helpers import auth_headers, create_scenario, register_user

REPORT_FORMATS = ["json", "csv", "xlsx", "pdf"]


# -- Part A: engine versioning -------------------------------------------------

def test_engine_version_is_semver():
    parts = ENGINE_VERSION.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts), ENGINE_VERSION


def test_factors_snapshot_records_engine_and_ef_version():
    snapshot = build_factors_snapshot(EventScenarioInput(name="v", attendees=10, event_days=1))
    assert snapshot["engine_version"] == ENGINE_VERSION
    assert snapshot["ef_version"] == EF.get("version", "unknown")


# -- sha256 canonicalization ---------------------------------------------------

def test_canonical_json_is_key_order_independent():
    a = {"b": 1, "a": {"y": 2, "x": [3, 4]}}
    b = {"a": {"x": [3, 4], "y": 2}, "b": 1}
    assert canonical_payload_json(a) == canonical_payload_json(b)
    assert payload_sha256(a) == payload_sha256(b)


def test_canonical_json_distinguishes_different_payloads():
    assert payload_sha256({"a": 1}) != payload_sha256({"a": 2})


def test_payload_sha256_is_hex_digest():
    digest = payload_sha256({"a": 1})
    assert len(digest) == 64
    int(digest, 16)  # raises if not hex


# -- Part C: PDF provenance footer ---------------------------------------------

def test_provenance_footer_shows_versions_and_short_digest():
    digest = "a" * 64
    text = _provenance_footer_text("2026.1", "2.0.0", digest)
    assert "2026.1" in text
    assert "2.0.0" in text
    assert digest[:12] in text
    assert digest not in text  # only the first 12 hex chars are printed


def test_provenance_footer_tolerates_missing_snapshot():
    assert _provenance_footer_text("", "", "") == ""


# -- Part C: write-on-export + retrieval (DB-backed) ---------------------------

@pytest.mark.parametrize("fmt", REPORT_FORMATS)
def test_export_writes_one_report_snapshot(client: TestClient, fmt: str):
    headers = register_user(client)
    scenario_id = create_scenario(client, headers)["scenario_id"]

    export = client.get(f"/api/exports/scenarios/{scenario_id}.{fmt}", headers=headers)
    assert export.status_code == 200

    listing = client.get(f"/api/scenarios/{scenario_id}/reports", headers=headers)
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["format"] == fmt
    assert row["ef_version"] == EF.get("version", "unknown")
    assert row["engine_version"] == ENGINE_VERSION
    assert len(row["sha256"]) == 64
    assert row["created_at"]
    # The listing is metadata-only — the payload is fetched separately.
    assert "payload" not in row


def test_report_snapshot_payload_hash_matches_stored_digest(client: TestClient):
    headers = register_user(client)
    scenario_id = create_scenario(client, headers)["scenario_id"]

    assert client.get(f"/api/exports/scenarios/{scenario_id}.json", headers=headers).status_code == 200
    row = client.get(f"/api/scenarios/{scenario_id}/reports", headers=headers).json()[0]

    detail = client.get(f"/api/reports/{row['id']}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == row["id"]
    assert body["sha256"] == row["sha256"]
    assert body["payload"]["scenario"]["scenario_id"] == scenario_id
    # The stored payload re-hashes to exactly the recorded digest (tamper-evidence).
    assert payload_sha256(body["payload"]) == row["sha256"]


def test_report_snapshots_accumulate_and_are_newest_first(client: TestClient):
    headers = register_user(client)
    scenario_id = create_scenario(client, headers)["scenario_id"]

    for fmt in REPORT_FORMATS:
        assert client.get(f"/api/exports/scenarios/{scenario_id}.{fmt}", headers=headers).status_code == 200

    rows = client.get(f"/api/scenarios/{scenario_id}/reports", headers=headers).json()
    assert len(rows) == len(REPORT_FORMATS)
    assert {r["format"] for r in rows} == set(REPORT_FORMATS)
    assert [r["created_at"] for r in rows] == sorted((r["created_at"] for r in rows), reverse=True)


def test_report_snapshot_endpoints_require_auth(client: TestClient):
    assert client.get("/api/scenarios/missing/reports").status_code == 401
    assert client.get("/api/reports/missing").status_code == 401


def test_report_snapshots_are_scoped_to_the_owning_user(client: TestClient):
    owner = register_user(client)
    scenario_id = create_scenario(client, owner)["scenario_id"]
    assert client.get(f"/api/exports/scenarios/{scenario_id}.json", headers=owner).status_code == 200
    snapshot_id = client.get(f"/api/scenarios/{scenario_id}/reports", headers=owner).json()[0]["id"]

    intruder = auth_headers("intruder@example.com")
    client.get("/api/auth/me", headers=intruder)  # JIT-provision the second profile

    assert client.get(f"/api/scenarios/{scenario_id}/reports", headers=intruder).status_code == 404
    assert client.get(f"/api/reports/{snapshot_id}", headers=intruder).status_code == 404
    # The owner is unaffected.
    assert client.get(f"/api/reports/{snapshot_id}", headers=owner).status_code == 200


def test_unknown_report_snapshot_is_404(client: TestClient):
    headers = register_user(client)
    assert client.get("/api/reports/00000000-0000-0000-0000-000000000000", headers=headers).status_code == 404


# -- Part D: factor-drift badge -------------------------------------------------

def _row(snapshot: dict | None) -> ScenarioDB:
    return ScenarioDB(
        id="s1",
        name="S",
        event_type="conference",
        attendees=10,
        event_days=1,
        total_tco2e=1.0,
        per_attendee_tco2e=0.1,
        factors_snapshot=snapshot,
    )


def test_serializer_reports_current_versions_and_not_stale_for_fresh_snapshot():
    data = serialize_scenario(_row({"ef_version": EF.get("version"), "engine_version": ENGINE_VERSION}))
    assert data["current_ef_version"] == EF.get("version", "unknown")
    assert data["current_engine_version"] == ENGINE_VERSION
    assert data["factors_stale"] is False


@pytest.mark.parametrize(
    "snapshot",
    [
        {"ef_version": "1999.1", "engine_version": ENGINE_VERSION},   # stale factor catalog
        {"ef_version": EF.get("version"), "engine_version": "1.0.0"},  # stale engine
        {"ef_version": EF.get("version")},                             # pre-versioning snapshot
    ],
)
def test_serializer_flags_stale_snapshots(snapshot):
    assert serialize_scenario(_row(snapshot))["factors_stale"] is True


def test_serializer_does_not_flag_scenarios_without_a_snapshot():
    # Nothing was captured, so there is nothing to be stale against.
    assert serialize_scenario(_row(None))["factors_stale"] is False


def test_scenario_api_exposes_drift_fields(client: TestClient):
    headers = register_user(client)
    scenario = create_scenario(client, headers)
    assert scenario["factors_stale"] is False
    assert scenario["current_ef_version"] == EF.get("version", "unknown")
    assert scenario["current_engine_version"] == ENGINE_VERSION
    assert scenario["factors_snapshot"]["engine_version"] == ENGINE_VERSION


def test_report_snapshot_payload_is_json_serializable(client: TestClient):
    headers = register_user(client)
    scenario_id = create_scenario(client, headers)["scenario_id"]
    assert client.get(f"/api/exports/scenarios/{scenario_id}.pdf", headers=headers).status_code == 200
    row = client.get(f"/api/scenarios/{scenario_id}/reports", headers=headers).json()[0]
    payload = client.get(f"/api/reports/{row['id']}", headers=headers).json()["payload"]
    json.dumps(payload)  # round-trips cleanly out of JSONB
