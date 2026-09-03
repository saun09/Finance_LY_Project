"""Module 8 evaluation harness.

Reports **detector performance on simulated behaviour only**. This has
never been run against real users and nothing here should be read as if
it had been -- see backend/README.md's "future work: real-user
validation" note, which is the only place that gap belongs as a stated
intention, not an accomplishment.

Run with: python -m app.services.drift_evaluation
"""

from dataclasses import dataclass

from app.services.drift_detector import DriftDetectionResult, run_drift_detection
from app.services.drift_personas import ALL_PERSONA_TRACES, PersonaTrace


@dataclass(frozen=True)
class PersonaEvalResult:
    persona_id: str
    persona_name: str
    starting_tier: int
    expected_final_tier: int
    detected_final_tier: int
    recovered_ground_truth: bool
    committed_months: tuple[int, ...]
    detail: DriftDetectionResult


def evaluate_persona(trace: PersonaTrace) -> PersonaEvalResult:
    result = run_drift_detection(trace)
    return PersonaEvalResult(
        persona_id=trace.persona.persona_id,
        persona_name=trace.persona.name,
        starting_tier=trace.persona.ground_truth_tier_start,
        expected_final_tier=trace.persona.ground_truth_tier_end,
        detected_final_tier=result.final_detected_tier,
        recovered_ground_truth=result.final_detected_tier == trace.persona.ground_truth_tier_end,
        committed_months=result.committed_months,
        detail=result,
    )


def evaluate_all_personas() -> list[PersonaEvalResult]:
    return [evaluate_persona(t) for t in ALL_PERSONA_TRACES]


def format_report(results: list[PersonaEvalResult]) -> str:
    lines = ["# Module 8 drift detector -- detector performance on simulated behaviour\n"]
    lines.append(
        "SIMULATED ONLY. Every persona below is a hand-authored synthetic trace, not real user "
        "data. This reports how well the detector recovers a *known, scripted* ground-truth tier "
        "change from that synthetic trace -- it is not evidence of accuracy on real behaviour.\n"
    )

    passed = sum(1 for r in results if r.recovered_ground_truth)
    lines.append(f"**{passed}/{len(results)} personas recovered their scripted ground-truth tier.**\n")

    lines.append("| Persona | Start tier | Expected end tier | Detected end tier | Recovered? | Commits at month(s) |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        mark = "yes" if r.recovered_ground_truth else "NO"
        months = ", ".join(str(m) for m in r.committed_months) or "(none)"
        lines.append(f"| {r.persona_name} | {r.starting_tier} | {r.expected_final_tier} | {r.detected_final_tier} | {mark} | {months} |")

    lines.append("\n## Future work: real-user validation\n")
    lines.append(
        "This detector, its thresholds, and this evaluation have been checked only against the "
        "hand-authored synthetic personas above. Whether the same safeguards (hysteresis depth, "
        "freeze window length, the two-signal-family requirement) hold up against real, noisy user "
        "behaviour is unvalidated and out of scope for this module. Real-user validation is future "
        "work, not a claim made anywhere in this codebase."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    results = evaluate_all_personas()
    report = format_report(results)
    print(report)


if __name__ == "__main__":
    main()
