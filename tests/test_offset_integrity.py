"""Offset credit integrity — pure tests (no DB).

Covers the VCMI/ICVCM evidence gate, the additionality-risk warning and the
residual sizing basis used by the recommendation endpoint.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.claims import (
    CLAIM_INTEGRITY_CAVEAT,
    find_banned_claims,
    portfolio_claim_statement,
)
from app.services.data_files import CARBON_OFFSETS
from app.services.offset_integrity import (
    additionality_risk_warning,
    claim_eligible,
    residual_basis,
)


def _purchase(**overrides):
    """A purchase carrying complete integrity evidence, minus any overrides."""
    fields = {
        "ccp_approved": True,
        "article6_adjustment": None,
        "vintage_year": 2026,
        "retirement_serial": "GS-1234-5678",
        "retirement_date": date(2026, 3, 1),
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


# -- claim_eligible ------------------------------------------------------------

def test_complete_ccp_evidence_is_claim_eligible():
    assert claim_eligible(_purchase()) is True


def test_article6_adjustment_alone_also_qualifies():
    # Article 6.4 credits (with a corresponding adjustment) are the other route
    # VCMI accepts for retirements from 1 Jan 2026.
    assert claim_eligible(_purchase(ccp_approved=None, article6_adjustment=True)) is True
    assert claim_eligible(_purchase(ccp_approved=False, article6_adjustment=True)) is True


@pytest.mark.parametrize(
    "missing",
    [
        {"ccp_approved": None, "article6_adjustment": None},
        {"ccp_approved": False, "article6_adjustment": False},
        {"retirement_serial": None},
        {"retirement_serial": ""},
        {"retirement_date": None},
        {"vintage_year": None},
    ],
)
def test_missing_integrity_evidence_is_not_claim_eligible(missing):
    assert claim_eligible(_purchase(**missing)) is False


def test_claim_eligible_tolerates_a_purchase_without_the_new_columns():
    # Rows written before the integrity migration have no attributes at all.
    assert claim_eligible(SimpleNamespace(vintage_year=2025)) is False


# -- additionality risk --------------------------------------------------------

def test_high_additionality_risk_carries_a_warning():
    warning = additionality_risk_warning("high")
    assert warning
    assert "additionality" in warning.lower()
    assert find_banned_claims(warning) == []


def test_redd_plus_is_the_high_risk_case_in_the_catalog():
    projects = CARBON_OFFSETS["project_types"]
    assert projects["redd_plus"]["additionality_risk"] == "high"
    assert additionality_risk_warning(projects["redd_plus"]["additionality_risk"])


@pytest.mark.parametrize("risk", ["very low", "low", "medium", "", None])
def test_lower_risk_tiers_carry_no_warning(risk):
    assert additionality_risk_warning(risk) == ""


# -- residual sizing -----------------------------------------------------------

def test_zero_reduction_sizes_against_the_gross_total():
    assert residual_basis(100.0, 0) == (100.0, "gross")
    assert residual_basis(100.0, None) == (100.0, "gross")


def test_reduction_pct_nets_the_committed_reduction_off_the_total():
    residual, basis = residual_basis(100.0, 40)
    assert residual == pytest.approx(60.0)
    assert basis == "net_of_reductions"


def test_reduction_pct_is_clamped_to_a_sane_range():
    assert residual_basis(100.0, 150)[0] == pytest.approx(0.0)
    assert residual_basis(100.0, -20) == (100.0, "gross")


# -- claim statement tie-in ----------------------------------------------------

def test_statement_flags_credits_without_integrity_evidence():
    flagged = portfolio_claim_statement(
        10.0, 10.0, {"verra": 10.0}, credits_claim_eligible=False
    )
    assert flagged.endswith(CLAIM_INTEGRITY_CAVEAT.strip())
    assert find_banned_claims(flagged) == []

    clean = portfolio_claim_statement(10.0, 10.0, {"verra": 10.0})
    assert CLAIM_INTEGRITY_CAVEAT.strip() not in clean


def test_climate_positive_guidance_follows_iso_14068_like_carbon_neutral():
    guidance = CARBON_OFFSETS["retirement_guidance"]["claim_types"]["climate_positive"]
    assert "ISO 14068-1" in guidance
    assert "residual" in guidance.lower()
    # The old wording ("Offset more than 100% ... net negative") invited exactly the
    # claim EU 2024/825 blacklists; the replacement must cite that restriction.
    assert "2024/825" in guidance
