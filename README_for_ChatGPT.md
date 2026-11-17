# Project Brief for ChatGPT: Conference Discovery

## What this document is for

Use this brief to understand the project and identify suitable, currently
open conferences for presenting or publishing its research. Do not assume
that every feature in the application is a research contribution. Search
for conferences whose scope, review process, publication route, and deadlines
fit the specific research strand being considered.

When recommending a conference:

- Verify the current call for papers on the conference's official website.
- Give the conference name, relevant track, submission deadline, event dates,
  location or online format, official URL, and publication/indexing details
  only when those details can be verified.
- Distinguish a peer-reviewed full paper from an abstract, poster, demo, or
  workshop submission. Do not imply that conference acceptance guarantees
  indexing.
- Check the conference's legitimacy and publisher/indexing claims. Flag
  unclear fees, misleading indexing claims, and unusually broad or
  unverified calls.
- Compare fit separately for the project's different research contributions.
- Do not describe synthetic responses as human participants or report
  synthetic-inclusive test metrics as performance on real people.
- Do not invent ethics approval, consent, funding, author details, or
  completed validation.

## Project at a glance

**Working description:** An India-focused personal-finance planning and
education application that prioritizes financial capacity before stated
investment risk preference, explains its rule-based recommendations, and
includes a separate prototype for verifying user-submitted market rumours
against company/exchange disclosures.

**Primary design principle — “ability before willingness”:** A person's
questionnaire response describes stated willingness to take risk. It does
not establish what the person can afford to lose. The system independently
estimates a capacity ceiling from financial information and caps the stated
risk tier:

```text
final risk tier = min(stated risk tier, financial capacity ceiling)
```

The application is a planning and education prototype, not a financial
product recommender. It gives category-level allocation guidance, not named
stocks, funds, ETFs, or schemes, and it does not promise returns.

## The application

The repository contains a React Native/Expo client, a FastAPI backend, a
separate rumour-verification research module, test suites, and offline
questionnaire-model research artifacts.

### Main user journey

1. A user creates a profile and enters income, income stability, expenses,
   debt/EMIs, insurance, and holdings.
2. The system calculates a financial-position snapshot, including surplus,
   net worth, emergency-buffer coverage, and EMI-to-income measures.
3. The user completes a risk-profile questionnaire.
4. The system computes stated risk and an independent financial-capacity
   ceiling, then applies the lower tier.
5. Holdings are mapped to broad asset classes and a category-level
   allocation is generated within the tier's limits.
6. The user can explore debt strategies, possible fees and recurring charges,
   and how their responses affect a personalized display.
7. Stored decisions can be inspected through transparent reasoning views.
8. The app includes financial-literacy lessons, quizzes, and
   behaviour-oriented progress milestones.
9. A separate feature accepts a rumour explicitly supplied by the user and
   searches a local filing corpus; it does not scrape social media.

### Functional areas

- **Financial data and event history:** Profile and financial records,
  monthly snapshots, and logged suggestion/outcome events.
- **Risk profile:** A weighted questionnaire for stated willingness plus a
  separate capacity assessment based on financial data.
- **Allocation:** Holding classification and look-through assumptions,
  followed by tier-constrained asset-class allocation.
- **Debt and spending analysis:** Avalanche/snowball comparisons,
  amortization, prepay-versus-invest framing, credit-card effective-rate and
  refinance calculations, plus idle-cash, fee, and recurring-charge checks.
  Expense information is currently entered manually; there is no bank
  statement parser.
- **Personalization:** A bounded adjustment to the *displayed* allocation
  based on recorded responses. It cannot change the risk tier, and the
  capacity cap is reapplied.
- **Risk-drift prototype:** Evaluated using five hand-authored synthetic
  personas. It is simulated only and is not a live-user feature.
- **Transparency:** Reconstructs explanations from stored decision events;
  missing information is reported as a gap rather than silently fabricated.
  The project calls the deterministic modules' output “transparent
  reasoning,” not “explainable AI.”
- **Financial education and milestones:** Lessons, quizzes, and progress
  indicators focus on financial behaviours and learning, not investment
  returns, app-opening streaks, or leaderboards.
- **Rumour verification:** See the separate research strand below.

## Research strand A: questionnaire-based risk-tier prediction

### Questionnaire and intended construct

The instrument is a **broader investor risk-profile questionnaire**, not a
pure risk-tolerance scale. It has seven items:

- Four intended risk-tolerance items: reaction to a market fall, hypothetical
  windfall allocation, a sure-gain-versus-gamble choice, and self-perceived
  risk-taking.
- Three contextual profile items: investment horizon, investment experience,
  and investment goal.

Risk capacity is not measured by this questionnaire; it is calculated
separately from financial information. The questionnaire's current scoring
uses hand-designed weights and equal-width tier breakpoints. These values
have not yet been empirically calibrated or psychometrically validated.
One sure-gain item is inspired by Grable and Lytton (1999), but it is not a
verbatim reproduction and does not use their original scoring.

