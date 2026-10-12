# Implementation Improvements Based on Expert/Guide Review

This document tracks concrete changes made to the project in response to feedback from the project guide/supervisor and reviewer input, as distinct from self-directed feature work. It exists so the "what changed and why" is traceable for the dissertation write-up (e.g. a "Validation & Refinement" or "Threats to Validity" chapter) rather than living only in chat history.

Each entry below is scoped to a module and records: what the guide/reviewer flagged, what was changed, and where.

---

## Module: Risk-Profiling Questionnaire — Content Validation Pass

**Trigger**: Step 4 of the supervisor's questionnaire validation plan (see `questions i have.md`, "How do I validate/defend the questionnaire's numbers for my dissertation?") calls for independent expert/reviewer content validation before a pilot study. Drafting the reviewer-facing content validation survey surfaced a round of design corrections from the guide, applied below before the survey goes out to reviewers.

**Files affected**: `risk_questionnaire_content_validation_survey.md` (reviewer-facing survey), `risk_questionnaire_item_table.md` (internal item-design rationale). No backend code (`risk_profile_config.py`) was changed — these are pre-pilot content corrections to the review materials, not to production scoring.

### Issues raised and corrections made

| # | Issue raised | Correction implemented |
|---|---|---|
| 1 | Ambiguous scope: the questionnaire mixes pure risk-tolerance items (`drawdown_reaction`, `windfall_allocation`, `sure_gain_tradeoff`, `friend_description`) with contextual items (`horizon`, `experience`, `goal`) but was being described to reviewers as a "risk-tolerance questionnaire." | Explicitly reclassified and documented as a **broader investor risk-profile questionnaire** (a risk-tolerance core plus three separate contextual dimensions), and reworded the reviewer-facing intro text to state this rather than implying all 7 items measure the same construct. |
| 2 | The sure-gain tradeoff item's design rationale incorrectly claimed "expected value and variance both increase monotonically" across its five options. | Corrected: expected value is designed to stay roughly constant (~Rs 5,000 across all five options: 5000 → 4900 → 5000 → 5100 → 5000) — only variance/risk increases. Added an explicit note for reviewers stating this, so they judge the item without being misled by the old (wrong) framing. |
| 3 | The windfall-allocation item's top answer option ("equity, and consider borrowing more to invest further") introduced leverage-seeking as a variable, conflating it with risk tolerance. | Replaced with "equity, including higher-risk/small-cap or thematic funds" — raises risk within the same equity-allocation dimension instead of introducing borrowed money as a separate construct. |
| 4 | The goal item's top answer option mixed two separate ideas: a growth objective ("maximize long-term growth") and comfort with short-term volatility ("swings don't bother me"), which is really an attitude already tested by `drawdown_reaction`. | Reworded to state the growth objective only: "Maximize long-term growth, even at the cost of short-term stability." Volatility comfort is no longer duplicated here. |
| 5 | Investment experience was implicitly at risk of being treated as a proxy for risk tolerance rather than its own dimension. | Reaffirmed `experience` as a standalone contextual profile dimension in both documents, with explicit reviewer-facing wording that more experience is *not* assumed to mean higher risk tolerance. |
| 6 | The drawdown-reaction item's answer ordering asserted "buying more" as self-evidently the higher-risk-tolerance response, which isn't automatically true (could reflect overconfidence or other factors). | Softened the internal rationale from an asserted "Yes" to "Open" pending reviewer judgment, and added a reviewer-facing note in the survey asking them not to assume this ordering — left for the content validity check to decide. |
| 7 | The friend-description item's highest-risk option used the wording "a real gambler," which may read as loaded/judgmental rather than neutral. | Did not unilaterally reword it. Instead added a dedicated extra question (Item 7, Q5) asking reviewers directly whether the phrase is appropriate or should be changed, with room for a suggested alternative. |
| 8 | The relevance/clarity rating scale (5-point Likert: Strongly Disagree → Strongly Agree) does not support a clean Content Validity Index (CVI) calculation, which conventionally requires an even-numbered, forced-choice scale. | Switched both the relevance and clarity questions to a 4-point scale (1 = Not relevant/clear ... 4 = Highly relevant/very clear), enabling I-CVI = proportion of reviewers rating 3 or 4, per Lynn (1986)/Polit & Beck (2006). |
| 9 | No structured way for reviewers to explain a low rating or a flagged ordering issue. | Added a standing open-text comment box after every item (not just when ordering was questioned), explicitly prompting an explanation whenever relevance/clarity is rated low or ordering is marked No/Unsure. |
| 10 | Reviewer background only asked for a yes/no on relevant experience, with no way to weight expert credibility. | Added fields for reviewer designation/role (e.g. financial advisor, CFA, psychometrician, academic) and approximate years of relevant experience. |

