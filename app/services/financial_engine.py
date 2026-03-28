"""
Financial savings + tax compliance engine.
Calculates carbon tax savings, energy cost reductions, green incentives,
and compliance value from emission reduction actions.
"""
import json
from pathlib import Path
from typing import List, Dict, Any

from app.models.schemas import (
    FinancialRequest, FinancialResult, TaxSaving, ComplianceCheck, ComplianceReport
)

_DATA_DIR = Path(__file__).parent.parent / "data"

with open(_DATA_DIR / "tax_incentives.json") as f:
    TAX_DATA = json.load(f)

# Electricity cost per kWh by region (USD)
ELECTRICITY_RATES_USD = {
    "singapore": 0.22,
    "eu": 0.28,
    "uk": 0.34,
    "australia": 0.25,
    "usa": 0.16,
    "global": 0.18,
}

# USD exchange rates to local
USD_TO_LOCAL = {
    "singapore": ("SGD", 1.0 / 0.74),
    "eu": ("EUR", 1.0 / 1.08),
    "uk": ("GBP", 1.0 / 1.27),
    "australia": ("AUD", 1.0 / 0.65),
    "usa": ("USD", 1.0),
    "global": ("USD", 1.0),
}


def calculate_carbon_tax_savings(
    co2e_reduced_tco2e: float, region: str
) -> List[TaxSaving]:
    """Calculate direct carbon tax savings from emission reductions."""
    savings = []
    region_key = region.lower().replace(" ", "_")

    rates_map = {
        "singapore": TAX_DATA["carbon_tax_rates"]["singapore"],
        "european_union": TAX_DATA["carbon_tax_rates"]["european_union"],
        "eu": TAX_DATA["carbon_tax_rates"]["european_union"],
        "uk": TAX_DATA["carbon_tax_rates"]["united_kingdom"],
        "united_kingdom": TAX_DATA["carbon_tax_rates"]["united_kingdom"],
        "australia": TAX_DATA["carbon_tax_rates"]["australia"],
        "usa": TAX_DATA["carbon_tax_rates"]["usa_california"],
        "usa_california": TAX_DATA["carbon_tax_rates"]["usa_california"],
    }

    if region_key in rates_map:
        rate_data = rates_map[region_key]
        usd_rate = rate_data.get("usd_exchange", 1.0)

        # Current rate
        if "current_rate_sgd" in rate_data:
            local_price = rate_data["current_rate_sgd"]
            currency = "SGD"
            savings_usd = co2e_reduced_tco2e * local_price * usd_rate
        elif "ets_price_eur" in rate_data:
            local_price = rate_data["ets_price_eur"]
            currency = "EUR"
            savings_usd = co2e_reduced_tco2e * local_price * usd_rate
        elif "ets_price_gbp" in rate_data:
            local_price = rate_data["ets_price_gbp"]
            currency = "GBP"
            savings_usd = co2e_reduced_tco2e * local_price * usd_rate
        elif "accu_price_aud" in rate_data:
            local_price = rate_data["accu_price_aud"]
            currency = "AUD"
            savings_usd = co2e_reduced_tco2e * local_price * usd_rate
        elif "cap_trade_price_usd" in rate_data:
            local_price = rate_data["cap_trade_price_usd"]
            currency = "USD"
            savings_usd = co2e_reduced_tco2e * local_price
        else:
            local_price = 25
            currency = "USD"
            savings_usd = co2e_reduced_tco2e * local_price

        savings.append(TaxSaving(
            scheme=rate_data.get("scheme", f"{region.title()} Carbon Scheme"),
            savings_usd=round(savings_usd, 2),
            savings_local=round(co2e_reduced_tco2e * local_price, 2),
            currency=currency,
            description=f"{co2e_reduced_tco2e:.2f} tCO₂e × {local_price} {currency}/tCO₂e"
        ))

        # Future rate savings (Singapore 2026 rate)
        if region_key == "singapore" and "2026_rate_sgd" in rate_data:
            future_price = rate_data["2026_rate_sgd"]
            future_savings_usd = co2e_reduced_tco2e * future_price * usd_rate
            savings.append(TaxSaving(
                scheme="Singapore Carbon Tax (2026 rate)",
                savings_usd=round(future_savings_usd, 2),
                savings_local=round(co2e_reduced_tco2e * future_price, 2),
                currency="SGD",
                description=f"Projected at SGD {future_price}/tCO₂e from 2026"
            ))

    # Always add voluntary carbon market value
    vcm_savings = co2e_reduced_tco2e * 15  # ~$15/tCO2e VCM
    savings.append(TaxSaving(
        scheme="Voluntary Carbon Market (offset credits)",
        savings_usd=round(vcm_savings, 2),
        savings_local=round(vcm_savings, 2),
        currency="USD",
        description=f"Carbon credits at ~USD 15/tCO₂e (Gold Standard estimate)"
    ))

    return savings


