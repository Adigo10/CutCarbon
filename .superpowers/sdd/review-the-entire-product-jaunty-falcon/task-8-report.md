# Task 8 — Obligation scoping — report

**Status:** COMPLETE
**Worktree:** `C:\Users\adity\Projects\CutCarbon\.claude\worktrees\agent-a1be5620f2e05d4d5`
**Branch:** `worktree-agent-a1be5620f2e05d4d5`
**Commit:** `fc70471` — feat(compliance): data-driven obligation scoping, drop the overall score

## Base correction (worth flagging)

The worktree branch was checked out at `d1acc30` (= `main`), **not** at the stated base
containing tasks 1/2/3/5. Those live on `product-upgrades` (`2dea8e9`). Since the branch
carried no commits of its own and the working tree was clean, I reset it to `2dea8e9`
before starting, so the diff applies on the intended base. Nothing was pushed and
`product-upgrades` itself was not touched.

## What was built

### Part A — `app/data/frameworks.json` (new)

Loaded via the `app/services/data_files.py` pattern (`FRAMEWORKS_DATA`). The file carries
every regulatory fact — status, as-of date, phase-in years, size thresholds, tier
boundaries, clause lists, source URLs — so it can be audited and updated without touching
code. The branching each framework needs lives in `financial_engine.py`, keyed by the
entry's `scope_rule`. A generic rule evaluator was rejected deliberately: the nine regimes
differ too much (a size conjunction, two tiered phase-ins, a nexus gate, an injunction),
and a data DSL general enough to express them would have been less auditable than named
functions.

Encoded, exactly as briefed (no re-research):

| key | status | scope encoded |
|---|---|---|
| `eu_csrd` | in_force | post-Omnibus I (adopted 24 Feb 2026): >1,000 employees **AND** >EUR 450m turnover, FY starting >= 1 Jan 2027; simplified ESRS adopted 3 Jul 2026 |
| `sgx_issb` | in_force | tiered — STI: ISSB from FY2025, Scope 3 from FY2026 (mandatory); listed non-STI >S$1bn from FY2028, remainder FY2030; large non-listed FY2030; Scope 3 voluntary off-STI |
| `uk_srs` | **proposed** | S1/S2 published 25 Feb 2026 for VOLUNTARY use; FCA policy statement expected autumn 2026; mandatory from 1 Jan 2027 only *proposed* |
| `au_asrs` | in_force | grouped — Group 2 first period from 1 Jul 2026; Scope 3 NOT required in the first reporting period, mandatory from the second (Group 1 same shape from 2025) |
| `ca_sb253` | in_force | >USD 1bn revenue **AND** California nexus; CARB rules adopted Feb 2026; first Scope 1/2 report due 10 Nov 2026; Scope 3 from 2027 covering FY2026; in-flux note |
| `ca_sb261` | **enjoined** | Ninth Circuit injunction 18 Nov 2025, pending — never asserted as binding |
| `ghg_protocol` | methodology | current Scope 3 Standard; the 95%-completeness revision explicitly flagged DRAFT and not applied |
| `nzce` | voluntary_initiative | 9-category methodology, biennial signatory reporting |
| `iso_20121_2024` | management_system_standard | clause evidence checklist, never a number; 31 Mar 2027 certificate transition |

Plus `event_carbon_intensity` (status `benchmark`) so the existing informational
event-band comparison is data-driven too.

**Size bands.** `employee_bands` and `turnover_bands` are cut *at* the thresholds the scope
tests use (1,000 employees; 450m and 1bn turnover), with exclusive low bounds
(`450m_1b` starts at 450,000,001). That makes every band sit unambiguously above or below
every threshold, so no scope decision is ever a guess. `_band_position` still returns
`"straddles"` if someone later edits the bands — degrading to an honest "cannot tell"
rather than a wrong answer — and a test asserts no encoded band straddles any threshold.

The multi-currency approximation (EUR 450m / USD 1bn / SGD 1bn share one band set) is
documented in the file's `conventions` block and named in every reason string that relies
on it. Likewise, the SGX non-STI tier's statutory test is *market capitalisation*, which
the profile does not capture; the reason says so explicitly rather than silently
substituting turnover.

**`reporting_fy` convention:** the calendar year in which the reporting period *begins*
(1 Jul 2026 - 30 Jun 2027 -> 2026). Documented in the data file and used consistently.

### Part B — schemas + engine rework

`app/models/schemas.py`:
- New `ReportingProfile` — `employee_band`, `annual_turnover_band`, `listing_status`,
  `reporting_fy`, `does_business_in_california`. Every field optional; bands are `Literal`
  types so an unknown band is a clean 422 rather than a silent mis-scope. A test asserts
  the Literals stay in step with `frameworks.json`.
