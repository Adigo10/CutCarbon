"""
TinyFish Web Agent layer — using the official TinyFish SDK.
Each agent sends a goal + url to the TinyFish API which runs a real headless
browser to extract live emission-factor and carbon-price data.

SDK: https://pypi.org/project/tinyfish/
client.agent.run(goal=..., url=...) → AgentRunResponse.result (str)
client.agent.stream(...)            → streaming with callbacks
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from tinyfish.client import AsyncTinyFish
from tinyfish.agent.types import CompleteEvent, ProgressEvent

from app.config import settings

_DATA_DIR = Path(__file__).parent.parent / "data"

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
            "factor_value": factor,
            "unit": "kg_co2e_per_kwh",
            "source": "EMA Singapore (via TinyFish)",
        }


class UKGridFactorAgent(TinyFishAgent):
    def __init__(self):
        super().__init__(
            name="uk_grid_factor",
            url="https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting",
            goal=(
                "Find the latest UK electricity grid emission factor in kg CO2e per kWh from DEFRA conversion factors. "
                "Return ONLY JSON: {\"factor\": <number>, \"unit\": \"kg_co2e_per_kwh\", \"year\": <year>}"
            ),
            category="venue_energy",
        )

    def parse_result(self, text: str) -> dict:
        match = re.search(r'"factor"\s*:\s*([\d.]+)', text)
        factor = float(match.group(1)) if match else None
        return {
            "category": "venue_energy",
            "region": "uk",
            "factor_value": factor,
            "unit": "kg_co2e_per_kwh",
            "source": "UK DEFRA (via TinyFish)",
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


# ── Agent registry ─────────────────────────────────────────────────────────────

REGISTERED_AGENTS: list[TinyFishAgent] = [
    SingaporeGridFactorAgent(),
    UKGridFactorAgent(),
    SingaporeCarbonTaxAgent(),
    EUETSPriceAgent(),
    FlightEmissionFactorAgent(),
    CateringEmissionFactorAgent(),
]


# ── Orchestrator ───────────────────────────────────────────────────────────────

async def run_all_agents() -> dict:
    """Run all registered TinyFish agents concurrently."""
    tasks = [agent.run() for agent in REGISTERED_AGENTS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = {}
    for agent, result in zip(REGISTERED_AGENTS, results):
        if isinstance(result, Exception):
            output[agent.name] = {"error": str(result)}
        else:
            output[agent.name] = result or {"status": "no_data"}

    return output


async def merge_fetched_factors(results: dict) -> dict:
    """
    Merge freshly fetched factors into emission_factors.json.
    Only overwrites values where the agent returned a non-None result.
    """
    ef_path = _DATA_DIR / "emission_factors.json"
    with open(ef_path) as f:
        ef = json.load(f)

    updated = []

    # Singapore grid
    sg = results.get("sg_grid_factor", {})
    if sg and sg.get("factor_value"):
        old = ef["venue_energy"]["grids"]["singapore"]["factor"]
        ef["venue_energy"]["grids"]["singapore"]["factor"] = sg["factor_value"]
        ef["venue_energy"]["grids"]["singapore"]["source"] = sg.get("source", "EMA SG via TinyFish")
        prov = sg.get("_provenance", {})
        ef["venue_energy"]["grids"]["singapore"]["last_fetched"] = prov.get("fetched_at")
        updated.append(f"SG grid: {old} → {sg['factor_value']} kg CO₂e/kWh")

    # UK grid
    uk = results.get("uk_grid_factor", {})
    if uk and uk.get("factor_value"):
        old = ef["venue_energy"]["grids"]["uk"]["factor"]
        ef["venue_energy"]["grids"]["uk"]["factor"] = uk["factor_value"]
        updated.append(f"UK grid: {old} → {uk['factor_value']} kg CO₂e/kWh")

    # Singapore carbon tax
    sg_tax = results.get("sg_carbon_tax", {})
    if sg_tax and sg_tax.get("current_rate_sgd"):
        ef.setdefault("carbon_tax_live", {})["singapore_current_sgd"] = sg_tax["current_rate_sgd"]
        if sg_tax.get("next_rate_sgd"):
            ef["carbon_tax_live"]["singapore_next_sgd"] = sg_tax["next_rate_sgd"]
        updated.append(f"SG carbon tax: SGD {sg_tax['current_rate_sgd']}/tCO₂e")

    # EU ETS
    eu = results.get("eu_ets_price", {})
    if eu and eu.get("price_eur_per_tco2e"):
        ef.setdefault("carbon_tax_live", {})["eu_ets_eur"] = eu["price_eur_per_tco2e"]
        updated.append(f"EU ETS: €{eu['price_eur_per_tco2e']}/tCO₂e")

    # Aviation factors
    icao = results.get("icao_flight_factors", {})
    if icao and icao.get("short_haul_economy"):
        ef["travel"]["short_haul_flight"]["economy"] = icao["short_haul_economy"]
        updated.append(f"ICAO short-haul economy: {icao['short_haul_economy']}")
    if icao and icao.get("long_haul_economy"):
        ef["travel"]["long_haul_flight"]["economy"] = icao["long_haul_economy"]
        updated.append(f"ICAO long-haul economy: {icao['long_haul_economy']}")

    # Catering factors
    food = results.get("food_emission_factors", {})
    if food and food.get("beef_factor"):
        ef["catering"]["red_meat_meal"]["factor"] = food["beef_factor"]
        updated.append(f"Beef meal: {food['beef_factor']} kg CO₂e")
    if food and food.get("vegetarian_factor"):
        ef["catering"]["vegetarian_meal"]["factor"] = food["vegetarian_factor"]
        updated.append(f"Vegetarian meal: {food['vegetarian_factor']} kg CO₂e")

    if updated:
        ef["last_agent_update"] = datetime.utcnow().isoformat()
        with open(ef_path, "w") as f:
            json.dump(ef, f, indent=2)

    return {"updated_fields": updated, "total": len(updated)}


async def run_and_update() -> dict:
    """Full pipeline: run all TinyFish agents → merge → return summary."""
    results = await run_all_agents()
    merge_summary = await merge_fetched_factors(results)
    return {
        "agent_results": {
            k: {
                "status": v.get("_provenance", {}).get("status", "ok") if isinstance(v, dict) else "error",
                "run_id": v.get("_provenance", {}).get("run_id") if isinstance(v, dict) else None,
                "steps": v.get("_provenance", {}).get("num_steps") if isinstance(v, dict) else None,
                "data": {kk: vv for kk, vv in v.items() if kk != "_provenance"} if isinstance(v, dict) else v,
            }
            for k, v in results.items()
        },
        "merge_summary": merge_summary,
        "ran_at": datetime.utcnow().isoformat(),
    }
