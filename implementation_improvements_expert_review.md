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

## How to extend this document

Add a new `## Module: <name>` section per review cycle, following the same shape: trigger, files affected, a table of issue → correction, and a re-validation status line. Keep entries scoped to changes that were actually driven by external (guide/reviewer/panel) feedback, not general feature work — that distinction is what makes this document useful as evidence of responsiveness to review, rather than a general changelog.