### Dataset and provenance

The questionnaire workbook contains **434 responses**:

- **130 real participant responses**
- **304 AI-generated synthetic responses created with Claude** to augment the
  small real sample and mimic response trends

This provenance comes from the project owner. Treat the two groups as
different data sources in all analyses and publications. The synthetic rows
are not additional participants, and must not be reported as survey
respondents. Disclose how they were generated, what information/prompts
informed generation, how they were labeled, and how they were used.

The training script derives the target tier by applying the app's deterministic
seven-item weighted scoring rule to each row. Thus, the ML task is primarily
to approximate that rule (including in a four-item “quick” mode); it does
not establish clinical/financial suitability, actual risk tolerance, future
investment behaviour, or investment outcomes.

### Models and reported offline results

The project compares Random Forest (RF), Gradient Boosting (GB), and a
scikit-learn multilayer perceptron (MLP) using seven-item and reduced
four-item feature sets. The target is the rule-derived stated tier. The
offline comparison reports an 80/20 stratified split with 347 training rows
and 87 test rows (random seed 42). The model-selection note reports:

| Model | Seven-item accuracy | Four-item accuracy |
|---|---:|---:|
| Random Forest | 79.3% | 78.2% |
| Gradient Boosting | 85.1% | 74.7% |
| MLP | 94.3% | 75.9% |

RF was selected for the application because it supports the project's
multiclass TreeSHAP explanation path and performed best among the compared
models in the four-item mode. In full questionnaire mode, the application
uses the deterministic score for the tier; the RF provides a supplementary
prediction and per-question SHAP contributions. The reduced four-item model
predicts a tier when a user answers only those four questions.

**Critical evaluation caveat:** The reported 347/87 split is drawn from the
434-row workbook, which includes synthetic responses. Unless the split was
explicitly grouped by provenance (the current research notes do not establish
that it was), these metrics may include synthetic rows in both training and
test sets. They are therefore not evidence of generalization to real
participants. For a defensible human-data claim, rerun evaluation with
provenance-aware splits and report performance on held-out real responses
separately. With only 130 real responses, uncertainty and class counts must
also be reported; avoid overclaiming from a small test sample.

The rule-derived labels also make high accuracy partly a measure of how well
a model reproduces a known scoring formula, not independent validation of
that formula. Psychometric evidence and external outcome validation remain
separate requirements.

### Questionnaire validation status

Project materials outline a content-validation survey for at least five
reviewers, followed by a 20–30 person pilot, reliability analysis, and
convergent/known-groups validation. The project notes state that actual
reviewer responses and those validation analyses have **not yet been
completed**.

Recently received supervisor feedback says to remove borrowing/leverage
from the windfall item and avoid judgmental labels such as “gambler” or
“speculator,” using neutral wording across answer options. The reviewer
survey documentation reflects earlier revisions, but the backend's current
questionnaire configuration still contains the prior borrowing-related
windfall option and “A real gambler.” Treat the newer feedback as a pending
instrument revision, not as a completed code or validation change. Any
future model comparison should document which questionnaire version was
used and retrain/re-evaluate if option meanings change.

## Research strand B: market-rumour verification

This separate research prototype evaluates retrieval of official disclosures
for a user-supplied market rumour, framed around India's SEBI LODR
Regulation 30(11). It compares:

1. A TF-IDF text-similarity baseline.
2. A constrained retriever that adds company/entity, temporal, and source
   authority checks, with a similarity floor.

The pipeline returns a candidate filing and a trace of why candidates passed
or were eliminated. Outcomes distinguish **confirmed**, **denied**,
**unaddressed** after the relevant 24-hour window, and **not yet due** in
timeline logic. “Unaddressed” is not assigned to companies outside the
described applicability scope. The tool verifies text a user supplies; it
does not discover or scrape rumours from social platforms.

### Corpus and reported results

- 11 individually sourced real rumour/filing pairs.
- 24 synthetic distractor documents in the retrieval corpus, clearly marked
  as synthetic and not represented as real disclosures.
- Retrieval evaluation: 11 queries ranked against the 35-document corpus.
- Reported baseline vs. constrained retrieval: MRR **0.914 vs. 1.000** and
  hit rate at 1 **0.909 vs. 1.000**.
- The rank improved for only one of the eleven rumours. The corpus was
  deliberately constructed with distractors, so the result demonstrates
  behaviour on this seed set, not general performance on a large live corpus.
- Explanation-trace checks report full coverage and soundness scores of
  1.000 for several properties, but entity-elimination recall is **0.811**.
  The evaluation also states that trace faithfulness does not establish
  usefulness to non-expert readers.
- Some source/date details are flagged for direct exchange-archive
  verification; the README for this module describes those caveats.

This is best positioned as a small, transparent prototype or preliminary
retrieval study unless the corpus is expanded, source verification is
completed, and evaluation uses a larger, independently curated set.

