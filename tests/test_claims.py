"""Green-claims guardrail — pure tests (no DB)."""
import pytest

from app.services.claims import (
    CLAIM_REDACTION,
    compliant_compensation_statement,
    describe_credit_sources,
    find_banned_claims,
    portfolio_claim_statement,
    sanitize_claim_language,
)
from app.services.data_files import CARBON_OFFSETS


@pytest.mark.parametrize(
    "phrase",
    [
        "carbon neutral",
        "carbon-neutral",
        "climate neutral",
        "climate-neutral",
        "climate positive",
        "carbon negative",
        "net zero event",
        "net-zero event",
        "eco-friendly",
        "eco friendly",
        "climate friendly",
        "green event",
    ],
)
def test_every_denylisted_phrase_is_detected(phrase: str):
    assert find_banned_claims(f"We deliver a {phrase} for you.") == [phrase]


def test_detection_is_case_insensitive_and_ordered_by_appearance():
    text = "Our Carbon-Neutral gala is climate positive and ECO FRIENDLY."
    assert find_banned_claims(text) == ["Carbon-Neutral", "climate positive", "ECO FRIENDLY"]


def test_repeated_phrase_reported_once():
    assert find_banned_claims("Carbon neutral? Yes, carbon neutral.") == ["Carbon neutral"]


@pytest.mark.parametrize(
    "text",
    [
        "Net Zero Carbon Events (NZCE) Measurement Methodology v1 categories.",
        "Net-zero by 2050 with 90% absolute reduction",
        "Green Events Tool estimate",
        "Julie's Bicycle Green Events Guide 2023",
        "Offsets are a neutralization entry, not a reduction.",
        "greenhouse gas protocol",
        "Carbon tax savings for a decarbonization roadmap.",
    ],
)
def test_factual_and_proper_noun_wording_is_not_flagged(text: str):
    assert find_banned_claims(text) == []


def test_sanitize_rewrites_claims_and_reports_them():
    clean, replaced = sanitize_claim_language(
        "Your event is carbon neutral thanks to offsets, and eco-friendly too."
    )
    assert replaced == ["carbon neutral", "eco-friendly"]
    assert find_banned_claims(clean) == []
    assert clean.startswith("Your event is ")
    assert clean.endswith(" too.")


def test_sanitize_is_idempotent():
    once, _ = sanitize_claim_language("A climate positive, carbon-neutral green event.")
    twice, replaced = sanitize_claim_language(once)
    assert twice == once
    assert replaced == []


def test_rewrites_are_redactions_not_counter_claims():
    """A rewrite must never assert a reduction, a compensation or a comparison
    the data does not back — swapping "carbon neutral" for "measured, reduced and
    residual-compensated" (or "eco-friendly" for "lower-carbon") would just trade
    one unsubstantiated claim for another."""
    clean, replaced = sanitize_claim_language(
        "Our Carbon Neutral, climate positive, eco-friendly gala."
    )
    assert clean == f"Our {CLAIM_REDACTION}, {CLAIM_REDACTION}, {CLAIM_REDACTION} gala."
    assert replaced == ["Carbon Neutral", "climate positive", "eco-friendly"]


def test_sanitize_leaves_unrelated_text_untouched():
    text = (
        "Indicative mapping to the Net Zero Carbon Events (NZCE) Measurement Methodology. "
        "Greenhouse gas totals are unchanged; neutralization is listed separately."
    )
    clean, replaced = sanitize_claim_language(text)
    assert clean == text
    assert replaced == []


def test_compliant_compensation_statement_renders_the_approved_construction():
    line = compliant_compensation_statement(
        120.5, 18.0, 12.25, "retired credits from Gold Standard"
    )
    assert line == (
        "120.500 tCO2e measured, 18.0% reduced, 12.250 tCO2e residual compensated "
        "outside the value chain via retired credits from Gold Standard"
    )
    assert find_banned_claims(line) == []


def test_compensation_statement_falls_back_when_no_credit_source_given():
    line = compliant_compensation_statement(10.0, 0.0, 0.0, "")
    assert line.endswith("via unspecified credits (registry not recorded)")


def test_partial_coverage_names_the_outstanding_residual():
    line = compliant_compensation_statement(
        120.5, 0.0, 120.5, "retired credits from Gold Standard", compensated_tco2e=3.0
    )
    assert line == (
        "120.500 tCO2e measured, 0.0% reduced, 3.000 of 120.500 tCO2e residual "
        "compensated outside the value chain via retired credits from Gold Standard; "
        "117.500 tCO2e residual not yet compensated"
    )
    assert find_banned_claims(line) == []


def test_full_coverage_drops_the_outstanding_clause():
    line = compliant_compensation_statement(
        10.0, 0.0, 10.0, "retired credits from Verra", compensated_tco2e=10.0
    )
    assert line == (
        "10.000 tCO2e measured, 0.0% reduced, 10.000 tCO2e residual compensated "
        "outside the value chain via retired credits from Verra"
    )


def test_portfolio_statement_counts_only_retired_credits_as_compensated():
    # 3 of 120.5 tCO2e retired must never read as the whole residual being covered.
    partial = portfolio_claim_statement(120.5, 3.0, {"gold_standard": 3.0})
    assert "3.000 of 120.500 tCO2e residual compensated" in partial
    assert partial.endswith("117.500 tCO2e residual not yet compensated")

    nothing_retired = portfolio_claim_statement(120.5, 0.0, {})
    assert "0.000 of 120.500 tCO2e residual compensated" in nothing_retired
    assert nothing_retired.endswith("120.500 tCO2e residual not yet compensated")

    full = portfolio_claim_statement(10.0, 10.0, {"verra": 10.0})
    assert "not yet compensated" not in full
    assert find_banned_claims(partial) == [] and find_banned_claims(full) == []


def test_describe_credit_sources():
    assert describe_credit_sources({"gold_standard": 2.0, "verra": 1.0}) == (
        "retired credits from Gold Standard, Verra"
    )
    assert describe_credit_sources({}) == "unspecified credits (registry not recorded)"


def test_offset_claim_guidance_cites_iso_14068_not_pas_2060():
    guidance = CARBON_OFFSETS["retirement_guidance"]["claim_types"]["carbon_neutral"]
    assert "PAS 2060" not in guidance
    assert "ISO 14068-1" in guidance
    assert "residual" in guidance.lower()
