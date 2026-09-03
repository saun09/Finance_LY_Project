from dataclasses import replace

from app.services.drift_detector import run_drift_detection
from app.services.drift_evaluation import evaluate_all_personas, format_report
from app.services.drift_personas import ALL_PERSONA_TRACES


def test_all_five_personas_are_defined():
    assert len(ALL_PERSONA_TRACES) == 5
    assert len({t.persona.persona_id for t in ALL_PERSONA_TRACES}) == 5  # distinct ids


def test_detector_recovers_every_persona_ground_truth_tier():
    results = evaluate_all_personas()
    failures = [r for r in results if not r.recovered_ground_truth]
    assert failures == [], f"detector failed to recover ground truth for: {[r.persona_id for r in failures]}"


def test_at_least_one_persona_drifts_up_and_one_drifts_down():
    results = evaluate_all_personas()
    assert any(r.detected_final_tier > r.starting_tier for r in results)
    assert any(r.detected_final_tier < r.starting_tier for r in results)


def test_at_least_two_personas_are_negative_controls_with_no_drift():
    results = evaluate_all_personas()
    no_drift = [r for r in results if r.detected_final_tier == r.starting_tier]
    assert len(no_drift) >= 2


def test_report_is_explicitly_labeled_simulated_only():
    report = format_report(evaluate_all_personas())
    assert "simulated behaviour" in report.lower()
    assert "SIMULATED ONLY" in report
    assert "future work: real-user validation" in report.lower()
    assert "not evidence of accuracy on real behaviour" in report


def test_report_never_claims_real_user_validation():
    report = format_report(evaluate_all_personas())
    lowered = report.lower()
    # the only occurrences of "real" should be inside the explicit
    # "future work: real-user validation" framing or the disclaimer text,
    # never asserting validation has actually happened
    assert "validated on real" not in lowered
    assert "tested on real users" not in lowered
    assert "proven on real" not in lowered


def test_freeze_window_is_load_bearing_for_the_panic_persona():
    # Not just that the persona ends at the right tier -- specifically
    # that removing the freeze window changes the outcome, proving the
    # safeguard does real work rather than being redundant with the
    # two-signal-family requirement.
    panic_trace = next(t for t in ALL_PERSONA_TRACES if t.persona.persona_id == "market_panic_recovery")

    with_freeze = run_drift_detection(panic_trace)
    without_freeze = run_drift_detection(replace(panic_trace, drawdown_month_index=None))

    assert with_freeze.committed_months == ()
    assert without_freeze.committed_months != ()  # the freeze suppressed a real commit that would otherwise happen
    assert any(c.reference_tier_after < c.reference_tier_before for c in without_freeze.cycles if c.committed)
