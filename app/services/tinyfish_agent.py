"""
TinyFish Web Agent layer — using the official TinyFish SDK (v0.2.x).

Each agent sends a goal + url to the TinyFish API which runs a real headless
browser and returns a STRUCTURED JSON result. With SDK 0.2.x the response is:

    response = await client.agent.run(goal=..., url=...)
    response.status   -> RunStatus enum (success == RunStatus.COMPLETED)
    response.result   -> dict | None   (already-structured JSON — no regex needed)
    response.error    -> RunError | None (.message, .category, ...)
    response.run_id / num_of_steps / started_at / finished_at

So we read fields straight off ``response.result`` and validate them against
per-metric sanity bounds. Out-of-range / missing values are dropped (treated as
no-data) so a bad scrape can never overwrite a good committed value.

Pipeline:
  run_and_update() -> run_all_agents() (TTL-cached) -> merge_fetched_factors()
The merge writes emission_factors.json ATOMICALLY (tempfile + os.replace) under an
asyncio lock, then reload_factors() refreshes the in-memory EF so the very next
calculation uses the new values WITHOUT a process restart.
"""
import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select, desc

from tinyfish.client import AsyncTinyFish
from tinyfish.agent.types import RunStatus

from app.config import settings

# How long a successful agent result stays valid before the agent re-runs.
AGENT_TTL_HOURS = 12

_DATA_DIR = Path(__file__).parent.parent / "data"

# Serializes concurrent merges so two refreshes can't clobber the JSON file.
_MERGE_LOCK = asyncio.Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


# ── Validation bounds ───────────────────────────────────────────────────────────
# Grid emission factors (kg CO2e/kWh) — reject clearly wrong values.
_GRID_FACTOR_BOUNDS: dict[str, tuple[float, float]] = {
    "singapore":   (0.30, 0.70),
    "uk":          (0.10, 0.45),
    "australia":   (0.40, 1.00),
    "usa":         (0.25, 0.60),
    "eu_average":  (0.15, 0.50),
}
_GRID_FACTOR_BOUNDS_DEFAULT = (0.01, 2.00)
_PRICE_BOUNDS = (0.0, 1000.0)     # carbon price per tonne (local currency, generous)
_FLIGHT_BOUNDS = (0.05, 1.5)      # kg CO2e per passenger-km
_MEAL_BOUNDS = (0.1, 40.0)        # kg CO2e per meal


def _as_float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _num(result: dict, *keys) -> Optional[float]:
    """Read the first present numeric key from a structured result dict."""
    if not isinstance(result, dict):
        return None
    for key in keys:
        v = _as_float(result.get(key))
        if v is not None:
            return v
    return None


def _validated(value: Optional[float], bounds: tuple[float, float]) -> Optional[float]:
    if value is None:
        return None
    lo, hi = bounds
    return value if lo <= value <= hi else None


def _validated_grid_factor(value: Optional[float], region: str) -> Optional[float]:
    """Return value if it falls within expected bounds for region, else None."""
    return _validated(value, _GRID_FACTOR_BOUNDS.get(region, _GRID_FACTOR_BOUNDS_DEFAULT))


def _grid_factor_from_result(result: dict, region: str) -> Optional[float]:
    """Read + unit-normalize a grid factor from a structured result dict.

    Converts based on the DECLARED unit (never on magnitude), then bounds-checks.
    """
    f = _num(result, "factor", "factor_value")
    if f is None:
        return None
    unit = str(result.get("unit", "")).lower().replace(" ", "") if isinstance(result, dict) else ""
    if "lb" in unit and "mwh" in unit:
        f = f / 2204.62                              # eGRID lb/MWh -> kg/kWh
    elif "kg" not in unit and "g" in unit and "kwh" in unit:
        f = f / 1000.0                               # grams/kWh -> kg/kWh (NOT kg/kWh)
    return _validated_grid_factor(f, region)


def _has_numeric(structured: dict) -> bool:
    """True if the extracted dict carries at least one usable numeric value."""
    return any(
        isinstance(v, (int, float)) for k, v in structured.items() if not k.startswith("_")
    )


