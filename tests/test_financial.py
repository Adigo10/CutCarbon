"""Unit tests for the financial engine (no DB, no HTTP)."""

from types import SimpleNamespace
from typing import get_args

import pytest

from app.models.schemas import (
    EmployeeBand,
    FinancialRequest,
    ListingStatus,
    ReportingProfile,
    TurnoverBand,
)
from app.services import emissions_engine
from app.services.data_files import FRAMEWORKS_DATA
from app.services.financial_engine import (
    build_scenario_financial_request,
    calculate_carbon_tax_savings,
    calculate_energy_savings,
    generate_financial_report,
    get_compliance_report,
)
from app.services.regions import normalize_region

# An SGX-listed STI constituent reporting FY2026 — the tier for which both ISSB
# climate disclosure and Scope 3 are mandatory.
PROFILE_STI_2026 = ReportingProfile(
    employee_band="gt_1000",
    annual_turnover_band="gt_1b",
    listing_status="sti_constituent",
    reporting_fy=2026,
)


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
        req = build_scenario_financial_request(row, "eu", 30.0, ["renewable_energy"])
        # 1 tCO2e * 1000 / 0.412 kg/kWh -> kWh, then x 30%
        assert req.energy_kwh_saved == pytest.approx(1000 / 0.412 * 0.30, rel=1e-3)

    def test_unusable_legacy_row_reports_zero_not_fabrication(self):
        row = self._row(input_payload={"attendees": -1}, factors_snapshot={})
        req = build_scenario_financial_request(row, "eu", 30.0, ["renewable_energy"])
        assert req.energy_kwh_saved == 0


class TestCarbonPriceBasis:
    """Statutory carbon pricing only applies to covered entities; everyone else gets
    an internal carbon price kept out of the headline total."""

    def _req(self, **overrides):
        base = dict(
            baseline_tco2e=100, reduced_tco2e=70, region="singapore",
            energy_kwh_saved=0, meal_switches=0, attendees=300, actions_taken=[],
        )
        base.update(overrides)
        return FinancialRequest(**base)

    def test_default_is_internal_basis_with_no_statutory_saving(self):
        res = generate_financial_report(self._req())
        assert res.carbon_price_basis == "internal"
        assert res.carbon_tax_savings == []
        assert res.total_financial_savings_usd == pytest.approx(0.0)

    def test_default_internal_price_is_50_usd(self):
        res = generate_financial_report(self._req())
        assert res.internal_carbon_price_usd == pytest.approx(50.0)
        assert res.internal_carbon_value_usd == pytest.approx(30 * 50)

    @pytest.mark.parametrize("preset", [25.0, 50.0, 100.0])
    def test_preset_internal_prices_honoured(self, preset):
        res = generate_financial_report(self._req(internal_carbon_price_usd=preset))
        assert res.internal_carbon_value_usd == pytest.approx(30 * preset)

    def test_internal_value_excluded_from_headline_total(self):
        res = generate_financial_report(self._req(energy_kwh_saved=1000, meal_switches=200))
        assert res.internal_carbon_value_usd > 0
        assert res.total_financial_savings_usd == pytest.approx(
            round(res.energy_cost_savings_usd + res.catering_cost_savings_usd, 2)
        )

    def test_notes_explain_why_and_label_reference_value(self):
        res = generate_financial_report(self._req())
        joined = " ".join(res.notes)
        assert "not a tax liability" in joined
        assert "25,000" in joined  # the Singapore coverage threshold is quoted

    def test_covered_entity_keeps_statutory_computation(self):
        res = generate_financial_report(self._req(covered_by_carbon_pricing=True))
        assert res.carbon_price_basis == "statutory"
        assert res.carbon_tax_savings
        assert res.internal_carbon_value_usd == 0.0
        assert res.internal_carbon_price_usd is None
        assert res.total_financial_savings_usd == pytest.approx(
            res.carbon_tax_savings[0].savings_usd
        )


class TestRegionMismatchNote:
    def _report(self, region):
        return generate_financial_report(FinancialRequest(
            baseline_tco2e=100, reduced_tco2e=70, region=region,
        ))

    def test_unrecognized_region_is_surfaced(self):
        res = self._report("Marina Bay Sands, Singapore")
        note = next(n for n in res.notes if "not recognized" in n)
        assert "Marina Bay Sands, Singapore" in note

    def test_explicit_global_is_not_flagged(self):
        assert not any("not recognized" in n for n in self._report("global").notes)

    def test_known_region_is_not_flagged(self):
        assert not any("not recognized" in n for n in self._report("EU").notes)