- `ComplianceRequest.reporting_profile: Optional[ReportingProfile] = None`.
- `ComplianceCheck` gains `framework_key`, `applies`, `reason`, `as_of`,
  `first_reporting_fy`, `scope3_required`, `readiness`, `clause_checklist`.
  `status` is repurposed to the *regulatory* status; `score_pct` became `Optional[float]`.
- New `ComplianceClause` (`clause`, `requirement`, `evidence_status`).
- `ComplianceReport`: **`overall_score_pct` dropped**; gains `profile_complete`,
  `profile_note`, `frameworks_as_of`.

`app/services/financial_engine.py` — `get_compliance_report` gains an optional trailing
`reporting_profile` (all existing call sites keep working positionally). Frameworks are
filtered to the normalized region, then resolved to an `applies` value:

`mandatory | voluntary | out_of_scope | not_in_force | enjoined | informational`

The cardinal rule is enforced structurally: a missing profile field, a band straddling a
threshold, or an unspecified tier all return `informational`; `uk_srs` and `ca_sb261`
short-circuit to `voluntary` / `enjoined` regardless of profile, so neither can ever come
out `mandatory`. `mandatory_frameworks` is derived (`applies == "mandatory"`), so it can
no longer drift from the checks.

`scope3_required` is a real cross-cutting concept, not a per-framework hack — four of the
encoded regimes phase Scope 3 separately (SGX, AASB S2, SB 253, ESRS E1). It stays `None`
where the concept does not apply.

`score_pct` survives only where the tool can genuinely assess completeness (GHG inventory,
NZCE, event intensity), with a `readiness` label; it is `None` for every statutory scoping
decision and for ISO 20121, where a number would be invented. ISO 20121's fabricated 50%
is replaced by the six-clause evidence checklist, all `not_evidenced` because the tool
collects none of that evidence.

### Part C — frontend + exports

- `frontend/src/types.ts` — `ReportingProfile`, `ComplianceClause`, reworked
  `ComplianceCheck` / `ComplianceReport` (no `overall_score_pct`).
- `frontend/src/lib/constants.ts` — band/tier option lists mirroring `frameworks.json`,
  `APPLIES_LABELS`, `FRAMEWORK_STATUS_LABELS`, and a default profile that is entirely
  blank (so the default run asserts nothing).
- `ComplianceView` (`views.tsx`) — a small reporting-profile form (three selects, an FY
  number input, a California checkbox); per-framework `applies` + `status` chips with the
  as-of date, first reporting FY, Scope 3 flag and the **reason**; ISO 20121 renders as a
  clause checklist; the completeness bar shows only when `score_pct` is non-null. The
  overall-score dial is gone, replaced by a mandatory-framework count that reads
  "profile incomplete" until a profile is entered. `appliesTone` colours a mandatory
  determination distinctly so an enjoined or informational row can never read as a live
  obligation.
- `App.tsx` — sends `reporting_profile` with unselected bands as `null`; the toast reports
  the mandatory count or the profile-incomplete state instead of a score.
- `dashboard.tsx` — the "Compliance pulse" score tile becomes a mandatory-framework count,
  null unless the profile is complete.
- `App.css` — `.framework-chips`, `.framework-meta`, `.framework-reason`, `.muted-note`.
- `app/routers/exports.py` — CSV, XLSX and PDF compliance sections now carry
  applies / status / as-of / reason / Scope 3 / clause checklist and **no overall score**.
  The XLSX summary row became "Mandatory Frameworks" + "Reporting Profile".
  Exports pass no profile (none is collected there), so every regulated framework is
  reported `informational` — a generated report can never claim an entity is in scope.

## Tests (TDD — written first, watched fail at import, then implemented)

`tests/test_financial.py` — the old `TestComplianceReport` (which asserted the score
behaviour being removed) was replaced by seven classes, +341 lines:

- `TestFrameworksData` — every entry well-formed; schema Literals match the data file;
  **no band straddles any encoded threshold**.
- `TestObligationScoping` — `overall_score_pct` absent from the model; missing profile ->
  `profile_complete` False, note contains "profile incomplete", `mandatory_frameworks`
  empty, and no regulated framework returns `mandatory`, across all five regions;
  region filtering.
- `TestEuCsrdScope` — 40-person EU agency -> `out_of_scope` (reason names both thresholds);
  large undertaking -> `not_in_force` at FY2026, `mandatory` at FY2027; missing bands ->
  `informational`.
