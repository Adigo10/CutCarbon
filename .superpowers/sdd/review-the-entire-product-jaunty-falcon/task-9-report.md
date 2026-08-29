# Task 9 — Boundary toggle + Scope 2 dual reporting — Report

**Status:** COMPLETE
**Worktree:** `C:\Users\adity\Projects\CutCarbon\.claude\worktrees\agent-ad05e4dc9507a2a1d`
**Branch:** `worktree-agent-ad05e4dc9507a2a1d`
**Commits:**
- `1669383` feat(scope): organizational-boundary toggle + Scope 2 dual reporting
- `26102f0` fix(ui): route the flow diagram's venue and equipment edges by the declared boundary
- `129c9c1` fix(scope): say 'no venue declared' instead of quoting two zero bases

## Base correction (before any work)

The worktree was checked out at `d1acc30` (main), not the base the dispatch described.
Confirmed `d1acc30` is an ancestor of `ded5d8d` (product-upgrades head, Tasks 1–5) and
the branch carried no commits of its own, so `git reset --hard ded5d8d` before starting.
This matches the coordinator's mid-task correction, which arrived after the reset was
already done.

## Part A — organizational-boundary control

- `app/models/schemas.py`: new `BoundaryControl` enum (`owned_operated` | `contracted`);
  `control` field added to `VenueEnergy` and `EquipmentGroup`, defaulting to `contracted`.
- `app/services/emissions_engine.py`: `_holds_control()` reads the boundary off either
  input group (absent input → `contracted`). In `calculate_scenario`:
  - venue owned → electricity to Scope 2 (+ venue Scope 1, still 0 in the engine);
    contracted → the whole venue line to Scope 3.
  - equipment owned → today's split (S1 generator fuel / S2 electricity / S3 stage+freight);
    contracted → `equip_kg` in full to Scope 3, generator fuel included.
  - Composes with T2's guards: the `venue_metered` electricity exclusion still runs
    inside `_equipment_emissions` before routing, and `physical_attendee_count`
    still sizes the proxies.
- Disclosure: `assumptions["boundary"]` names the routing for each line and states that
  the total is unchanged, only the scope.
- Frontend: `BOUNDARY_CONTROL_OPTIONS` selector in the builder's venue section with
  helper text; `draft.venue_control` threads into both `venue_energy.control` and
  `equipment.control` (the venue boundary governs the kit plugged into it).

## Part B — Scope 2 dual reporting

- `RenewableInstrument` enum (`rec` | `ppa` | `green_tariff` | `none`) on `VenueEnergy`,
  default `none`.
- `_venue_energy_emissions` now returns a `VenueEnergyResult` NamedTuple carrying
  `location_kg`, `market_kg` and `instrument_backed` alongside the headline total:
  - **location** = every kWh at the published grid factor, no renewable discount.
  - **market** = instrument-backed share zeroed; the remainder priced at
    `residual_mix_factor(grid_ef)`. With `none`, market == location.
  - headline = market when instrument-backed, location otherwise.
- `ScopeBreakdown` gains `scope2_location_tco2e` / `scope2_market_tco2e`.
- `assumptions["scope2_reporting"]` carries both figures, the headline basis, the
  instrument and a prose note. When contracted, the Scope 2 fields are zero but the
  note still discloses the electricity line on both bases (per the brief).
- Exports: shared `_scope_rows()` helper with explicit labels feeds CSV, PDF and XLSX;
  JSON is automatic via the payload dump. **The XLSX report had no scope breakdown at
  all** — a Scope block was added to its Report Summary sheet. The bulk scenarios
  workbook gained the same two columns and its "Scope 2" header was disambiguated to
  "Scope 2 (headline basis)".
- Frontend: instrument selector next to the renewable slider; the scenario comparison
  panel now shows Scope 2 (headline / location / market) with a fallback to the
  headline figure for pre-dual-reporting rows.

### Residual-mix factor

`app/data/emission_factors.json` → `venue_energy.residual_mix.global_uplift_on_location_factor`:
a **ratio of 1.43** applied to the selected region's own location factor, with `source`,
`methodology` and `limitations` fields.

Derivation (documented in the file): residual mix = grid emissions / untracked
generation. Approximating the contractually claimed share by the global renewable share
of generation R ≈ 0.30 (IEA/Ember 2023) gives `residual_EF = location_EF / (1 - R) =
location_EF × 1.43`. Stored as a ratio rather than an absolute kg/kWh so regional
differences in grid intensity are preserved (France stays clean, South Africa stays dirty).

The brief permitted "one documented global approximation" where no defensible regional
source is at hand; I took that option rather than transcribing AIB/Green-e figures I
could not verify offline. The `limitations` field states plainly that it is an upper
bound, that it overstates the residual mix in low-renewable grids (Singapore, UAE) and
understates it where guarantees of origin are heavily exported (France, the Nordics),
and names AIB / Green-e as the replacements to source.

Sanity check: 1.43× lands inside the plausible band for published residual mixes
(typically 1.3–1.6× the location factor).

### Design decision — persistence without a migration

The two figures persist through the existing `assumptions` JSONB column
(`scenario_serializer.scope2_dual_bases` reads them back) rather than new
`ScenarioDB` columns. Rationale: no Alembic head to collide with the sibling tasks
also in flight, and legacy rows degrade correctly — a row with no recorded instrument
has market == location == the stored headline, which is exactly right for it. If a
future task wants them queryable, promoting them to columns is mechanical.

## Tests

TDD: 12 new engine tests written and confirmed red before implementation
(`TestOrganizationalBoundary`, `TestScope2DualReporting`), covering the brief's four
cases plus the contracted disclosure, the documented-factor check and a
routing-conserves-the-total check.

