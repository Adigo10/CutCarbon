# TinyFish Web Agents — Reference

CutCarbon runs 10 headless-browser agents via the TinyFish SDK to keep `emission_factors.json` current with live data from authoritative sources. This document covers every agent's specification, the shared caching and validation model, the API endpoints for triggering and monitoring runs, and a developer guide for extending the agent roster.

---

## Agent Roster

| # | Agent ID | Category | Source Authority | Geographic Scope | Data Destination |
|---|---|---|---|---|---|
| 1 | `sg_grid_factor` | Grid factor | EMA (Singapore Electricity Market Authority) | Singapore | `emission_factors.json["venue_energy"]["grids"]["singapore"]` |
| 2 | `uk_grid_factor` | Grid factor | UK DEFRA (2024 GHG Conversion Factors) | UK | `emission_factors.json["venue_energy"]["grids"]["uk"]` |
| 3 | `au_grid_factor` | Grid factor | Clean Energy Regulator (NGER) | Australia | `emission_factors.json["venue_energy"]["grids"]["australia"]` |
| 4 | `usa_grid_factor` | Grid factor | EPA eGRID | USA | `emission_factors.json["venue_energy"]["grids"]["usa"]` |
| 5 | `eu_grid_factor` | Grid factor | EEA (European Environment Agency) | EU average | `emission_factors.json["venue_energy"]["grids"]["eu_average"]` |
| 6 | `sg_carbon_tax` | Carbon pricing | NEA (Singapore National Environment Agency) | Singapore | `emission_factors.json["carbon_tax_live"]["singapore_*"]` |
| 7 | `eu_ets_price` | Carbon pricing | Ember Climate | EU | `emission_factors.json["carbon_tax_live"]["eu_ets_eur"]` |
| 8 | `uk_ets_price` | Carbon pricing | UK Government (UK ETS guidance) | UK | `emission_factors.json["carbon_tax_live"]["uk_ets_gbp"]` |
| 9 | `icao_flight_factors` | Travel | ICAO Carbon Offset calculator | Global | `emission_factors.json["travel"]["*_flight"]["*"]` |
| 10 | `food_emission_factors` | Catering | Our World in Data | Global | `emission_factors.json["catering"]["*_meal"]["factor"]` |

---

## Grid Emission Factor Agents (5)

These agents fetch the electricity grid carbon intensity (kg CO₂e per kWh) for each supported region. All values are validated against region-specific bounds before being written; out-of-range values are silently discarded to prevent corrupted parses from overwriting good data.

### `sg_grid_factor` — Singapore (EMA)

| Field | Value |
|---|---|
| **Source** | Singapore Electricity Market Authority (EMA) |
| **URL** | `https://www.ema.gov.sg/consumer-information/electricity/buying-electricity/understanding-electricity/grid-emission-factor` |
| **Output fields** | `factor_value` (kg CO₂e/kWh), `unit` (`kg_co2e_per_kwh`), `region` (`singapore`) |
| **Validation bounds** | 0.30 – 0.70 kg CO₂e/kWh |
| **Unit conversion** | None |
| **DB category** | `venue_energy` / subcategory `grid` / region `singapore` |

Parse logic: regex searches for `"factor": <number>` JSON pattern; falls back to bare-value pattern `0.\d{3,4} kg`.

---

### `uk_grid_factor` — UK (DEFRA)

| Field | Value |
|---|---|
| **Source** | UK DEFRA — Greenhouse Gas Reporting Conversion Factors 2024 |
| **URL** | `https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2024` |
| **Output fields** | `factor_value` (kg CO₂e/kWh), `unit`, `region` (`uk`) |
| **Validation bounds** | 0.10 – 0.45 kg CO₂e/kWh |
| **Unit conversion** | None |
| **DB category** | `venue_energy` / subcategory `grid` / region `uk` |

---

### `au_grid_factor` — Australia (Clean Energy Regulator)

| Field | Value |
|---|---|
| **Source** | Australian Clean Energy Regulator — NGER Emission Factor Profile |
| **URL** | `https://www.cleanenergyregulator.gov.au/NGER/National-greenhouse-and-energy-reporting-scheme-measurement/Emission-factor-profile` |
| **Output fields** | `factor_value` (kg CO₂e/kWh), `unit`, `year`, `region` (`australia`) |
| **Validation bounds** | 0.40 – 1.00 kg CO₂e/kWh |
| **Unit conversion** | None |
| **DB category** | `venue_energy` / subcategory `grid` / region `australia` |

Australia's range is the highest across all regions, reflecting its coal-heavy generation mix.

---

### `usa_grid_factor` — USA (EPA eGRID)

