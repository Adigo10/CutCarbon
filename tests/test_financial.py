"""Unit tests for the financial engine (no DB, no HTTP)."""

from types import SimpleNamespace

import pytest

from app.models.schemas import FinancialRequest
from app.services import emissions_engine
from app.services.financial_engine import (
    build_scenario_financial_request,
    calculate_carbon_tax_savings,
    calculate_energy_savings,
    generate_financial_report,
    get_compliance_report,
)
from app.services.regions import normalize_region


class TestRegions:
    def test_aliases_normalize(self):
        assert normalize_region("EU") == "european_union"
        assert normalize_region("United Kingdom") == "united_kingdom"
        assert normalize_region("usa_california") == "usa"
        assert normalize_region("korea") == "south_korea"

    def test_unknown_region_falls_back_to_global(self):
        assert normalize_region("atlantis") == "global"


class TestCarbonTaxSavings:
    def test_unknown_region_returns_no_savings(self):
        assert calculate_carbon_tax_savings(10, "atlantis") == []

    def test_eu_alias_resolves(self):
        savings = calculate_carbon_tax_savings(10, "EU")
        assert savings and savings[0].currency == "EUR"

    def test_singapore_includes_future_rate_projection(self):
        savings = calculate_carbon_tax_savings(10, "singapore")
        schemes = [s.scheme for s in savings]
        assert "Singapore Carbon Tax (future rate)" in schemes
        future = next(s for s in savings if "future rate" in s.scheme)
        # Low bound of the announced 2030 range (SGD 50-80).
        assert future.savings_local == pytest.approx(10 * 50)

    def test_live_next_rate_preferred_over_static_range(self):
        live = emissions_engine.EF.setdefault("carbon_tax_live", {})
        live["singapore_next_sgd"] = 60
        try:
            savings = calculate_carbon_tax_savings(10, "singapore")
            future = next(s for s in savings if "future rate" in s.scheme)
            assert future.savings_local == pytest.approx(600)
        finally:
            live.pop("singapore_next_sgd", None)

    def test_live_price_discloses_static_fx(self):
        live = emissions_engine.EF.setdefault("carbon_tax_live", {})
        live["singapore_current_sgd"] = 99
        try:
            savings = calculate_carbon_tax_savings(10, "singapore")
            assert "live price" in savings[0].description
            assert "static FX" in savings[0].description
        finally:
            live.pop("singapore_current_sgd", None)


class TestEnergySavings:
    def test_region_rate_applied(self):
        assert calculate_energy_savings(1000, "uk") == pytest.approx(1000 * 0.34)

    def test_unknown_region_uses_global_rate(self):
        assert calculate_energy_savings(1000, "atlantis") == pytest.approx(1000 * 0.18)


class TestScenarioFinancialRequest:
    """kWh must come from the scenario's own venue input, never the request region's grid."""

    def _row(self, **overrides):
        base = dict(
            id="row1",
            total_tco2e=50.0,
            venue_energy_tco2e=1.0,
            attendees=100,
            event_days=2,
            input_payload={
                "name": "Row", "attendees": 100, "event_days": 2,
                "venue_energy": {"grid_region": "singapore", "kwh_consumed": 2500, "renewable_pct": 10},
            },
            factors_snapshot={"venue_grid_kg_per_kwh": 0.412},
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_kwh_from_scenario_input_regardless_of_request_region(self):
        for region in ("singapore", "eu", "australia"):
            req = build_scenario_financial_request(self._row(), region, 30.0, ["renewable_energy"])
            assert req.energy_kwh_saved == pytest.approx(2500 * 0.30)

    def test_legacy_row_backsolves_from_own_snapshot(self):
        row = self._row(input_payload={"attendees": -1})  # invalid -> snapshot path
        req = build_scenario_financial_request(row, "eu", 30.0, [])
        # 1 tCO2e * 1000 / 0.412 kg/kWh -> kWh, then x 30%
        assert req.energy_kwh_saved == pytest.approx(1000 / 0.412 * 0.30, rel=1e-3)

    def test_unusable_legacy_row_reports_zero_not_fabrication(self):
        row = self._row(input_payload={"attendees": -1}, factors_snapshot={})
        req = build_scenario_financial_request(row, "eu", 30.0, [])
        assert req.energy_kwh_saved == 0


class TestComplianceReport:
    def test_nzce_check_present_everywhere(self):
        report = get_compliance_report(50, True, True, "australia", 2, 100)
        frameworks = [c.framework for c in report.checks]
        assert any("Net Zero Carbon Events" in f for f in frameworks)
        assert "Net Zero Carbon Events (NZCE) Measurement Methodology" not in report.mandatory_frameworks

    def test_regional_regimes(self):
        sg = get_compliance_report(50, True, True, "singapore", 2, 100)
        assert any("SGX" in c.framework for c in sg.checks)
        assert "SGX Sustainability Reporting (Scope 1+2)" in sg.mandatory_frameworks

        eu = get_compliance_report(50, True, True, "EU", 2, 100)
        assert any("CSRD" in c.framework for c in eu.checks)

        au = get_compliance_report(50, True, True, "australia", 2, 100)
        assert not any("SGX" in c.framework or "CSRD" in c.framework for c in au.checks)

    def test_intensity_branches(self):
        low = get_compliance_report(1, True, True, "australia", 2, 100)
        intensity_low = next(c for c in low.checks if "intensity" in c.framework)
        assert intensity_low.status == "compliant"

        high = get_compliance_report(500, True, True, "australia", 1, 100)
        intensity_high = next(c for c in high.checks if "intensity" in c.framework)
        assert intensity_high.status == "partial"


def test_headline_total_composition():
    req = FinancialRequest(
        baseline_tco2e=100, reduced_tco2e=70, region="singapore",
        energy_kwh_saved=1000, meal_switches=200, attendees=300,
        actions_taken=["renewable_energy"],
    )
    res = generate_financial_report(req)
    primary = res.carbon_tax_savings[0].savings_usd
    assert res.total_financial_savings_usd == pytest.approx(
        round(primary + res.energy_cost_savings_usd + res.catering_cost_savings_usd, 2)
    )
    assert res.roi_months is None
    assert res.compliance_value_usd == 0.0
