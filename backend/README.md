# Backend

FastAPI + SQLAlchemy + Alembic + PostgreSQL (SQLite in tests). Nine modules
live here so far:

- **Module 1 — Data Model & Event Logging**: the `suggestion_event` and
  `user_monthly_snapshot` tables every other module depends on, plus a
  logging service and read queries/endpoints over both.
- **Module 2 — Onboarding & Financial Position**: profile/EMI/insurance/
  holdings/expense capture, and the pure net-worth/surplus/buffer/EMI-ratio
  calculations, which write a `user_monthly_snapshot` row via Module 1's
  logging function on completion and on every material edit.
- **Module 3 — Risk Profiling**: a deterministic questionnaire scorer
  (willingness) and an independent, objective capacity ceiling (ability)
  computed from Module 2 data, combined as `final = min(stated, capacity)`
  — never the reverse. Every computation is logged as a `suggestion_event`
  (`module_source="risk_profile"`).
- **Module 4 — Asset Class Mapping & Allocation**: classifies each holding
  (Module 2) into cash/debt/equity/real assets/alternatives, with true
  look-through decomposition for hybrid funds and insurance-linked
  products — never the wrapper's own label — plus a category-level target
  allocation for the user's final tier (Module 3). Category level only,
  everywhere: no named fund/stock/scheme ever appears in this module's
  output, logs, or test data.
- **Module 6 — Debt and Leak Engine**: avalanche/snowball payoff
  comparison, a certain-return prepay-vs-invest framing, a credit-card
  effective-rate calculator, and refinance breakeven, against Module 2's
  actual EMIs — plus idle-cash flagging, a fee/drag audit, and recurring-
  charge detection over Module 2's manually-entered expenses (Module 2
  never got a statement parser, which genuinely reduces what the leak half
  can see — documented, not hidden). One combined headline "recoverable
  Rs/year" figure, logged as a `suggestion_event`
  (`module_source="debt_leak_engine"`).
- **Module 7 — Fast Feedback Loop**: a bounded personalization offset
  (equity percentage points, clamped to [-10,+10]) learned from how users
  actually respond to Module 4's allocation suggestions, via an
  evidence-weighted EWMA replayed from Module 1's event log — no new state
  table. Only ever adjusts the *displayed* allocation; never touches
  Module 3's risk tier, and Module 3's capacity ceiling is reapplied after
  the offset every time, so personalization can never display an equity %
  past what a user's own ability supports.
- **Module 8 — Drift Detection (Simulated)**: a behavioural drift
  detector for Module 3's risk tier, validated only against 5
  hand-authored synthetic personas — **simulated only; never run against
  real users, and never claimed to be** (see the module's own section
  below for exactly where that boundary is stated). Requires two
  independent signal families (a behavioural-edit read and a Module-3
  capacity-ceiling read) to agree before any candidate drift registers,
  with asymmetric hysteresis (slower to lower a tier than to raise one)
  and a freeze window after a simulated market drawdown — all reused
  directly from Module 3's and Module 7's own logic, not reimplemented.
- **Module 9 — Transparency Layer**: a rule-tracing view per decision type
  (risk tier, allocation, recoverable Rs/year, personalization offset),
  reconstructed strictly from what Modules 3/4/6/7 already store in
  `suggestion_event` — never recomputed. A stored event missing a field a
  decision type needs is flagged as a gap (`gap_detected`), not silently
  patched over. Labeled **"transparent reasoning"** everywhere, never
  "explainable AI" or "AI-powered" — these are weighted sums and rule-table
  lookups, and printing them *is* the feature. Module 5's genuinely
  multi-step retrieval-and-elimination trace gets its own, separately
  justified "explanation" framing — see `modules/rumour_verification/README.md`.
- **Module 10 — Gamification**: milestones tied only to financial
  behaviour (buffer months, debt cleared, subscriptions cancelled,
  surplus-consistency streaks) — never app engagement, never a leaderboard
  or cross-user comparison. Module 3's capacity ceiling rising is the one
  "real" progression mechanic, surfaced with the actual before/after
  equity numbers, not a cosmetic badge. Effort-only, enforced at import
  time: a milestone catalog entry declaring an outcome signal (market
  returns, portfolio value) makes the app fail to start, not just fail
  code review.

## Layout

```
app/
  models/
    suggestion_event.py, user_monthly_snapshot.py     Module 1
    onboarding.py                                      Module 2: UserProfile,
                                                         EmiEntry, InsurancePolicy,
                                                         Holding, ExpenseItem,
                                                         ExpenseSourceDecisionRecord
  schemas/           Pydantic read/write schemas for both modules
  services/
    event_log.py               Module 1: log_suggestion_event, record_suggestion_outcome,
                                log_monthly_snapshot, get_user_event_history,
                                get_user_snapshot_history
    financial_position.py      Module 2: pure net worth / surplus / buffer-months /
                                EMI-to-income calculations (no I/O)
    expense_source_decision.py Module 2: pure manual-vs-statement-parsing
                                decision timeline logic (no I/O)
    onboarding.py               Module 2: profile/EMI/insurance/holding/expense
                                capture, wired to financial_position.py and
                                event_log.log_monthly_snapshot
    risk_profile.py              Module 3: pure questionnaire scorer +
                                 capacity ceiling + final-tier composition
                                 (no I/O)
    risk_profile_config.py       Module 3: versioned questionnaire +
                                 capacity rule table (plain data)
    risk_profile_service.py      Module 3: gathers Module 2 data into
                                 CapacityInputs, calls the pure functions,
                                 logs the suggestion_event
    asset_classification_config.py  Module 4: versioned HoldingType taxonomy +
                                     look-through decomposition assumptions
    allocation_config.py            Module 4: versioned target allocation by tier
    asset_classification.py         Module 4: pure classify_holding +
                                     aggregate_classifications (no I/O)
    allocation.py                   Module 4: pure compute_target_allocation (no I/O)
    allocation_service.py           Module 4: gathers Module 2 holdings + Module 3's
                                     tier, calls the pure functions, logs the
                                     suggestion_event
    debt_leak_config.py              Module 6: versioned keyword lists +
                                     idle-cash reference rate + amortization cap
    debt_amortization.py             Module 6: shared amortization simulator (no I/O)
    debt_engine.py                   Module 6: pure avalanche/snowball, prepay-vs-invest,
                                     credit-card, refinance calculators (no I/O)
    leak_engine.py                   Module 6: pure idle-cash, fee-drag, recurring-charge
                                     detection + combined headline (no I/O)
    debt_leak_service.py             Module 6: gathers Module 2 EMIs/expenses,
                                     calls the pure functions, logs the suggestion_event
    personalization.py               Module 7: pure evidence-weighted EWMA +
                                     capacity-capped offset application (no I/O)
    personalization_service.py       Module 7: replays Module 1's event log into
                                     the EWMA, records outcomes, logs the
                                     suggestion_event
    drift_detection_config.py        Module 8: versioned hysteresis/freeze-window/
                                     signal-family thresholds (plain data)
    drift_personas.py                Module 8: 5 hand-authored synthetic personas
                                     + trace generation (SIMULATED ONLY)
    drift_detector.py                Module 8: pure two-signal-family drift
                                     detector with hysteresis + freeze window (no I/O)
    drift_evaluation.py              Module 8: evaluation harness -- reports
                                     "detector performance on simulated behaviour"
    transparency.py                  Module 9: rule-tracing view per decision
                                     type, reads suggestion_event only (no I/O
                                     beyond that, no recomputation)
    gamification_config.py           Module 10: versioned milestone catalog +
                                     thresholds; effort-only signal_type
                                     enforced at import time
    gamification.py                  Module 10: pure threshold-crossing /
                                     streak helpers (no I/O)
    gamification_service.py          Module 10: detects + logs newly earned
                                     milestones from Modules 2/3/6's own data
    rumour_verification_bridge.py    Module 1 <-> Module 5 bridge: adds
                                     modules/rumour_verification/src to
                                     sys.path, calls verify_rumour unchanged,
                                     logs the result for auditability
  api/
    routes_events.py            Module 1 read endpoints
    routes_onboarding.py        Module 2 endpoints (incl. close_emi, remove_expense_item)
    routes_risk_profile.py      Module 3 endpoints
    routes_allocation.py        Module 4 endpoints
    routes_debt_leak.py         Module 6 endpoints
    routes_personalization.py   Module 7 endpoints
                                 (Module 8 has no API routes -- it's a
                                 simulation/evaluation module, not a live feature)
    routes_transparency.py      Module 9 endpoints
    routes_gamification.py      Module 10 endpoints
    routes_rumour_verification.py   Module 5 bridge endpoint
  db.py, config.py        engine/session setup, DATABASE_URL
migrations/            Alembic migrations:
                        0001 suggestion_event, 0002 user_monthly_snapshot,
                        0003 onboarding tables, 0004 adds holding_type to holding,
                        0005 adds emi_entry.closed_at + expense_item.removed_at
                        (Modules 3, 6, 7, 8, and 9 add no tables)
scripts/
  demo_log_stub.py            Module 1 stub call: logs a fake event + snapshot, reads them back
  personalization_demo.py     Module 7: replays synthetic edits through the EWMA,
                               no database needed -- run with `python -m scripts.personalization_demo`
tests/                 pytest suite (290 tests)
```