| Field | Value |
|---|---|
| **Source** | US Environmental Protection Agency — eGRID Summary Data |
| **URL** | `https://www.epa.gov/egrid/summary-data` |
| **Output fields** | `factor_value` (kg CO₂e/kWh after conversion), `unit`, `year`, `region` (`usa`) |
| **Validation bounds** | 0.25 – 0.60 kg CO₂e/kWh |
| **Unit conversion** | eGRID reports in lb/MWh. If parsed value > 2, auto-converts: `factor_kg_kwh = factor_lb_mwh / 2204.62` |
| **DB category** | `venue_energy` / subcategory `grid` / region `usa` |

The conversion guard prevents raw lb/MWh values (~400) from being stored directly.

---

### `eu_grid_factor` — EU average (EEA)

| Field | Value |
|---|---|
| **Source** | European Environment Agency — CO₂ Intensity of Electricity Generation |
| **URL** | `https://www.eea.europa.eu/en/analysis/indicators/co2-intensity-of-electricity-generation` |
| **Output fields** | `factor_value` (kg CO₂e/kWh after conversion), `unit`, `year`, `region` (`eu_average`) |
| **Validation bounds** | 0.15 – 0.50 kg CO₂e/kWh |
| **Unit conversion** | EEA reports in g CO₂e/kWh. If parsed value > 1, divides by 1000. A second guard applies if the value is still > 2. |
| **DB category** | `venue_energy` / subcategory `grid` / region `eu_average` |

---

## Carbon Pricing Agents (3)

These agents fetch live carbon prices and tax rates. Data is written to the `carbon_tax_live` key in `emission_factors.json` and used by `financial_engine.py` for tax liability and savings calculations.

### `sg_carbon_tax` — Singapore (NEA)

| Field | Value |
|---|---|
| **Source** | Singapore National Environment Agency |
| **URL** | `https://www.nea.gov.sg/our-services/climate-change-energy-efficiency/climate-change/singapore-s-carbon-tax` |
| **Output fields** | `current_rate_sgd` (SGD/tCO₂e), `next_rate_sgd` (optional), `next_rate_year` (optional) |
| **Data destination** | `emission_factors.json["carbon_tax_live"]["singapore_current_sgd"]` and `["singapore_next_sgd"]` |
| **DB category** | `carbon_tax` / subcategory `current_rate` / region `singapore` / unit `sgd_per_tco2e` |

Fetches both the current rate and any announced future rate step-up, enabling forward-looking financial projections.

---

### `eu_ets_price` — EU ETS (Ember Climate)

| Field | Value |
|---|---|
| **Source** | Ember Climate — Carbon Price Viewer |
| **URL** | `https://ember-climate.org/data/data-tools/carbon-price-viewer/` |
| **Output fields** | `price_eur` (EUR/tCO₂e), `date` (YYYY-MM-DD) |
| **Data destination** | `emission_factors.json["carbon_tax_live"]["eu_ets_eur"]` |
| **DB category** | `carbon_tax` / subcategory `ets_price` / region `eu` / unit `eur_per_tco2e` |

---

### `uk_ets_price` — UK ETS (UK Government)

| Field | Value |
|---|---|
| **Source** | UK Government — UK Emissions Trading Scheme guidance |
| **URL** | `https://www.gov.uk/guidance/uk-emissions-trading-scheme-uk-ets` |
| **Output fields** | `price_gbp` (GBP/tCO₂e), `date` |
| **Data destination** | `emission_factors.json["carbon_tax_live"]["uk_ets_gbp"]` |
| **DB category** | `carbon_tax` / subcategory `ets_price` / region `uk` / unit `gbp_per_tco2e` |

---

## Travel & Catering Agents (2)

### `icao_flight_factors` — Aviation (ICAO)

| Field | Value |
|---|---|
| **Source** | International Civil Aviation Organization — Carbon Offset calculator |
| **URL** | `https://www.icao.int/environmental-protection/CarbonOffset/Pages/default.aspx` |
| **Output fields** | `short_haul_economy`, `long_haul_economy`, `long_haul_business` (all in kg CO₂e/passenger-km), `unit` (`kg_co2e_per_passenger_km`) |
| **Data destination** | `emission_factors.json["travel"]["short_haul_flight"]["economy"]`, `["long_haul_flight"]["economy"]`, `["long_haul_flight"]["business"]` |
| **DB category** | `travel` / subcategory `short_haul_flight` or `long_haul_flight` / region `global` |

Note: The Radiative Forcing Index (RFI) multiplier (1.9×) is applied separately in `emissions_engine.py`; this agent only fetches the base kg CO₂/pax-km factors.

---

### `food_emission_factors` — Catering (Our World in Data)