### Re-validation status

- The content validation survey (`risk_questionnaire_content_validation_survey.md`) now reflects all corrections above and is ready to circulate to the 5+ reviewers called for in the supervisor's validation plan.
- Scoring plan updated accordingly: I-CVI (≥0.78 threshold, Lynn 1986 / Polit & Beck 2006) for relevance and clarity per item, plus the existing answer-ordering CVI.
- Not yet done (tracked as next steps per `questions i have.md`): collecting actual reviewer responses, computing I-CVI/S-CVI, running the ~20–30 person pilot for Cronbach's alpha, and convergent validity against the published Grable & Lytton (1999) scale.

---

## Module: Spending "Leaks" / Budgeting Nudges

**Trigger**: Reviewer raised a concern that budgeting/"leak" nudges could tell a user to cut spending on things that are actually a basic need (the example given: telling someone to stop ordering food), which would be tone-deaf and could undermine trust in the platform's recommendations.

**Files checked**: `backend/app/services/leak_engine.py` (detection logic), `backend/app/services/debt_leak_config.py` (keyword configuration), `frontend/src/screens/insights/LeaksScreen.tsx` (display only, no category logic).

### Issue raised and current status

| # | Issue raised | Status |
|---|---|---|
| 1 | Leak/budgeting nudges could target basic-needs spending (e.g. food) rather than genuinely wasteful spending. | **Confirmed already out of scope, not a live bug.** The leak engine only ever flags three things: (a) idle cash sitting above the emergency-buffer target, (b) bank/account **fees** matched against an explicit fee-keyword list (`bank charge, account maintenance, amc, atm fee, late fee, forex markup, overdraft fee, ...`), and (c) recurring **subscriptions** matched against a separate keyword list (`subscription, streaming, membership, gym, ott, saas, vpn, ...`) plus near-duplicate detection. Food, groceries, and delivery are not in either keyword list and are never targeted by category name. In addition, the subscription check explicitly skips any expense the user has marked `is_essential` (`leak_engine.py`: "essential-flagged items are the user's own judgment call, not ours") — so even a borderline category the user considers a basic need is respected and excluded. |

### Re-validation status

- No code change was required for this item — the review surfaced a legitimate design risk, and checking the implementation confirmed the leak engine was already scoped narrowly enough (fees + subscriptions + idle cash only) to avoid it.
- Documented here so the scope decision is explicit and traceable, rather than looking like an oversight that happened to not manifest.
- Future-proofing note: if new leak categories are ever added, the same constraint should apply — no category that could plausibly be a basic need (food, transport to work, medical) should be added without an explicit essential-goods exclusion, mirroring the existing `is_essential` check.

---

## Module: Asset Allocation Granularity

**Trigger**: Reviewer feedback that the platform's asset allocation should be performed at a more detailed level than three broad buckets (gold/equity/debt), i.e. it should distinguish sub-categories within each class rather than treating each asset class as a single lump.

**Files checked**: `backend/app/services/asset_classification_config.py` (asset class + holding-type definitions), `backend/app/services/allocation.py` / `allocation_service.py` / `allocation_config.py` (target allocation computation), `frontend/src/theme/tokens.ts` (`ASSET_CLASS_COLOR_KEY`).

### Issue raised and current status

