"""
Financial savings + tax compliance engine.
Calculates carbon tax savings, energy cost reductions, green incentives,
and compliance value from emission reduction actions.
"""
from typing import List, Dict, Any

from app.models.schemas import (
    FinancialRequest, FinancialResult, TaxSaving, ComplianceCheck, ComplianceReport
)
from app.services.data_files import TAX_DATA
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
    from app.services.emissions_engine import estimate_venue_kwh

    baseline = scenario_row.total_tco2e or 0.0
    reduced = baseline * (1 - reduction_pct / 100)

    payload = scenario_row.input_payload or {}
    venue_kwh = 0.0
    try:
        scenario_input = EventScenarioInput.model_validate(payload)
        venue_kwh = estimate_venue_kwh(
            scenario_input.venue_energy, scenario_input.attendees, scenario_input.event_days
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
            f"USD {internal_price:,.0f}/tCO2e x {co2e_reduced:.2f} tCO2e = "
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


def get_compliance_report(
    total_tco2e: float,
    has_scope3: bool,
    has_ghg_report: bool,
    region: str,
    event_days: int,
    attendees: int,
) -> ComplianceReport:
    """Generate compliance status across key frameworks."""
    checks = []
    mandatory = []

    # GHG Protocol — completeness of the inventory the tool can actually assess.
    ghg_score = 100 if (has_ghg_report and has_scope3) else (60 if has_ghg_report else 20)
    ghg_gaps = []
    if not has_scope3:
        ghg_gaps.append("Scope 3 emissions not fully measured")
    if not has_ghg_report:
        ghg_gaps.append("No formal GHG report generated")
    checks.append(ComplianceCheck(
        framework="GHG Protocol",
        status="compliant" if ghg_score >= 80 else ("partial" if ghg_score >= 40 else "non_compliant"),
        score_pct=ghg_score,
        gaps=ghg_gaps,
        recommendations=["Calculate all 3 scopes", "Generate downloadable GHG inventory report"],
    ))

    # ISO 20121 — a management-system standard certified by third-party audit, not a
    # numeric per-event score. We present it as a checklist of what's still required.
    checks.append(ComplianceCheck(
        framework="ISO 20121 (Sustainable Events management system)",
        status="partial",
        score_pct=50.0,
        gaps=[
            "Sustainability policy not documented",
            "Stakeholder engagement plan not provided",
            "Supply-chain sustainability procedures not evidenced",
            "Third-party certification audit not performed",
        ],
        recommendations=[
            "ISO 20121 certifies a management system via accredited audit, not an emissions number",
            "Document policy, objectives, stakeholder engagement and continual improvement",
        ],
    ))

    # Net Zero Carbon Events — the event industry's own measurement methodology
    # (9 emission categories, Scope 1/2/3 per GHG Protocol, biennial reporting).
    # Voluntary signatory-based, so NOT added to mandatory_frameworks.
    nzce_score = 60.0 if (has_ghg_report and has_scope3) else (40.0 if has_ghg_report else 25.0)
    checks.append(ComplianceCheck(
        framework="Net Zero Carbon Events (NZCE) Measurement Methodology",
        status="partial",
        score_pct=nzce_score,
        gaps=[
            "Categories measured here: Travel, Local Transport, Energy, Accommodation, "
            "Food & Beverage, Waste, Digital Content, and parts of Production & Materials; "
            "Freight & Logistics only as an equipment freight line",
            "Biennial public reporting commitment to NZCE not evidenced",
            "No baseline year or reduction trajectory towards net zero by 2050 provided",
        ],
        recommendations=[
            "Use the NZCE category mapping section included in the exported reports",
            "Become an NZCE signatory and report progress at least every two years",
            "Set a baseline year and interim reduction targets per the NZCE roadmap",
        ],
    ))

    # Event carbon intensity vs published EVENT benchmarks (informational — SBTi is a
    # CORPORATE framework, not an event one). Compare per attendee per day correctly.
    per_att_day = total_tco2e / max(attendees, 1) / max(event_days, 1)
    band_typical = 0.30  # tCO2e/attendee/day (MeetGreen/JMIC range ~0.15–0.5)
    on_track = per_att_day <= band_typical
    intensity_score = 80.0 if on_track else 40.0
    checks.append(ComplianceCheck(
        framework="Event carbon intensity (vs published event benchmarks)",
        status="compliant" if on_track else "partial",
        score_pct=intensity_score,
        gaps=([] if on_track else
              [f"{per_att_day:.3f} tCO2e/attendee/day exceeds the ~{band_typical} typical event band"]),
        recommendations=[
            "Informational only — not an SBTi determination (SBTi validates corporate inventories)",
            "Compare against Net Zero Carbon Events / MeetGreen published event bands",
        ],
    ))

    # Region-specific reporting regimes.
    region = normalize_region(region)
    if region == "singapore":
        mandatory.append("SGX Sustainability Reporting (Scope 1+2)")
        sgx_score = 70 if has_ghg_report else 20
        checks.append(ComplianceCheck(
            framework="SGX Sustainability Reporting",
            status="partial" if sgx_score >= 40 else "non_compliant",
            score_pct=sgx_score,
            gaps=["Mandatory Scope 1+2 from FY2025; Scope 3 from FY2026 for STI constituents"],
            recommendations=["Prepare annual sustainability report", "Align with IFRS S2 / ISSB"],
        ))

    if region == "european_union":
        mandatory.append("EU CSRD")
        csrd_score = 50 if has_ghg_report else 10
        checks.append(ComplianceCheck(
            framework="EU CSRD",
            status="partial" if csrd_score >= 40 else "non_compliant",
            score_pct=csrd_score,
            gaps=[
                "Double materiality assessment required",
                "ESRS E1 climate disclosure incomplete",
                "Statutory penalties are member-state specific (e.g. Germany: up to EUR 10M or 5% of turnover); "
                "Omnibus I (in force 18 Mar 2026) narrows in-scope entities",
            ],
            recommendations=["Commission double materiality assessment", "Align reporting with ESRS standards"],
        ))

    overall = sum(c.score_pct for c in checks) / len(checks) if checks else 0

    return ComplianceReport(
        overall_score_pct=round(overall, 1),
        checks=checks,
        mandatory_frameworks=mandatory,
        # We do not fabricate a probability-weighted penalty. Statutory maximum exposure
        # is surfaced qualitatively in the CSRD gaps above instead.
        penalty_risk_usd=0.0,
        disclaimer=(
            "Informational self-assessment based on the data entered — not a third-party "
            "compliance determination or legal advice. Scores indicate completeness/maturity, "
            "not certified conformance."
        ),
    )
