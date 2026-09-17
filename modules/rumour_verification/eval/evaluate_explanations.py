"""Evaluation harness for the *explanations*, not the retrieval.

`eval/evaluate.py` answers "does constrained retrieval find the right
filing more often than TF-IDF alone" -- a ranking question. It says
nothing about whether the trace this project shows a user is any good,
and "our explanations are good" is the one claim in Module 9 that was
previously asserted rather than measured. Claiming genuine explainability
while only ever evaluating accuracy is exactly the overclaim the rest of
the module is careful to avoid.

So this harness scores the trace itself, on four properties that can be
checked mechanically against ground truth rather than judged by taste:

1. COVERAGE -- does every candidate the retriever considered actually get
   an explanation, with at least one reason line? An explanation that
   silently omits candidates is worse than none, because the omission is
   invisible.

2. ELIMINATION CORRECTNESS -- when the trace says "eliminated by
   temporal", is that independently true? Each of the three constraints
   is recomputed here from the labeled dataset and the corpus, NOT read
   back from the trace, and the two are compared. Per-constraint
   precision (of the eliminations claimed, how many were real) and recall
   (of the eliminations that should have been claimed, how many were).
   The entity check is deliberately grounded in the dataset's own
   `company_name` label rather than the retriever's text-scanning
   heuristic, so agreement here is evidence rather than tautology.

3. WINNER-JUSTIFICATION SOUNDNESS -- the trace claims the winner "ranked
   first among the candidates that passed all three constraints". That is
   a falsifiable claim: it holds only if the winner really is the
   highest-scoring passing candidate. Checked on every query.

4. SUFFICIENCY -- could a reader who saw only the trace have predicted
   the verdict? Reconstruct the outcome using nothing but the per-
   candidate scores and pass flags the trace exposes, and compare it to
   what the system actually returned. This is the strongest of the four:
   it tests whether the explanation is *the* reason for the answer rather
   than a plausible story told alongside it.

Run with:

    python -m eval.evaluate_explanations

Read the numbers as a property check on a seed set of 11 labeled
rumours, not as a generalization claim.
"""

from dataclasses import dataclass, field
from pathlib import Path

from src.corpus import Filing, RumourCase, load_corpus, load_rumour_dataset
from src.retrieval_constrained import DEFAULT_MAX_DAYS_AFTER, normalize_company_name
from src.transparency import explain_all_candidates, format_full_trace
from src.verification import verify_rumour

RESULTS_PATH = Path(__file__).resolve().parent / "explanation_results.md"

#: Includes the similarity floor, which is a real elimination reason and
#: must therefore be one the trace is scored on -- it was omitted from the
#: trace originally, and that omission is what the sufficiency metric caught.
CONSTRAINTS = ("entity", "temporal", "source_authority", "score_floor")


# --------------------------------------------------------------------------
# Ground truth, recomputed independently of the trace under test
# --------------------------------------------------------------------------


def expected_failed_constraints(filing: Filing, case: RumourCase, score: float, min_score: float) -> set[str]:
    """Which constraints a candidate *should* fail, derived from the labeled
    dataset and the corpus rather than from the system's own output."""
    failed = set()

    if normalize_company_name(filing.company_name) != normalize_company_name(case.company_name):
        failed.add("entity")

    days_after = (filing.filing_date - case.rumour_date).days
    if not (0 <= days_after <= DEFAULT_MAX_DAYS_AFTER):
        failed.add("temporal")

    if filing.source_authority != "official_exchange_filing":
        failed.add("source_authority")

    if score < min_score:
        failed.add("score_floor")

    return failed


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


@dataclass
class ConstraintCounts:
    claimed: int = 0           # trace said this constraint eliminated the candidate
    actual: int = 0            # ground truth says it should have
    agreed: int = 0            # both

    @property
    def precision(self) -> float:
        return self.agreed / self.claimed if self.claimed else 1.0

    @property
    def recall(self) -> float:
        return self.agreed / self.actual if self.actual else 1.0


@dataclass
class ExplanationMetrics:
    queries: int = 0
    candidates_explained: int = 0
    candidates_considered: int = 0
    candidates_with_reasons: int = 0
    queries_with_any_elimination: int = 0
    winner_claims_checked: int = 0
    winner_claims_sound: int = 0
    sufficiency_checked: int = 0
    sufficiency_reproduced: int = 0
    per_constraint: dict[str, ConstraintCounts] = field(
        default_factory=lambda: {c: ConstraintCounts() for c in CONSTRAINTS}
    )
    disagreements: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        return self.candidates_explained / self.candidates_considered if self.candidates_considered else 0.0

    @property
    def reason_coverage(self) -> float:
        return self.candidates_with_reasons / self.candidates_explained if self.candidates_explained else 0.0

    @property
    def non_vacuity(self) -> float:
        return self.queries_with_any_elimination / self.queries if self.queries else 0.0

    @property
    def winner_soundness(self) -> float:
        return self.winner_claims_sound / self.winner_claims_checked if self.winner_claims_checked else 1.0

    @property
    def sufficiency(self) -> float:
        return self.sufficiency_reproduced / self.sufficiency_checked if self.sufficiency_checked else 0.0