| Field | Value |
|---|---|
| **Source** | Our World in Data — Food choice vs. eating local |
| **URL** | `https://ourworldindata.org/food-choice-vs-eating-local` |
| **Output fields** | `beef_factor`, `chicken_factor`, `vegetarian_factor`, `vegan_factor` (all in kg CO₂e/meal) |
| **Data destination** | `emission_factors.json["catering"]["red_meat_meal"]["factor"]`, `["white_meat_meal"]["factor"]`, `["vegetarian_meal"]["factor"]`, `["vegan_meal"]["factor"]` |
| **DB category** | `catering` / region `global` |

---

## Caching & Validation Behavior

### TTL Caching

All agents share a 12-hour TTL cache. Before executing a run, the orchestrator queries `AgentRunDB` for the most recent successful run with `status = "success"`. If that run's `fetched_at` timestamp is within the last 12 hours, the cached result is returned immediately with a `_cache_hit: true` flag and no TinyFish API call is made.

The `force=true` parameter on the run endpoint bypasses the TTL check and triggers all agents regardless of cache freshness.

### Validation Bounds

Grid factor agents use a `_GRID_FACTOR_BOUNDS` dict with per-region min/max values. If a parsed value falls outside the bounds, `_validated_grid_factor()` returns `None`. The merge step skips any `None` value, leaving the previous valid value in `emission_factors.json` unchanged.

### Unit Conversions Applied

| Agent | Raw unit from source | Stored as | Conversion |
|---|---|---|---|
| `usa_grid_factor` | lb/MWh (eGRID) | kg CO₂e/kWh | `÷ 2204.62` if value > 2 |
| `eu_grid_factor` | g CO₂e/kWh (EEA) | kg CO₂e/kWh | `÷ 1000` if value > 1 |
| All others | kg CO₂e/kWh | kg CO₂e/kWh | None |

### Merge Strategy

`merge_fetched_factors()` in `tinyfish_agent.py` iterates over agent results. Each field is only written to `emission_factors.json` if the agent returned a non-`None` validated value. This conservative merge prevents a failed or corrupted parse from overwriting a previously good value.

After writing the JSON, affected rows are upserted to `EmissionFactorDB` with `is_verified = True` and the current `last_fetched` / `last_updated` timestamps.

### Provenance

Every successful run stores the following in `AgentRunDB`:

```json
{
  "source_url": "https://...",
  "agent": "sg_grid_factor",
  "run_id": "<tinyfish-run-id>",
  "num_steps": 7,
  "status": "success",
  "started_at": "2026-03-28T02:00:00Z",
  "finished_at": "2026-03-28T02:00:43Z",
  "fetched_at": "2026-03-28T02:00:44Z"
}
```

The `run_id` is the unique TinyFish run identifier, usable to replay or inspect the agent's browser session in the TinyFish dashboard.

---

## API Endpoints

All endpoints live under `/api/agents/` (router: `app/routers/agents.py`).

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/agents/run` | Trigger all agents as a background task. Returns immediately. |
| `GET` | `/api/agents/run/sync` | Trigger all agents synchronously. Waits for completion. |
| `GET` | `/api/agents/status` | Per-agent status: last run time, cache validity, result summary. |
| `GET` | `/api/agents/history` | Paginated run history (50 most recent by default). |

The `force=true` query parameter is accepted by both run endpoints to bypass the 12-hour TTL cache.

---

## Adding or Modifying an Agent

1. **Create an agent class** in `app/services/tinyfish_agent.py`. Subclass `TinyfishAgent` (or follow the pattern of existing agents). Set:
   - `name`: unique snake_case identifier
   - `url`: target URL
   - `goal`: instruction string for the headless browser
   - `output_schema`: Pydantic model defining the expected JSON output

2. **Register the agent** by adding an instance to the `REGISTERED_AGENTS` list at the bottom of `tinyfish_agent.py`.

3. **Add merge logic** in `merge_fetched_factors()`: map the agent's output fields to their keys in `emission_factors.json` and `EmissionFactorDB`.

4. **Add validation bounds** (for numeric factors) to `_GRID_FACTOR_BOUNDS` or a similar dict, with region-appropriate min/max values. Include a conversion step if the source reports in non-standard units.

5. **Test** by calling `GET /api/agents/run/sync?force=true` and checking `/api/agents/status` for the new agent's result.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Agent status shows `error` | Source URL changed or site structure updated | Check the TinyFish run log for the HTML it received; update the `url` or `goal` in the agent class |
| Factor value unchanged after successful run | Parsed value fell outside validation bounds | Lower/raise bounds in `_GRID_FACTOR_BOUNDS` if the source data is legitimately out of range |
| Unit conversion producing wrong value | Source changed reporting units | Add/adjust conversion in the agent's `_parse_result()` method |
| Agent always shows `_cache_hit: true` | Within 12-hour TTL window | Use `force=true` to bypass: `GET /api/agents/run/sync?force=true` |
| DB write fails after successful fetch | `EmissionFactorDB` upsert error | Check `DATABASE_URL` env var and ensure the `emission_factors` table exists (auto-created on startup) |
