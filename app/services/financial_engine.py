"""
Financial savings + tax compliance engine.
Calculates carbon tax savings, energy cost reductions, green incentives,
and compliance value from emission reduction actions.
"""
from typing import List, Dict, Any, Optional, Tuple

from app.models.schemas import (
    FinancialRequest, FinancialResult, TaxSaving, ComplianceCheck, ComplianceClause,
    ComplianceReport, ReportingProfile,
)
from app.services.data_files import FRAMEWORKS_DATA, TAX_DATA
from app.services.regions import (
    CARBON_TAX_KEYS,
    ELECTRICITY_KEYS,
    INCENTIVE_KEYS,
    normalize_region,
)

# Electricity cost per kWh by region (USD) — sourced from tax_incentives.json
# ("electricity_rates_usd", carries its own as_of date).
_ELEC_BLOCK = TAX_DATA.get("electricity_rates_usd", {})
ELECTRICITY_RATES_USD = {
    k: v for k, v in _ELEC_BLOCK.items() if isinstance(v, (int, float))
} or {"global": 0.18}

# Shadow price used when the entity is not covered by a compliance carbon scheme.
# The UI offers 25 / 50 / 100 USD/tCO2e presets; this is the fallback.
DEFAULT_INTERNAL_CARBON_PRICE_USD = 50.0


# -- Reduction actions -> which savings line they feed -------------------------
# Derived from the fields tax_incentives.json records against each action, so adding
# an action to the data file automatically routes it to the right line.
_ACTION_SAVINGS = TAX_DATA.get("reduction_action_savings", {})

# UI / chat action keys -> the canonical reduction_action_savings key they mean.
_ACTION_ALIASES = {
    "renewable_energy": "renewable_energy_venue",
    "led_lighting": "led_lighting_upgrade",
    "vegetarian_menu": "switch_to_vegetarian_meal",
    "vegan_menu": "switch_to_vegan_meal",
    "local_seasonal": "local_seasonal_catering",
    "zero_waste": "zero_waste_catering",
    "hybrid_event": "virtual_attendance_option",
    "rail_travel": "rail_instead_of_short_haul",
    "local_venue": "local_venue_selection",
    "carbon_offset": "carbon_offset_purchase",
    "carbon_removal": "carbon_removal_purchase",
}


def _actions_recording(*fields: str) -> set:
    """Canonical action keys whose data-file entry records any of these fields."""
    return {
        key for key, data in _ACTION_SAVINGS.items()
        if isinstance(data, dict) and any(f in data for f in fields)
    }


# Actions that cut venue electricity (feed energy_kwh_saved) and actions that swap
# meals (feed meal_switches). Anything else feeds neither.
ENERGY_ACTIONS = _actions_recording("co2e_saved_per_kwh_kg", "co2e_saved_pct_energy")
MEAL_ACTIONS = _actions_recording("co2e_saved_per_meal_kg")


def canonical_actions(actions: List[str]) -> set:
    """Normalize UI/chat action keys onto the tax_incentives.json action vocabulary."""
    resolved = set()
    for action in actions or []:
        key = (action or "").strip().lower()
        if not key:
            continue
        resolved.add(_ACTION_ALIASES.get(key, key))
    return resolved


def _live_carbon_prices() -> dict:
    """Live carbon prices fetched by the TinyFish agents (carbon_tax_live), if any."""
    try:
        from app.services.emissions_engine import EF
        return EF.get("carbon_tax_live", {}) or {}
    except Exception:
        return {}


# Region key -> (rate_data field, currency). First matching field is the headline price.
_PRICE_FIELDS = [
    ("current_rate_sgd", "SGD"),
    ("ets_price_eur", "EUR"),
    ("ets_price_gbp", "GBP"),
    ("accu_price_aud", "AUD"),
    ("cap_trade_price_usd", "USD"),
    ("federal_rate_cad", "CAD"),
    ("tax_rate_jpy", "JPY"),
    ("ets_price_krw", "KRW"),
    ("ets_price_cny", "CNY"),
]

