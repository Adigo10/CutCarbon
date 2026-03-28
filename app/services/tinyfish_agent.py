"""
TinyFish Web Agent layer — using the official TinyFish SDK.
Each agent sends a goal + url to the TinyFish API which runs a real headless
browser to extract live emission-factor and carbon-price data.

SDK: https://pypi.org/project/tinyfish/
client.agent.run(goal=..., url=...) → AgentRunResponse.result (str)
client.agent.stream(...)            → streaming with callbacks

Optimization: Results are cached in the AgentRunDB table for AGENT_TTL_HOURS.
Agents are skipped on re-run if a successful result exists within the TTL window.
Use force=True in run_all_agents() to bypass the cache.

Agents registered (10 total):
  Grid factors:  singapore, uk, australia, usa, eu_average
  Carbon prices: singapore_tax, eu_ets, uk_ets
  Travel:        icao_flights
  Catering:      food_factors
"""
import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import select, desc

from tinyfish.client import AsyncTinyFish
from tinyfish.agent.types import CompleteEvent, ProgressEvent

from app.config import settings

# How long a successful agent result stays valid before the agent re-runs.
AGENT_TTL_HOURS = 12

_DATA_DIR = Path(__file__).parent.parent / "data"

# Sanity bounds for grid emission factors (kg CO2e/kWh).
# Rejects clearly wrong values from misparses.
_GRID_FACTOR_BOUNDS: dict[str, tuple[float, float]] = {
    "singapore":   (0.30, 0.70),
    "uk":          (0.10, 0.45),
    "australia":   (0.40, 1.00),
    "usa":         (0.25, 0.60),
    "eu_average":  (0.15, 0.50),
}
_GRID_FACTOR_BOUNDS_DEFAULT = (0.01, 2.00)


def _validated_grid_factor(value: Optional[float], region: str) -> Optional[float]:
    """Return value if it falls within expected bounds for region, else None."""
    if value is None:
        return None
    lo, hi = _GRID_FACTOR_BOUNDS.get(region, _GRID_FACTOR_BOUNDS_DEFAULT)
    return value if lo <= value <= hi else None


# ── Shared client factory ─────────────────────────────────────────────────────

def _get_client() -> AsyncTinyFish:
    """Return an authenticated TinyFish async client."""
    return AsyncTinyFish(api_key=settings.TINYFISH_API_KEY)


# ── Base agent class ──────────────────────────────────────────────────────────

class TinyFishAgent:
    """
    Wraps a single TinyFish agent task: a goal + starting URL.
    On run(), sends the task to the TinyFish API (real browser agent),
    parses the result text, and returns structured data with provenance.
    """

    def __init__(self, name: str, url: str, goal: str, category: str):
        self.name = name
        self.url = url
        self.goal = goal
        self.category = category
        self.last_run: Optional[datetime] = None
        self.last_result: Optional[dict] = None

    def parse_result(self, result_text: str) -> dict:
        """
        Override to parse the agent's free-text result into structured data.
        Default: try JSON parse, fall back to returning raw text.
        """
        try:
            return json.loads(result_text)
        except Exception:
            return {"raw": result_text}

    async def run(self) -> Optional[dict]:
        """Execute via TinyFish API, parse result, record provenance."""
        if not settings.TINYFISH_API_KEY:
            print(f"[TinyFish:{self.name}] TINYFISH_API_KEY not set — skipping.")
            return None

        async with _get_client() as client:
            try:
                response = await client.agent.run(
                    goal=self.goal,
                    url=self.url,
                )
            except Exception as exc:
                print(f"[TinyFish:{self.name}] API error: {exc}")
                return None

        if response.error:
            print(f"[TinyFish:{self.name}] Agent error: {response.error}")
            return None

        result_text = response.result or ""
        structured = self.parse_result(result_text)
        structured["_provenance"] = {
            "source_url": self.url,
            "agent": self.name,
            "run_id": response.run_id,
            "num_steps": response.num_of_steps,
            "status": response.status,
            "started_at": str(response.started_at),
            "finished_at": str(response.finished_at),
            "fetched_at": datetime.utcnow().isoformat(),
        }
        self.last_run = datetime.utcnow()
        self.last_result = structured
        return structured

    async def stream(
        self,
        on_progress=None,
        on_complete=None,
    ) -> Optional[dict]:
        """Streaming variant — calls progress/complete callbacks as the agent works."""
        if not settings.TINYFISH_API_KEY:
            return None

        result_holder: dict = {}

        def _on_progress(evt: ProgressEvent):
            if on_progress:
                on_progress(evt)
            print(f"[TinyFish:{self.name}] step → {evt.purpose}")

        def _on_complete(evt: CompleteEvent):
            if on_complete:
                on_complete(evt)
            if evt.result_json:
                try:
                    result_holder["data"] = json.loads(evt.result_json)
                except Exception:
                    result_holder["data"] = {"raw": evt.result_json}

        async with _get_client() as client:
            try:
                stream = client.agent.stream(
                    goal=self.goal,
                    url=self.url,
                    on_progress=_on_progress,
                    on_complete=_on_complete,
                )
                async with stream:
                    pass
            except Exception as exc:
                print(f"[TinyFish:{self.name}] stream error: {exc}")
                return None

        return result_holder.get("data")


