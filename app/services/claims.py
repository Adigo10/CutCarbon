"""Green-claims guardrail — keeps generated text free of offset-based neutrality claims.

Why this exists:
  * EU Directive (EU) 2024/825 ("Empowering Consumers for the Green Transition",
    national rules apply from 27 September 2026) puts claims that a product or
    service is "carbon neutral", "climate neutral" or "climate positive" on the
    Annex I blacklist whenever the claim rests on greenhouse-gas offsetting.
  * The UK Digital Markets, Competition and Consumers Act 2024 gives the CMA
    direct enforcement powers over the same kind of unsubstantiated green claim.
  * ISO 14068-1:2023 replaced the withdrawn PAS 2060: reduce first against a
    documented baseline, restrict offsetting to residual emissions, and evidence
    the retirement of verified, additional, permanent credits.

So instead of a claim we state a fact — the construction rendered by
:func:`compliant_compensation_statement`:

    "<total> tCO2e measured, <pct>% reduced, <residual> tCO2e residual
     compensated outside the value chain via <credits>"

When only part of the residual is covered by retired credits the statement names
both the covered and the outstanding tonnage, so partial coverage can never be
read as full compensation.

A banned phrase is *redacted*, not paraphrased: it is replaced by
:data:`CLAIM_REDACTION`, which points the reader at those figures. Substituting a
readable phrase ("measured, reduced and residual-compensated", "lower-carbon")
would trade one unsubstantiated claim for another — the rewrite must never assert
a reduction, a compensation or a comparison that the data does not back.

Scope: this linter is for text the product *generates* (chat replies, export and
offset narrative, free text saved alongside them). It is deliberately not applied
to static UI labels or to factual references such as the "Net Zero Carbon Events"
methodology name.

Denylist judgement calls:
  * "net zero"/"net-zero" is only banned in the phrase "net zero event(s)".
    Bare "net zero" is legitimate in framework names ("Net Zero Carbon Events")
    and trajectories ("net-zero by 2050").
  * "green event(s)" is banned as a claim but not when it opens a proper noun
    ("Green Events Tool", "Green Events Guide" — both cited as factor sources),
    detected as a following capitalized word.
  * The noun forms "carbon/climate neutrality" are banned too: they are the same
    claim, and a guardrail that only caught the adjective would be trivial to
    slip past.
"""

import re
from typing import Mapping

DEFAULT_CREDIT_DESC = "unspecified credits (registry not recorded)"

# What a banned phrase is replaced with. Deliberately not a paraphrase: it asserts
# nothing about reductions, compensation or comparisons, and it contains no banned
# phrase itself, which is what makes sanitizing idempotent.
CLAIM_REDACTION = "[claim removed — see the measured/reduced/compensated figures]"

# Every pattern is word-boundary anchored and matched case-insensitively, so
# unrelated words are never touched ("neutralization", "greenhouse",
# "decarbonization").
_CLAIM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:carbon|climate)[\s-]+neutrality\b", re.I),
    re.compile(r"\b(?:carbon|climate)[\s-]+neutral\b", re.I),
    re.compile(r"\b(?:climate[\s-]+positive|carbon[\s-]+negative)\b", re.I),
    re.compile(r"\bnet[\s-]+zero\s+events?\b", re.I),
    re.compile(r"\b(?:eco|climate)[\s-]+friendly\b", re.I),
    # (?-i:[A-Z]) stays case-sensitive inside the case-insensitive pattern so the
    # proper-noun exclusion ("Green Events Tool") actually keys off a capital.
    re.compile(r"\bgreen\s+events?\b(?!\s+(?-i:[A-Z]))", re.I),
]


def _matches(text: str) -> list[tuple[int, str]]:
    """(position, matched phrase) for every banned claim in ``text``."""
    return [(m.start(), m.group(0)) for pattern in _CLAIM_PATTERNS for m in pattern.finditer(text or "")]


def _dedup_in_order(found: list[tuple[int, str]]) -> list[str]:
    """Matched phrases ordered by position, one entry per distinct phrase."""
    seen: set[str] = set()
    phrases = []
    for _, phrase in sorted(found):
        if phrase.lower() not in seen:
            seen.add(phrase.lower())
            phrases.append(phrase)
    return phrases


def find_banned_claims(text: str) -> list[str]:
    """The banned claim phrases in ``text``, as written, in order of appearance."""
    return _dedup_in_order(_matches(text))


def sanitize_claim_language(text: str) -> tuple[str, list[str]]:
    """Redact banned claims, leaving :data:`CLAIM_REDACTION` in their place.

    Returns the rewritten text plus the banned phrases that were replaced (same
    shape as :func:`find_banned_claims`). Sanitizing already-clean text is a
    no-op, so this is safe to apply repeatedly at a chokepoint.
    """
    if not text:
        return text, []

    replaced = _dedup_in_order(_matches(text))
    for pattern in _CLAIM_PATTERNS:
        text = pattern.sub(CLAIM_REDACTION, text)
    return text, replaced


def describe_credit_sources(by_registry: Mapping[str, float]) -> str:
    """Human-readable credit source for the compensation statement."""
    names = [key.replace("_", " ").title() for key in sorted(by_registry or {})]
    if not names:
        return DEFAULT_CREDIT_DESC
    return "retired credits from " + ", ".join(names)


def compliant_compensation_statement(
    total_tco2e: float,
    reduced_pct: float,
    residual_tco2e: float,
    credit_desc: str = DEFAULT_CREDIT_DESC,
    compensated_tco2e: float | None = None,
) -> str:
    """Render the measured / reduced / residual-compensated construction.

    This is what replaces a neutrality claim: no adjective, just the numbers a
    reader (or an auditor) needs to judge the compensation themselves.

    ``compensated_tco2e`` is how much of the residual retired credits actually
    cover. When it falls short of the residual, both the covered and the
    outstanding tonnage are named so partial coverage cannot be read as full
    compensation; ``None`` means the residual is fully compensated.
    """
    credits = credit_desc or DEFAULT_CREDIT_DESC
    prefix = f"{total_tco2e:.3f} tCO2e measured, {reduced_pct:.1f}% reduced, "
    if compensated_tco2e is None or compensated_tco2e >= residual_tco2e:
        return (
            f"{prefix}{residual_tco2e:.3f} tCO2e residual compensated "
            f"outside the value chain via {credits}"
        )
    return (
        f"{prefix}{compensated_tco2e:.3f} of {residual_tco2e:.3f} tCO2e residual "
        f"compensated outside the value chain via {credits}; "
        f"{residual_tco2e - compensated_tco2e:.3f} tCO2e residual not yet compensated"
    )


def portfolio_claim_statement(
    total_tco2e: float,
    retired_tco2e: float,
    by_registry: Mapping[str, float],
) -> str:
    """Compliant wording for an offset portfolio held against a measured total.

    The reduction is stated as 0% because a scenario carries no reduction
    baseline yet (the NZCE compliance check reports that as a gap) — an
    undocumented reduction is precisely what must not be claimed. With no
    reduction, the residual *is* the measured total; only the retired credits
    count as compensated, so anything less leaves an outstanding balance.
    """
    return compliant_compensation_statement(
        total_tco2e,
        0.0,
        total_tco2e,
        describe_credit_sources(by_registry),
        compensated_tco2e=retired_tco2e,
    )
