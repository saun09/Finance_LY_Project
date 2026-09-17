# Risk Questionnaire — Item-Level Table

Step 1 of the supervisor's validation plan. Source: `backend/app/services/risk_profile_config.py` (`QUESTIONNAIRE_V1` + `QUESTIONNAIRE_V2`). Options are listed in their stored order (current score 1→5); "expected answer order" records whether that order genuinely runs low-risk → high-risk on inspection, ahead of the reviewer check in step 4.

| # | Question ID | Question text | Construct being measured | Source / reference | Answer options (current score) | Expected order correct? | Current weight |
|---|---|---|---|---|---|---|---|
| 1 | `horizon` | "When will you need most of this money?" | Investment time horizon | Original item. Standard dimension in suitability/risk-tolerance questionnaires generally (e.g. FinaMetrica, typical KYC risk forms); not drawn from a single cited instrument. | Within 1 year (1) · 1–3 years (2) · 3–7 years (3) · 7–15 years (4) · More than 15 years (5) | Yes — longer horizon consistently associated with higher risk capacity/tolerance in the literature | 3 |
| 2 | `drawdown_reaction` | "If your investments fell 20% in a month, what would you do?" | Loss aversion / behavioral risk tolerance | Original wording. Same construct as the "market decline" item used in Grable & Lytton (1999) and FinaMetrica; not a verbatim reproduction. | Sell everything immediately (1) · Sell some to limit further loss (2) · Hold and wait it out (3) · Buy a little more if I can (4) · Buy significantly more (5) | Open — selling under loss plausibly reflects lower tolerance, but "buying the dip" isn't automatically proof of higher tolerance (could reflect overconfidence, contrarian behavior, etc.); leaving this ordering for reviewers to confirm rather than assuming it | 3 |
| 3 | `experience` | "How much experience do you have with market-linked investments (equity, mutual funds)?" | Investment experience / financial literacy proxy | Original item. Standard in suitability questionnaires (e.g. FINRA/SEC-style suitability forms); experience is a known correlate of, not identical to, risk tolerance. | None (1) · Under 2 years (2) · 2–5 years (3) · 5–10 years (4) · 10+ years (5) | Plausible but not certain — experience correlates with tolerance but is arguably a distinct construct (see step 2) | 2 |
| 4 | `goal` | "What best describes your primary goal for this money?" | Investment objective / return-orientation | Original item, goal-based investing framing common to suitability questionnaires. | Preserve, minimize any loss (1) · Generate steady income (2) · Balanced growth and stability (3) · Grow it meaningfully (4) · Maximize long-term growth, even at the cost of short-term stability (5) | Yes — ordering runs preservation → growth-maximizing. (Option 5 was reworded to state the growth objective only; it previously also claimed comfort with short-term volatility, which is a separate attitude already tested by `drawdown_reaction`.) | 2 |
| 5 | `windfall_allocation` | "You unexpectedly receive Rs 20,000. What would you do with it?" | Risk tolerance (revealed allocation preference) | Original wording. Conceptually similar to hypothetical-windfall/income-gamble items used in behavioral risk-tolerance research (e.g. Barsky et al., 1997); not a direct reproduction. | FD/savings (1) · Debt/bond funds (2) · Split debt/equity (3) · Equity funds (4) · Equity, including higher-risk/small-cap or thematic funds (5) | Yes. (Option 5 previously read "equity + consider borrowing more to invest further," which conflated risk tolerance with leverage-seeking; reworded to raise risk within equity itself instead.) | 4 |
| 6 | `sure_gain_tradeoff` | "Which would you choose: a guaranteed amount, or a chance at more?" | Risk tolerance (certainty equivalent / gamble preference) | **Adapted from Grable & Lytton (1999)** — forced-choice item contrasting a guaranteed amount against escalating, lower-probability, higher-payout gambles of broadly similar expected value. Wording and amounts are this project's own; scoring (linear 1–5) is not Grable & Lytton's original scoring. | Guaranteed Rs 5,000 (1) · 70% chance at Rs 7,000 (2) · 50% chance at Rs 10,000 (3) · 30% chance at Rs 17,000 (4) · 10% chance at Rs 50,000 (5) | Yes — variance/risk increases monotonically across the options. Expected value stays roughly constant throughout (5000 → 4900 → 5000 → 5100 → 5000); it is *not* increasing, only variance is. | 4 |
| 7 | `friend_description` | "In general, how would your closest friend describe you as a risk-taker with money?" | Self-perceived risk-taking propensity | Same construct as an item in Grable & Lytton's (1999) 13-item scale (a "how would your friends describe you" risk-propensity item); wording adapted, not verbatim. | A real risk avoider (1) · Cautious (2) · Willing to take calculated risks after research (3) · Comfortable taking risks for bigger rewards (4) · A real gambler (5) | Yes, though "a real gambler" may read as loaded/judgmental — flagged as an explicit wording-check question for reviewers (Item 7, Q5) rather than decided here | 2 |