| # | Issue raised | Status |
|---|---|---|
| 1 | Target allocation and recommendations are expressed only at 5 top-level classes (`cash, debt, equity, real_assets, alternatives`) — no breakdown within a class (e.g. gold vs. REITs within real assets, government vs. corporate bonds within debt, large-cap vs. small-cap within equity). | **Not yet implemented — flagged as an open gap, not corrected.** The finer-grained data actually already exists in the codebase but is only used one layer removed from where the reviewer's concern applies: `HoldingType` (24 values, e.g. `GOLD_ETF`, `SOVEREIGN_GOLD_BOND`, `PHYSICAL_GOLD`, `REIT_INVIT`, `DEBT_MUTUAL_FUND`, `PPF`, `NPS`) each carry a `decomposition` fraction into the 5 broad classes, but this is used only to compute a user's *current* exposure from their actual holdings — not to set a more granular *target* allocation or to structure recommendations. The target allocation, risk-ladder bounds, and capital market assumptions (`allocation_config.py`) are all still keyed on just the 5 broad classes. |

### Re-validation status

- **Not yet implemented.** This is recorded as a known limitation/planned improvement rather than a completed correction.
- Suggested path forward (not yet built): extend `RISK_LADDER_BOUNDS_V1` and `CAPITAL_MARKET_ASSUMPTIONS_V1` to operate on a sub-category level (e.g. split `real_assets` into gold vs. REIT/InvIT, split `debt` into government vs. corporate/credit-risk debt), reusing the `HoldingType` decomposition data that already exists for exposure tracking, so the same taxonomy drives both current exposure and target allocation instead of two different levels of granularity.
- Until this is built, this should be listed explicitly as a limitation in the dissertation (e.g. under "Threats to Validity" or "Future Work"), since it was directly raised by a reviewer and not yet resolved.

---

## Module: Financial Literacy Onboarding / Accessibility

**Trigger**: Reviewer feedback that the platform should be more accessible to people with no financial literacy background, rather than assuming the user already understands investing concepts.

**Files checked**: `backend/app/services/gamification_config.py` (`ROADMAP`, `CHECKLIST`), `frontend/src/screens/progress/ProgressScreen.tsx` (rendering).

### Issue raised and correction implemented

| # | Issue raised | Correction implemented |
|---|---|---|
| 1 | The platform assumed financial literacy and didn't give non-expert users a foundation before pointing them at investing features. | Added a structured, ordered learning path rather than a single static page: the gamification `ROADMAP` runs Level 1 "Financial Basics" (income vs. expenses, needs vs. wants, budgeting, **emergency funds**, inflation/interest) → Level 2 "Financial Safety" (buffers, **insurance**, paying off high-interest debt, credit scores) → Level 3 "Banking & Saving" → Level 4 "Investing Basics" (asset classes, diversification, SIPs) → Level 5 "Taxes & Retirement". A parallel `CHECKLIST` groups the same idea under explicit section labels — "Financial foundation" (track income/expenses, budget, pay off/plan high-interest debt, build an emergency fund, get adequate insurance) is placed and rendered *before* "Savings" and "Investing" sections. |

### Re-validation status

- Live in the frontend today: `ProgressScreen.tsx` renders this as the "Financial literacy roadmap" ("Learn with purpose") with section order `Financial foundation → Savings → Investing → Financial literacy`, and copy stating progress "reflects learning, never wealth or returns" — reinforcing that this is educational, not a performance/investment metric.
- Worth noting for the dissertation: there isn't a single page literally titled "basics you need before investing" — the accessibility fix is structural/sequencing (foundation topics gated before investing topics in the roadmap and checklist) rather than one dedicated static page. If a reviewer expects a single consolidated "start here" page rather than a roadmap, that would be a follow-up UX change, not yet done.

---

## How to extend this document

Add a new `## Module: <name>` section per review cycle, following the same shape: trigger, files affected, a table of issue → correction, and a re-validation status line. Keep entries scoped to changes that were actually driven by external (guide/reviewer/panel) feedback, not general feature work — that distinction is what makes this document useful as evidence of responsiveness to review, rather than a general changelog.
