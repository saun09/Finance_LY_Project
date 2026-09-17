# Module 5 — Rumour Verification (Research Component)

Given a market rumour the user pastes in, find the exchange filing that
verifies it and report whether it was confirmed, denied, or left
unaddressed — with a full trace of why. This module never detects or
ingests rumours on its own: no automated or real-time social-media
scraping, ever. It only verifies a rumour the user explicitly supplies.
That boundary is a hard project constraint, not a v1 limitation.

This is the project's novel contribution, so this README treats dataset
quality and evaluation rigor as the deliverable, ahead of UI polish (there
is no UI — `demo.py` is a CLI).

## 1. Regulatory framing

### The rule

Regulation 30(11) of the SEBI (Listing Obligations and Disclosure
Requirements) Regulations, 2015 ("LODR"), inserted by SEBI's May 2024
amendment, requires certain listed entities to **confirm, deny, or clarify**
a qualifying market rumour reported in mainstream media, within **24 hours**
of the triggering **material price movement (MPM)**.

- **Applicability rollout**: the top 100 listed entities by market
  capitalisation from **1 June 2024**; the top 250 from **1 December 2024**;
  market-cap coverage is recalculated annually. Entities outside this set
  have no Regulation 30(11) obligation — a rumour about them can be
  newsworthy but is never "overdue" in the sense defined below.
- **What triggers the clock**: a material price movement, defined by
  intraday price-band thresholds (≥5% for stocks under ₹100, ≥4% for
  ₹100–199.99, ≥3% for ₹200+), adjusted for concurrent Nifty 50/Sensex
  moves of ≥1% in the same direction. The clock starts at the MPM trigger,
  not at the moment the rumour was published — the two are often close but
  not identical.
- **What counts as mainstream media**: a defined list of English national
  dailies, financial dailies, top regional-language dailies, specified
  digital and wire sources (e.g. Reuters, PTI, Bloomberg, Moneycontrol),
  and named business news channels. News aggregators and social media are
  explicitly excluded, even when they're where a user actually saw the
  story — which is precisely why this module treats an official exchange
  filing, not the aggregator or social post, as the ground truth to verify
  against (see the source-authority constraint in §3).
- **What a valid response looks like**: the company may confirm, deny, or
  clarify that the event "has not become disclosable at the present time."
  A response that neither confirms nor denies the substance of the claim
  (e.g. "not in a position to confirm or deny," generic boilerplate about
  routinely evaluating opportunities) is a real, common outcome under this
  regime and is treated in this project as its own category rather than
  forced into confirmed/denied.

### Dataset labels

Three terminal labels, applied only once a case is *ripe* for judgement:

| Label | Meaning |
|---|---|
| `confirmed` | The company's own filing affirmatively states the rumoured fact is accurate. |
| `denied` | The company's own filing affirmatively states the rumoured fact is false, or explicitly disclaims the reported activity as not its own. |
| `unaddressed` | The 24-hour window has elapsed and no substantive confirm/deny exists — either nothing was filed, or what was filed was non-committal. |

A fourth, non-terminal state, `not_yet_due`, exists in the timeline logic
(`src/labels.py::classify_rumour_status`) for real-time use (the demo path
can hit it for a rumour dated within the last 24 hours) but by construction
never appears in the dataset itself: every seed entry is a retrospective,
already-resolved case where the 24-hour window has long since closed. This
is the precise distinction the project brief asks for — "unaddressed" is a
factual finding (the company had an obligation and didn't meet it
substantively), while "not yet due" is simply "ask again later," and
conflating the two would misrepresent a company that is still well within
its compliance window as having failed to respond.

A late confirmation or denial (filed after the 24-hour deadline) is still
labeled `confirmed`/`denied` — the label reflects what actually happened,
not whether the company was timely; timeliness is a separate compliance
question this project doesn't score.

Companies outside the top-250 coverage are out of scope for a mandatory
`unaddressed` finding: silence from an uncovered company is not a
violation, just voluntary non-disclosure, and is excluded from the dataset
entirely rather than mislabeled.

## 2. Dataset

`data/rumour_dataset.json` — **11 real, individually-sourced rumour → filing
pairs**, each with the rumour text, its publication, the company, the
matching filing, the assigned label, a one-sentence rationale quoting the
operative language of the filing, and source URLs. `data/filings_corpus.json`
— the retrieval corpus: those same 11 real filings, plus **24 clearly-marked
synthetic distractors** (`is_real: false, is_synthetic_distractor: true`,
fictional companies) used only to give the retrieval systems something to
be tested against; none of them are presented as real company disclosures.