class TestActionDerivedSavingsInputs:
    """Each savings line is fed only by the actions that actually produce it."""

    def _row(self):
        return SimpleNamespace(
            id="row1", total_tco2e=50.0, venue_energy_tco2e=1.0, attendees=100, event_days=2,
            input_payload={
                "name": "Row", "attendees": 100, "event_days": 2,
                "venue_energy": {"grid_region": "singapore", "kwh_consumed": 2500, "renewable_pct": 10},
            },
            factors_snapshot={"venue_grid_kg_per_kwh": 0.412},
        )

    def test_renewables_only_books_no_meal_switches(self):
        req = build_scenario_financial_request(self._row(), "singapore", 30.0, ["renewable_energy"])
        assert req.energy_kwh_saved > 0
        assert req.meal_switches == 0

    def test_catering_only_books_no_energy_savings(self):
        req = build_scenario_financial_request(self._row(), "singapore", 30.0, ["vegetarian_menu"])
        assert req.energy_kwh_saved == 0
        assert req.meal_switches > 0

    def test_irrelevant_actions_book_neither(self):
        req = build_scenario_financial_request(self._row(), "singapore", 30.0, ["ghg_reporting"])
        assert req.energy_kwh_saved == 0
        assert req.meal_switches == 0

    def test_data_file_action_keys_are_accepted_directly(self):
        req = build_scenario_financial_request(
            self._row(), "singapore", 30.0, ["led_lighting_upgrade", "switch_to_vegan_meal"]
        )
        assert req.energy_kwh_saved > 0
        assert req.meal_switches > 0


def _check(report, key):
    """The check for ``key``, or None when the framework is not in the region."""
    return next((c for c in report.checks if c.framework_key == key), None)


class TestFrameworksData:
    def test_every_framework_is_well_formed(self):
        assert FRAMEWORKS_DATA["frameworks"]
        keys = set()
        for fw in FRAMEWORKS_DATA["frameworks"]:
            for field in ("key", "name", "status", "as_of", "scope_rule", "regions", "note"):
                assert fw.get(field), f"{fw.get('key')} missing {field}"
            assert fw["key"] not in keys
            keys.add(fw["key"])
            assert fw["status"] in FRAMEWORKS_DATA["statuses"]
        assert {
            "eu_csrd", "sgx_issb", "uk_srs", "au_asrs", "ca_sb253", "ca_sb261",
            "ghg_protocol", "nzce", "iso_20121_2024",
        } <= keys

    def test_schema_band_literals_match_the_data_file(self):
        assert set(get_args(EmployeeBand)) == set(FRAMEWORKS_DATA["employee_bands"])
        assert set(get_args(TurnoverBand)) == set(FRAMEWORKS_DATA["turnover_bands"])
        assert set(get_args(ListingStatus)) == set(FRAMEWORKS_DATA["listing_statuses"])

    def test_size_bands_do_not_straddle_the_encoded_thresholds(self):
        # Every band must sit unambiguously above or below each threshold the
        # scope tests use, otherwise a scope decision would be undecidable.
        for bands, thresholds in (
            (FRAMEWORKS_DATA["employee_bands"], [1000]),
            (FRAMEWORKS_DATA["turnover_bands"], [450_000_000, 1_000_000_000]),
        ):
            for name, band in bands.items():
                for threshold in thresholds:
                    above = band["min"] > threshold
                    below = band["max"] is not None and band["max"] <= threshold
                    assert above or below, f"{name} straddles {threshold}"