# ── Shared client factory ─────────────────────────────────────────────────────

def _get_client() -> AsyncTinyFish:
    """Return an authenticated TinyFish async client."""
    return AsyncTinyFish(api_key=settings.TINYFISH_API_KEY)


# ── Base agent class ──────────────────────────────────────────────────────────

class TinyFishAgent:
    """A single TinyFish agent task: a goal + starting URL.

    Subclasses implement ``extract(result: dict)`` to map the agent's structured
    JSON result into a normalized factor dict with provenance.
    """

    def __init__(self, name: str, url: str, goal: str, category: str):
        self.name = name
        self.url = url
        self.goal = goal
        self.category = category
        self.last_run: Optional[datetime] = None
        self.last_result: Optional[dict] = None

    def extract(self, result: dict) -> dict:
        """Override: map the structured result dict into a normalized factor dict.

        Default returns the raw structured dict unchanged.
        """
        return dict(result) if isinstance(result, dict) else {}

    async def run(self) -> Optional[dict]:
        """Execute via TinyFish API, validate, attach provenance. None on failure."""
        if not settings.TINYFISH_API_KEY:
            print(f"[TinyFish:{self.name}] TINYFISH_API_KEY not set — skipping.")
            return None

        async with _get_client() as client:
            try:
                response = await client.agent.run(goal=self.goal, url=self.url)
            except Exception as exc:
                print(f"[TinyFish:{self.name}] API error: {exc}")
                return None

        if response.status != RunStatus.COMPLETED or response.result is None:
            detail = getattr(response.error, "message", None) or f"status={response.status}"
            print(f"[TinyFish:{self.name}] no usable result: {detail}")
            return None

        raw = response.result if isinstance(response.result, dict) else {}
        structured = self.extract(raw)

        if not _has_numeric(structured):
            print(f"[TinyFish:{self.name}] result had no valid numeric value — treating as no-data.")
            return None

        structured["_provenance"] = {
            "source_url": self.url,
            "agent": self.name,
            "run_id": response.run_id,
            "num_steps": response.num_of_steps,
            "status": getattr(response.status, "value", str(response.status)),
            "started_at": str(response.started_at),
            "finished_at": str(response.finished_at),
            "fetched_at": _utcnow_iso(),
        }
        self.last_run = _utcnow()
        self.last_result = structured
        return structured


# ── Concrete agents ────────────────────────────────────────────────────────────

class _GridFactorAgent(TinyFishAgent):
    """Shared base for the five regional grid-factor agents."""

    region_key = "global_average"
    source_label = "Grid (via TinyFish)"

    def extract(self, result: dict) -> dict:
        return {
            "category": "venue_energy",
            "region": self.region_key,
            "factor_value": _grid_factor_from_result(result, self.region_key),
            "unit": "kg_co2e_per_kwh",
            "source": self.source_label,
        }


class SingaporeGridFactorAgent(_GridFactorAgent):
    region_key = "singapore"
    source_label = "EMA Singapore (via TinyFish)"

    def __init__(self):
        super().__init__(
            name="sg_grid_factor",
            url="https://www.ema.gov.sg/consumer-information/electricity/buying-electricity/understanding-electricity/grid-emission-factor",
            goal=(
                "Find the current Singapore Grid Emission Factor value in kg CO2/kWh (or kgCO2e/kWh). "
                "Return ONLY a JSON object: {\"factor\": <number>, \"unit\": \"kg_co2e_per_kwh\", \"year\": <year>}"
            ),
            category="venue_energy",
        )


class UKGridFactorAgent(_GridFactorAgent):
    region_key = "uk"
    source_label = "UK DEFRA (via TinyFish)"

    def __init__(self):
        super().__init__(
            name="uk_grid_factor",
            url="https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2024",
            goal=(
                "Find the UK electricity grid emission factor (Scope 2, location-based) in kg CO2e per kWh "
                "from the latest DEFRA/DESNZ greenhouse gas conversion factors publication. "
                "Return ONLY JSON: {\"factor\": <number>, \"unit\": \"kg_co2e_per_kwh\", \"year\": <year>}"
            ),
            category="venue_energy",
        )