## Running

```
pip install -r requirements.txt

# apply migrations (defaults to sqlite:///./dev.db; set DATABASE_URL for Postgres)
alembic upgrade head

# run the API
uvicorn app.main:app --reload

# run the Module 1 stub demo (logs + reads back a fake event and snapshot)
python -m scripts.demo_log_stub

# run tests
pytest
```

Tests run entirely against SQLite (in-memory for service/API-layer tests, a
temp file for the `test_migrations.py` tests that actually execute `alembic
upgrade head` / `downgrade base` and inspect the resulting schema) so the
suite needs no local Postgres server. `DATABASE_URL` (e.g.
`postgresql+psycopg://user:pass@host/db`) switches both the app and Alembic
to Postgres for real deployment; `psycopg[binary]` is already in
requirements.txt for that. In-memory SQLite engines use `StaticPool` (see
`app/db.py`) so every thread — including FastAPI TestClient's worker
threadpool — shares the same connection; without it, a multi-request API
test can silently hit a fresh empty database mid-flow.

---

## Module 1 — Data Model & Event Logging

### Schema

**suggestion_event** — one row per suggestion instance shown to a user, from
any module (`module_source`: `risk_profile`, `allocation`, `debt_engine`,
`leak_engine`, ...). `suggested_value`, `chosen_value`, and `delta` are JSON
because different modules suggest structurally different things (a rupee
amount, an asset-class split, a debt payoff order); `delta` is JSON rather
than a single number so a module can report a structured diff instead of
collapsing it to one figure. `action_taken` is a Postgres-native enum
(`accepted` / `edited` / `rejected` / `ignored`), null until the user acts.
`tier` and `offset` are module-defined (e.g. a risk tier, and the
suggestion's position within the set shown). `market_context` is a JSON
snapshot at event time so a later transparency view can explain "why this,
then."

**user_monthly_snapshot** — one row per user per calendar month (`month` is
always normalized to the 1st). Money fields (`income`, `surplus`, `cash`)
are integer paise. `debt_to_income_ratio` and `buffer_coverage_months` are
ratios, not money, and are stored as exact `NUMERIC` (Python `Decimal`)
rather than float so downstream caps and comparisons stay deterministic.
`(user_id, month)` is unique; re-logging the same month updates the
existing row (upsert) rather than duplicating it.

Both tables use string UUIDs (`String(36)`, not Postgres-native `UUID`) and
a generic `JSON` column type — a deliberate portability tradeoff so the
exact same models/migrations run against SQLite in tests and Postgres in
production, with no dialect-specific branching in application code.

### Read endpoints

- `GET /users/{user_id}/events?module_source=&since=&until=&limit=&offset=`
- `GET /users/{user_id}/snapshots?since_month=&until_month=&limit=`

The write path (`log_suggestion_event`, `record_suggestion_outcome`,
`log_monthly_snapshot`) is exposed as plain Python functions for other
backend modules to call directly, not as HTTP endpoints — those modules run
in the same backend process/codebase per the project's stack. Module 2's
`onboarding.py` is the first real caller.

---

## Module 2 — Onboarding & Financial Position

### Profile capture

`PUT /users/{user_id}/profile` — income (paise), `income_stability`
(`regular`/`irregular` — an explicit field the future capacity/ability
layer needs, not inferred from anything else), `employment_type`
(`salaried`/`self_employed`/`business_owner`/`freelancer`/`unemployed`/
`other`), dependents count, and current cash balance (paise).

`POST /users/{user_id}/emis` — one row per loan: lender, the **monthly EMI
payment** (paise), remaining tenure (months), and the annual rate (basis
points). There's no separate "outstanding principal" field — onboarding
captures the payment schedule, and the current liability is *derived* from
it (see below). `POST /users/{user_id}/emis/{emi_id}/close` marks one as
fully paid off (`closed_at` set, excluded from financial-position
calculations from then on, but the row stays so Module 10 can still see
it existed) — added for Module 10's "debt cleared" milestone, which was
otherwise structurally undetectable: Module 2's EMI/expense CRUD was
add-only until this.

`POST /users/{user_id}/insurance-policies` — policy type (`life`/`health`)
and sum assured (paise). Doesn't feed net worth/surplus/buffer/EMI-ratio,
so adding one does **not** trigger a snapshot write (see "material edit"
below) — it's captured for later modules, not this one's computed outputs.

`POST /users/{user_id}/holdings` — freeform `description` + `value_paise`,
plus an optional `holding_type` (Module 4's classification category — see
below; nullable here because Module 2 predates that taxonomy, but Module 4
requires it before a holding can be classified). Emergency-fund coverage
above uses only the explicit cash balance, not holdings, regardless of
`holding_type` — a classified holding still isn't necessarily liquid.

### Expense entry and the manual-vs-parsing decision

`POST /users/{user_id}/expenses` — category, amount (paise), `frequency`
(`monthly`/`annual`/`one_time`), and `is_essential`. This module builds
**manual entry only** — no statement parser. Per the project brief, that
omission has to be an explicit, dated decision, not a silent gap, because
it determines whether leak detection and idle-cash flagging (later
modules) are buildable at all. `app/services/expense_source_decision.py`
implements this as a pure, timeline-based function:
`resolve_expense_source_mode` — an explicit decision (recorded via `PUT
/users/{user_id}/expense-source-decision`) always wins; otherwise, once 14
days have passed since onboarding started with no decision made, the mode
auto-resolves to `manual_only`; before that, it's `manual_only` in
practice but reported as not-yet-explicit, so a caller can tell "we chose
this" apart from "nobody's decided yet." `GET
/users/{user_id}/expense-source-decision` reads the resolved state.
`POST /users/{user_id}/expenses/{item_id}/remove` marks a recurring item
cancelled (`removed_at` set, excluded going forward, row kept for
history) — the same Module 10 motivation as `close_emi` above.

### Computed outputs (`app/services/financial_position.py`, pure)

- **Net worth** = cash + holdings − Σ(outstanding EMI principal). Outstanding
  principal per loan is the present value of its remaining payments at its
  own rate (standard annuity-PV formula), since onboarding only captures
  the payment schedule, not a tracked balance.
- **Monthly surplus** = income − total monthly expenses − total monthly EMI.
  Annual expenses are normalized to a monthly run-rate; one-time expenses
  are excluded from the run-rate (they're real spends but not recurring).
- **Emergency-fund coverage (months)** = cash ÷ average monthly *essential*
  expense (discretionary spending excluded).
- **EMI-to-income ratio** = total monthly EMI ÷ income.

`user_monthly_snapshot.debt_to_income_ratio` and `.buffer_coverage_months`
are `NUMERIC` and `NOT NULL`, so the zero-denominator edge cases (no
essential expenses recorded yet; zero income) resolve to a capped sentinel
(`MAX_BUFFER_MONTHS` = 9999.99, `MAX_EMI_TO_INCOME_RATIO` = 9.9999) rather
than `None` — documented in the docstrings, and for the EMI ratio this
isn't just a technical workaround: zero income with existing EMI debt is a
genuinely extreme, ability-capping case, and the cap conveys "severe"
rather than crashing or reporting zero burden.

All four are hand-checked against an independently-computed reference
scenario in `tests/test_financial_position.py` and
`tests/test_onboarding_service.py` (same numbers, checked twice — once as
pure functions, once through the full onboarding flow).

### Snapshot writes

`upsert_profile`, `add_emi`, `add_expense_item`, and `add_holding` are
"material edits" — each recomputes the financial position and calls
Module 1's `log_monthly_snapshot` immediately afterward, upserting the
current month's row. `POST /users/{user_id}/complete-onboarding` marks
`onboarding_completed_at` and does the same. `add_insurance_policy` and
`record_expense_source_decision` don't, since neither feeds any of the
four computed metrics.

### Read

`GET /users/{user_id}/financial-position` returns all four computed
metrics directly (not just what's on the latest snapshot row), always
re-derived from the current `user_profile`/`emi_entry`/`expense_item`/
`holding` rows — which is how these figures stay traceable to their inputs
without a separate reasoning-inputs blob on the snapshot table itself.

---

## Module 3 — Risk Profiling

Enforces "ability before willingness" as a literal formula, not a design
note: `final_tier = min(stated_tier, capacity_ceiling)`. Stated tier
reflects what the user says they want; capacity ceiling reflects what
their finances can objectively absorb, computed independently and only
from Module 2 data. Capacity can never raise the tier above what was
stated, and willingness can never override a lower capacity ceiling.

### Stated tier (willingness) — `app/services/risk_profile.py::compute_stated_tier`

A 4-question weighted-sum questionnaire (`risk_profile_config.py::QUESTIONNAIRE_V1`,
version `v1`): investment horizon, reaction to a 20% drawdown, market
experience, and primary goal, weighted 3/3/2/2 (total weight 10, score
range 10-50). Four breakpoints (18/26/34/42) split that range into 5 equal
tiers. Pure function, no model call — this is a fixed weighted sum, not an
LLM judgment call.

### Capacity ceiling (ability) — `compute_capacity_ceiling`

Four independently-scored dimensions, each an explicit banded rule table
in `risk_profile_config.py::CAPACITY_RULE_TABLE_V1` (version `v1`) — not
inline thresholds buried in logic:

| Dimension | Ceiling 1 | Ceiling 5 (no ceiling) |
|---|---|---|
| Emergency buffer (months) | < 1 | >= 6 |
| EMI-to-income ratio | >= 50% | < 20% |
| Income stability | irregular -> ceiling 3 (flat; the underlying data is binary, not banded) | regular -> ceiling 5 |
| Insurance adequacy (life cover / (12 x monthly income x 10), only when dependents > 0) | < 25% of required cover | >= 100% of required cover |

The overall capacity ceiling is the **minimum across applicable
components** (insurance is skipped entirely when `dependents_count == 0`).
These bands are the product's own conservative policy, not a regulatory
limit — documented as such in the rule table's docstring so nobody mistakes
them for an RBI/SEBI requirement.

### Output: both tiers, the exact binding constraint(s), and a computed unlock

`compute_final_tier` returns `stated_tier`, `capacity_ceiling`, `final_tier`,
`capped`, `binding_constraints` (only the component(s) whose ceiling
*equals* the overall minimum — not everything that's merely imperfect),
and one `UnlockCondition` per binding constraint with a message computed
from the user's real numbers, e.g. *"Bring your EMI-to-income ratio below
20% - reduce your monthly EMI outflow by Rs 25,000."* Rupee figures use
Indian digit grouping (`Rs 1,20,00,000`, not `Rs 12,000,000`) via a small
formatter in `risk_profile.py`, tested on its own in
`tests/test_risk_profile_formatting.py`.

### The core scenario — explicitly tested

`tests/test_risk_profile_final_tier.py` and
`tests/test_risk_profile_service.py` both carry the product's core case
end-to-end: a user answers the questionnaire "aggressive" (stated tier 5)
but has a 2-month buffer and a 45%-of-income EMI. The tests assert: the
tier is capped to 2; the binding constraint is *exactly*
`emi_to_income_ratio` and *not* `buffer_months` (buffer's own ceiling, 3,
isn't the tightest constraint here — naming it would overstate the cap);
and the unlock message names the precise rupee reduction needed. The
service-layer version of this test builds the scenario through the real
Module 2 onboarding flow (profile + expense + EMI), not hand-constructed
inputs, and also asserts the logged event.

### Logging

Every call to `compute_and_log_risk_tier` logs one `suggestion_event`
(`module_source="risk_profile"`, `tier` = the final tier) via Module 1's
`log_suggestion_event`, with the full breakdown (answers, both tiers,
component ceilings, binding constraints, unlock conditions) in
`suggested_value`, and the raw objective inputs (buffer months, EMI ratio,
income stability, dependents, life cover) in `market_context` — reused
here as a general "objective inputs at computation time" snapshot rather
than literal market data, per Module 1's stated purpose for that field.
Module 3 adds **no new tables**: `GET /users/{user_id}/risk-profile/latest`
reads the most recent computation straight back out of `suggestion_event`
via Module 1's existing `get_user_event_history`, which is exactly the
read path that table was built for.

### Endpoints

- `POST /users/{user_id}/risk-profile` `{"answers": {...}}` — computes,
  logs, and returns the full tiering result.
- `GET /users/{user_id}/risk-profile/latest` — the most recent computation.
- `GET /risk-profile/questionnaire` — not user-scoped (static config, not
  per-user data): the 4 questions and their options, for a client to
  render without hardcoding a duplicate copy of `QUESTIONNAIRE_V1`.
  Deliberately omits each option's point value, so a caller can never
  reconstruct the scoring formula — only `POST /risk-profile` computes a
  score, from the full weighted sum.

---

## Module 4 — Asset Class Mapping & Allocation

Classifies every Module 2 holding into one of five asset classes (cash,
debt, equity, real assets, alternatives) with genuine look-through for
hybrid funds and insurance-linked products, then looks up a category-level
target allocation for the user's Module 3 tier. **Hard constraint,
enforced mechanically, not just by convention: nothing in this module ever
receives, computes with, or logs a named fund, stock, or scheme — only
`HoldingType` category values, `holding_id`s, and computed numbers.** A
holding's freeform `description` (Module 2) never crosses into this
module's outputs; `tests/test_allocation_service.py` and
`tests/test_api_allocation.py` both mechanically scan the logged/returned
JSON for the exact description strings entered in their test fixtures to
confirm this rather than just asserting a specific field is absent.

### Classification taxonomy (`app/services/asset_classification_config.py`, version `v1`)

24 `HoldingType` categories (a controlled vocabulary — this is what the
user picks when entering a holding, e.g. "PPF", "ELSS", "ULIP", never a
scheme name), each mapped to:

- **Decomposition**: fractions across the five asset classes, summing to 1.
  Simple types are 100% one class (e.g. `direct_equity` -> 100% equity,
  `ppf` -> 100% debt). Hybrid mutual fund sub-types use SEBI's own
  scheme-categorization equity bands at their midpoint (Aggressive Hybrid
  65-80% equity -> 70/30; Balanced Hybrid 40-60% -> 50/50; Conservative
  Hybrid 10-25% -> 15/85). `ulip`, `endowment_or_moneyback_policy`, and
  `nps` use illustrative default splits, documented in the config's own
  docstring as assumptions (a ULIP's real split depends on the internal
  fund option the policyholder chose, which a category label can't
  reveal) rather than facts about any specific product — exactly the
  detail the project brief calls out as usually hand-waved.
- **Liquidity**: `liquid` (redeemable near-instantly, no cost) /
  `semi_liquid` (redeemable, but with delay/exit load/practical friction —
  e.g. a bank FD's premature-withdrawal penalty) / `locked_in`
  (contractually or statutorily unavailable before a term — e.g. ELSS's
  3-year lock-in, a ULIP's IRDAI-mandated 5-year lock-in, PPF's 15-year
  statutory term).
- **`lock_in_months`**: set for fixed-term locked-in types (ELSS 36, PPF
  180, ULIP 60, SGB 96); left `None` where the real constraint is
  event-based rather than a fixed duration (EPF releases on job
  change/retirement, not a clock).
- **Tax treatment category**: a qualitative label only — e.g.
  `eee_exempt`, `equity_ltcg_stcg_stt_paid`, `debt_mf_slab_rate_all_gains`
  — deliberately with no numeric rate attached. Rates change with each
  Finance Act and belong in a dedicated versioned tax-slab config (per the
  project's own convention), not smuggled into an asset-classification
  table. One genuinely load-bearing nuance this does encode: a hybrid fund
  with >=65% equity (Aggressive Hybrid) gets equity tax treatment, while
  one under 65% (Balanced/Conservative Hybrid) gets debt-fund tax
  treatment regardless of still holding meaningful equity — both are
  asserted directly in `tests/test_asset_classification.py`.

### Look-through vs. wrapper-level (`app/services/asset_classification.py`, pure)

Asset-class exposure **is** decomposed (look-through): a ULIP's equity
slice counts as equity in the aggregate. Liquidity and tax treatment are
**not** decomposed — both are properties of the whole instrument (you
can't partially withdraw just the equity portion of a locked ULIP), so
they're summed at the holding level. This distinction is deliberate and
documented in the module docstring, not an oversight.

`classify_holding` splits a holding's paise value across its decomposition
fractions with residual-conserving rounding (each share rounds to the
nearest paise; any leftover from rounding goes to the largest share, so
the parts always sum back to the whole exactly). `aggregate_classifications`
sums exposure across a portfolio and also computes:

- **Concentration**: the largest single holding as a % of total portfolio
  value, and an asset-class Herfindahl-Hirschman Index (0-10000; the
  standard sum-of-squared-shares concentration score).
- **Liquidity breakdown**: portfolio value grouped by `liquid`/
  `semi_liquid`/`locked_in`, wrapper-level.
- **Tax treatment breakdown**: portfolio value grouped by tax category,
  wrapper-level.

### Definition-of-done scenario, hand-checked

`tests/test_asset_classification.py::test_aggregate_look_through_exposure_is_not_the_label_exposure`
builds a portfolio of an equity fund, a savings account, a ULIP, and an
endowment policy, and asserts the aggregate equity exposure (Rs 2,15,000)
is *not* what you'd get from summing only holdings labeled "equity"
(Rs 1,00,000) — it's Rs 1,15,000 more, hidden inside the ULIP and
endowment wrappers, and the test asserts that gap explicitly rather than
just checking the final number in isolation.
`tests/test_allocation_service.py` repeats the same numbers through the
real Module 2 holdings + Module 4 service path.

### Target allocation (`app/services/allocation.py` + `allocation_config.py`, version `v1`)

A simple, auditable lookup from Module 3's final tier (1-5) to a
percentage split across the five classes — equity rises from 10% at tier 1
to 65% at tier 5, cash falls from 40% to 5%, alternatives stay at or near
0% until tier 3+ given their illiquidity. The "reasoning trace" the brief
asks for is exactly what this lookup is: `TargetAllocationResult` carries
`final_tier`, `rule_table_version`, and a `reasoning` string naming both —
there's no hidden formula to explain because there isn't one, just an
explicit table.

### Logging

`compute_and_log_allocation` reads the holdings straight from Module 2,
the latest final tier straight from Module 3's `suggestion_event` log
(`get_user_event_history(module_source="risk_profile", limit=1)` — no new
table needed to hold "current tier" state, same reasoning as Module 3
reusing Module 1's read path), computes everything, and logs one
`suggestion_event` (`module_source="allocation"`) with the full breakdown
(target %, current exposure %, concentration, liquidity/tax breakdowns,
per-holding classifications) in `suggested_value`, and the classification/
allocation config versions used in `market_context`.

### Endpoints

- `GET /users/{user_id}/allocation` — computes, logs, and returns the full
  report. `422` if any holding is missing `holding_type`; `409` if Module
  3's tier hasn't been computed yet.

---

## Module 6 — Debt and Leak Engine

### Scope reduction, stated up front

Module 2 settled on manual-entry-only expenses — no statement parser
exists, and building one needs its own fresh decision (see the
expense-source decision above). That is a real, documented reduction in
what the leak half of this module can do, not a silently dropped
deliverable: `ExpenseItem` rows have a `category` label and a declared
`frequency`, never a merchant name or a transaction date. "Recurring-charge
detection via merchant-name clustering and periodicity analysis" therefore
becomes: periodicity is read directly off the field the user already
filled in (there's nothing left to infer), and `category` text stands in
for a merchant name for near-duplicate clustering and keyword matching —
a real but reduced substitute for clustering actual dated transactions.
Every leak report carries this as an explicit `data_source_note` field, and
every response also reports Module 2's *resolved* expense-source mode
(`manual_only` today, `is_explicit_decision` telling you whether that's a
deliberate choice or just the 14-day default), so the limitation travels
with the output rather than living only in this README.

### Debt calculators (`app/services/debt_engine.py` + `debt_amortization.py`, pure)

All four build on one shared amortization simulator (interest accrues
monthly on the declared rate; each payment covers interest first, the rest
reduces principal — the same math as Module 2's closed-form annuity PV,
just run forward month-by-month instead of solved in closed form, because
avalanche/snowball need a payment that *changes* once a debt clears).

- **Avalanche vs. snowball**: simulates both strategies against the user's
  actual EMI list, with the standard "waterfall" behavior — once a debt
  clears, its own EMI gets redirected as extra payment toward the current
  target. Avalanche targets highest-rate-first, snowball targets
  smallest-balance-first, both using a fixed initial ordering (the
  standard definition of each method — not re-sorted as balances change).
  Reports months-to-clear and total interest under each, and the
  rupees/months avalanche saves over snowball. The "extra monthly payment"
  used is Module 2's own current monthly surplus (only run at all when
  there's at least one EMI and positive surplus) — no additional input
  needed beyond what's already on file.
- **Prepay vs. invest**: compares the debt's own interest rate, framed
  explicitly as a *certain*, risk-free return — every rupee that prepays
  principal definitively stops accruing that rate, no market risk, no
  timing dependence — against investing the same amount, without ever
  asserting what an investment would return. `PrepayVsInvestResult.framing_note`
  states this in writing: the app doesn't project investment returns
  because it can't promise what markets will do, only the debt's own rate
  is certain. Run automatically for the user's highest-rate EMI, using
  Module 2's surplus as the extra amount.
- **Credit-card revolving-cost calculator**: converts a monthly rate into
  both a naive nominal annual rate and the true, compounded effective
  annual rate (`(1+monthly_rate)^12 - 1`) — the gap between the two is the
  real insight (a card advertising a monthly rate is quietly charging
  meaningfully more than the naive annualization suggests). Also simulates
  payoff under a percentage-of-balance-or-floor minimum-payment rule,
  demonstrating the classic minimum-payment trap (a Rs 50,000 balance at
  3.5%/month, minimum 5% of balance, takes 294 months — over 24 years — to
  clear at minimums only). Standalone: Module 2 doesn't model revolving
  credit-card balances as EMIs, so this takes explicit balance/rate/
  minimum-payment inputs rather than reading from stored data.
- **Refinance breakeven**: given a new rate and fees for one of the user's
  existing EMIs (looked up by id, so the current outstanding principal and
  remaining tenure come from Module 2/the same annuity-PV derivation as
  everywhere else), computes the new EMI at the new rate over the same
  remaining tenure, and the month the monthly savings recover the fees.
  Needs a hypothetical new rate this module has no way to originate on its
  own, so — like the credit-card calculator — it's a separate, input-driven
  endpoint, not part of the automatic report.

### Leak detection (`app/services/leak_engine.py`, pure)

- **Idle-cash flagging**: idle cash = declared cash balance minus the
  buffer Module 3's own capacity rule table treats as fully adequate (the
  lower bound of its uncapped top band — 6 months — reused directly rather
  than introducing a second, potentially-drifting threshold). Opportunity
  cost is that idle amount times a documented, versioned reference rate
  (`debt_leak_config.py::IDLE_CASH_REFERENCE_RATE_ANNUAL_BPS`, 6.50% p.a.,
  explicitly labeled illustrative and not tied to any product — not a
  literal inline number in the calculation, and reviewable/bumpable as its
  own config version).
- **Fee/drag audit**: recurring `ExpenseItem`s whose category text matches
  a versioned keyword list (bank charges, AMC, demat, ATM fees, forex
  markup, and similar) are summed as annualized fee drag. Deliberately
  does not attempt to estimate embedded mutual-fund expense-ratio drag —
  Module 4's holdings don't capture a TER field, so that drag is invisible
  here; a known gap, stated rather than papered over with a guessed number.
- **Recurring-charge detection**: two signals over declared recurring
  items — a versioned subscription-keyword list, applied only to items the
  user themselves marked non-essential (their own judgment isn't
  second-guessed), and near-duplicate category-text clustering
  (`difflib` similarity ratio) across *all* recurring items regardless of
  essential flag, since accidental duplicate/overlapping entries are a
  data-consolidation signal, not a necessity judgment.

### The headline

One `total_recoverable_annual_paise` figure, summing itemized
`RecoverableComponent`s (idle cash as one line, one line per matched fee,
one line per flagged recurring charge) — each with its own `explanation`
and `concrete_action`. Deliberately **leak-side only**: avalanche/snowball
and prepay-vs-invest savings are a one-time/multi-year total over a debt's
payoff horizon, not a perpetual per-year amount, so folding them into an
annual headline would misrepresent them; refinance and the credit-card
calculator need extra input this module doesn't have automatically. All of
these are still reported, just not force-summed into the "recoverable
Rs/year" number.

### Logging

One `suggestion_event` per computation (`module_source="debt_leak_engine"`)
via `compute_and_log_debt_leak_report`, with the full headline breakdown,
leak components, and avalanche/snowball + prepay-vs-invest results in
`suggested_value`, and the resolved expense-source mode plus counts of
debts/expenses considered in `market_context`. The on-demand credit-card
and refinance calculators don't log their own events (they're general
tools, not tied to a specific stored computation).

### Endpoints

- `GET /users/{user_id}/debt-leak` — computes, logs, and returns the full
  report (headline, leak components, avalanche/snowball, prepay-vs-invest).
- `POST /users/{user_id}/debt-leak/credit-card-revolving-cost` — standalone
  calculator.
- `POST /users/{user_id}/debt-leak/refinance-breakeven` — `{"emi_id",
  "new_annual_rate_bps", "fees_paise"}`, `404` if the EMI isn't the user's.

---

## Module 7 — Fast Feedback Loop

A lightweight personalization layer: it learns, from how a user actually
responds to Module 4's allocation suggestions, a small bounded nudge to
how much equity gets *displayed* — never a change to the risk tier itself,
and never past what Module 3's capacity ceiling allows.

### No new state table

Like Modules 3/4/6, the offset isn't stored anywhere of its own — it's
replayed fresh from Module 1's `suggestion_event` log every time it's
needed. Concretely: `record_allocation_outcome` attaches a user's reaction
(accept/edit/reject/ignore, plus whether they actually funded it) to one
of their own Module 4 `module_source="allocation"` events, using Module
1's existing `record_suggestion_outcome`; `compute_and_log_personalization`
reads every allocation event with a recorded outcome
(`get_user_event_history(module_source="allocation")`), sorts them
chronologically (the log itself returns most-recent-first), and replays
them through the EWMA. This means the offset is always exactly
reproducible from the log and can never drift out of sync with it.

### Evidence-weighted EWMA (`app/services/personalization.py`, pure)

`offset_new = (1 - alpha*weight)*offset_old + (alpha*weight)*delta`, where
`delta` is the user's chosen equity % minus what was suggested, and
`weight` is evidence strength:

| Case | Weight |
|---|---|
| Funded edit (named in the brief) | 1.0 |
| Unfunded acceptance (named in the brief) | 0.5 |
| Rejection ("confusion", named in the brief) | 0.0 |
| Ignored | 0.0 (extrapolated: no direction, no confirmation) |
| Funded acceptance | 1.0 (extrapolated: full follow-through on the suggestion as given) |
| Unfunded edit / `funded=None` | 0.5 (extrapolated: same conservative discount as unfunded acceptance) |

The three named cases come straight from the module brief; the rest are
extrapolated from two factors those named cases already turn on —
whether the action carries a directional preference at all (accept/edit
do, reject/ignore don't), and whether it was actually followed through on
(`funded`). This is stated explicitly in `evidence_weight`'s docstring
rather than left for a reader to reverse-engineer.

When `weight=0`, the update is an *exact* no-op — `offset_new == offset_old`
bit for bit, not a hidden decay toward zero. This is checked directly in
`test_rejection_is_an_exact_no_op` and matters: "counts zero" should mean
zero influence, not a disguised pull toward "no personalization needed."

**Default alpha = 0.3**, configurable per call. With weight=1 (a funded
edit), the fraction of the *old* estimate remaining after `n` consecutive
full-weight observations is `(1-0.3)^n`: 70% after one edit, ~34% after
three, ~8% after seven. A single edit only nudges the offset 30% of the
way toward that one data point — real resistance to a one-off or mistaken
edit — while a consistent pattern across 5-7 interactions comes to
dominate the estimate. Fast enough to feel like a "fast feedback loop"
within a first week of real use, without overreacting to any single event.

### Applying the offset (`apply_personalization_offset`)

`displayed_equity = clamp(base_equity + offset, 0, capacity_ceiling_equity, 100)`,
where `base_equity` is Module 4's target for the user's *final* tier and
`capacity_ceiling_equity` is Module 4's target for the *capacity ceiling*
tier (ability, not the possibly-lower final tier) — reusing Module 4's own
tier→allocation table rather than inventing a second cap. The other four
classes absorb whatever the equity change is, rescaled proportionally to
their own current weights, so the result always sums to exactly 100.00.

One real bug caught and fixed during testing: the rounding-residual
correction (needed because splitting percentages into 2-decimal pieces
can leave a cent of drift) was initially allowed to land on the equity
slot itself — which could silently push displayed equity a cent past the
capacity cap this function exists to enforce. Fixed to only ever adjust
the residual among the other four classes; `test_offset_still_bounded_by_own_clamp_even_when_capacity_is_generous`
in `tests/test_personalization.py` pins this down.

### Logging

One `suggestion_event` per computation (`module_source="personalization"`),
carrying the offset, alpha, edit count, base vs. displayed allocation, and
the full step-by-step trace (`market_context["trace"]`) — everything
needed for a later transparency view to show exactly how the offset was
arrived at, not just its final value.

### Demo (no external dependency)

```
python -m scripts.personalization_demo
```

Replays a synthetic six-edit sequence (funded edits trending toward more
equity, one rejection, one unfunded acceptance) entirely in memory — no
database, no other module's live computation — printing the offset
converging step by step, then applies it to a sample Module 4 allocation
twice: once with a capacity ceiling tight enough to actually cap the
result (demonstrating the reapplication requirement concretely, not just
in the abstract), and once with a generous ceiling where the same offset
applies in full.

### Endpoints

- `POST /users/{user_id}/allocation/{event_id}/outcome` —
  `{"action_taken", "chosen_target_pct", "funded"}`, records a reaction to
  one of the user's own Module 4 allocation events. `404` if the event
  doesn't belong to that user or isn't an allocation event.
- `GET /users/{user_id}/personalization` — computes, logs, and returns the
  offset and the resulting displayed allocation. `409` if Module 3's tier
  or Module 4's allocation hasn't been computed yet.

---

## Module 8 — Drift Detection (Simulated)

A behavioural drift detector for Module 3's risk tier: does the evidence
say a user's tier should move, and if so, when is that evidence strong
enough to actually act on?

### Simulated only — stated once here, enforced everywhere else

**This module has never been evaluated against real user behaviour.**
Every persona, every trace, every number in `drift_personas.py` is
hand-authored to express a specific, known behavioural story — none of it
is sampled from, derived from, or validated against real users. That
constraint is repeated in the module docstrings
(`drift_detection_config.py`, `drift_detector.py`, `drift_evaluation.py`),
in the evaluation report's own output ("detector performance on simulated
behaviour"), and here — not because any one of those places is
authoritative, but so no future edit to any single file can make this
module *read* as validated by only changing the others. See "Future work:
real-user validation" at the end of this section for the only place that
gap belongs as a stated intention.

### Five personas (`drift_personas.py`)

| Persona | Start → end tier | What it tests |
|---|---|---|
| Steady Conservative | 1 → 1 | Negative control: genuinely stable capacity + behavior produces no false drift. |
| Windfall Riser | 2 → 4 | Upward drift where capacity (a raise, debt payoff) reaches tier-5 territory but revealed behavior plateaus at tier 4 — the detector stops at what both families actually support, not what capacity alone would allow. |
| Debt Spiral Faller | 4 → 2 | Downward drift over 15 months, exercising the slower (asymmetric) hysteresis for lowering a tier. |
| Confused Middle | 3 → 3 | Negative control: capacity holds flat while behavior swings erratically (rejections, ignored suggestions, alternating extremes) — noisy single-family signal, structurally blocked from ever registering as agreement since capacity never deviates. |
| Market Panic Then Recovery | 4 → 4 | Freeze-window control: a simulated drawdown triggers 3 months of panicked, two-family-agreeing evidence — without the freeze this commits a spurious downward re-tier that reverses again once behavior recovers; the freeze suppresses it entirely. |

### Two independent signal families (`drift_detector.py`, pure)

Reused directly from Modules 3 and 7 rather than reimplemented:

- **Capacity signal**: Module 3's own `compute_capacity_ceiling`, applied
  to a trailing 3-month average of simulated `buffer_coverage_months` and
  `debt_to_income_ratio` (the same two fields Module 1's
  `user_monthly_snapshot` tracks).
- **Behavioral signal**: an evidence-weighted average of chosen equity %
  over a trailing 3-month window of allocation-suggestion outcomes, using
  Module 7's own `evidence_weight` (funded edit=1.0, unfunded
  acceptance=0.5, rejection/ignored=0.0) — a deviation only counts once
  it's at least `BEHAVIORAL_SIGNAL_DEADBAND_PCT` (3 points) from what the
  current reference tier's own target would suggest.

A review cycle only produces candidate drift evidence when **both**
families deviate from the current reference tier in the same direction
(`MIN_AGREEING_SIGNAL_FAMILIES = 2`, enforced literally — with exactly two
families defined, "agreeing" means both, not just the louder one).

### Safeguards (`drift_detection_config.py`)

All four requested safeguards are implemented, not just documented as
aspirational:

- **Asymmetric thresholds**: `HYSTERESIS_CYCLES_TO_RAISE_TIER = 2`,
  `HYSTERESIS_CYCLES_TO_LOWER_TIER = 3` — raising a tier commits faster
  than lowering one. This tradeoff (slower to take capacity away,
  protecting against a transient rough patch being misread as permanent
  deterioration, at the cost of being slower to reflect genuine decline)
  is stated as a deliberate design choice, not proven optimal against any
  real outcome.
- **Freeze window**: `DRAWDOWN_FREEZE_WINDOW_CYCLES = 2` review cycles
  immediately after a simulated drawdown are skipped entirely — not
  reset, skipped: no signal is even computed, and any streak already
  built before the freeze carries over unchanged once it ends. Proven
  load-bearing, not just present: `test_freeze_window_is_load_bearing_for_the_panic_persona`
  in `tests/test_drift_evaluation.py` runs the Market Panic persona's
  exact trace with and without the freeze flag and confirms the freeze
  version commits nothing while the unfrozen version commits a spurious
  downward-then-upward round trip.
- **≥2 agreeing signal families**: as above — a single family, however
  consistent, never accumulates hysteresis on its own
  (`test_capacity_alone_deviating_never_drifts_without_behavioral_agreement`
  and its behavioral-only counterpart in `tests/test_drift_detector.py`).
- **Hysteresis across consecutive cycles**: a streak only survives if the
  *same-direction* agreement repeats in consecutive non-frozen cycles; a
  cycle that disagrees (or drops to no-agreement) resets it. Because both
  signals are read over trailing windows, a single interrupting month gets
  smoothed rather than instantly flipping the streak — the detector
  reacts to *sustained* reversals, not single-month noise
  (`test_sustained_reversal_eventually_resets_and_flips_the_streak_direction`).
  A committed change moves exactly one tier and resets the streak to keep
  monitoring, so a multi-tier drift (as in Debt Spiral Faller) shows up as
  a sequence of discrete commits, never one large jump.

### Evaluation

```
python -m app.services.drift_evaluation
```

Runs all 5 personas and reports whether the detector's final tier matches
each persona's scripted ground-truth end tier, explicitly headed
"detector performance on simulated behaviour" and closing with a "Future
work: real-user validation" note — both are in the report's own output,
not just this README, so the disclaimer travels with the result wherever
it's read. Current result: 5/5 recovered.

### Future work: real-user validation

This detector, its thresholds, and this evaluation have been checked only
against the hand-authored synthetic personas above. Whether the same
safeguards — hysteresis depth, freeze window length, the two-signal-family
requirement — hold up against real, noisy user behaviour is unvalidated.
Real-user validation is the natural next step before this module could
inform an actual re-tiering decision, and is explicitly out of scope here.

---

## Module 9 — Transparency Layer

A rule-tracing view over what Modules 3, 4, 6, and 7 have already
computed and stored — never a second computation of its own.

### The rule, and how it's enforced, not just stated

"Do not recompute or fabricate a trace after the fact" is the module's
central constraint. `transparency.py` obeys it structurally:
`build_trace` only ever reads `event.suggested_value` and
`event.market_context` off a stored `SuggestionEvent` — it has no access
to (and never calls) any of Modules 3/4/6/7's actual computation
functions. Each decision type declares the exact stored keys it needs
(`DecisionTypeSpec.required_suggested_value_keys` /
`required_market_context_keys`); if a stored event is missing any of
them, the response sets `gap_detected=True` and lists `missing_fields`
instead of silently omitting them or (worse) calling back into the
originating module to fill them in fresh — which would mean the "trace"
no longer describes what actually drove the stored decision, only what a
*new* computation would produce.
`tests/test_transparency.py::test_incomplete_stored_event_is_flagged_as_a_gap_not_fabricated`
proves this by feeding `build_trace` a deliberately incomplete
`risk_profile`-shaped event and confirming it's flagged, not patched over.
As it happens, Modules 3/4/6/7 all currently store complete traces (by
design — see each module's own `suggested_value`/`market_context`
construction), so there is no live gap to report today; the mechanism
exists so a future module that under-stores its reasoning gets caught
here rather than silently producing a fabricated-looking trace.

### Four decision types (`DECISION_TYPES` in `transparency.py`)

| `module_source` | What it traces | Reused from |
|---|---|---|
| `risk_profile` | Questionnaire weights + answers, capacity component ceilings, binding constraint(s), unlock condition(s) | Module 3's `suggested_value`/`market_context` |
| `allocation` | Which tier, which rule-table version, the lookup's own `reasoning` string, per-holding classification | Module 4's `suggested_value`/`market_context` |
| `debt_leak_engine` | Every itemized recoverable-Rs component with its own explanation/action, the manual-entry-only scope note | Module 6's `suggested_value` |
| `personalization` | The full step-by-step EWMA trace (weight, delta, offset before/after per edit) | Module 7's `market_context.trace` |

Each has a `headline` (a one-line human summary) and a structured
`reasoning` dict, both built by pure functions over the stored JSON — no
new numbers are computed, only formatted.

### "Transparent reasoning," not "explainable AI"

Every one of these four decision types is either a weighted sum (Module
3's questionnaire) or a table lookup (everything else). `FRAMING_LABEL =
"transparent reasoning"` is attached to every response, and
`test_all_decision_types_use_the_transparent_reasoning_label_never_ai`
checks the label itself and that neither "ai" nor "explainable" appears
in it. This mirrors Module 1's original convention that scoring/cap logic
stays pure, deterministic, and free of model calls — there's no model
here to be "AI" about, and printing the weights already *is* the
transparency feature.

### Module 5 is out of scope for this file, on purpose

Module 5 (rumour verification) lives in `modules/rumour_verification/`
with no *build-time* dependency on this backend, and produces its own
trace at verification time rather than through `suggestion_event`. Its
transparency view is built there instead
(`modules/rumour_verification/src/transparency.py`), reusing
`VerificationResult.all_candidates` directly. That file is also where
"explanation"/"explainable" language is used deliberately and
differently from here — see its own module docstring for exactly why a
multi-stage retrieval-and-elimination pipeline earns that word while a
weighted sum doesn't.

This backend does, separately, expose Module 5 over HTTP for
auditability — `POST /users/{user_id}/rumour-verification`, described
below. That endpoint is glue, not a merge: `rumour_verification_bridge.py`
adds `modules/rumour_verification`'s own `src/` to `sys.path` and calls
`verify_rumour` unchanged, then (by default) logs the result via
`log_suggestion_event` purely so "a verification was shown to a user" is
auditable — never through the accept/edit/reject lifecycle, since a
factual confirmed/denied/unaddressed finding isn't a suggestion the way
Modules 3/4/6/7's outputs are. This is a Module 1 <-> Module 5 integration
point, independent of Module 9's transparency work above.

- `POST /users/{user_id}/rumour-verification` `{"rumour_text",
  "rumour_date"?, "company_name"?, "evaluated_at"?}` — runs Module 5's
  `verify_rumour` and returns the match, status, score, and top-candidate
  reasons. `?log_event=false` skips logging (defaults to `true`).

### Endpoints

- `GET /users/{user_id}/transparency` — which decision types this user has
  at least one logged decision for, and how many.
- `GET /users/{user_id}/transparency/{module_source}` — the trace for the
  latest (or `?event_id=` a specific) decision of that type. `404` for an
  unknown decision type or no matching event.

---

## Module 10 — Gamification

A thin layer: milestones over what Modules 2/3/6 already compute, logged
through Module 1's event log, nothing more.

### Two small additions to Module 2, and why they were necessary

"Debt principal cleared" and "subscriptions cancelled" turned out to be
structurally undetectable before this module: Module 2's EMI/expense CRUD
was add-only (no way to mark a loan paid off or a recurring charge
cancelled), so there was never a state transition for a milestone to
observe. `close_emi` and `remove_expense_item` (both in `onboarding.py`,
both soft — `closed_at`/`removed_at` timestamps, not deletes, so history
stays intact) exist to make those two milestone categories real rather
than aspirational. Both are "material edits" the same way `add_emi`/
`add_expense_item` are: each re-derives and re-logs the month's snapshot
via Module 1's `log_monthly_snapshot`, and both are excluded from ongoing
financial-position calculations (Module 2's `_gather_inputs`, and Module
6's own EMI/expense queries, both now filter `closed_at`/`removed_at IS
NULL`).

### Milestone categories, all effort signals (`gamification_config.py`, version `v1`)

| Category | Signal | Thresholds |
|---|---|---|
| Buffer | `buffer_coverage_months` crossing a new high (latest snapshot) | 1, 2, 4, 6 months — reuses Module 3's own capacity band edges, not a second set of numbers |
| **Capacity unlock** | Module 3's `capacity_ceiling` reaching a new peak across the user's own risk-tier history | one per ceiling value 2-5 |
| Debt | total outstanding EMI principal (active EMIs only) reaching zero, having ever had at least one EMI recorded | one-time, "debt_free" |
| Subscriptions | expense items with `removed_at` set whose category matches Module 6's own subscription-keyword list | 1, 3, 5 cancelled |
| Consistency | consecutive trailing months of positive `surplus` in snapshot history | 3, 6, 12 months |

### The one "real" progression mechanic

Per the module brief, a capacity-ceiling rise is treated as qualitatively
different from the other, more badge-like milestones: `_check_capacity_unlock`
in `gamification_service.py` walks the user's own `risk_profile` event
history for the highest ceiling ever reached, and when a new peak is hit,
names the real before/after numbers — old ceiling, new ceiling, and (by
calling Module 4's own `compute_target_allocation` for each) the actual
capped-equity percentage that changed, e.g. *"Capacity ceiling rose from 2
to 4 — capped equity target rose from 20% to 50%"* — not a generic "Level
Up!" label with no number behind it.

### Effort, never outcome — enforced in code, not just promised

`gamification_config.py` requires every `MilestoneDefinition` to declare
a `SignalType` (`EFFORT` or `OUTCOME`), and `_assert_all_effort_signals`
runs against the real catalog **at import time** — a milestone declaring
`OUTCOME` doesn't get flagged in review, it stops the app from starting
(`GamificationOutcomeSignalError`), proven by
`test_guard_actually_rejects_an_outcome_signal` feeding it a poisoned
catalog entry. Underneath the declared type, the actual data sources back
this up: every signal above comes from Module 2's own declared inputs or
Module 3's rule-table output, and this module never reads Module 4's
`current_exposure_paise`/`current_exposure_pct`/`total_value_paise`
(portfolio value or market exposure) — checked directly by
`test_gamification_source_never_reads_module4_outcome_fields`, which
scans the actual detection-logic source files for those terms rather than
trusting that no one added them.

One correctness bug this surfaced during testing, fixed rather than
worked around: Module 2's `compute_emergency_fund_coverage_months`
returns a documented sentinel (`MAX_BUFFER_MONTHS` = 9999.99) when no
essential expenses have been recorded yet — an empty profile, not an
amazing buffer. The first version of the buffer-milestone check didn't
know about the sentinel and would have awarded all four buffer milestones
to a brand-new user with zero expenses entered; `_check_buffer_milestones`
now explicitly excludes it.

### Hard exclusions, structurally

No leaderboard, no cross-user comparison: every function in
`gamification_service.py` takes exactly one `user_id` and every query
filters on it — there is no code path that reads more than one user's
data. No streak for merely opening the app: this module has no access to
any "app opened" event type in Module 1's schema (none exists), and the
one streak it does track (consistency) is built from `surplus`, a
financial figure, not usage.

### Logging

Each newly-earned milestone is its own `suggestion_event`
(`module_source="gamification"`, `suggested_value = {milestone_id,
category, headline, details}`). No new "achieved milestones" table:
`check_milestones` reads a user's own past gamification events first to
find out what's already been awarded (the same replay-from-the-log
pattern as Modules 3/4/6/7/9), so there's no separate state that could
drift out of sync with the log.

### Endpoints

- `POST /users/{user_id}/gamification/check` — detects and logs any newly
  earned milestones since the last check, returns just the new ones.
- `GET /users/{user_id}/gamification/history` — every milestone this user
  has ever earned, oldest first.

---

## Out of scope here

No analytics dashboards, no ML training pipeline, no statement parser
(see the expense-source decision above, and Module 6's scope-reduction
note). Named-product recommendations of any kind are never in scope for
this module, or any future one — that's a hard legal boundary, not a v1
gap. No real-user validation of Module 8's drift detector — see that
module's own section for why, and for where that gap is tracked as future
work. Module 9's transparency layer never recomputes a decision to
explain it — see that module's own section for the mechanism that
enforces this. Module 10's gamification layer never rewards an outcome
signal — see that module's own section for the import-time guard that
enforces this. Module 1's schema, Module 2's profile/expense/holding
tables, Module 3's tier, Module 4's classification/allocation logic,
Module 6's debt/leak calculators, Module 7's personalization offset,
Module 8's drift detector, Module 9's transparency layer, and Module 10's
milestone catalog are designed so future modules can be built against
them without changes here.