# Which live carbon_tax_live key (if present) overrides the static price per currency.
_LIVE_PRICE_KEYS = {
    "current_rate_sgd": "singapore_current_sgd",
    "ets_price_eur": "eu_ets_eur",
    "ets_price_gbp": "uk_ets_gbp",
}


def calculate_carbon_tax_savings(
    co2e_reduced_tco2e: float, region: str
) -> List[TaxSaving]:
    """Direct carbon-tax/ETS liability avoided by the emission reduction.

    Prefers a live carbon price fetched by the TinyFish agents (carbon_tax_live) and
    falls back to the static tax_incentives.json value. Returns no savings for regions
    with no configured carbon price rather than fabricating one.
    """
    savings: List[TaxSaving] = []
    region_key = normalize_region(region)

    rate_key = CARBON_TAX_KEYS.get(region_key)
    rate_data = TAX_DATA["carbon_tax_rates"].get(rate_key) if rate_key else None
    if not rate_data:
        # No carbon price configured for this region — do not invent one.
        return savings

    usd_rate = rate_data.get("usd_exchange", 1.0)
    live = _live_carbon_prices()

    local_price = None
    currency = "USD"
    is_live = False
    for field, cur in _PRICE_FIELDS:
        if field in rate_data:
            currency = cur
            live_key = _LIVE_PRICE_KEYS.get(field)
            if live_key and live.get(live_key):
                local_price = live[live_key]
                is_live = True
            else:
                local_price = rate_data[field]
            break

    if local_price is None:
        return savings

    description = f"{co2e_reduced_tco2e:.2f} tCO2e x {local_price} {currency}/tCO2e"
    if is_live:
        description += " (live price"
        fx_as_of = rate_data.get("fx_as_of")
        if currency != "USD" and fx_as_of:
            description += f", converted at static FX as of {fx_as_of}"
        description += ")"

    savings.append(TaxSaving(
        scheme=rate_data.get("scheme", f"{region.title()} Carbon Scheme"),
        savings_usd=round(co2e_reduced_tco2e * local_price * usd_rate, 2),
        savings_local=round(co2e_reduced_tco2e * local_price, 2),
        currency=currency,
        description=description,
    ))

    # Singapore's announced rate trajectory — a labeled forward projection. Prefer
    # the live announced next-step rate; else the low bound of the 2030 range.
    if region_key == "singapore":
        future_price = live.get("singapore_next_sgd")
        source_note = "announced next-step rate (live)"
        if not future_price:
            rate_range = rate_data.get("2030_rate_sgd_range") or []
            future_price = rate_range[0] if rate_range else None
            source_note = "low bound of the announced SGD 50-80/tCO2e range by 2030"
        if future_price:
            savings.append(TaxSaving(
                scheme="Singapore Carbon Tax (future rate)",
                savings_usd=round(co2e_reduced_tco2e * future_price * usd_rate, 2),
                savings_local=round(co2e_reduced_tco2e * future_price, 2),
                currency="SGD",
                description=f"Projected at SGD {future_price}/tCO2e — {source_note}",
            ))

    return savings


def calculate_energy_savings(energy_kwh_saved: float, region: str) -> float:
    """Calculate direct energy cost savings in USD."""
    key = ELECTRICITY_KEYS.get(normalize_region(region), "global")
    rate = ELECTRICITY_RATES_USD.get(key, ELECTRICITY_RATES_USD["global"])
    return round(energy_kwh_saved * rate, 2)


def get_available_incentives(region: str, actions: List[str]) -> List[Dict[str, Any]]:
    """Match taken actions to available green incentives."""
    mapped = INCENTIVE_KEYS.get(normalize_region(region), "singapore")
    incentives = TAX_DATA["green_incentives"].get(mapped, [])
    expanded_actions = set(actions)
    action_aliases = {
        "ghg_reporting": "sustainability_reporting",
        "renewable_energy": "energy_efficiency",
        "led_lighting": "energy_efficiency",
    }
    for action in list(expanded_actions):
        alias = action_aliases.get(action)
        if alias:
            expanded_actions.add(alias)

    matched = []
    for inc in incentives:
        applicable = inc.get("applicable_actions", [])
        if not applicable or any(a in expanded_actions for a in applicable):
            matched.append(inc)

    return matched