def evaluate_explanations(corpus: list[Filing], dataset: list[RumourCase]) -> ExplanationMetrics:
    metrics = ExplanationMetrics()
    by_id = {f.filing_id: f for f in corpus}

    for case in dataset:
        result = verify_rumour(case.rumour_text, corpus, rumour_date=case.rumour_date)
        explanations = explain_all_candidates(result)

        metrics.queries += 1
        metrics.candidates_considered += len(result.all_candidates)
        metrics.candidates_explained += len(explanations)

        eliminated_here = 0
        for e in explanations:
            if e.reasons:
                metrics.candidates_with_reasons += 1

            claimed = set(e.failed_constraints)
            expected = expected_failed_constraints(by_id[e.filing_id], case, e.score, result.min_score)
            if claimed:
                eliminated_here += 1

            for constraint in CONSTRAINTS:
                counts = metrics.per_constraint[constraint]
                in_claimed = constraint in claimed
                in_expected = constraint in expected
                counts.claimed += int(in_claimed)
                counts.actual += int(in_expected)
                counts.agreed += int(in_claimed and in_expected)
                if in_claimed != in_expected:
                    metrics.disagreements.append(
                        f"{case.rumour_id}/{e.filing_id}: trace "
                        f"{'claims' if in_claimed else 'does not claim'} {constraint}, "
                        f"ground truth {'expects' if in_expected else 'does not expect'} it"
                    )

        if eliminated_here:
            metrics.queries_with_any_elimination += 1

        # 3. Is the winner-ranked-first claim actually true?
        winner = next((e for e in explanations if e.is_winner), None)
        if winner is not None:
            metrics.winner_claims_checked += 1
            passing_scores = [e.score for e in explanations if e.eligible]
            if passing_scores and winner.score >= max(passing_scores):
                metrics.winner_claims_sound += 1
            else:
                metrics.disagreements.append(
                    f"{case.rumour_id}: winner {winner.filing_id} scored {winner.score:.3f} but a "
                    f"passing candidate scored {max(passing_scores):.3f}"
                )

        # 4. Could the verdict be predicted from the trace alone?
        metrics.sufficiency_checked += 1
        eligible = [e for e in explanations if e.eligible]
        predicted = max(eligible, key=lambda e: e.score).filing_id if eligible else None
        actual = result.matched_filing.filing_id if result.matched_filing else None
        if predicted == actual:
            metrics.sufficiency_reproduced += 1
        else:
            metrics.disagreements.append(
                f"{case.rumour_id}: trace implies {predicted}, system returned {actual}"
            )

    return metrics


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def format_report(metrics: ExplanationMetrics, dataset: list[RumourCase]) -> str:
    lines = ["# Explanation quality - evaluation results\n"]
    lines.append(
        f"Evaluated on the {len(dataset)} labeled rumour/filing pairs in "
        "`data/rumour_dataset.json`. This measures the *trace*, not retrieval accuracy; "
        "for the latter see `results.md`.\n"
    )

    lines.append("## Summary\n")
    lines.append("| Property | Score | What a failure would mean |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Candidate coverage | {metrics.coverage:.3f} | "
        "The trace silently omits candidates the retriever considered. |"
    )
    lines.append(
        f"| Reason coverage | {metrics.reason_coverage:.3f} | "
        "A candidate is shown with no per-constraint reason line. |"
    )
    lines.append(
        f"| Non-vacuity | {metrics.non_vacuity:.3f} | "
        "Queries where nothing was eliminated, so the trace says nothing interesting. |"
    )
    lines.append(
        f"| Winner-justification soundness | {metrics.winner_soundness:.3f} | "
        "The trace claims the winner ranked first among passing candidates when it did not. |"
    )
    lines.append(
        f"| Verdict sufficiency | {metrics.sufficiency:.3f} | "
        "The verdict cannot be predicted from the trace alone -- i.e. the explanation is a "
        "story told alongside the answer rather than the reason for it. |"
    )
    lines.append("")

    lines.append("## Elimination correctness, per constraint\n")
    lines.append(
        "Each constraint is recomputed independently from the dataset labels and the corpus, "
        "then compared with what the trace claimed. Precision: of the eliminations the trace "
        "claimed, how many were real. Recall: of the eliminations that should have been claimed, "
        "how many were.\n"
    )
    lines.append("| Constraint | Claimed | Expected | Agreed | Precision | Recall |")
    lines.append("|---|---|---|---|---|---|")
    for constraint in CONSTRAINTS:
        c = metrics.per_constraint[constraint]
        lines.append(
            f"| {constraint} | {c.claimed} | {c.actual} | {c.agreed} | "
            f"{c.precision:.3f} | {c.recall:.3f} |"
        )
    lines.append("")

    lines.append("## Volume\n")
    lines.append(f"- Queries evaluated: {metrics.queries}")
    lines.append(f"- Candidate explanations produced: {metrics.candidates_explained}")
    lines.append(f"- Candidates considered by the retriever: {metrics.candidates_considered}")
    lines.append("")

    lines.append("## Disagreements\n")
    if not metrics.disagreements:
        lines.append("None. Every elimination the trace claimed was independently verifiable, every "
                     "winner-ranked-first claim held, and every verdict was reproducible from the "
                     "trace alone.\n")
    else:
        grouped: dict[str, list[str]] = {}
        for d in metrics.disagreements:
            rumour_id = d.split("/")[0].split(":")[0]
            grouped.setdefault(rumour_id, []).append(d)
        lines.append(
            f"{len(metrics.disagreements)} case(s) across {len(grouped)} rumour(s) where the trace "
            "and independently recomputed ground truth disagree. Grouped by rumour, with one "
            "example each; a disagreement is a finding, not noise to be tuned away.\n"
        )
        lines.append("| Rumour | Cases | Example |")
        lines.append("|---|---|---|")
        for rumour_id in sorted(grouped):
            cases = grouped[rumour_id]
            lines.append(f"| {rumour_id} | {len(cases)} | {cases[0]} |")
        lines.append("")

    entity = metrics.per_constraint["entity"]
    if entity.recall < 1.0:
        lines.append("## Known finding: the entity check no-ops on unrecognized companies\n")
        lines.append(
            f"Entity recall is {entity.recall:.3f}, not 1.000, and this is a real property of the "
            "system rather than a measurement artefact. `mentioned_companies` scans the rumour "
            "text for a corpus company by name or ticker; when it recognizes none, "
            "`ConstrainedRetriever._annotate` treats the entity constraint as satisfied for every "
            "candidate (`entity_ok = (not mentioned) or ...`). On this dataset that happens for "
            "rumours naming a company in a form the corpus does not match exactly (for example "
            '"Vedanta Aluminium" against the corpus\'s "Vedanta Aluminium Metal Ltd"), and the '
            "entity constraint then eliminates nobody.\n"
        )
        lines.append(
            "The behaviour is documented and deliberately compensated for -- `verify_rumour` "
            "applies the similarity floor precisely so an unconstrained query is reported as "
            "no-match rather than as a confident wrong answer -- but it means the trace's entity "
            'line should be read as "the entity constraint did not eliminate this candidate", '
            'which on those queries is weaker than "this candidate is the right company". '
            "Recorded here rather than smoothed over: an explanation's honest failure mode is "
            "part of what a reader needs in order to trust the rest of it.\n"
        )

    lines.append("## How to read this\n")
    lines.append(
        "High scores here mean the trace is faithful to the pipeline that produced the answer -- "
        "that it names real eliminations, makes a winner claim that holds, and contains enough "
        "information to re-derive the verdict. They do NOT mean the explanation is *useful* to a "
        "non-expert reader; that is a human-subjects question this harness cannot answer. They "
        "also do not generalize beyond this 35-document corpus and 11 labeled rumours. The "
        "entity check is grounded in the dataset's own `company_name` label rather than the "
        "retriever's text-scanning heuristic, so entity agreement is evidence rather than the "
        "system marking its own homework."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    corpus = load_corpus()
    dataset = load_rumour_dataset()
    metrics = evaluate_explanations(corpus, dataset)
    report = format_report(metrics, dataset)
    print(report)
    RESULTS_PATH.write_text(report, encoding="utf-8")
    print(f"\nWrote {RESULTS_PATH}")

    sample = verify_rumour(dataset[0].rumour_text, corpus, rumour_date=dataset[0].rumour_date)
    print("\n--- Sample trace (first dataset case) ---\n")
    print(format_full_trace(sample))


if __name__ == "__main__":
    main()
