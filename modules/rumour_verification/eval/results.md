# Baseline vs. constrained retrieval - evaluation results

Evaluated on the 11 labeled real rumour/filing pairs in `data/rumour_dataset.json`, ranked against the full `data/filings_corpus.json` corpus (11 real target filings + 24 distractors).

## Summary

| Metric | Baseline (TF-IDF only) | Constrained (+ entity/temporal/source) |
|---|---|---|
| MRR | 0.914 | 1.000 |
| Precision@1 | 0.909 | 1.000 |
| Precision@3 | 0.303 | 0.333 |
| Precision@5 | 0.182 | 0.200 |
| hit_rate@1 | 0.909 | 1.000 |
| hit_rate@3 | 0.909 | 1.000 |
| hit_rate@5 | 0.909 | 1.000 |

## Per-query rank of the correct filing

| Rumour | Baseline rank | Constrained rank |
|---|---|---|
| R001 (Adani Enterprises Ltd) | 1 | 1 |
| R002 (Coforge Ltd) | 1 | 1 |
| R003 (Gensol Engineering Ltd) | 1 | 1 |
| R004 (IDBI Bank Ltd) | 1 | 1 |
| R005 (Vedanta Aluminium Metal Ltd) | 18 | 1 |
| R006 (Ola Electric Mobility Ltd) | 1 | 1 |
| R007 (One97 Communications Ltd) | 1 | 1 |
| R008 (One97 Communications Ltd) | 1 | 1 |
| R009 (Mphasis Ltd) | 1 | 1 |
| R010 (Jio Financial Services Ltd) | 1 | 1 |
| R011 (IndusInd Bank Ltd) | 1 | 1 |

## Does structured retrieval outperform text similarity alone?

Yes, on this seed set. The constrained system reaches MRR=1.000 vs. baseline MRR=0.914, and hit_rate@1=1.000 vs. baseline hit_rate@1=0.909. The correct filing's rank improved (moved strictly closer to #1) for 1/11 rumours when constraints were added. The corpus was deliberately built with near-duplicate lexical distractors (a news-article paraphrase of a real filing, and same-company filings on unrelated dates) specifically to give text similarity something to get wrong and the constraints something to fix; the gap should be read as evidence the constraints are doing real filtering work here, not as a claim it generalizes to an unconstrained, much larger real-world filing corpus without further evaluation.