def build_scenario_financial_request(
    scenario_row,
    region: str,
    reduction_pct: float,
    actions_taken: List[str],
) -> FinancialRequest:
    """Build a FinancialRequest from a stored scenario row.

    Energy kWh saved is derived from the scenario's own venue-energy input (its
    grid and renewable share) — never from the requesting region's grid factor.

    Each savings input is fed only by the actions that actually produce it: a
    renewables-only plan books no catering saving, and a menu-only plan books no
    energy saving. The headline reduction_pct alone never conjures a line item.
    """
    from app.models.schemas import EventScenarioInput
    from app.services.emissions_engine import estimate_venue_kwh, physical_attendee_count

    baseline = scenario_row.total_tco2e or 0.0
    reduced = baseline * (1 - reduction_pct / 100)

    payload = scenario_row.input_payload or {}
    venue_kwh = 0.0
    try:
        scenario_input = EventScenarioInput.model_validate(payload)
        # Same on-site headcount the emissions engine sized the venue with, so the
        # kWh back-calculation cannot disagree with the venue figure it mirrors.
        venue_kwh = estimate_venue_kwh(
            scenario_input.venue_energy,
            physical_attendee_count(scenario_input),
            scenario_input.event_days,
        )
    except Exception:
        # Legacy rows without a valid stored payload: back-solve from this row's own
        # factor snapshot; report zero rather than fabricating a figure from another
        # region's grid factor.
        snapshot = getattr(scenario_row, "factors_snapshot", None) or {}
        grid_ef = snapshot.get("venue_grid_kg_per_kwh") or 0.0
        renewable_pct = (payload.get("venue_energy") or {}).get("renewable_pct") or 0.0
        effective_ef = grid_ef * (1 - renewable_pct / 100)
        if effective_ef > 0:
            venue_kwh = (scenario_row.venue_energy_tco2e or 0.0) * 1000 / effective_ef

    resolved_actions = canonical_actions(actions_taken)
    meals_served = (scenario_row.attendees or 0) * (scenario_row.event_days or 1) * 2

    return FinancialRequest(
        scenario_id=scenario_row.id,
        baseline_tco2e=baseline,
        reduced_tco2e=reduced,
        region=region,
        energy_kwh_saved=(
            venue_kwh * (reduction_pct / 100) if resolved_actions & ENERGY_ACTIONS else 0.0
        ),
        meal_switches=(
            int(meals_served * (reduction_pct / 100)) if resolved_actions & MEAL_ACTIONS else 0
        ),
        attendees=scenario_row.attendees or 0,
        actions_taken=actions_taken,
    )


def _carbon_pricing_scope(region_key: str) -> str:
    """The 'who is covered' text the data file records for a region's scheme, if any."""
    rate_key = CARBON_TAX_KEYS.get(region_key)
    rate_data = TAX_DATA["carbon_tax_rates"].get(rate_key) if rate_key else None
    return (rate_data or {}).get("scope", "")


def _region_note(raw_region: str) -> str:
    """Note when the requested region resolved to 'global' (no regional pricing)."""
    raw = (raw_region or "").strip()
    if not raw:
        return (
            "No region provided — no regional carbon pricing or electricity rate was "
            "applied; global average rates used."
        )
    return (
        f"Region '{raw}' not recognized — no regional carbon pricing applied; "
        "global average electricity rates used. Pick a supported region "
        "(Singapore, EU, UK, Australia, USA, Canada, Japan) for jurisdictional figures."
    )