class AustraliaGridFactorAgent(_GridFactorAgent):
    region_key = "australia"
    source_label = "DCCEEW Australia (via TinyFish)"

    def __init__(self):
        super().__init__(
            name="au_grid_factor",
            url="https://www.dcceew.gov.au/climate-change/publications/national-greenhouse-accounts-factors-2024",
            goal=(
                "Find the Australian national electricity grid emission factor (Scope 2) in kg CO2e per kWh "
                "from the DCCEEW National Greenhouse Accounts (NGA) Factors. "
                "Return ONLY JSON: {\"factor\": <number>, \"unit\": \"kg_co2e_per_kwh\", \"year\": <year>}"
            ),
            category="venue_energy",
        )


class USAGridFactorAgent(_GridFactorAgent):
    region_key = "usa"
    source_label = "EPA eGRID (via TinyFish)"

    def __init__(self):
        super().__init__(
            name="usa_grid_factor",
            url="https://www.epa.gov/egrid/summary-data",
            goal=(
                "Find the US national average electricity grid emission factor from the EPA eGRID summary data. "
                "Look for the US Total CO2e output emission rate. If the figure is in lb/MWh, also report the unit. "
                "Return ONLY JSON: {\"factor\": <number>, \"unit\": \"kg_co2e_per_kwh\" or \"lb_co2e_per_mwh\", \"year\": <year>}"
            ),
            category="venue_energy",
        )


class EUGridFactorAgent(_GridFactorAgent):
    region_key = "eu_average"
    source_label = "EEA (via TinyFish)"

    def __init__(self):
        super().__init__(
            name="eu_grid_factor",
            url="https://www.eea.europa.eu/en/analysis/indicators/co2-intensity-of-electricity-generation",
            goal=(
                "Find the EU average (EU-27) electricity CO2 intensity from the European Environment Agency. "
                "Report the value and its unit (grams CO2e/kWh or kg CO2e/kWh). "
                "Return ONLY JSON: {\"factor\": <number>, \"unit\": \"g_co2e_per_kwh\" or \"kg_co2e_per_kwh\", \"year\": <year>}"
            ),
            category="venue_energy",
        )


class SingaporeCarbonTaxAgent(TinyFishAgent):
    def __init__(self):
        super().__init__(
            name="sg_carbon_tax",
            url="https://www.nea.gov.sg/our-services/climate-change-energy-efficiency/climate-change/singapore-s-carbon-tax",
            goal=(
                "Find the current Singapore carbon tax rate in SGD per tonne of CO2 equivalent, "
                "and any upcoming rate changes. "
                "Return ONLY JSON: {\"current_rate_sgd\": <number>, \"next_rate_sgd\": <number or null>, \"next_rate_year\": <year or null>}"
            ),
            category="carbon_tax",
        )

    def extract(self, result: dict) -> dict:
        return {
            "category": "carbon_tax",
            "region": "singapore",
            "current_rate_sgd": _validated(_num(result, "current_rate_sgd"), _PRICE_BOUNDS),
            "next_rate_sgd": _validated(_num(result, "next_rate_sgd"), _PRICE_BOUNDS),
            "source": "NEA Singapore (via TinyFish)",
        }


class EUETSPriceAgent(TinyFishAgent):
    def __init__(self):
        super().__init__(
            name="eu_ets_price",
            url="https://ember-climate.org/data/data-tools/carbon-price-viewer/",
            goal=(
                "Find the current EU ETS (Emissions Trading System) carbon price in EUR per tonne CO2. "
                "Return ONLY JSON: {\"price_eur\": <number>, \"date\": \"<YYYY-MM-DD>\"}"
            ),
            category="carbon_tax",
        )

    def extract(self, result: dict) -> dict:
        return {
            "category": "carbon_tax",
            "region": "eu",
            "price_eur_per_tco2e": _validated(_num(result, "price_eur", "price_eur_per_tco2e"), _PRICE_BOUNDS),
            "source": "Ember Climate (via TinyFish)",
        }


