# Personal Finance Planning App (India) — Final Year Project

A modular personal finance planning system for Indian users. See each module's
own README for details. Product philosophy and hard constraints (no named
product/fund/stock recommendations, ability-before-willingness risk capping,
certain-returns-first suggestions, INR-in-paise money math, mandatory event
logging) apply across every module and are enforced at the code level, not
just in docs.

## Modules

| Module | Status | Path |
|---|---|---|
| 1 — Data Model & Event Logging | Done | [backend/](backend/) |
| 2 — Onboarding & Financial Position | Done | [backend/](backend/) |
| 3 — Risk Profiling | Done | [backend/](backend/) |
| 4 — Asset Class Mapping & Allocation | Done | [backend/](backend/) |
| 5 — Rumour Verification (research component) | Done | [modules/rumour_verification/](modules/rumour_verification/) |
| 6 — Debt and Leak Engine | Done | [backend/](backend/) |
| 7 — Fast Feedback Loop | Done | [backend/](backend/) |
| 8 — Drift Detection (Simulated) | Done | [backend/](backend/) |
| 9 — Transparency Layer | Done | [backend/](backend/) + [modules/rumour_verification/](modules/rumour_verification/) |
| 10 — Gamification | Done | [backend/](backend/) |

All planned modules are now built. Module 6's leak half runs at reduced
scope (manual-entry expenses only, no statement parser), and Module 8 is
validated only against simulated personas, never real users — see
backend/README.md for both. Module 10's milestones reward
financial-behaviour effort only, never market outcomes or app engagement,
enforced by an import-time guard, not just policy.

Module 9 makes three claims of deliberately different strength, and the
code will not let them be confused. Modules 3/4/6/7/10's traces are
labeled **"transparent reasoning"** — weighted sums and rule tables, not
AI; printing the weights is the whole feature. Module 5's *local
constrained-retrieval* engine is labeled **"retrieval explanation"**,
because naming which constraint eliminated which candidate filing and why
the winner ranked first is a genuine multi-step answer — and that claim is
now measured, not asserted, in
`modules/rumour_verification/eval/evaluate_explanations.py`. Module 5's
*n8n workflow* path is labeled **"third-party workflow output"**: its
prose is the workflow's own self-report, which this project neither
computed nor evaluated. An import-time assertion restricts the permitted
labels and rejects any containing "AI" or "explainable".

## Stack

- Backend: Python + FastAPI, SQLAlchemy, Alembic
- Database: PostgreSQL in production; tests run against SQLite so the suite
  needs no local Postgres server (see [backend/README.md](backend/README.md))
- Module 5 retrieval: scikit-learn TF-IDF, run as an isolated service/library
  so it can be tuned independently of the rest of the app

## Money handling

All monetary fields are integers in paise (1 INR = 100 paise). Never store
or compute money as float. Formatting to `₹` happens only at display time.