## Step 2 — Dimension separation

| Dimension | Items | Item count | Reliability feasible? |
|---|---|---|---|
| Risk tolerance (attitude) | `drawdown_reaction`, `windfall_allocation`, `sure_gain_tradeoff`, `friend_description` | 4 | Yes — enough items for a per-dimension alpha/omega (step 8) |
| Investment horizon | `horizon` | 1 | No — single item, no internal consistency to test |
| Investment experience | `experience` | 1 | No — single item |
| Investment objective / goal | `goal` | 1 | No — single item, and conceptually mixed (see below) |
| Risk capacity | *(none in this questionnaire)* | 0 | N/A — see below |
| Financial commitments | *(none in this questionnaire)* | 0 | N/A — see below |

**Risk capacity and financial commitments are not questionnaire items at all.** They're computed separately, objectively, from real onboarding/spending data — buffer-fund coverage in months, EMI-to-income ratio, income stability, and life-cover-to-dependents ratio — by `compute_capacity_ceiling()` in `backend/app/services/risk_profile.py`. Nobody is asked to self-report their EMI ratio or dependents; the system reads it from the financial data already captured elsewhere and turns it into a ceiling tier. That ceiling is then combined with this questionnaire's score as `final_tier = min(stated_tier, capacity_ceiling)` — the questionnaire is never the sole source of the final risk tier.

**So: is this a pure risk-tolerance scale, or a broader risk-profile score?** Since `horizon`, `experience`, and `goal` are being kept, this is a **broader investor risk-profile questionnaire**, not a pure risk-tolerance scale — a 4-item risk-tolerance core (`drawdown_reaction`, `windfall_allocation`, `sure_gain_tradeoff`, `friend_description`) plus three single-item contextual dimensions (`horizon`, `experience`, `goal`) that aren't tolerance itself but are commonly collected alongside it. It deliberately does *not* try to cover capacity or financial commitments — that's handled by a separate, objective calculation elsewhere in the system, and the two are combined downstream. The content-validation survey's intro text has been updated to describe it this way explicitly, rather than calling it a "risk-tolerance questionnaire."

Two structural gaps worth deciding on before the reviewer pass: (1) `horizon`, `experience`, and `goal` are each single items standing in for what look like three separate constructs — per step 8, none of them can get a real reliability check on their own, so either treat them explicitly as single-item covariates (common practice for horizon/experience-type items in the literature) rather than sub-scales, or expand each to 2–3 items if per-dimension reliability is wanted for all of them, not just risk tolerance. (2) `goal`'s last option previously mixed two ideas — the growth objective and comfort with short-term volatility (an attitude already tested by `drawdown_reaction`). It's now reworded to state the growth objective only ("Maximize long-term growth, even at the cost of short-term stability"); still worth asking reviewers whether it now reads cleanly as a needs/objective item rather than an attitude item.

## Step 3 — Equal weighting (proposed, not yet applied to code)

Per instruction, no code has been changed. This is the weighting scheme to apply once the item set is confirmed by content validation:

| Question ID | Current weight | Proposed weight |
|---|---|---|
| `horizon` | 3 | 1 |
| `drawdown_reaction` | 3 | 1 |
| `experience` | 2 | 1 |
| `goal` | 2 | 1 |
| `windfall_allocation` | 4 | 1 |
| `sure_gain_tradeoff` | 4 | 1 |
| `friend_description` | 2 | 1 |

With unit weighting, the raw score is a simple sum of the seven 1–5 answers: range **7–35**. Per step 9, this should stay a **continuous score** through the validation phase — no 1–5 tiers should be cut from it yet. Tier breakpoints get decided only after the ~150–200-person main sample, from that sample's actual score distribution, not before.

## Notes for step 10 (reviewing the 1–5 scoring itself)

All seven items currently use the same linear 1–5 scale regardless of what's actually being measured. Two items are the ones most worth reviewer scrutiny before treating "1–5, evenly spaced" as safe to assume:

- `windfall_allocation`: option 5 was reworded from "equity + consider borrowing more to invest further" (which brought leverage into what should be a pure asset-allocation question) to "equity, including higher-risk/small-cap or thematic funds" — worth confirming with reviewers that this now reads as one point riskier than "equity funds" rather than a qualitatively different choice.
- `experience`: is the psychological distance between "significant (5–10y)" and "extensive (10+y)" the same as between "none" and "a little (under 2y)"? Equal integer spacing assumes so; this hasn't been tested.