def generate_financial_report(req: FinancialRequest) -> FinancialResult:
    """Full financial analysis of emission reductions."""
    co2e_reduced = max(0.0, req.baseline_tco2e - req.reduced_tco2e)
    reduction_pct = (co2e_reduced / req.baseline_tco2e * 100) if req.baseline_tco2e > 0 else 0

    notes: List[str] = []

    # Region mismatch: "Marina Bay Sands, Singapore" silently resolves to "global",
    # which zeroes regional pricing. Say so instead of returning a bare zero.
    region_key = normalize_region(req.region)
    if region_key == "global" and (req.region or "").strip().lower().replace(" ", "_") != "global":
        notes.append(_region_note(req.region))

    # Carbon pricing: statutory only for covered entities; otherwise an internal
    # (shadow) carbon price, reported separately from the headline total.
    internal_price = None
    internal_value = 0.0
    if req.covered_by_carbon_pricing:
        carbon_price_basis = "statutory"
        tax_savings = calculate_carbon_tax_savings(co2e_reduced, req.region)
        if not tax_savings:
            notes.append(
                "No statutory carbon price is configured for this region — "
                "carbon tax/ETS savings are 0."
            )
    else:
        carbon_price_basis = "internal"
        tax_savings = []
        scope = _carbon_pricing_scope(region_key)
        reason = (
            "Carbon tax/ETS savings are 0: this entity is not marked as covered by a "
            "compliance carbon pricing scheme."
        )
        if scope:
            reason += f" Scheme coverage: {scope}."
        reason += (
            " Tick 'covered by a carbon pricing scheme' if the organisation has a "
            "statutory liability."
        )
        notes.append(reason)

        internal_price = (
            req.internal_carbon_price_usd
            if req.internal_carbon_price_usd is not None
            else DEFAULT_INTERNAL_CARBON_PRICE_USD
        )
        internal_value = round(internal_price * co2e_reduced, 2)
        notes.append(
            f"Internal carbon price — reference value, not a tax liability: "
            f"USD {internal_price:,.2f}/tCO2e x {co2e_reduced:.2f} tCO2e = "
            f"USD {internal_value:,.2f}. Excluded from total financial savings."
        )

    # Energy cost savings
    energy_savings = calculate_energy_savings(req.energy_kwh_saved, req.region)

    # Catering cost savings — per-meal delta sourced from the data file (not a literal).
    veg = TAX_DATA.get("reduction_action_savings", {}).get("switch_to_vegetarian_meal", {})
    per_meal_saving = abs(veg.get("typical_cost_delta_usd", -2.5))
    catering_savings = req.meal_switches * per_meal_saving

    # Available incentives are listed for awareness only — quantifying grant/tax-credit
    # value needs project-cost inputs the tool doesn't collect, and penalty-avoidance
    # depends on member-state law and entity turnover. Neither is fabricated into the
    # headline; both stay 0.0 with the qualitative list surfaced instead.
    incentives = get_available_incentives(req.region, req.actions_taken)

    # Headline = carbon-tax/ETS liability avoided + real operating-cost savings only.
    primary_tax = tax_savings[0].savings_usd if tax_savings else 0
    total_savings = primary_tax + energy_savings + catering_savings

    return FinancialResult(
        total_co2e_reduced=round(co2e_reduced, 4),
        carbon_tax_savings=tax_savings,
        energy_cost_savings_usd=energy_savings,
        catering_cost_savings_usd=round(catering_savings, 2),
        available_incentives=incentives,
        total_financial_savings_usd=round(total_savings, 2),
        co2e_reduction_pct=round(reduction_pct, 1),
        # ROI in "months" implied an annual recurring saving; an event saving is one-off,
        # so we omit the misleading metric rather than divide a one-time figure by 12.
        roi_months=None,
        compliance_value_usd=0.0,
        carbon_price_basis=carbon_price_basis,
        internal_carbon_price_usd=internal_price,
        internal_carbon_value_usd=internal_value,
        notes=notes,
    )