### Sourcing and labeling method

Each real pair was found via targeted search for actual Regulation 30(11)
filings and their triggering media reports (BSE/NSE announcement archives,
company investor-relations pages, and business-news coverage that quotes
the filing directly), then labeled by reading the filing's own operative
sentence against the confirmed/denied/unaddressed definitions above — not
by inferring intent. One filing (Adani Enterprises, `F001`) was fetched and
read directly from the company's primary-source PDF; the rest are
paraphrased from the filing's quoted text as reported by financial-news
coverage or filing aggregators (Business Standard, BusinessToday,
Trendlyne, TheOutlook, ThePrint, Whalesbook), because the raw BSE/NSE PDF
was not reliably fetchable in this research pass. Two entries (`F002`
Coforge, `F004` IDBI Bank) carry a `notes` field flagging that their exact
date is an approximate placeholder pending direct exchange-archive
verification — flagged rather than presented as fully confirmed, per the
project's verifiable-information principle. Expanding this dataset means
repeating the same method: find the media report, find the company's own
Regulation 30(11) response (BSE/NSE filing, or the company's investor-
relations "corporate announcements" page), quote its operative sentence,
and label from that quote alone.

### Schema

`rumour_dataset.json` entries: `rumour_id`, `company_name`, `ticker_bse`,
`ticker_nse`, `rumour_text`, `rumour_source_publication`, `rumour_date`,
`matching_filing_id` (foreign key into the corpus), `label`,
`label_rationale`, `source_urls`, optional `notes`.

`filings_corpus.json` entries: `filing_id`, `company_name`, `ticker_bse`,
`ticker_nse`, `filing_date`, `filing_type`, `exchanges`, `filing_text`,
`source_url`, `is_real`, `is_synthetic_distractor`, `source_authority`
(`official_exchange_filing` | `news_article`), `determination`
(`confirms` | `denies` | `non_committal` | `null` for filings that aren't
rumour-verification responses at all, e.g. a routine dividend or board
meeting intimation). `determination` is curated ground truth, the same way
a human analyst (or, per the project's future-work note, a downstream
classifier) would tag a filing when adding it to the corpus — it is
deliberately *not* inferred from the filing text at query time by a
keyword classifier, since a classifier tuned to correctly read all 11
filings I hand-picked would just be overfit to my own paraphrasing, not a
real evaluation of anything.

### Distractor design

The 24 synthetic filings exist to make retrieval non-trivial and to give
each of the three constraints something concrete to filter:

- 8 fictional companies each get a routine, non-rumour Reg 30 filing
  (results, ESOP allotment, credit-rating update, KMP change, subsidiary
  incorporation, litigation update, buyback, dividend) as generic noise.
- Several of those same fictional companies also get a *second* filing —
  a genuine rumour-verification response on an unrelated date/topic — so
  the temporal constraint has same-company, wrong-time candidates to reject
  (e.g. `S001` vs. `S009`, both "Meridian Textiles Ltd").
- 4 entries are typed `news_article` rather than `official_exchange_filing`,
  including one (`N003`) that closely paraphrases the real Adani filing
  `F001` — a strong lexical match for the baseline, and exactly what the
  source-authority constraint exists to reject.

## 3. Systems

**Baseline** (`src/retrieval_baseline.py`) — a single TF-IDF vector space
(unigrams + bigrams, English stopwords removed) fit once over the whole
corpus; a rumour is scored against every filing by cosine similarity and
ranked. No knowledge of company identity, dates, or document type.

**Constrained** (`src/retrieval_constrained.py`) — the same baseline
ranking, then three structured filters:

