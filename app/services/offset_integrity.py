"""Offset credit integrity — the evidence a retired credit needs to back a claim.

Why this exists:
  * The **VCMI Claims Code of Practice** only recognises retirements made from
    1 January 2026 when the credits are ICVCM **CCP-approved** or issued under
    **Paris Agreement Article 6.4** with a corresponding adjustment. A tonne
    bought without one of those labels can still be a real contribution, but it
    cannot carry a compensation claim.
  * ISO 14068-1:2023 additionally requires the retirement itself to be evidenced —
    a registry serial and a retirement date — and a vintage, so the tonne can be
    traced and cannot be double counted.

`claim_eligible` is therefore a two-part gate: an integrity label (CCP *or*
Article 6.4) **plus** traceable retirement evidence (serial + date + vintage).
It is deliberately a data check, not a judgement: nothing here asserts the credit
is good, only that the evidence needed to make a claim about it is on file.

The module also holds the integrity-adjacent helpers the offsets router and the
exports share, so they live next to the gate they qualify:
  * :func:`sum_by_registry` — the retired-only aggregation that decides which
    registries a compensation statement may name.
  * :func:`additionality_risk_warning` — surfaced with a recommendation whose
    project type is flagged high additionality risk in ``carbon_offsets.json``
    (REDD+ today).
  * :func:`residual_basis` — offsetting applies to *residual* emissions, so the
    recommendation is sized against the total net of a stated reduction, and the
    basis it used is reported alongside the tonnage.
"""

from typing import Any, Dict, Iterable, Tuple

# Risk tiers in app/data/carbon_offsets.json that warrant a warning on a recommendation.
_HIGH_ADDITIONALITY_RISK = {"high", "very high"}

HIGH_ADDITIONALITY_RISK_WARNING = (
    "High additionality risk: crediting baselines for this project type are "
    "contested and over-crediting has been documented. Require ICVCM CCP-approved "
    "credits and independent baseline evidence before retiring them against a claim."
)

# Reported alongside the tonnage a recommendation was sized against.
BASIS_GROSS = "gross"
BASIS_NET_OF_REDUCTIONS = "net_of_reductions"


def claim_eligible(purchase: Any) -> bool:
    """True when ``purchase`` carries the evidence a post-2026 claim requires.

    ``purchase`` is any object with the integrity attributes (an
    ``OffsetPurchaseDB`` row in practice); missing attributes read as absent, so
    rows written before the integrity migration are simply not eligible.
    """
    labelled = bool(getattr(purchase, "ccp_approved", None)) or bool(
        getattr(purchase, "article6_adjustment", None)
    )
    return bool(
        labelled
        and getattr(purchase, "retirement_serial", None)
        and getattr(purchase, "retirement_date", None)
        and getattr(purchase, "vintage_year", None)
    )


def sum_by_registry(purchases: Iterable[Any]) -> Dict[str, float]:
    """tCO2e per registry across ``purchases``.

    Both the offsets API and the exports feed the *retired* subset of this through
    :func:`app.services.claims.describe_credit_sources`, so the compensation
    statement names only registries whose credits were actually retired.
    """
    totals: Dict[str, float] = {}
    for p in purchases:
        totals[p.registry] = totals.get(p.registry, 0.0) + p.quantity_tco2e
    return totals


def additionality_risk_warning(additionality_risk: str | None) -> str:
    """Warning text for a high-additionality-risk project type, else ``""``."""
    if (additionality_risk or "").strip().lower() in _HIGH_ADDITIONALITY_RISK:
        return HIGH_ADDITIONALITY_RISK_WARNING
    return ""


def residual_basis(total_tco2e: float, reduction_pct: float | None = 0.0) -> Tuple[float, str]:
    """The tonnage a recommendation should cover, and the basis it was sized on.

    A reduction commitment of ``reduction_pct`` leaves ``total × (1 − pct/100)``
    as residual. With no stated reduction the sizing falls back to the gross
    total — reported as ``"gross"`` so it is never mistaken for a residual.
    """
    pct = float(reduction_pct or 0.0)
    if pct <= 0:
        return float(total_tco2e), BASIS_GROSS
    pct = min(pct, 100.0)
    return float(total_tco2e) * (1 - pct / 100.0), BASIS_NET_OF_REDUCTIONS
