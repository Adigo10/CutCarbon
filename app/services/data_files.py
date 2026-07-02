"""Loads the static data JSONs once, shared across services.

emission_factors.json is NOT here — it lives in emissions_engine as the mutable
``EF`` dict with in-place reload semantics (TinyFish refreshes mutate it live).
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def _load(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


TAX_DATA = _load("tax_incentives.json")
CARBON_OFFSETS = _load("carbon_offsets.json")