def calculate_energy_savings(energy_kwh_saved: float, region: str) -> float:
    """Calculate direct energy cost savings in USD."""
    rate = ELECTRICITY_RATES_USD.get(region.lower(), ELECTRICITY_RATES_USD["global"])
    return round(energy_kwh_saved * rate, 2)


def get_available_incentives(region: str, actions: List[str]) -> List[Dict[str, Any]]:
    """Match taken actions to available green incentives."""
    region_key = region.lower()
    region_map = {
        "singapore": "singapore",
        "eu": "european_union",
        "european_union": "european_union",
        "uk": "united_kingdom",
        "united_kingdom": "united_kingdom",
        "australia": "australia",
        "usa": "usa",
    }
    mapped = region_map.get(region_key, "singapore")
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


def estimate_incentive_value(incentives: List[Dict], baseline_tco2e: float, attendees: int) -> float:
    """Conservative USD estimate from matched incentives.

    Only directly quantifiable incentives are included in the total savings figure.
    Unbounded grants/financing programs stay listed in `available_incentives` but are
    not converted into cash savings without project-cost inputs.
    """
    total = 0.0
    for inc in incentives:
        itype = inc.get("type", "")
        if itype == "tax_credit":
            # Estimate 30% of energy cost at $0.18/kWh for estimated kWh
            kwh_est = baseline_tco2e * 1000 / 0.4  # rough reverse from Singapore grid
            total += kwh_est * 0.18 * 0.30
        elif itype == "compliance_requirement":
            # Penalty avoidance value
            total += inc.get("max_grant_sgd", 10000) * 0.01  # 1% of max penalty
        elif itype in {"grant", "tax_allowance", "tax_deduction", "financing"}:
            continue
    return round(total, 2)


def calculate_compliance_value(actions: List[str], region: str) -> float:
    """USD value of avoiding non-compliance penalties."""
    value = 0.0
    frameworks = TAX_DATA["compliance_frameworks"]

    if "ghg_reporting" in actions or "sustainability_audit" in actions:
        # EU CSRD penalty avoidance
        if region.lower() in ("eu", "european_union"):
            value += frameworks["eu_csrd"]["penalties_eur"] * 0.001 * 1.08  # 0.1% of max penalty
        # SGX penalty (regulatory action risk)
        if region.lower() == "singapore":
            value += 50000  # Estimated regulatory compliance value

    if "carbon_audit" in actions:
        value += 5000  # Cost of non-compliance investigation

    return round(value, 2)