## Technology and implementation

- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic; PostgreSQL is
  the intended database, with SQLite used in tests.
- **Frontend:** React Native, Expo, TypeScript, React Navigation, and TanStack
  Query.
- **ML/research:** scikit-learn, SHAP, joblib; a separate Python module for
  rumour retrieval and evaluation.
- **Testing:** Backend pytest suites cover services, APIs, migrations, and
  research logic. The frontend uses Jest/Jest Expo tests.
- **Voice assistant:** The frontend includes an ElevenLabs/LiveKit voice
  integration; it requires a native development build and is not needed to
  understand the two research strands.

## Limitations and responsible interpretation

- The questionnaire scoring weights and breakpoints are designed rules, not
  empirically calibrated parameters.
- Questionnaire response options and the instrument itself are undergoing
  expert feedback; reviewer validation, pilot reliability, convergent
  validity, and known-groups testing remain outstanding.
- Synthetic data expand the training set but cannot substitute for real
  participants or independent validation. Keep synthetic and real results
  separate.
- Model labels are derived from the app's own weighted score; this is
  rule-emulation rather than ground-truth prediction.
- Reported ML evaluation on the combined 434-row set is not a real-only
  validation result.
- Rumour-retrieval results use only 11 real cases and a 35-document corpus;
  source verification is incomplete for some entries.
- Drift detection is simulated, not deployed to real users.
- Spending analysis uses manually entered expenses rather than bank feeds.
- Product outputs are category-level planning information, not personalized
  professional investment, tax, legal, or insurance advice.

## Possible conference-search directions

Search separately for:

1. **Financial technology / responsible digital finance:** the end-to-end
   financial-planning system, with “ability before willingness” as its
   design principle. A strong paper would need to distinguish software
   engineering contribution from empirical user-outcome evidence.
2. **Applied machine learning / decision support:** questionnaire-based
   tier prediction and per-item explanations. Be explicit that the target is
   a deterministic rubric and that the dataset is mixed real/synthetic.
3. **Information retrieval / trustworthy NLP systems:** constrained,
   source-aware retrieval and traceable elimination for regulatory
   disclosures. Present current results as preliminary because the corpus is
   small.
4. **Human-computer interaction / financial literacy:** only if there is
   user-study, usability, or learning-outcome evidence. The software feature
   alone is not evidence that users understand or benefit from it.

Look for suitable peer-reviewed tracks, workshops, student research forums,
or demo tracks, and explain which contribution each venue would accept.
Do not recommend a venue solely because its title contains “AI,” “finance,”
or “international.”

## Repository sources of truth

Use these files for deeper verification before drafting a paper or
recommending a track:

- `README.md` — project overview, architecture, application features, ethics,
  and testing.
- `backend/README.md` — backend modules and service/API details.
- `risk_questionnaire_item_table.md` — item constructs, current options,
  weights, and scoring rationale.
- `risk_questionnaire_content_validation_survey.md` — reviewer survey draft
  and proposed content-validity procedure.
- `implementation_improvements_expert_review.md` — supervisor/reviewer
  feedback and implementation status.
- `questions i have.md` — risk-scoring explanation and validation questions.
- `research_artifacts/results/MODEL_SELECTION.md` — reported questionnaire
  model comparison and selection rationale.
- `research_artifacts/results/` — metrics, confusion matrices, and figures.
- `research_artifacts/models/MANIFEST.json` — model-split sizes and model
  artifacts.
- `backend/scripts/train_risk_tier_reduced_model.py` — data mapping and
  reduced-model training logic.
- `backend/app/services/risk_profile.py` and
  `backend/app/services/risk_profile_config.py` — deterministic scoring and
  current questionnaire configuration.
- `backend/app/services/risk_profile_ml.py` — application ML inference and
  SHAP explanation path.
- `modules/rumour_verification/README.md` — regulatory framing, corpus
  provenance, method, and limits.
- `modules/rumour_verification/eval/results.md` — retrieval metrics.
- `modules/rumour_verification/eval/explanation_results.md` — trace-quality
  evaluation and known entity-matching issue.

## Short summary suitable for conference searches

An India-focused personal-finance planning prototype applies an
“ability-before-willingness” rule: questionnaire-based stated risk is capped
by an independent assessment of financial capacity. Its research materials
compare classifiers that reproduce a rule-derived five-tier score from a
434-row questionnaire dataset consisting of 130 real and 304
Claude-generated synthetic responses; reported test metrics require
provenance-aware re-evaluation before being interpreted as performance on
people. A separate prototype evaluates TF-IDF versus entity-, time-, and
source-constrained retrieval for matching user-supplied market rumours to
company disclosures, using 11 real cases and 24 synthetic distractors. Both
are preliminary: questionnaire psychometric validation is pending, and the
rumour corpus is small. The application also implements financial-position
tracking, category-level allocation, debt/leak analysis, personalization,
transparent reasoning, education, and simulated-only drift detection.