Updated with per-test justification:

| Test | Why it changed |
|---|---|
| `TestEquipmentDoubleCountGuard::test_metered_equipment_contributes_no_scope2` | Reads the double-count guard off the Scope 2 figure, which is 0 by design under the contracted default. Now pins an owned/operated boundary via a new `_owned()` helper, keeping the guard witnessed. |
| `TestEquipmentDoubleCountGuard::test_unmetered_venue_still_counts_equipment_electricity` | Same reason, same fix. |
| `test_characterization::test_seeded_scenario_category_totals` | The seeded payload claims 10% renewable with no instrument. That share is no longer deducted, so venue 0.9045 → 1.005 tCO2e and total 74.5019 → 74.6024. This is the Part B fix landing, not drift. |

New: `test_characterization::test_seeded_scenario_scope_split_follows_the_boundary`
pins the contracted default's scope split and the contracted-case disclosure;
`test_reporting_exports` asserts both Scope 2 lines in the JSON, CSV and XLSX exports.

**Back-compat check.** Routing alone moves no kilograms:
`test_routing_alone_does_not_change_the_total` asserts identical totals and identical
`venue_energy_tco2e` / `equipment_tco2e` between the two boundaries. The *only* number
that moves for an existing payload is a venue with `renewable_pct > 0` and no
instrument — which is precisely the Part B correction the brief specifies
("instrument 'none' ⇒ NO market-based reduction"), and it is characterized above.

**Frontend:** `npm run build` (tsc + vite) clean.

**Test runs.** The shared Supabase pooler was saturated by sibling worktrees for the
whole session (`TooManyConnectionsError` / `EMAXPOOLSREACHED` / `max pools count
reached`). Every run is cited:

| # | Scope | Result |
|---|---|---|
| 1 | `test_reporting_exports.py` + `test_scenarios.py` | 12 passed, 14 pooler errors |
| 2 | **full suite** | **1 failed, 191 passed, 21 pooler errors** — the single failure was `test_seeded_scenario_category_totals`, fixed and characterized above |
| 3 | exports + scenarios + agents + financial | 42 passed, 19 pooler errors (`…[xlsx]` passed here — the new XLSX Scope-block assertion is green) |
| 4 | `test_reporting_exports.py` | 7 passed, 11 pooler errors |
| 5 | full suite (after a 5-min pause, backgrounded) | **abandoned** — sat at 0% CPU for ~30 min blocked acquiring a connection; killed |
| 6 | `test_reporting_exports.py` + `test_scenarios.py` (after killing #5) | 7 passed, 19 pooler errors |
| 7 | all non-DB suites, final code state | **122 passed, 1 skipped** |

Three sibling `pytest` processes were confirmed running concurrently against the same
pooler (`Get-Process python` showed PIDs 9392 / 16240 / 17368, all near-zero CPU).
**No run at any point produced a non-pooler failure other than the characterization
value, which is fixed.** Every error was `asyncpg.exceptions.TooManyConnectionsError`
or `InternalServerError (EMAXPOOLSREACHED)` raised in the session fixture, before any
test body ran.

The DB-backed tests this change actually touches did pass when they got a connection:
`test_single_scenario_report_exports_return_expected_files[xlsx]` (run 3) exercises the
new XLSX Scope block, and the CSV/JSON variants passed in run 2. **Recommendation: the
controller should re-run `tests/test_reporting_exports.py` and `tests/test_scenarios.py`
once the sibling worktrees are done, before merging.**

## Collateral fix

`financial_engine.build_scenario_financial_request`'s legacy fallback back-solves venue
kWh from the stored emission by dividing by `grid_ef * (1 - renewable_pct/100)`. That
divisor no longer matches what the engine stored, so it now mirrors the engine's rule
(residual mix when instrument-backed, plain grid factor otherwise). Exception path only —
the primary path uses `estimate_venue_kwh`, which my change does not touch.

`build_factors_snapshot` also records `venue_residual_mix_kg_per_kwh` so a reader can
audit what a market-based claim was priced at (provenance only, never read back).

## Concerns

1. **Residual mix is an approximation, by design and disclosed.** A single global uplift
   is wrong in both directions for specific grids (see `limitations` in the JSON). It is
   the honest option available offline; sourcing AIB (EU/EEA) and Green-e (US) per-region
   residual mixes is a clean follow-up that only touches the data file plus a lookup in
   `residual_mix_factor`.
2. **A rate below the global renewable share makes market > location.** With a 1.43×
   uplift, an instrument covering less than ~30% of supply yields a market figure above
   the location figure. That is the correct incentive under Scope 2 guidance (claiming
   less clean power than the grid average leaves you a dirtier residual), but it will
   surprise a user who buys a token REC. Worth a UI note if it comes up in review.
3. **PDF export is asserted only at the smoke level** (`startswith(b"%PDF")`), matching
   the existing test style — reportlab output is compressed and not cheaply searchable.
   The two Scope 2 lines reach the PDF through the same `_scope_rows()` helper that CSV
   and XLSX assert on, so they are covered by construction rather than directly.
4. **Merge surface with siblings:** `scenario_serializer.py` (provenance panel task),
   `exports.py` (report snapshots task) and `financial_engine.py` (Task 3's file) all
   have small additions here. No Alembic migration was added, deliberately, so there is
   no head collision.
5. **The chat tool schema (`openai_service.py`) was not extended** with `control` /
   `renewable_instrument` — the brief scoped the UI to the builder. Chat-extracted
   scenarios therefore land on the safe defaults (contracted, no instrument).