# -- Obligation scoping --------------------------------------------------------
#
# Which disclosure frameworks actually BIND a given reporting entity is a scoping
# question, not a score. The regulatory facts (status, as-of date, phase-in years,
# size thresholds, tier boundaries) all live in app/data/frameworks.json so they can
# be audited and updated without touching code; the branching each framework needs
# lives here, keyed by the framework's ``scope_rule``.
#
# The cardinal rule: never assert an obligation the profile does not support. A
# missing profile field, a size band that straddles a threshold, or an unspecified
# tier all yield "informational", and an enjoined or merely proposed regime can
# never come out "mandatory".

_FRAMEWORKS: List[Dict[str, Any]] = FRAMEWORKS_DATA["frameworks"]
_EMPLOYEE_BANDS: Dict[str, Any] = FRAMEWORKS_DATA["employee_bands"]
_TURNOVER_BANDS: Dict[str, Any] = FRAMEWORKS_DATA["turnover_bands"]

_PROFILE_INCOMPLETE_NOTE = (
    "Profile incomplete — showing all frameworks as informational. No obligation "
    "determination has been made; complete the reporting profile to scope them."
)
_NO_PROFILE_REASON = (
    "Profile incomplete — shown for information only. This framework's scope test "
    "needs the reporting entity's profile, which was not supplied."
)

# (applies, reason, scope3_required)
ScopeDecision = Tuple[str, str, Optional[bool]]


def _band_position(band_key: Optional[str], bands: Dict[str, Any], threshold: float) -> str:
    """Where a size band sits relative to a "strictly greater than" threshold.

    Returns "above", "below", "straddles" (the band spans the threshold, so the
    test cannot be decided) or "unknown" (no band supplied). Bands in
    frameworks.json are cut at the thresholds the scope tests use, so "straddles"
    should not occur for the encoded frameworks — it exists so that editing the
    bands degrades to an honest "cannot tell" rather than a wrong answer.
    """
    band = bands.get(band_key or "")
    if not band:
        return "unknown"
    low, high = band["min"], band["max"]
    if low > threshold:
        return "above"
    if high is not None and high <= threshold:
        return "below"
    return "straddles"


def _band_label(band_key: Optional[str], bands: Dict[str, Any]) -> str:
    band = bands.get(band_key or "")
    return band["label"] if band else "not specified"


def _indeterminate(what: str) -> ScopeDecision:
    return "informational", f"Cannot scope this framework: {what}", None


# -- Per-framework scope rules -------------------------------------------------

def _scope_eu_csrd(fw: Dict[str, Any], profile: ReportingProfile) -> ScopeDecision:
    thresholds = fw["thresholds"]
    employees = _band_position(profile.employee_band, _EMPLOYEE_BANDS, thresholds["employees_gt"])
    turnover = _band_position(profile.annual_turnover_band, _TURNOVER_BANDS, thresholds["turnover_gt"])
    first_fy = fw["first_reporting_fy"]
    test = f"{thresholds['employees_gt_label']} AND {thresholds['turnover_gt_label']}"

    if profile.reporting_fy is None:
        return _indeterminate("the reporting financial year was not supplied.")
    if employees == "unknown" or turnover == "unknown":
        return _indeterminate("the employee and turnover bands are both needed for the "
                              f"post-Omnibus I size test ({test}).")
    if employees == "below" or turnover == "below":
        return (
            "out_of_scope",
            f"Post-Omnibus I (adopted 24 February 2026), CSRD is mandatory only for "
            f"undertakings with {test}. This profile reports "
            f"{_band_label(profile.employee_band, _EMPLOYEE_BANDS)} employees and "
            f"{_band_label(profile.annual_turnover_band, _TURNOVER_BANDS)} turnover.",
            None,
        )
    if employees == "straddles" or turnover == "straddles":
        return _indeterminate(f"a reported size band spans the threshold ({test}).")
    if profile.reporting_fy < first_fy:
        return (
            "not_in_force",
            f"In scope on size, but CSRD applies to financial years starting on or after "
            f"1 January {first_fy} (simplified ESRS adopted 3 July 2026). This profile "
            f"reports FY{profile.reporting_fy}.",
            None,
        )
    return (
        "mandatory",
        f"In scope: {test}, reporting FY{profile.reporting_fy} (CSRD applies to financial "
        f"years starting on or after 1 January {first_fy}). ESRS E1 requires Scope 3.",
        True,
    )


