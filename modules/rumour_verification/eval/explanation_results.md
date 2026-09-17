# Explanation quality - evaluation results

Evaluated on the 11 labeled rumour/filing pairs in `data/rumour_dataset.json`. This measures the *trace*, not retrieval accuracy; for the latter see `results.md`.

## Summary

| Property | Score | What a failure would mean |
|---|---|---|
| Candidate coverage | 1.000 | The trace silently omits candidates the retriever considered. |
| Reason coverage | 1.000 | A candidate is shown with no per-constraint reason line. |
| Non-vacuity | 1.000 | Queries where nothing was eliminated, so the trace says nothing interesting. |
| Winner-justification soundness | 1.000 | The trace claims the winner ranked first among passing candidates when it did not. |
| Verdict sufficiency | 1.000 | The verdict cannot be predicted from the trace alone -- i.e. the explanation is a story told alongside the answer rather than the reason for it. |

## Elimination correctness, per constraint

Each constraint is recomputed independently from the dataset labels and the corpus, then compared with what the trace claimed. Precision: of the eliminations the trace claimed, how many were real. Recall: of the eliminations that should have been claimed, how many were.

| Constraint | Claimed | Expected | Agreed | Precision | Recall |
|---|---|---|---|---|---|
| entity | 301 | 371 | 301 | 1.000 | 0.811 |
| temporal | 353 | 353 | 353 | 1.000 | 1.000 |
| source_authority | 44 | 44 | 44 | 1.000 | 1.000 |
| score_floor | 355 | 355 | 355 | 1.000 | 1.000 |

## Volume

- Queries evaluated: 11
- Candidate explanations produced: 385
- Candidates considered by the retriever: 385

## Disagreements

70 case(s) across 3 rumour(s) where the trace and independently recomputed ground truth disagree. Grouped by rumour, with one example each; a disagreement is a finding, not noise to be tuned away.

| Rumour | Cases | Example |
|---|---|---|
| R005 | 34 | R005/F011: trace does not claim entity, ground truth expects it |
| R006 | 34 | R006/S017: trace does not claim entity, ground truth expects it |
| R010 | 2 | R010/F008: trace does not claim entity, ground truth expects it |

## Known finding: the entity check no-ops on unrecognized companies

Entity recall is 0.811, not 1.000, and this is a real property of the system rather than a measurement artefact. `mentioned_companies` scans the rumour text for a corpus company by name or ticker; when it recognizes none, `ConstrainedRetriever._annotate` treats the entity constraint as satisfied for every candidate (`entity_ok = (not mentioned) or ...`). On this dataset that happens for rumours naming a company in a form the corpus does not match exactly (for example "Vedanta Aluminium" against the corpus's "Vedanta Aluminium Metal Ltd"), and the entity constraint then eliminates nobody.

The behaviour is documented and deliberately compensated for -- `verify_rumour` applies the similarity floor precisely so an unconstrained query is reported as no-match rather than as a confident wrong answer -- but it means the trace's entity line should be read as "the entity constraint did not eliminate this candidate", which on those queries is weaker than "this candidate is the right company". Recorded here rather than smoothed over: an explanation's honest failure mode is part of what a reader needs in order to trust the rest of it.

## How to read this

High scores here mean the trace is faithful to the pipeline that produced the answer -- that it names real eliminations, makes a winner claim that holds, and contains enough information to re-derive the verdict. They do NOT mean the explanation is *useful* to a non-expert reader; that is a human-subjects question this harness cannot answer. They also do not generalize beyond this 35-document corpus and 11 labeled rumours. The entity check is grounded in the dataset's own `company_name` label rather than the retriever's text-scanning heuristic, so entity agreement is evidence rather than the system marking its own homework.