class TestObligationScoping:
    def test_overall_score_pct_is_gone(self):
        report = get_compliance_report(50, True, True, "australia", 2, 100)
        assert "overall_score_pct" not in report.model_dump()
        assert not hasattr(report, "overall_score_pct")

    def test_missing_profile_reports_everything_as_informational(self):
        for region in ("singapore", "EU", "uk", "australia", "usa"):
            report = get_compliance_report(50, True, True, region, 2, 100)
            assert report.profile_complete is False
            assert "profile incomplete" in report.profile_note.lower()
            assert report.mandatory_frameworks == []
            regulated = [c for c in report.checks if c.status in ("in_force", "proposed")]
            assert regulated, f"no regulated framework surfaced for {region}"
            for check in regulated:
                assert check.applies in ("informational", "enjoined", "voluntary")
                assert check.applies != "mandatory"
                assert check.reason
                assert check.as_of

    def test_fy_only_profile_is_not_complete_and_asserts_no_negative(self):
        # The SPA sends blank bands as null, so a user who fills in only the
        # reporting year leaves every size test undecided. That must NOT read as
        # "nothing binds you": profile_complete stays False and the note names
        # exactly which frameworks went undetermined.
        for region, key in (("EU", "eu_csrd"), ("singapore", "sgx_issb"),
                            ("australia", "au_asrs")):
            report = get_compliance_report(
                50, True, True, region, 2, 100, ReportingProfile(reporting_fy=2027)
            )
            assert _check(report, key).applies == "informational"
            assert report.mandatory_frameworks == []
            assert report.profile_complete is False, f"{region} wrongly reported complete"
            assert "profile incomplete" in report.profile_note.lower()
            assert _check(report, key).framework in report.profile_note

    def test_california_nexus_is_a_real_answer_not_a_missing_one(self):
        # does_business_in_california is a checkbox with a meaningful default, so
        # "not ticked" is an answer: SB 253 is genuinely out of scope, and the
        # empty mandatory list for the US is therefore supported.
        report = get_compliance_report(
            50, True, True, "usa", 2, 100, ReportingProfile(reporting_fy=2027)
        )
        assert _check(report, "ca_sb253").applies == "out_of_scope"
        assert _check(report, "ca_sb261").applies == "enjoined"
        assert report.profile_complete is True
        assert report.mandatory_frameworks == []

    def test_fully_determined_profile_is_complete_with_no_note(self):
        report = get_compliance_report(50, True, True, "singapore", 2, 100, PROFILE_STI_2026)
        assert report.profile_complete is True
        assert report.profile_note == ""
        assert _check(report, "sgx_issb").applies == "mandatory"

    def test_out_of_scope_everywhere_still_counts_as_complete(self):
        # A genuinely determined profile that nothing binds: the empty mandatory
        # list IS supported here, because no framework came back informational.
        report = get_compliance_report(
            50, True, True, "EU", 2, 100,
            ReportingProfile(employee_band="lt_50", annual_turnover_band="lt_50m",
                             listing_status="none", reporting_fy=2027),
        )
        assert report.profile_complete is True
        assert report.mandatory_frameworks == []
        assert _check(report, "eu_csrd").applies == "out_of_scope"

    def test_voluntary_frameworks_never_need_a_profile(self):
        report = get_compliance_report(50, True, True, "australia", 2, 100)
        for key in ("ghg_protocol", "nzce", "iso_20121_2024"):
            check = _check(report, key)
            assert check is not None
            assert check.applies == "voluntary"
        assert _check(report, "nzce").framework not in report.mandatory_frameworks

    def test_region_filters_which_regimes_are_shown(self):
        sg = get_compliance_report(50, True, True, "singapore", 2, 100, PROFILE_STI_2026)
        assert _check(sg, "sgx_issb") is not None
        assert _check(sg, "eu_csrd") is None
        assert _check(sg, "ca_sb253") is None

        au = get_compliance_report(50, True, True, "australia", 2, 100)
        assert _check(au, "au_asrs") is not None
        assert _check(au, "sgx_issb") is None


class TestEuCsrdScope:
    def test_small_agency_is_out_of_scope(self):
        # 40-person agency: below both post-Omnibus I thresholds.
        profile = ReportingProfile(
            employee_band="lt_50", annual_turnover_band="lt_50m",
            listing_status="none", reporting_fy=2027,
        )
        check = _check(get_compliance_report(50, True, True, "EU", 2, 100, profile), "eu_csrd")
        assert check.applies == "out_of_scope"
        assert check.status == "in_force"
        assert "1,000" in check.reason and "450" in check.reason

    def test_large_undertaking_is_mandatory_from_fy2027(self):
        base = dict(employee_band="gt_1000", annual_turnover_band="gt_1b", listing_status="listed")
        early = _check(
            get_compliance_report(50, True, True, "EU", 2, 100, ReportingProfile(reporting_fy=2026, **base)),
            "eu_csrd",
        )
        assert early.applies == "not_in_force"
        assert early.first_reporting_fy == 2027

        live = _check(
            get_compliance_report(50, True, True, "EU", 2, 100, ReportingProfile(reporting_fy=2027, **base)),
            "eu_csrd",
        )
        assert live.applies == "mandatory"
        assert live.scope3_required is True
        assert live.framework in get_compliance_report(
            50, True, True, "EU", 2, 100, ReportingProfile(reporting_fy=2027, **base)
        ).mandatory_frameworks

    def test_missing_size_bands_stay_informational(self):
        profile = ReportingProfile(reporting_fy=2027, listing_status="listed")
        check = _check(get_compliance_report(50, True, True, "EU", 2, 100, profile), "eu_csrd")
        assert check.applies == "informational"