class UKETSPriceAgent(TinyFishAgent):
    def __init__(self):
        super().__init__(
            name="uk_ets_price",
            url="https://www.gov.uk/guidance/uk-emissions-trading-scheme-uk-ets",
            goal=(
                "Find the current UK ETS (Emissions Trading Scheme) carbon allowance price in GBP per tonne of CO2 equivalent. "
                "Return ONLY JSON: {\"price_gbp\": <number>, \"date\": \"<YYYY-MM-DD or recent month>\"}"
            ),
            category="carbon_tax",
        )

    def extract(self, result: dict) -> dict:
        return {
            "category": "carbon_tax",
            "region": "uk",
            "price_gbp_per_tco2e": _validated(_num(result, "price_gbp", "price_gbp_per_tco2e"), _PRICE_BOUNDS),
            "source": "UK ETS (via TinyFish)",
        }


class FlightEmissionFactorAgent(TinyFishAgent):
    def __init__(self):
        super().__init__(
            name="icao_flight_factors",
            # DEFRA/DESNZ publishes the per-passenger-km cabin-class air-travel factors.
            url="https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2024",
            goal=(
                "From the UK DEFRA/DESNZ GHG conversion factors air-travel table, find the emission factors "
                "for short-haul and long-haul flights in kg CO2e per passenger-km for economy and business class. "
                "Return ONLY JSON: {\"short_haul_economy\": <number>, \"long_haul_economy\": <number>, "
                "\"long_haul_business\": <number>, \"unit\": \"kg_co2e_per_passenger_km\"}"
            ),
            category="travel",
        )

    def extract(self, result: dict) -> dict:
        she = _validated(_num(result, "short_haul_economy"), _FLIGHT_BOUNDS)
        lhe = _validated(_num(result, "long_haul_economy"), _FLIGHT_BOUNDS)
        lhb = _validated(_num(result, "long_haul_business"), _FLIGHT_BOUNDS)
        # Business must be >= economy; drop it otherwise.
        if lhb is not None and lhe is not None and lhb < lhe:
            lhb = None
        return {
            "category": "travel",
            "subcategory": "aviation",
            "short_haul_economy": she,
            "long_haul_economy": lhe,
            "long_haul_business": lhb,
            "unit": "kg_co2e_per_passenger_km",
            "source": "UK DEFRA/DESNZ (via TinyFish)",
        }


class CateringEmissionFactorAgent(TinyFishAgent):
    """Fetches latest food emission factors from Our World in Data."""

    def __init__(self):
        super().__init__(
            name="food_emission_factors",
            url="https://ourworldindata.org/food-choice-vs-eating-local",
            goal=(
                "Find the greenhouse gas emissions per meal (kg CO2e) for: "
                "beef, chicken, vegetarian, and vegan meals. "
                "Return ONLY JSON: {\"beef_kg_co2e_per_meal\": <number>, "
                "\"chicken_kg_co2e_per_meal\": <number>, "
                "\"vegetarian_kg_co2e_per_meal\": <number>, "
                "\"vegan_kg_co2e_per_meal\": <number>}"
            ),
            category="catering",
        )

    def extract(self, result: dict) -> dict:
        return {
            "category": "catering",
            "beef_factor": _validated(_num(result, "beef_kg_co2e_per_meal", "beef_factor"), _MEAL_BOUNDS),
            "chicken_factor": _validated(_num(result, "chicken_kg_co2e_per_meal", "chicken_factor"), _MEAL_BOUNDS),
            "vegetarian_factor": _validated(_num(result, "vegetarian_kg_co2e_per_meal", "vegetarian_factor"), _MEAL_BOUNDS),
            "vegan_factor": _validated(_num(result, "vegan_kg_co2e_per_meal", "vegan_factor"), _MEAL_BOUNDS),
            "unit": "kg_co2e_per_meal",
            "source": "Our World in Data (via TinyFish)",
        }


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_cached_run(agent_name: str) -> Optional[dict]:
    """Return the most recent successful AgentRunDB result within TTL, else None."""
    from app.models.database import AgentRunDB, AsyncSessionLocal
    cutoff = _utcnow().replace(tzinfo=None) - timedelta(hours=AGENT_TTL_HOURS)
    async with AsyncSessionLocal() as session:
        row = await session.scalar(
            select(AgentRunDB)
            .where(AgentRunDB.agent_name == agent_name)
            .where(AgentRunDB.status == "success")
            .where(AgentRunDB.fetched_at >= cutoff)
            .order_by(desc(AgentRunDB.fetched_at))
            .limit(1)
        )
    return row.result_json if row else None