def _scope_sgx_issb(fw: Dict[str, Any], profile: ReportingProfile) -> ScopeDecision:
    tiers = fw["tiers"]
    fy = profile.reporting_fy
    if fy is None:
        return _indeterminate("the reporting financial year was not supplied.")
    if not profile.listing_status:
        return _indeterminate("the listing status determines the SGX phase-in tier.")

    tier = tiers.get(profile.listing_status)
    if tier is None:
        return _indeterminate(
            f"listing status '{profile.listing_status}' is not an SGX reporting tier."
        )

    if profile.listing_status == "sti_constituent":
        first_fy, scope3_fy = tier["first_reporting_fy"], tier["scope3_from_fy"]
        if fy < first_fy:
            return (
                "not_in_force",
                f"STI constituents report ISSB climate-related disclosures from FY{first_fy}; "
                f"this profile reports FY{fy}.",
                None,
            )
        scope3 = fy >= scope3_fy
        return (
            "mandatory",
            f"STI constituent: ISSB climate-related disclosure mandatory from FY{first_fy}, "
            f"Scope 3 mandatory from FY{scope3_fy}. Reporting FY{fy}, so Scope 3 is "
            f"{'required' if scope3 else 'not yet required'}.",
            scope3,
        )

    # Non-STI tiers: the phase-in year turns on size, and Scope 3 stays voluntary.
    size = _band_position(profile.annual_turnover_band, _TURNOVER_BANDS, tier["size_threshold"])
    size_test = tier["size_threshold_label"]
    approximation = (
        f" The statutory test is {size_test}, approximated here by the reported size band."
    )
    if size in ("unknown", "straddles"):
        return _indeterminate(f"the tier turns on {size_test} and the reported band cannot settle it.")

    if profile.listing_status == "listed":
        first_fy = (tier["first_reporting_fy_above_threshold"] if size == "above"
                    else tier["first_reporting_fy_below_threshold"])
        if fy < first_fy:
            return (
                "not_in_force",
                f"{tier['label']}: in scope from FY{first_fy}; this profile reports FY{fy}."
                + approximation,
                None,
            )
        return (
            "mandatory",
            f"{tier['label']}: climate reporting from FY{first_fy}, reporting FY{fy}. "
            f"Scope 3 disclosure is voluntary outside the STI tier." + approximation,
            False,
        )

    # Non-listed: only the large ones ever come into scope.
    first_fy = tier["first_reporting_fy_above_threshold"]
    if size == "below":
        return (
            "out_of_scope",
            f"Only large non-listed companies ({size_test}) come into scope, from FY{first_fy}. "
            f"This profile reports {_band_label(profile.annual_turnover_band, _TURNOVER_BANDS)}."
            + approximation,
            None,
        )
    if fy < first_fy:
        return (
            "not_in_force",
            f"{tier['label']}: in scope from FY{first_fy}; this profile reports FY{fy}."
            + approximation,
            None,
        )
    return (
        "mandatory",
        f"{tier['label']}: climate reporting from FY{first_fy}, reporting FY{fy}. "
        f"Scope 3 disclosure is voluntary outside the STI tier." + approximation,
        False,
    )


def _scope_uk_srs(fw: Dict[str, Any], profile: Optional[ReportingProfile]) -> ScopeDecision:
    # Published for voluntary use; the mandatory regime is only proposed, so this
    # can never be "mandatory" regardless of how large the entity is.
    return "voluntary", fw["reason"], None