1. **Entity** — the filing's company must be named (by name or ticker) in
   the rumour text. If no company can be recognized in the text at all,
   the filter no-ops rather than rejecting everything (see the
   `min_score` floor below for why that's still safe).
2. **Temporal** — the filing date must fall 0–45 days *after* the rumour
   date. A filing can't verify a rumour that hadn't happened yet.
3. **Source authority** — the candidate must be `official_exchange_filing`,
   not `news_article`.

`ConstrainedRetriever.explain()` returns every candidate annotated with
pass/fail on all three checks and a human-readable reason for each.
`verify_rumour` keeps this full annotated list on `VerificationResult.all_candidates`
(distinct from `.candidates`, which is just the constraint-passing subset)
specifically so a later transparency view could show *every* candidate
considered, not only the winner — see Module 9 below, which is exactly
that later view, reusing this trace rather than re-deriving it.

### Demo path

```
python demo.py "Adani Enterprises shares rally 4% on $686 million investment in not-for-profit healthcare initiative" --date 2025-02-11
```

Returns the matched filing, its date, the confirmed/denied/unaddressed
determination (via `src/labels.py`, combining the filing's curated
`determination` with the Reg 30(11) 24-hour timeline), the similarity
score, and the three constraint reasons for the top match. `verify_rumour`
in `src/verification.py` applies a `min_score` floor (default 0.08) so an
unrelated rumour with no real match honestly reports "no filing passed"
instead of forcing a low-confidence match — this matters because the
entity constraint intentionally no-ops when it can't recognize any company
in the text, so without a score floor an off-topic query could otherwise
"pass" all three constraints against whatever happened to be temporally
in-window. Add `--full-trace` to see every candidate considered, pass or
fail, and which constraint eliminated each one — see Module 9 below.

### Evaluation

```
python -m eval.evaluate
```

Computes MRR and precision@{1,3,5} (plus hit_rate@k, reported alongside
since there is exactly one relevant filing per query and precision@k =
hit_rate@k / k) for both systems against the 11 labeled pairs, ranked
against the full 35-document corpus. Writes `eval/results.md`. Current
result: constrained reaches MRR 1.000 / hit_rate@1 1.000 vs. baseline's
0.914 / 0.909 — a modest, honestly-reported gap (only one query actually
changes rank), consistent with a corpus that was deliberately built with a
few sharp distractors rather than a claim that constraints matter this
much on an arbitrary, much larger real-world filing corpus.

## 4. Running

```
pip install -r requirements.txt
pytest                    # 46 tests: labels, retrieval, verification, eval,
                          # transparency, explanation-quality evaluation
python -m eval.evaluate                 # retrieval accuracy -> eval/results.md
python -m eval.evaluate_explanations    # explanation quality -> eval/explanation_results.md
python demo.py "<rumour text>" --date YYYY-MM-DD
python demo.py "<rumour text>" --date YYYY-MM-DD --full-trace   # Module 9's view
```

The explainable path is also reachable from the running app, not only
from `demo.py`: the backend imports this module through
`backend/app/services/rumour_local_engine.py` and serves it at
`POST /users/{id}/rumour-verification/explain`. That matters more than it
sounds — while `format_full_trace` was CLI-only, the project's
explainability claim was true of this research module and false of the
shipped product.

## Module 9 — Transparency view (`src/transparency.py`)

`explain_all_candidates(result)` and `format_full_trace(result)` turn
`VerificationResult.all_candidates` (every candidate the retrieval and
constraint pipeline considered, computed once at verification time — this
never re-runs retrieval or re-checks constraints) into a full account of
which check(s) eliminated each candidate that didn't win, and why the
winner ranked first among those that survived. Nothing here is recomputed
after the fact; it's a pure formatting pass over the trace `verify_rumour`
already produced.

This is the one place in the whole project where genuine "explanation" /
"explainable" language is appropriate, and it's used deliberately here,
in contrast to the backend's Module 9 transparency layer (see
`backend/README.md`), which is labeled "transparent reasoning" and
explicitly avoids "explainable AI" framing for Modules 3/4/6/7/10's
weighted-sum and rule-table decisions. The distinction: those decisions
*are* just printed weights and a table lookup, so calling that
"explainable AI" would overclaim what a few `if` statements are. This
module runs an actual multi-stage retrieval-then-elimination pipeline
(TF-IDF ranking, then three independent constraint checks, any one of
which can eliminate a candidate, then a similarity floor) — "why did this
filing win and these others lose" is a genuine, non-trivial question with
a real multi-step answer, so "explanation" is an honest word for it here.
It still never claims "AI": TF-IDF cosine similarity and rule-based
filters aren't a model, just a retrieval pipeline worth walking through
step by step.

### The score floor is part of the explanation

`verify_rumour` applies a similarity floor (`min_score`, default 0.08)
*after* the three structured constraints. The trace originally omitted
it, which meant a candidate could pass every check the explanation
mentioned and still not be returned — leaving the trace unable to account
for the answer it accompanied. On one dataset query the trace even
printed "No candidate passed all three constraints" when three had.

The floor is now reported as its own named elimination reason
(`score_floor`) rather than folded into the three constraints, because it
is a different kind of check: a confidence guard on the retrieval score,
not a structured rule about the filing. `CandidateExplanation` carries
`met_score_floor` and `eligible` (passed the constraints *and* cleared
the floor) alongside `passed`.