# ── Concrete agents ────────────────────────────────────────────────────────────

class SingaporeGridFactorAgent(TinyFishAgent):
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

    def parse_result(self, text: str) -> dict:
        match = re.search(r'"factor"\s*:\s*([\d.]+)', text)
        factor = float(match.group(1)) if match else None
        if factor is None:
            match = re.search(r'(0\.\d{3,4})\s*kg', text, re.IGNORECASE)
            factor = float(match.group(1)) if match else None
        return {
            "category": "venue_energy",
            "region": "singapore",
            "factor_value": _validated_grid_factor(factor, "singapore"),
            "unit": "kg_co2e_per_kwh",
            "source": "EMA Singapore (via TinyFish)",
        }


class UKGridFactorAgent(TinyFishAgent):
    def __init__(self):
        super().__init__(
            name="uk_grid_factor",
            url="https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2024",
            goal=(
                "Find the UK electricity grid emission factor (Scope 2, location-based) in kg CO2e per kWh "
                "from the latest DEFRA/BEIS greenhouse gas conversion factors publication. "
                "Return ONLY JSON: {\"factor\": <number>, \"unit\": \"kg_co2e_per_kwh\", \"year\": <year>}"
            ),
            category="venue_energy",
        )

    def parse_result(self, text: str) -> dict:
        match = re.search(r'"factor"\s*:\s*([\d.]+)', text)
        factor = float(match.group(1)) if match else None
        if factor is None:
            match = re.search(r'(0\.\d{2,4})\s*kg\s*CO2e?\s*/\s*kWh', text, re.IGNORECASE)
            factor = float(match.group(1)) if match else None
        return {
            "category": "venue_energy",
            "region": "uk",
            "factor_value": _validated_grid_factor(factor, "uk"),
            "unit": "kg_co2e_per_kwh",
            "source": "UK DEFRA 2024 (via TinyFish)",
        }


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

    def parse_result(self, text: str) -> dict:
        current = re.search(r'"current_rate_sgd"\s*:\s*([\d.]+)', text)
        next_r = re.search(r'"next_rate_sgd"\s*:\s*([\d.]+)', text)
        return {
            "category": "carbon_tax",
            "region": "singapore",
            "current_rate_sgd": float(current.group(1)) if current else None,
            "next_rate_sgd": float(next_r.group(1)) if next_r else None,
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

    def parse_result(self, text: str) -> dict:
        match = re.search(r'"price_eur"\s*:\s*([\d.]+)', text)
        price = float(match.group(1)) if match else None
        return {
            "category": "carbon_tax",
            "region": "eu",
            "price_eur_per_tco2e": price,
            "source": "Ember Climate (via TinyFish)",
        }


class FlightEmissionFactorAgent(TinyFishAgent):
    def __init__(self):
        super().__init__(
            name="icao_flight_factors",
            url="https://www.icao.int/environmental-protection/CarbonOffset/Pages/default.aspx",
            goal=(
                "Find the ICAO aviation emission factors for short-haul and long-haul flights "
                "in kg CO2 per passenger-km for economy and business class. "
                "Return ONLY JSON: {\"short_haul_economy\": <number>, \"long_haul_economy\": <number>, "
                "\"long_haul_business\": <number>, \"unit\": \"kg_co2e_per_passenger_km\"}"
            ),
            category="travel",
        )

    def parse_result(self, text: str) -> dict:
        she = re.search(r'"short_haul_economy"\s*:\s*([\d.]+)', text)
        lhe = re.search(r'"long_haul_economy"\s*:\s*([\d.]+)', text)
        lhb = re.search(r'"long_haul_business"\s*:\s*([\d.]+)', text)
        return {
            "category": "travel",
            "subcategory": "aviation",
            "short_haul_economy": float(she.group(1)) if she else None,
            "long_haul_economy": float(lhe.group(1)) if lhe else None,
            "long_haul_business": float(lhb.group(1)) if lhb else None,
            "unit": "kg_co2e_per_passenger_km",
            "source": "ICAO (via TinyFish)",
        }


class CateringEmissionFactorAgent(TinyFishAgent):
    """New agent: fetches latest food emission factors from OurWorldInData."""
    def __init__(self):
        super().__init__(
            name="food_emission_factors",
            url="https://ourworldindata.org/food-choice-vs-eating-local",
            goal=(
                "Find the greenhouse gas emissions per meal or per kg of food for: "
                "beef, chicken, vegetarian, and vegan diets. "
                "Return ONLY JSON: {\"beef_kg_co2e_per_meal\": <number>, "
                "\"chicken_kg_co2e_per_meal\": <number>, "
                "\"vegetarian_kg_co2e_per_meal\": <number>, "
                "\"vegan_kg_co2e_per_meal\": <number>}"
            ),
            category="catering",
        )

    def parse_result(self, text: str) -> dict:
        beef = re.search(r'"beef_kg_co2e_per_meal"\s*:\s*([\d.]+)', text)
        chk = re.search(r'"chicken_kg_co2e_per_meal"\s*:\s*([\d.]+)', text)
        veg = re.search(r'"vegetarian_kg_co2e_per_meal"\s*:\s*([\d.]+)', text)
        vgn = re.search(r'"vegan_kg_co2e_per_meal"\s*:\s*([\d.]+)', text)
        return {
            "category": "catering",
            "beef_factor": float(beef.group(1)) if beef else None,
            "chicken_factor": float(chk.group(1)) if chk else None,
            "vegetarian_factor": float(veg.group(1)) if veg else None,
            "vegan_factor": float(vgn.group(1)) if vgn else None,
            "unit": "kg_co2e_per_meal",
            "source": "Our World in Data (via TinyFish)",
        }


class AustraliaGridFactorAgent(TinyFishAgent):
    def __init__(self):
        super().__init__(
            name="au_grid_factor",
            url="https://www.cleanenergyregulator.gov.au/NGER/National-greenhouse-and-energy-reporting-scheme-measurement/Emission-factor-profile",
            goal=(
                "Find the Australian national electricity grid emission factor (Scope 2) in kg CO2e per kWh "
                "from the Clean Energy Regulator NGER emission factor profile. "
                "Return ONLY JSON: {\"factor\": <number>, \"unit\": \"kg_co2e_per_kwh\", \"year\": <year>}"
            ),
            category="venue_energy",
        )

    def parse_result(self, text: str) -> dict:
        match = re.search(r'"factor"\s*:\s*([\d.]+)', text)
        factor = float(match.group(1)) if match else None
        if factor is None:
            match = re.search(r'(0\.\d{2,4})\s*kg\s*CO2e?\s*/\s*kWh', text, re.IGNORECASE)
            factor = float(match.group(1)) if match else None
        return {
            "category": "venue_energy",
            "region": "australia",
            "factor_value": _validated_grid_factor(factor, "australia"),
            "unit": "kg_co2e_per_kwh",
            "source": "Clean Energy Regulator Australia (via TinyFish)",
        }


class USAGridFactorAgent(TinyFishAgent):
    def __init__(self):
        super().__init__(
            name="usa_grid_factor",
            url="https://www.epa.gov/egrid/summary-data",
            goal=(
                "Find the US national average electricity grid emission factor (CO2e per kWh) "
                "from the EPA eGRID summary data. Look for the US Total row and the CO2e output emission rate. "
                "Convert from lb/MWh to kg/kWh if needed (divide by 2204.62). "
                "Return ONLY JSON: {\"factor\": <number in kg_co2e_per_kwh>, \"unit\": \"kg_co2e_per_kwh\", \"year\": <year>}"
            ),
            category="venue_energy",
        )

    def parse_result(self, text: str) -> dict:
        match = re.search(r'"factor"\s*:\s*([\d.]+)', text)
        factor = float(match.group(1)) if match else None
        if factor is None:
            match = re.search(r'(0\.\d{2,4})\s*kg\s*CO2e?\s*/\s*kWh', text, re.IGNORECASE)
            factor = float(match.group(1)) if match else None
        # eGRID reports lb/MWh; if value > 2 it's probably lb/MWh still
        if factor and factor > 2:
            factor = round(factor / 2204.62, 4)
        return {
            "category": "venue_energy",
            "region": "usa",
            "factor_value": _validated_grid_factor(factor, "usa"),
            "unit": "kg_co2e_per_kwh",
            "source": "EPA eGRID (via TinyFish)",
        }


class EUGridFactorAgent(TinyFishAgent):
    def __init__(self):
        super().__init__(
            name="eu_grid_factor",
            url="https://www.eea.europa.eu/en/analysis/indicators/co2-intensity-of-electricity-generation",
            goal=(
                "Find the EU average (EU-27) electricity CO2 intensity in grams of CO2 per kWh or kg CO2e per kWh "
                "from the European Environment Agency indicator page. "
                "Return ONLY JSON: {\"factor\": <number in kg_co2e_per_kwh>, \"unit\": \"kg_co2e_per_kwh\", \"year\": <year>}"
            ),
            category="venue_energy",
        )

    def parse_result(self, text: str) -> dict:
        match = re.search(r'"factor"\s*:\s*([\d.]+)', text)
        factor = float(match.group(1)) if match else None
        if factor is None:
            match = re.search(r'([\d.]+)\s*g\s*CO2e?\s*/\s*kWh', text, re.IGNORECASE)
            if match:
                factor = round(float(match.group(1)) / 1000, 4)  # g→kg
        # If reported in g/kWh it will be >1; convert
        if factor and factor > 2:
            factor = round(factor / 1000, 4)
        return {
            "category": "venue_energy",
            "region": "eu_average",
            "factor_value": _validated_grid_factor(factor, "eu_average"),
            "unit": "kg_co2e_per_kwh",
            "source": "EEA (via TinyFish)",
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

    def parse_result(self, text: str) -> dict:
        match = re.search(r'"price_gbp"\s*:\s*([\d.]+)', text)
        price = float(match.group(1)) if match else None
        return {
            "category": "carbon_tax",
            "region": "uk",
            "price_gbp_per_tco2e": price,
            "source": "UK ETS (via TinyFish)",
        }


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_cached_run(agent_name: str) -> Optional[dict]:
    """
    Return the most recent successful AgentRunDB result if it is within TTL,
    or None if the agent needs to run again.
    """
    from app.models.database import AgentRunDB, AsyncSessionLocal
    cutoff = datetime.utcnow() - timedelta(hours=AGENT_TTL_HOURS)
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
        fetched_at=datetime.utcnow(),
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
    """
    Run a single agent with TTL cache check.
    Returns the result dict, tagging it with a 'cache_hit' key when served from DB.
    """
    if not force:
        cached = await _get_cached_run(agent.name)
        if cached is not None:
            print(f"[TinyFish:{agent.name}] Cache hit — skipping API call (TTL {AGENT_TTL_HOURS}h).")
            return {**cached, "_cache_hit": True}

    result = await agent.run()
    if result is not None:
        await _save_agent_run(agent, result)
    else:
        await _save_agent_run(agent, None, error="Agent returned no data")
    return result or {"status": "no_data"}


async def run_all_agents(force: bool = False) -> dict:
    """
    Run all registered TinyFish agents concurrently, respecting the TTL cache.
    Pass force=True to bypass the cache and always call the TinyFish API.
    """
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
    """
    Write/update EmissionFactorDB rows from agent results.
    Each tuple: (category, subcategory, region, value, unit, source_url)
    """
    from app.models.database import EmissionFactorDB, AsyncSessionLocal
    now = datetime.utcnow()
    async with AsyncSessionLocal() as session:
        for category, subcategory, region, value, unit, source in rows:
            # Check for existing row to update
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
                existing.is_verified = True
            else:
                session.add(EmissionFactorDB(
                    category=category,
                    subcategory=subcategory,
                    region=region,
                    factor_value=value,
                    unit=unit,
                    source_url=source,
                    methodology_tag="tinyfish_agent",
                    last_updated=now,
                    is_verified=True,
                ))
        await session.commit()


async def merge_fetched_factors(results: dict) -> dict:
    """
    Merge freshly fetched factors into emission_factors.json and EmissionFactorDB.
    Only overwrites values where the agent returned a non-None result.
    """
    ef_path = _DATA_DIR / "emission_factors.json"
    with open(ef_path) as f:
        ef = json.load(f)

    updated = []
    db_rows = []  # (category, subcategory, region, value, unit, source)

    def _patch_grid(region_key: str, agent_key: str, label: str):
        r = results.get(agent_key, {})
        v = r.get("factor_value") if isinstance(r, dict) else None
        if v:
            old = ef["venue_energy"]["grids"][region_key]["factor"]
            ef["venue_energy"]["grids"][region_key]["factor"] = v
            ef["venue_energy"]["grids"][region_key]["source"] = r.get("source", f"{label} via TinyFish")
            ef["venue_energy"]["grids"][region_key]["last_fetched"] = datetime.utcnow().isoformat()
            updated.append(f"{label} grid: {old} → {v} kg CO₂e/kWh")
            db_rows.append(("venue_energy", "grid", region_key, v, "kg_co2e_per_kwh", r.get("source", "")))

    _patch_grid("singapore",  "sg_grid_factor",  "SG")
    _patch_grid("uk",         "uk_grid_factor",  "UK")
    _patch_grid("australia",  "au_grid_factor",  "AU")
    _patch_grid("usa",        "usa_grid_factor", "USA")
    _patch_grid("eu_average", "eu_grid_factor",  "EU avg")

    # Singapore carbon tax
    sg_tax = results.get("sg_carbon_tax", {})
    if isinstance(sg_tax, dict) and sg_tax.get("current_rate_sgd"):
        ef.setdefault("carbon_tax_live", {})["singapore_current_sgd"] = sg_tax["current_rate_sgd"]
        if sg_tax.get("next_rate_sgd"):
            ef["carbon_tax_live"]["singapore_next_sgd"] = sg_tax["next_rate_sgd"]
        updated.append(f"SG carbon tax: SGD {sg_tax['current_rate_sgd']}/tCO₂e")
        db_rows.append(("carbon_tax", "current_rate", "singapore", sg_tax["current_rate_sgd"], "sgd_per_tco2e", sg_tax.get("source", "")))

    # EU ETS
    eu_ets = results.get("eu_ets_price", {})
    if isinstance(eu_ets, dict) and eu_ets.get("price_eur_per_tco2e"):
        ef.setdefault("carbon_tax_live", {})["eu_ets_eur"] = eu_ets["price_eur_per_tco2e"]
        updated.append(f"EU ETS: €{eu_ets['price_eur_per_tco2e']}/tCO₂e")
        db_rows.append(("carbon_tax", "ets_price", "eu", eu_ets["price_eur_per_tco2e"], "eur_per_tco2e", eu_ets.get("source", "")))

    # UK ETS
    uk_ets = results.get("uk_ets_price", {})
    if isinstance(uk_ets, dict) and uk_ets.get("price_gbp_per_tco2e"):
        ef.setdefault("carbon_tax_live", {})["uk_ets_gbp"] = uk_ets["price_gbp_per_tco2e"]
        updated.append(f"UK ETS: £{uk_ets['price_gbp_per_tco2e']}/tCO₂e")
        db_rows.append(("carbon_tax", "ets_price", "uk", uk_ets["price_gbp_per_tco2e"], "gbp_per_tco2e", uk_ets.get("source", "")))

    # Aviation factors
    icao = results.get("icao_flight_factors", {})
    if isinstance(icao, dict):
        if icao.get("short_haul_economy"):
            ef["travel"]["short_haul_flight"]["economy"] = icao["short_haul_economy"]
            updated.append(f"ICAO short-haul economy: {icao['short_haul_economy']}")
            db_rows.append(("travel", "short_haul_flight", "global", icao["short_haul_economy"], "kg_co2e_per_passenger_km", icao.get("source", "")))
        if icao.get("long_haul_economy"):
            ef["travel"]["long_haul_flight"]["economy"] = icao["long_haul_economy"]
            updated.append(f"ICAO long-haul economy: {icao['long_haul_economy']}")
            db_rows.append(("travel", "long_haul_flight", "global", icao["long_haul_economy"], "kg_co2e_per_passenger_km", icao.get("source", "")))
        if icao.get("long_haul_business"):
            ef["travel"]["long_haul_flight"]["business"] = icao["long_haul_business"]
            updated.append(f"ICAO long-haul business: {icao['long_haul_business']}")

    # Catering factors
    food = results.get("food_emission_factors", {})
    if isinstance(food, dict):
        if food.get("beef_factor"):
            ef["catering"]["red_meat_meal"]["factor"] = food["beef_factor"]
            updated.append(f"Beef meal: {food['beef_factor']} kg CO₂e")
            db_rows.append(("catering", "red_meat_meal", "global", food["beef_factor"], "kg_co2e_per_meal", food.get("source", "")))
        if food.get("chicken_factor"):
            ef["catering"]["white_meat_meal"]["factor"] = food["chicken_factor"]
            updated.append(f"Chicken meal: {food['chicken_factor']} kg CO₂e")
            db_rows.append(("catering", "white_meat_meal", "global", food["chicken_factor"], "kg_co2e_per_meal", food.get("source", "")))
        if food.get("vegetarian_factor"):
            ef["catering"]["vegetarian_meal"]["factor"] = food["vegetarian_factor"]
            updated.append(f"Vegetarian meal: {food['vegetarian_factor']} kg CO₂e")
            db_rows.append(("catering", "vegetarian_meal", "global", food["vegetarian_factor"], "kg_co2e_per_meal", food.get("source", "")))
        if food.get("vegan_factor"):
            ef["catering"]["vegan_meal"]["factor"] = food["vegan_factor"]
            updated.append(f"Vegan meal: {food['vegan_factor']} kg CO₂e")
            db_rows.append(("catering", "vegan_meal", "global", food["vegan_factor"], "kg_co2e_per_meal", food.get("source", "")))

    if updated:
        ef["last_agent_update"] = datetime.utcnow().isoformat()
        with open(ef_path, "w") as f:
            json.dump(ef, f, indent=2)

    # Persist updated factors to EmissionFactorDB
    if db_rows:
        await _upsert_emission_factors(db_rows)

    return {"updated_fields": updated, "total": len(updated)}


async def run_and_update(force: bool = False) -> dict:
    """Full pipeline: run all TinyFish agents → merge → return summary."""
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
        "ran_at": datetime.utcnow().isoformat(),
        "ttl_hours": AGENT_TTL_HOURS,
        "forced": force,
    }