class TestSgxScope:
    def test_sti_constituent_scope3_mandatory_from_fy2026(self):
        fy2025 = _check(
            get_compliance_report(
                50, True, True, "singapore", 2, 100,
                ReportingProfile(listing_status="sti_constituent", reporting_fy=2025),
            ),
            "sgx_issb",
        )
        assert fy2025.applies == "mandatory"
        assert fy2025.scope3_required is False

        fy2026 = _check(
            get_compliance_report(50, True, True, "singapore", 2, 100, PROFILE_STI_2026), "sgx_issb"
        )
        assert fy2026.applies == "mandatory"
        assert fy2026.scope3_required is True

    def test_listed_non_sti_scope3_is_voluntary(self):
        check = _check(
            get_compliance_report(
                50, True, True, "singapore", 2, 100,
                ReportingProfile(listing_status="listed", annual_turnover_band="gt_1b", reporting_fy=2028),
            ),
            "sgx_issb",
        )
        assert check.applies == "mandatory"
        assert check.scope3_required is False
        assert "voluntary" in check.reason.lower()

    def test_smaller_listed_issuer_waits_for_fy2030(self):
        smaller = dict(listing_status="listed", annual_turnover_band="450m_1b")
        assert _check(
            get_compliance_report(50, True, True, "singapore", 2, 100, ReportingProfile(reporting_fy=2028, **smaller)),
            "sgx_issb",
        ).applies == "not_in_force"
        assert _check(
            get_compliance_report(50, True, True, "singapore", 2, 100, ReportingProfile(reporting_fy=2030, **smaller)),
            "sgx_issb",
        ).applies == "mandatory"

    def test_small_non_listed_company_is_out_of_scope(self):
        check = _check(
            get_compliance_report(
                50, True, True, "singapore", 2, 100,
                ReportingProfile(listing_status="none", annual_turnover_band="lt_50m", reporting_fy=2030),
            ),
            "sgx_issb",
        )
        assert check.applies == "out_of_scope"


class TestUkSrsScope:
    def test_uk_srs_is_never_mandatory(self):
        profiles = [
            None,
            ReportingProfile(reporting_fy=2027, employee_band="gt_1000",
                             annual_turnover_band="gt_1b", listing_status="listed"),
            ReportingProfile(reporting_fy=2030, employee_band="gt_1000",
                             annual_turnover_band="gt_1b", listing_status="listed"),
        ]
        for profile in profiles:
            check = _check(get_compliance_report(50, True, True, "uk", 2, 100, profile), "uk_srs")
            assert check.status == "proposed"
            assert check.applies == "voluntary"
            assert check.applies != "mandatory"
            assert "1 January 2027" in check.reason


class TestAuAsrsScope:
    def test_group2_first_period_excludes_scope3(self):
        def scope(fy):
            return _check(
                get_compliance_report(
                    50, True, True, "australia", 2, 100,
                    ReportingProfile(listing_status="asrs_group2", reporting_fy=fy),
                ),
                "au_asrs",
            )

        assert scope(2025).applies == "not_in_force"
        first = scope(2026)
        assert first.applies == "mandatory"
        assert first.scope3_required is False
        assert "first reporting period" in first.reason.lower()
        assert scope(2027).scope3_required is True

    def test_unspecified_group_stays_informational(self):
        check = _check(
            get_compliance_report(
                50, True, True, "australia", 2, 100, ReportingProfile(reporting_fy=2027, listing_status="none")
            ),
            "au_asrs",
        )
        assert check.applies == "informational"