## Evaluating the explanations (`eval/evaluate_explanations.py`)

`eval/evaluate.py` measures whether retrieval finds the right filing.
That says nothing about whether the trace shown to a user is any good,
and "our explanations are good" was the one claim here that was asserted
rather than measured — the same overclaim the rest of the module is
careful to avoid. This harness scores the trace itself on four properties
that can be checked mechanically:

| Property | Current | What a failure would mean |
|---|---|---|
| Candidate coverage | 1.000 | The trace silently omits candidates the retriever considered |
| Reason coverage | 1.000 | A candidate is shown with no per-check reason line |
| Non-vacuity | 1.000 | Nothing was eliminated, so the trace says nothing interesting |
| Winner-justification soundness | 1.000 | The trace claims the winner ranked first when it didn't |
| Verdict sufficiency | 1.000 | The verdict can't be predicted from the trace alone |

Per-check elimination correctness is measured as precision and recall
against ground truth recomputed independently from the dataset labels and
the corpus — never read back from the trace. Precision is 1.000 for all
four checks: the trace never claims an elimination that didn't happen.

**Verdict sufficiency is the metric that earns the claim.** It asks
whether a reader who saw only the trace could have predicted the answer,
by re-deriving the outcome from nothing but the per-candidate scores and
eligibility flags. It is what caught the missing score floor described
above: sufficiency was 0.909, not 1.000, because one query's verdict was
unreachable from the trace.

**Known finding: entity recall is 0.811, not 1.000.** `mentioned_companies`
scans the rumour text for a corpus company by name or ticker; when it
recognizes none, the entity constraint is treated as satisfied for every
candidate and eliminates nobody. On this dataset that happens for rumours
naming a company in a form the corpus doesn't match exactly ("Vedanta
Aluminium" vs. the corpus's "Vedanta Aluminium Metal Ltd"). This is
documented behaviour, deliberately compensated for by the similarity
floor — but it means the trace's entity line reads as "the entity
constraint did not eliminate this candidate", which on those queries is
weaker than "this is the right company". Reported rather than smoothed
over: an explanation's honest failure mode is part of what a reader needs
in order to trust the rest of it.

Read all of this as a property check on 11 labeled rumours over a
35-document corpus, not as a generalization claim — and note that it
measures whether the trace is *faithful*, not whether it is *useful to a
non-expert*, which is a human-subjects question this harness can't answer.

## Relationship to Module 1's event log

This module still has no *build-time* dependency on Module 1 (backend/) —
its pure logic, tests, and data live entirely in this directory, and
nothing here imports from `backend/`. It is, however, now wired in for
auditability: `backend/app/services/rumour_verification_bridge.py` adds
this directory's `src/` to `sys.path` (the same import style this
module's own files already use internally) and calls `verify_rumour`
completely unchanged, then logs the result via Module 1's
`log_suggestion_event` (`module_source="rumour_verification"`) — exactly
the integration point sketched above, now built as a one-way bridge
rather than a merge. A rumour-verification result is still not quite a
"suggestion" in the `suggestion_event` sense (no accept/edit/reject action
applies to a factual confirmed/denied/unaddressed finding), so the bridge
never sets `action_taken`/`chosen_value`/`funded` — the event exists only
so "a verification was shown to a user" is auditable, which matters for a
transparency-focused project even here. See `backend/README.md`'s Module
5 integration section, and `POST /users/{user_id}/rumour-verification` in
`backend/app/api/routes_rumour_verification.py`.

## 5. Layout

```
data/
  filings_corpus.json     35 filings: 11 real + 24 synthetic distractors
  rumour_dataset.json     11 labeled real rumour -> filing pairs
src/
  labels.py                pure timeline logic: confirmed/denied/unaddressed/not_yet_due
  corpus.py                JSON loaders -> typed Filing / RumourCase
  retrieval_baseline.py     TF-IDF cosine similarity
  retrieval_constrained.py  baseline + entity/temporal/source-authority constraints
  verification.py           demo path: rumour -> matched filing -> status + trace
  transparency.py           Module 9: full per-candidate explanation over
                             VerificationResult.all_candidates (no recomputation)
eval/
  evaluate.py                 retrieval accuracy: baseline vs constrained
  results.md                  generated report (precision@k, MRR)
  evaluate_explanations.py    explanation quality: coverage, elimination
                               correctness, winner soundness, verdict sufficiency
  explanation_results.md      generated report
tests/                      46 pytest tests across all of the above
demo.py                     CLI entry point (--full-trace for Module 9's view)
```