def _scope_au_asrs(fw: Dict[str, Any], profile: ReportingProfile) -> ScopeDecision:
    fy = profile.reporting_fy
    if fy is None:
        return _indeterminate("the reporting financial year was not supplied.")
    tier = fw["tiers"].get(profile.listing_status or "")
    if tier is None:
        return _indeterminate(
            "the ASRS group was not specified. AASB S2 phases in by entity group, which "
            "depends on consolidated revenue, assets, employees and emitter status."
        )

    first_fy, scope3_fy = tier["first_reporting_fy"], tier["scope3_from_fy"]
    if fy < first_fy:
        return (
            "not_in_force",
            f"{tier['label']}: {tier['first_period_note']} This profile reports FY{fy}.",
            None,
        )
    scope3 = fy >= scope3_fy
    first_period = "" if scope3 else (
        " Scope 3 is not required in an entity's first reporting period and becomes "
        "mandatory from the second."
    )
    return (
        "mandatory",
        f"{tier['label']}: {tier['first_period_note']} Reporting FY{fy}, so Scope 3 is "
        f"{'required' if scope3 else 'not yet required'}.{first_period}",
        scope3,
    )


def _scope_ca_sb253(fw: Dict[str, Any], profile: ReportingProfile) -> ScopeDecision:
    thresholds = fw["thresholds"]
    fy = profile.reporting_fy
    if fy is None:
        return _indeterminate("the reporting financial year was not supplied.")
    if not profile.does_business_in_california:
        return (
            "out_of_scope",
            "SB 253 applies to entities doing business in California; this profile does "
            "not report a California nexus.",
            None,
        )
    revenue = _band_position(profile.annual_turnover_band, _TURNOVER_BANDS, thresholds["revenue_gt"])
    test = thresholds["revenue_gt_label"]
    if revenue in ("unknown", "straddles"):
        return _indeterminate(f"the revenue test is {test} and the reported band cannot settle it.")
    if revenue == "below":
        return (
            "out_of_scope",
            f"SB 253 applies to entities with {test}. This profile reports "
            f"{_band_label(profile.annual_turnover_band, _TURNOVER_BANDS)} revenue.",
            None,
        )

    first_fy, scope3_fy, due = fw["first_reporting_fy"], fw["scope3_from_fy"], fw["first_report_due"]
    if fy < first_fy:
        return (
            "not_in_force",
            f"In scope on size and California nexus, but the first reporting year is "
            f"FY{first_fy}; this profile reports FY{fy}.",
            None,
        )
    scope3 = fy >= scope3_fy
    return (
        "mandatory",
        f"In scope: {test} and doing business in California. The first Scope 1 and 2 "
        f"report (covering FY{first_fy}) is due {due}; Scope 3 reporting begins in "
        f"{scope3_fy + 1} covering FY{scope3_fy}. Reporting FY{fy}, so Scope 3 is "
        f"{'required' if scope3 else 'not yet required'}.",
        scope3,
    )


def _scope_ca_sb261(fw: Dict[str, Any], profile: Optional[ReportingProfile]) -> ScopeDecision:
    # An enjoined statute is never a live obligation, whatever the profile says.
    return "enjoined", fw["reason"], None


_SCOPE_RULES = {
    "eu_csrd": _scope_eu_csrd,
    "sgx_issb": _scope_sgx_issb,
    "uk_srs": _scope_uk_srs,
    "au_asrs": _scope_au_asrs,
    "ca_sb253": _scope_ca_sb253,
    "ca_sb261": _scope_ca_sb261,
}


def _base_check(fw: Dict[str, Any], applies: str, reason: str,
                scope3_required: Optional[bool] = None) -> ComplianceCheck:
    return ComplianceCheck(
        framework=fw["name"],
        framework_key=fw["key"],
        applies=applies,
        reason=reason,
        status=fw["status"],
        as_of=fw["as_of"],
        first_reporting_fy=fw.get("first_reporting_fy"),
        scope3_required=scope3_required,
        gaps=list(fw.get("gaps", [])),
        recommendations=list(fw.get("recommendations", [])),
    )