class TestCaliforniaScope:
    def test_sb253_needs_a_california_nexus_and_the_revenue_threshold(self):
        no_nexus = _check(
            get_compliance_report(
                50, True, True, "usa", 2, 100,
                ReportingProfile(annual_turnover_band="gt_1b", reporting_fy=2026,
                                 does_business_in_california=False),
            ),
            "ca_sb253",
        )
        assert no_nexus.applies == "out_of_scope"

        too_small = _check(
            get_compliance_report(
                50, True, True, "usa", 2, 100,
                ReportingProfile(annual_turnover_band="450m_1b", reporting_fy=2026,
                                 does_business_in_california=True),
            ),
            "ca_sb253",
        )
        assert too_small.applies == "out_of_scope"

    def test_sb253_scope3_starts_with_fy2026(self):
        def scope(fy):
            return _check(
                get_compliance_report(
                    50, True, True, "usa", 2, 100,
                    ReportingProfile(annual_turnover_band="gt_1b", reporting_fy=fy,
                                     does_business_in_california=True),
                ),
                "ca_sb253",
            )

        assert scope(2024).applies == "not_in_force"
        fy2025 = scope(2025)
        assert fy2025.applies == "mandatory"
        assert fy2025.scope3_required is False
        assert "10 November 2026" in fy2025.reason
        assert scope(2026).scope3_required is True

    def test_sb261_is_never_mandatory_while_enjoined(self):
        profiles = [
            None,
            ReportingProfile(annual_turnover_band="gt_1b", reporting_fy=2030,
                             does_business_in_california=True),
        ]
        for profile in profiles:
            check = _check(get_compliance_report(50, True, True, "usa", 2, 100, profile), "ca_sb261")
            assert check.status == "enjoined"
            assert check.applies == "enjoined"
            assert check.applies != "mandatory"
            assert "Ninth Circuit" in check.reason
            assert check.framework not in get_compliance_report(
                50, True, True, "usa", 2, 100, profile
            ).mandatory_frameworks


class TestIso20121Checklist:
    def test_iso_is_a_clause_checklist_not_a_score(self):
        check = _check(get_compliance_report(50, True, True, "australia", 2, 100), "iso_20121_2024")
        assert check.score_pct is None
        assert check.applies == "voluntary"
        clauses = [item.clause for item in check.clause_checklist]
        for clause in ("6.3", "7.3", "9.3.4"):
            assert clause in clauses
        joined = " ".join(f"{i.clause} {i.requirement}" for i in check.clause_checklist).lower()
        assert "climate change" in joined
        assert "legacy" in joined
        assert "annex d" in joined
        assert all(item.evidence_status == "not_evidenced" for item in check.clause_checklist)
        assert any("31 March 2027" in text for text in [check.reason, *check.recommendations])


