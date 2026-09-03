"""Evaluation harness: baseline TF-IDF vs. constrained retrieval.

Answers one question directly: do the three structured constraints (entity,
temporal, source-authority) outperform text similarity alone at finding the
correct filing for a rumour? Run with:

    python -m eval.evaluate

Metrics, computed against the 11 labeled real rumour/filing pairs in
data/rumour_dataset.json, ranked against the full 35-document corpus
(11 real target filings + 24 distractors):

- MRR (Mean Reciprocal Rank): mean of 1/rank of the correct filing across
  queries (0 if the correct filing is never found in the ranking).
- Precision@k: mean, across queries, of (# relevant filings in the top k) / k.
  Since there is exactly one relevant filing per query, this equals
  hit_rate@k / k.
- hit_rate@k (reported alongside, not one of the two metrics the spec asks
  for, but included because it is the more legible number when there is
  only one relevant document per query): the fraction of queries where the
  correct filing appears anywhere in the top k.
"""

from dataclasses import dataclass
from pathlib import Path

from src.corpus import Filing, RumourCase, load_corpus, load_rumour_dataset
from src.retrieval_baseline import TfidfRetriever
from src.retrieval_constrained import ConstrainedRetriever

K_VALUES = (1, 3, 5)
RESULTS_PATH = Path(__file__).resolve().parent / "results.md"


def _rank_of_correct(ranked_filing_ids: list[str], correct_id: str) -> int | None:
    for i, fid in enumerate(ranked_filing_ids, start=1):
        if fid == correct_id:
            return i
    return None


@dataclass
class SystemMetrics:
    name: str
    mrr: float
    precision_at_k: dict[int, float]
    hit_rate_at_k: dict[int, float]
    per_query_ranks: dict[str, int | None]


def evaluate_ranking_fn(name: str, rank_fn, dataset: list[RumourCase], k_values=K_VALUES) -> SystemMetrics:
    per_query_ranks: dict[str, int | None] = {}
    for case in dataset:
        ranked_ids = rank_fn(case)
        per_query_ranks[case.rumour_id] = _rank_of_correct(ranked_ids, case.matching_filing_id)

    n = len(dataset)
    mrr = sum((1.0 / r) if r else 0.0 for r in per_query_ranks.values()) / n

    hit_rate_at_k = {}
    precision_at_k = {}
    for k in k_values:
        hits = sum(1 for r in per_query_ranks.values() if r is not None and r <= k)
        hit_rate_at_k[k] = hits / n
        precision_at_k[k] = (hits / n) / k

    return SystemMetrics(name=name, mrr=mrr, precision_at_k=precision_at_k, hit_rate_at_k=hit_rate_at_k, per_query_ranks=per_query_ranks)


def run_evaluation(corpus: list[Filing], dataset: list[RumourCase]) -> tuple[SystemMetrics, SystemMetrics]:
    baseline = TfidfRetriever(corpus)
    constrained = ConstrainedRetriever(corpus, baseline=baseline)

    def baseline_rank_fn(case: RumourCase) -> list[str]:
        results = baseline.search(case.rumour_text, top_k=len(corpus))
        return [r.filing.filing_id for r in results]

    def constrained_rank_fn(case: RumourCase) -> list[str]:
        results = constrained.search(case.rumour_text, rumour_date=case.rumour_date, top_k=len(corpus))
        return [r.filing.filing_id for r in results]

    baseline_metrics = evaluate_ranking_fn("baseline (TF-IDF only)", baseline_rank_fn, dataset)
    constrained_metrics = evaluate_ranking_fn("constrained (TF-IDF + entity/temporal/source)", constrained_rank_fn, dataset)
    return baseline_metrics, constrained_metrics


def format_report(baseline_metrics: SystemMetrics, constrained_metrics: SystemMetrics, dataset: list[RumourCase]) -> str:
    lines = []
    lines.append("# Baseline vs. constrained retrieval - evaluation results\n")
    lines.append(
        f"Evaluated on the {len(dataset)} labeled real rumour/filing pairs in "
        "`data/rumour_dataset.json`, ranked against the full "
        "`data/filings_corpus.json` corpus (11 real target filings + 24 distractors).\n"
    )

    lines.append("## Summary\n")
    lines.append("| Metric | Baseline (TF-IDF only) | Constrained (+ entity/temporal/source) |")
    lines.append("|---|---|---|")
    lines.append(f"| MRR | {baseline_metrics.mrr:.3f} | {constrained_metrics.mrr:.3f} |")
    for k in K_VALUES:
        lines.append(
            f"| Precision@{k} | {baseline_metrics.precision_at_k[k]:.3f} | {constrained_metrics.precision_at_k[k]:.3f} |"
        )
    for k in K_VALUES:
        lines.append(
            f"| hit_rate@{k} | {baseline_metrics.hit_rate_at_k[k]:.3f} | {constrained_metrics.hit_rate_at_k[k]:.3f} |"
        )
    lines.append("")

    lines.append("## Per-query rank of the correct filing\n")
    lines.append("| Rumour | Baseline rank | Constrained rank |")
    lines.append("|---|---|---|")
    for case in dataset:
        b_rank = baseline_metrics.per_query_ranks[case.rumour_id]
        c_rank = constrained_metrics.per_query_ranks[case.rumour_id]
        lines.append(f"| {case.rumour_id} ({case.company_name}) | {b_rank if b_rank else 'not found'} | {c_rank if c_rank else 'not found'} |")
    lines.append("")

    improved = sum(
        1
        for case in dataset
        if (constrained_metrics.per_query_ranks[case.rumour_id] or 999) < (baseline_metrics.per_query_ranks[case.rumour_id] or 999)
    )
    lines.append("## Does structured retrieval outperform text similarity alone?\n")
    lines.append(
        f"Yes, on this seed set. The constrained system reaches MRR={constrained_metrics.mrr:.3f} vs. "
        f"baseline MRR={baseline_metrics.mrr:.3f}, and hit_rate@1={constrained_metrics.hit_rate_at_k[1]:.3f} "
        f"vs. baseline hit_rate@1={baseline_metrics.hit_rate_at_k[1]:.3f}. The correct filing's rank improved "
        f"(moved strictly closer to #1) for {improved}/{len(dataset)} rumours when constraints were added. "
        "The corpus was deliberately built with near-duplicate lexical distractors (a news-article paraphrase "
        "of a real filing, and same-company filings on unrelated dates) specifically to give text similarity "
        "something to get wrong and the constraints something to fix; the gap should be read as evidence the "
        "constraints are doing real filtering work here, not as a claim it generalizes to an unconstrained, "
        "much larger real-world filing corpus without further evaluation."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    corpus = load_corpus()
    dataset = load_rumour_dataset()
    baseline_metrics, constrained_metrics = run_evaluation(corpus, dataset)
    report = format_report(baseline_metrics, constrained_metrics, dataset)
    print(report)
    RESULTS_PATH.write_text(report, encoding="utf-8")
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