def generate_financial_report(req: FinancialRequest) -> FinancialResult:
    """Full financial analysis of emission reductions."""
    co2e_reduced = max(0.0, req.baseline_tco2e - req.reduced_tco2e)
    reduction_pct = (co2e_reduced / req.baseline_tco2e * 100) if req.baseline_tco2e > 0 else 0

    # Carbon tax savings
    tax_savings = calculate_carbon_tax_savings(co2e_reduced, req.region)

    # Energy cost savings
    energy_savings = calculate_energy_savings(req.energy_kwh_saved, req.region)

    # Catering cost savings (vegetarian/vegan meals cheaper)
    catering_savings = req.meal_switches * 2.5  # ~$2.5 saved per switched meal

    # Available incentives
    incentives = get_available_incentives(req.region, req.actions_taken)
    incentive_value = estimate_incentive_value(incentives, req.baseline_tco2e, req.attendees)

    # Compliance value
    compliance_value = calculate_compliance_value(req.actions_taken, req.region)

    # Primary tax saving (current year)
    primary_tax = tax_savings[0].savings_usd if tax_savings else 0
    total_savings = primary_tax + energy_savings + catering_savings + incentive_value + compliance_value

    # ROI: if we spent ~$50/attendee on sustainability measures, when do we break even?
    investment_est = req.attendees * 50 if req.attendees > 0 else 500
    roi_months = (investment_est / (total_savings / 12)) if total_savings > 0 else None

    return FinancialResult(
        total_co2e_reduced=round(co2e_reduced, 4),
        carbon_tax_savings=tax_savings,
        energy_cost_savings_usd=energy_savings,
        catering_cost_savings_usd=round(catering_savings, 2),
        available_incentives=incentives,
        total_financial_savings_usd=round(total_savings, 2),
        co2e_reduction_pct=round(reduction_pct, 1),
        roi_months=round(roi_months, 1) if roi_months else None,
        compliance_value_usd=compliance_value,
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

    # GHG Protocol
    ghg_score = 100 if (has_ghg_report and has_scope3) else (60 if has_ghg_report else 20)
    checks.append(ComplianceCheck(
        framework="GHG Protocol",
        status="compliant" if ghg_score >= 80 else ("partial" if ghg_score >= 40 else "non_compliant"),
        score_pct=ghg_score,
        gaps=[] if ghg_score == 100 else [
            "Scope 3 emissions not fully measured" if not has_scope3 else "",
            "No formal GHG report generated" if not has_ghg_report else "",
        ],
        recommendations=["Calculate all 3 scopes", "Generate downloadable GHG inventory report"],
    ))

    # ISO 20121 Sustainable Events
    iso_score = 40  # Base score for using this tool
    if has_ghg_report:
        iso_score += 30
    if total_tco2e > 0:
        iso_score += 30
    checks.append(ComplianceCheck(
        framework="ISO 20121 (Sustainable Events)",
        status="partial",
        score_pct=iso_score,
        gaps=["Supply chain sustainability policy not documented", "Stakeholder engagement plan not provided"],
        recommendations=["Document sustainability policy", "Engage suppliers on emission reporting"],
    ))

    # SBTi 1.5°C pathway
    # Rough proxy: if per-attendee < 0.5 tCO2e for multi-day event → on pathway
    per_att = total_tco2e / max(attendees, 1)
    on_pathway = per_att < (0.3 * event_days)
    sbti_score = 80 if on_pathway else 35
    checks.append(ComplianceCheck(
        framework="SBTi 1.5°C Pathway",
        status="compliant" if on_pathway else "non_compliant",
        score_pct=sbti_score,
        gaps=[] if on_pathway else [f"Per-attendee emissions {per_att:.2f} tCO₂e exceeds 1.5°C budget"],
        recommendations=["Target <0.3 tCO₂e/attendee/day", "Offset residual emissions with high-quality credits"],
    ))

    # Region-specific
    if region.lower() == "singapore":
        mandatory.append("SGX Sustainability Reporting (Scope 1+2)")
        sgx_score = 70 if has_ghg_report else 20
        checks.append(ComplianceCheck(
            framework="SGX Sustainability Reporting",
            status="partial" if sgx_score >= 40 else "non_compliant",
            score_pct=sgx_score,
            gaps=["Scope 3 from supply chain not reported (mandatory from 2026)"],
            recommendations=["Prepare annual sustainability report", "Align with GRI or TCFD framework"],
        ))

    if region.lower() in ("eu", "european_union"):
        mandatory.append("EU CSRD")
        csrd_score = 50 if has_ghg_report else 10
        checks.append(ComplianceCheck(
            framework="EU CSRD",
            status="partial" if csrd_score >= 40 else "non_compliant",
            score_pct=csrd_score,
            gaps=["Double materiality assessment required", "ESRS E1 climate disclosure incomplete"],
            recommendations=["Commission double materiality assessment", "Align reporting with ESRS standards"],
        ))

    overall = sum(c.score_pct for c in checks) / len(checks) if checks else 0

    # Penalty risk: EU CSRD if non-compliant
    penalty_risk = 0.0
    if region.lower() in ("eu", "european_union") and not has_ghg_report:
        penalty_risk = TAX_DATA["compliance_frameworks"]["eu_csrd"]["penalties_eur"] * 0.001 * 1.08

    return ComplianceReport(
        overall_score_pct=round(overall, 1),
        checks=checks,
        mandatory_frameworks=mandatory,
        penalty_risk_usd=round(penalty_risk, 2),
    )