def _voluntary_check(
    fw: Dict[str, Any], has_scope3: bool, has_ghg_report: bool
) -> ComplianceCheck:
    """The frameworks that bind nobody by force of law — but that the tool CAN assess."""
    check = _base_check(fw, "voluntary", fw.get("reason", fw["note"]))

    if fw["key"] == "ghg_protocol":
        # Completeness of the inventory the tool actually holds.
        check.score_pct = 100.0 if (has_ghg_report and has_scope3) else (60.0 if has_ghg_report else 20.0)
        check.readiness = ("compliant" if check.score_pct >= 80
                           else "partial" if check.score_pct >= 40 else "non_compliant")
        if not has_scope3:
            check.gaps.append("Scope 3 emissions not fully measured")
        if not has_ghg_report:
            check.gaps.append("No formal GHG report generated")
    elif fw["key"] == "nzce":
        check.score_pct = 60.0 if (has_ghg_report and has_scope3) else (40.0 if has_ghg_report else 25.0)
        check.readiness = "partial"
    elif fw["key"] == "iso_20121_2024":
        # Never a number: a management system is certified against clauses by audit.
        check.clause_checklist = [
            ComplianceClause(clause=item["clause"], requirement=item["requirement"])
            for item in fw.get("clause_checklist", [])
        ]
    return check


def _intensity_check(
    fw: Dict[str, Any], total_tco2e: float, event_days: int, attendees: int
) -> ComplianceCheck:
    """Informational comparison against published EVENT bands (never an SBTi call)."""
    per_att_day = total_tco2e / max(attendees, 1) / max(event_days, 1)
    band = fw["typical_band_tco2e_per_attendee_day"]
    on_track = per_att_day <= band

    check = _base_check(fw, "informational", fw["reason"])
    check.score_pct = 80.0 if on_track else 40.0
    check.readiness = "compliant" if on_track else "partial"
    if not on_track:
        check.gaps.append(
            f"{per_att_day:.3f} tCO2e/attendee/day exceeds the ~{band} typical event band"
        )
    return check


def get_compliance_report(
    total_tco2e: float,
    has_scope3: bool,
    has_ghg_report: bool,
    region: str,
    event_days: int,
    attendees: int,
    reporting_profile: Optional[ReportingProfile] = None,
) -> ComplianceReport:
    """Scope each reporting framework against the entity profile.

    Frameworks are filtered to the requested region, then each is resolved to an
    ``applies`` value with the reason behind it. Without a profile every regulated
    framework comes back "informational" — the report describes the landscape and
    asserts no obligation.
    """
    region = normalize_region(region)
    checks: List[ComplianceCheck] = []

    for fw in _FRAMEWORKS:
        regions = fw.get("regions", ["*"])
        if "*" not in regions and region not in regions:
            continue

        rule = fw["scope_rule"]
        if rule == "always_voluntary":
            checks.append(_voluntary_check(fw, has_scope3, has_ghg_report))
        elif rule == "benchmark":
            checks.append(_intensity_check(fw, total_tco2e, event_days, attendees))
        elif reporting_profile is None and fw.get("profile_required", True):
            checks.append(_base_check(fw, "informational", _NO_PROFILE_REASON))
        else:
            applies, reason, scope3 = _SCOPE_RULES[rule](fw, reporting_profile)
            checks.append(_base_check(fw, applies, reason, scope3))

    profile_complete = reporting_profile is not None and reporting_profile.reporting_fy is not None

    return ComplianceReport(
        checks=checks,
        mandatory_frameworks=[c.framework for c in checks if c.applies == "mandatory"],
        profile_complete=profile_complete,
        profile_note="" if profile_complete else _PROFILE_INCOMPLETE_NOTE,
        frameworks_as_of=FRAMEWORKS_DATA["as_of"],
        # We do not fabricate a probability-weighted penalty. Statutory maximum exposure
        # is surfaced qualitatively in the per-framework gaps instead.
        penalty_risk_usd=0.0,
        disclaimer=(
            "Informational self-assessment of which reporting frameworks apply, based on "
            "the profile entered — not a third-party compliance determination or legal "
            "advice. Confirm scope and deadlines with the regulator or your adviser before "
            "relying on them."
        ),
    )