async def _save_agent_run(agent: "TinyFishAgent", result: Optional[dict], error: Optional[str] = None):
    """Persist an agent run result (or error) to AgentRunDB."""
    from app.models.database import AgentRunDB, AsyncSessionLocal
    provenance = (result or {}).get("_provenance", {})
    row = AgentRunDB(
        agent_name=agent.name,
        category=agent.category,
        source_url=agent.url,
        status="error" if error else "success",
        run_id=provenance.get("run_id"),
        num_steps=provenance.get("num_steps"),
        result_json={k: v for k, v in (result or {}).items() if k != "_provenance"},
        error=error,
        fetched_at=_utcnow().replace(tzinfo=None),
    )
    async with AsyncSessionLocal() as session:
        session.add(row)
        await session.commit()


# ── Agent registry ─────────────────────────────────────────────────────────────

REGISTERED_AGENTS: list[TinyFishAgent] = [
    # Grid emission factors
    SingaporeGridFactorAgent(),
    UKGridFactorAgent(),
    AustraliaGridFactorAgent(),
    USAGridFactorAgent(),
    EUGridFactorAgent(),
    # Carbon prices / taxes
    SingaporeCarbonTaxAgent(),
    EUETSPriceAgent(),
    UKETSPriceAgent(),
    # Travel & catering
    FlightEmissionFactorAgent(),
    CateringEmissionFactorAgent(),
]


# ── Orchestrator ───────────────────────────────────────────────────────────────

async def _run_agent_with_cache(agent: TinyFishAgent, force: bool) -> dict:
    """Run a single agent with TTL cache check; tag cache hits with _cache_hit."""
    if not force:
        cached = await _get_cached_run(agent.name)
        if cached is not None:
            print(f"[TinyFish:{agent.name}] Cache hit — skipping API call (TTL {AGENT_TTL_HOURS}h).")
            return {**cached, "_cache_hit": True}

    result = await agent.run()
    if result is not None:
        await _save_agent_run(agent, result)
    else:
        await _save_agent_run(agent, None, error="Agent returned no validated data")
    return result or {"status": "no_data"}


