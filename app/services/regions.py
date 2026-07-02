"""Canonical region normalization — the single alias map for every region-keyed
lookup (carbon tax rates, electricity prices, incentives, compliance regimes).

Canonical names: singapore, european_union, united_kingdom, australia, usa,
canada, japan, south_korea, china, global. Unknown input falls back to "global"
(callers decide what that means for their domain).
"""

_ALIASES = {
    "singapore": "singapore",
    "sg": "singapore",
    "eu": "european_union",
    "europe": "european_union",
    "european_union": "european_union",
    "uk": "united_kingdom",
    "gb": "united_kingdom",
    "united_kingdom": "united_kingdom",
    "australia": "australia",
    "au": "australia",
    "usa": "usa",
    "us": "usa",
    "united_states": "usa",
    "usa_california": "usa",
    "california": "usa",
    "canada": "canada",
    "japan": "japan",
    "korea": "south_korea",
    "south_korea": "south_korea",
    "china": "china",
    "global": "global",
}


def normalize_region(region: str) -> str:
    return _ALIASES.get((region or "").strip().lower().replace(" ", "_"), "global")


# Canonical name -> key in tax_incentives.json "carbon_tax_rates"
CARBON_TAX_KEYS = {
    "singapore": "singapore",
    "european_union": "european_union",
    "united_kingdom": "united_kingdom",
    "australia": "australia",
    "usa": "usa_california",
    "canada": "canada",
    "japan": "japan",
    "south_korea": "south_korea",
    "china": "china",
}

# Canonical name -> key in tax_incentives.json "electricity_rates_usd"
ELECTRICITY_KEYS = {
    "singapore": "singapore",
    "european_union": "eu",
    "united_kingdom": "uk",
    "australia": "australia",
    "usa": "usa",
    "global": "global",
}

# Canonical name -> key in tax_incentives.json "green_incentives"
INCENTIVE_KEYS = {
    "singapore": "singapore",
    "european_union": "european_union",
    "united_kingdom": "united_kingdom",
    "australia": "australia",
    "usa": "usa",
    "canada": "canada",
    "japan": "japan",
}