class TestTierAwareFirstReportingFy:
    """The displayed first reporting year must be the PROFILE's tier year.

    Reading the framework's top-level year showed an ASRS Group 2 entity Group 1's
    FY2025 next to a reason saying its period begins in FY2026, and a sub-threshold
    SGX issuer the STI year next to a reason saying FY2030.
    """

    def test_au_group2_shows_its_own_year_not_group1s(self):
        group2 = _check(
            get_compliance_report(
                50, True, True, "australia", 2, 100,
                ReportingProfile(listing_status="asrs_group2", reporting_fy=2026),
            ),
            "au_asrs",
        )
        assert group2.first_reporting_fy == 2026
        assert f"FY{group2.first_reporting_fy}" != "FY2025"

        group1 = _check(
            get_compliance_report(
                50, True, True, "australia", 2, 100,
                ReportingProfile(listing_status="asrs_group1", reporting_fy=2026),
            ),
            "au_asrs",
        )
        assert group1.first_reporting_fy == 2025

        # Not-in-force branch names the same tier year it is waiting for.
        waiting = _check(
            get_compliance_report(
                50, True, True, "australia", 2, 100,
                ReportingProfile(listing_status="asrs_group2", reporting_fy=2025),
            ),
            "au_asrs",
        )
        assert waiting.applies == "not_in_force"
        assert waiting.first_reporting_fy == 2026

    def test_sgx_sub_threshold_issuer_shows_fy2030_not_the_sti_year(self):
        smaller = _check(
            get_compliance_report(
                50, True, True, "singapore", 2, 100,
                ReportingProfile(listing_status="listed", annual_turnover_band="450m_1b",
                                 reporting_fy=2028),
            ),
            "sgx_issb",
        )
        assert smaller.applies == "not_in_force"
        assert smaller.first_reporting_fy == 2030
        assert "FY2030" in smaller.reason

        large = _check(
            get_compliance_report(
                50, True, True, "singapore", 2, 100,
                ReportingProfile(listing_status="listed", annual_turnover_band="gt_1b",
                                 reporting_fy=2028),
            ),
            "sgx_issb",
        )
        assert large.first_reporting_fy == 2028
        assert _check(
            get_compliance_report(50, True, True, "singapore", 2, 100, PROFILE_STI_2026),
            "sgx_issb",
        ).first_reporting_fy == 2025

    def test_displayed_year_always_agrees_with_the_reason(self):
        # Whatever year the card shows must be the one the reason argues for.
        profiles = [
            ("australia", "au_asrs", ReportingProfile(listing_status="asrs_group2", reporting_fy=2026)),
            ("australia", "au_asrs", ReportingProfile(listing_status="asrs_group1", reporting_fy=2025)),
            ("singapore", "sgx_issb", ReportingProfile(listing_status="listed",
                                                       annual_turnover_band="450m_1b", reporting_fy=2028)),
            ("singapore", "sgx_issb", ReportingProfile(listing_status="none",
                                                       annual_turnover_band="gt_1b", reporting_fy=2029)),
            ("EU", "eu_csrd", ReportingProfile(employee_band="gt_1000",
                                               annual_turnover_band="gt_1b", reporting_fy=2026)),
        ]
        for region, key, profile in profiles:
            check = _check(get_compliance_report(50, True, True, region, 2, 100, profile), key)
            assert check.first_reporting_fy is not None
            # The year itself must appear in the reason; CSRD words it as a date
            # ("1 January 2027"), the tiered regimes as "FY2027".
            assert str(check.first_reporting_fy) in check.reason, (
                f"{key}: shows FY{check.first_reporting_fy} but reason says {check.reason!r}"
            )

    def test_undetermined_tier_shows_no_year_at_all(self):
        for region, key in (("singapore", "sgx_issb"), ("australia", "au_asrs")):
            check = _check(
                get_compliance_report(50, True, True, region, 2, 100,
                                      ReportingProfile(reporting_fy=2027)),
                key,
            )
            assert check.applies == "informational"
            assert check.first_reporting_fy is None, (
                f"{key} named a year without knowing the tier"
            )

    def test_tiered_frameworks_carry_no_misleading_top_level_year(self):
        by_key = {f["key"]: f for f in FRAMEWORKS_DATA["frameworks"]}
        for key in ("sgx_issb", "au_asrs"):
            assert by_key[key].get("first_reporting_fy") is None
            assert by_key[key].get("tiers")
        # Untiered regimes keep theirs.
        assert by_key["eu_csrd"]["first_reporting_fy"] == 2027
        assert by_key["ca_sb253"]["first_reporting_fy"] == 2025


class TestRetainedQualitativeChecks:
    def test_ghg_protocol_gaps_still_track_the_inventory(self):
        weak = _check(get_compliance_report(50, False, False, "australia", 2, 100), "ghg_protocol")
        assert weak.score_pct == 20
        assert any("Scope 3" in gap for gap in weak.gaps)
        strong = _check(get_compliance_report(50, True, True, "australia", 2, 100), "ghg_protocol")
        assert strong.score_pct == 100
        assert strong.gaps == []
        assert "draft" in strong.reason.lower()  # the 95% completeness revision is DRAFT only

    def test_intensity_branches(self):
        low = _check(get_compliance_report(1, True, True, "australia", 2, 100), "event_carbon_intensity")
        assert low.readiness == "compliant"
        assert low.applies == "informational"

        high = _check(get_compliance_report(500, True, True, "australia", 1, 100), "event_carbon_intensity")
        assert high.readiness == "partial"

    def test_nzce_keeps_its_gaps_and_recommendations(self):
        check = _check(get_compliance_report(50, True, True, "australia", 2, 100), "nzce")
        assert check.status == "voluntary_initiative"
        assert check.gaps and check.recommendations
        assert any("two years" in rec for rec in check.recommendations)


def test_headline_total_composition():
    # Statutory carbon pricing only enters the headline for a covered entity.
    req = FinancialRequest(
        baseline_tco2e=100, reduced_tco2e=70, region="singapore",
        energy_kwh_saved=1000, meal_switches=200, attendees=300,
        actions_taken=["renewable_energy"], covered_by_carbon_pricing=True,
    )
    res = generate_financial_report(req)
    primary = res.carbon_tax_savings[0].savings_usd
    assert res.total_financial_savings_usd == pytest.approx(
        round(primary + res.energy_cost_savings_usd + res.catering_cost_savings_usd, 2)
    )
    assert res.roi_months is None
    assert res.compliance_value_usd == 0.0