async def run_all_agents(force: bool = False) -> dict:
    """Run all registered TinyFish agents concurrently, respecting the TTL cache."""
    tasks = [_run_agent_with_cache(agent, force) for agent in REGISTERED_AGENTS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = {}
    for agent, result in zip(REGISTERED_AGENTS, results):
        if isinstance(result, Exception):
            output[agent.name] = {"error": str(result)}
        else:
            output[agent.name] = result

    return output


async def _upsert_emission_factors(rows: list[tuple]) -> None:
    """Write/update EmissionFactorDB rows from agent results.

    Each tuple: (category, subcategory, region, value, unit, source_url, run_id)
    Auto-fetched values are stored with is_verified=False — "verified" is reserved
    for values cross-checked against a citable primary source, which scraping is not.
    """
    from app.models.database import EmissionFactorDB, AsyncSessionLocal
    now = _utcnow().replace(tzinfo=None)
    async with AsyncSessionLocal() as session:
        for category, subcategory, region, value, unit, source, run_id in rows:
            existing = await session.scalar(
                select(EmissionFactorDB)
                .where(EmissionFactorDB.category == category)
                .where(EmissionFactorDB.subcategory == subcategory)
                .where(EmissionFactorDB.region == region)
                .limit(1)
            )
            if existing:
                existing.factor_value = value
                existing.unit = unit
                existing.source_url = source
                existing.last_updated = now
                existing.is_verified = False
            else:
                session.add(EmissionFactorDB(
                    category=category,
                    subcategory=subcategory,
                    region=region,
                    factor_value=value,
                    unit=unit,
                    source_url=source,
                    methodology_tag=f"tinyfish_agent:{run_id}" if run_id else "tinyfish_agent",
                    last_updated=now,
                    is_verified=False,
                ))
        await session.commit()


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically (tempfile + os.replace) so a crash can't corrupt the file."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


async def merge_fetched_factors(results: dict) -> dict:
    """Merge freshly fetched factors into emission_factors.json + EmissionFactorDB.

    Only overwrites values where the agent returned a non-None validated result.
    Writes atomically under a lock, then reloads the in-memory factor table so the
    next calculation uses the new values without a restart.
    """
    ef_path = _DATA_DIR / "emission_factors.json"

    async with _MERGE_LOCK:
        with open(ef_path, encoding="utf-8") as f:
            ef = json.load(f)

        updated = []
        db_rows = []  # (category, subcategory, region, value, unit, source, run_id)

        def _run_id(agent_key: str) -> Optional[str]:
            r = results.get(agent_key, {})
            return r.get("_provenance", {}).get("run_id") if isinstance(r, dict) else None

        def _patch_grid(region_key: str, agent_key: str, label: str):
            r = results.get(agent_key, {})
            v = r.get("factor_value") if isinstance(r, dict) else None
            if v:
                old = ef["venue_energy"]["grids"][region_key]["factor"]
                ef["venue_energy"]["grids"][region_key]["factor"] = v
                ef["venue_energy"]["grids"][region_key]["source"] = r.get("source", f"{label} via TinyFish")
                ef["venue_energy"]["grids"][region_key]["last_fetched"] = _utcnow_iso()
                updated.append(f"{label} grid: {old} → {v} kg CO2e/kWh")
                db_rows.append(("venue_energy", "grid", region_key, v, "kg_co2e_per_kwh", r.get("source", ""), _run_id(agent_key)))

        _patch_grid("singapore",  "sg_grid_factor",  "SG")
        _patch_grid("uk",         "uk_grid_factor",  "UK")
        _patch_grid("australia",  "au_grid_factor",  "AU")
        _patch_grid("usa",        "usa_grid_factor", "USA")
        _patch_grid("eu_average", "eu_grid_factor",  "EU avg")

        carbon_tax_live = ef.setdefault("carbon_tax_live", {})

        # Singapore carbon tax
        sg_tax = results.get("sg_carbon_tax", {})
        if isinstance(sg_tax, dict) and sg_tax.get("current_rate_sgd"):
            carbon_tax_live["singapore_current_sgd"] = sg_tax["current_rate_sgd"]
            if sg_tax.get("next_rate_sgd"):
                carbon_tax_live["singapore_next_sgd"] = sg_tax["next_rate_sgd"]
            carbon_tax_live["singapore_fetched_at"] = _utcnow_iso()
            updated.append(f"SG carbon tax: SGD {sg_tax['current_rate_sgd']}/tCO2e")
            db_rows.append(("carbon_tax", "current_rate", "singapore", sg_tax["current_rate_sgd"], "sgd_per_tco2e", sg_tax.get("source", ""), _run_id("sg_carbon_tax")))

        # EU ETS
        eu_ets = results.get("eu_ets_price", {})
        if isinstance(eu_ets, dict) and eu_ets.get("price_eur_per_tco2e"):
            carbon_tax_live["eu_ets_eur"] = eu_ets["price_eur_per_tco2e"]
            carbon_tax_live["eu_fetched_at"] = _utcnow_iso()
            updated.append(f"EU ETS: €{eu_ets['price_eur_per_tco2e']}/tCO2e")
            db_rows.append(("carbon_tax", "ets_price", "eu", eu_ets["price_eur_per_tco2e"], "eur_per_tco2e", eu_ets.get("source", ""), _run_id("eu_ets_price")))

        # UK ETS
        uk_ets = results.get("uk_ets_price", {})
        if isinstance(uk_ets, dict) and uk_ets.get("price_gbp_per_tco2e"):
            carbon_tax_live["uk_ets_gbp"] = uk_ets["price_gbp_per_tco2e"]
            carbon_tax_live["uk_fetched_at"] = _utcnow_iso()
            updated.append(f"UK ETS: £{uk_ets['price_gbp_per_tco2e']}/tCO2e")
            db_rows.append(("carbon_tax", "ets_price", "uk", uk_ets["price_gbp_per_tco2e"], "gbp_per_tco2e", uk_ets.get("source", ""), _run_id("uk_ets_price")))

        # Aviation factors
        icao = results.get("icao_flight_factors", {})
        if isinstance(icao, dict):
            if icao.get("short_haul_economy"):
                ef["travel"]["short_haul_flight"]["economy"] = icao["short_haul_economy"]
                updated.append(f"Flight short-haul economy: {icao['short_haul_economy']}")
                db_rows.append(("travel", "short_haul_flight", "global", icao["short_haul_economy"], "kg_co2e_per_passenger_km", icao.get("source", ""), _run_id("icao_flight_factors")))
            if icao.get("long_haul_economy"):
                ef["travel"]["long_haul_flight"]["economy"] = icao["long_haul_economy"]
                updated.append(f"Flight long-haul economy: {icao['long_haul_economy']}")
                db_rows.append(("travel", "long_haul_flight", "global", icao["long_haul_economy"], "kg_co2e_per_passenger_km", icao.get("source", ""), _run_id("icao_flight_factors")))
            if icao.get("long_haul_business"):
                ef["travel"]["long_haul_flight"]["business"] = icao["long_haul_business"]
                updated.append(f"Flight long-haul business: {icao['long_haul_business']}")
                db_rows.append(("travel", "long_haul_flight_business", "global", icao["long_haul_business"], "kg_co2e_per_passenger_km", icao.get("source", ""), _run_id("icao_flight_factors")))

        # Catering factors
        food = results.get("food_emission_factors", {})
        if isinstance(food, dict):
            for src_key, ef_key, label in [
                ("beef_factor", "red_meat_meal", "Beef"),
                ("chicken_factor", "white_meat_meal", "Chicken"),
                ("vegetarian_factor", "vegetarian_meal", "Vegetarian"),
                ("vegan_factor", "vegan_meal", "Vegan"),
            ]:
                if food.get(src_key):
                    ef["catering"][ef_key]["factor"] = food[src_key]
                    updated.append(f"{label} meal: {food[src_key]} kg CO2e")
                    db_rows.append(("catering", ef_key, "global", food[src_key], "kg_co2e_per_meal", food.get("source", ""), _run_id("food_emission_factors")))

        if updated:
            ef["last_agent_update"] = _utcnow_iso()
            _atomic_write_json(ef_path, ef)

        # Persist updated factors to EmissionFactorDB.
        if db_rows:
            await _upsert_emission_factors(db_rows)

    # Refresh the in-memory factor table so the next calculation uses the new values.
    if updated:
        try:
            from app.services.emissions_engine import reload_factors
            reload_factors()
        except Exception as exc:  # pragma: no cover - reload best-effort
            print(f"[TinyFish] reload_factors failed: {exc}")

    return {"updated_fields": updated, "total": len(updated)}


async def run_and_update(force: bool = False) -> dict:
    """Full pipeline: run all TinyFish agents → merge → reload → return summary."""
    results = await run_all_agents(force=force)
    merge_summary = await merge_fetched_factors(results)
    return {
        "agent_results": {
            k: {
                "cache_hit": v.get("_cache_hit", False) if isinstance(v, dict) else False,
                "status": v.get("_provenance", {}).get("status", "ok") if isinstance(v, dict) else "error",
                "run_id": v.get("_provenance", {}).get("run_id") if isinstance(v, dict) else None,
                "steps": v.get("_provenance", {}).get("num_steps") if isinstance(v, dict) else None,
                "data": {kk: vv for kk, vv in v.items() if kk not in ("_provenance", "_cache_hit")} if isinstance(v, dict) else v,
            }
            for k, v in results.items()
        },
        "merge_summary": merge_summary,
        "ran_at": _utcnow_iso(),
        "ttl_hours": AGENT_TTL_HOURS,
        "forced": force,
    }