- `TestSgxScope` — STI FY2025 mandatory with `scope3_required is False`, **FY2026 with
  `scope3_required is True`**; listed non-STI Scope 3 voluntary; smaller listed issuer
  waits for FY2030; small non-listed out of scope.
- `TestUkSrsScope` — never `mandatory` for any profile including None; status `proposed`.
- `TestAuAsrsScope` — Group 2 FY2025 not in force, FY2026 mandatory with Scope 3
  **excluded in the first reporting period**, FY2027 included; unspecified group ->
  `informational`.
- `TestCaliforniaScope` — SB 253 needs both nexus and revenue; Scope 3 from FY2026; the
  10 Nov 2026 due date in the reason. **SB 261 `enjoined`, never `mandatory`, never in
  `mandatory_frameworks`, with or without a profile.**
- `TestIso20121Checklist` / `TestRetainedQualitativeChecks` — no score, clauses 6.3 / 7.3 /
  9.3.4 / climate change / legacy / Annex D present and `not_evidenced`, 31 Mar 2027 note;
  GHG Protocol gaps and the DRAFT flag; intensity branches; NZCE gaps/recommendations.

`tests/test_reporting_exports.py` — export assertions updated (CSRD `informational`,
`mandatory_frameworks` empty, `profile_complete` False, CSV carries `applies` and no
`overall_score_pct`), plus **two new DB-backed route tests**: one asserting the
`/api/financial/compliance` route scopes from the profile (bare -> informational; STI
FY2026 -> mandatory + Scope 3), one asserting an unknown band is a 422.

## Verification

| Run | Result |
|---|---|
| Non-DB: `test_financial` + `test_claims` + `test_emissions_engine` | **136 passed** |
| DB-backed `tests/test_reporting_exports.py` (isolated, shared pooler) | **20 passed** (254s) |
| `npm run build` | **clean** (built in 4.9s, no TS errors) |
| Full suite (see note) | see below |

**Shared-pooler note.** The Supabase pooler is shared with sibling worktrees. A full-suite
run mid-task returned `1 failed, 166 passed, 34 errors`, where the 34 errors were
`asyncpg.exceptions.TooManyConnectionsError` raised at fixture setup across
`test_scenarios.py`, `test_offsets.py` and `test_reporting_exports.py` — i.e. connection
exhaustion from concurrent sibling runs, not assertion failures. Every one of those files
passes when run on its own (`test_reporting_exports.py`: 20/20). The final full-suite
result is recorded in the reply to the controller.

## Concerns / follow-ups (deliberately out of scope)

1. **Docs still describe the removed score.** `USER_GUIDE.md:190,716,1020` and
   `QUICK_START.md:49` show an "Overall Score: 88/100" / "Compliance Score: 88%" in
   illustrative screens, and `CLAUDE.md` does not list the new `app/data/frameworks.json`
   among the static data files. Left untouched to honour the scoped-diff instruction and
   to avoid colliding with the sibling doing honest-label renames — but they are now
   factually wrong and should be swept.
2. **Exports collect no reporting profile.** Every export therefore reports the regulated
   frameworks as `informational`. That is the honest default, but if a scoped report is
   wanted, the export endpoints would need profile query params alongside the existing
   `region` / `has_scope3` / `has_ghg_report` overrides.
3. **Currency approximation.** One turnover band set serves EUR 450m, USD 1bn and SGD 1bn.
   Documented and surfaced in every reason string, but a per-currency band set would be
   more precise if the product ever scopes multi-jurisdiction entities seriously.
4. **SGX non-STI uses turnover as a market-cap proxy.** Stated plainly in the reason. A
   dedicated `market_cap_band` field would remove the approximation; it was not in the
   brief's profile field list.
5. **ASRS group is user-asserted.** Group membership actually derives from consolidated
   revenue/assets/employees/emitter tests the profile does not collect, so an unspecified
   group yields `informational` rather than a derived group.
6. **Shared test DB.** Full-suite runs hit connection exhaustion from sibling worktrees;
   see the Verification note.
7. **`ComplianceCheck.status` changed meaning** — it was `compliant | partial |
   non_compliant`, it is now the *regulatory* status (`in_force`, `proposed`, `enjoined`,
   ...). The readiness sense moved to the new optional `readiness` field. Every in-repo
   consumer (ComplianceView, dashboard, all four export formats) is updated, and nothing
   persists a `ComplianceReport` today — but the sibling task adding **report snapshots to
   the database** should be merged aware of this: a snapshot taken before this change
   would carry the old `status` semantics and no `applies` field. Worth a look at merge
   time.
