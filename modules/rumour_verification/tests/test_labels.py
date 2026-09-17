from datetime import datetime, timedelta

from src.labels import FilingResponse, classify_rumour_status

T0 = datetime(2026, 2, 11, 10, 0, 0)  # MPM trigger


def test_confirmed_within_window():
    response = FilingResponse(exists=True, filed_at=T0 + timedelta(hours=5), determination="confirms")
    label = classify_rumour_status(mpm_trigger_at=T0, evaluated_at=T0 + timedelta(hours=6), response=response)
    assert label == "confirmed"


def test_denied_within_window():
    response = FilingResponse(exists=True, filed_at=T0 + timedelta(hours=5), determination="denies")
    label = classify_rumour_status(mpm_trigger_at=T0, evaluated_at=T0 + timedelta(hours=6), response=response)
    assert label == "denied"


def test_late_confirmation_still_counts_as_confirmed():
    # Filed after the 24h deadline: non-compliant with the timeline, but a
    # confirmation is still ground truth about what actually happened.
    response = FilingResponse(exists=True, filed_at=T0 + timedelta(hours=48), determination="confirms")
    label = classify_rumour_status(mpm_trigger_at=T0, evaluated_at=T0 + timedelta(hours=50), response=response)
    assert label == "confirmed"


def test_no_filing_before_deadline_is_not_yet_due():
    response = FilingResponse(exists=False)
    label = classify_rumour_status(mpm_trigger_at=T0, evaluated_at=T0 + timedelta(hours=10), response=response)
    assert label == "not_yet_due"


def test_no_filing_at_exact_deadline_is_unaddressed():
    # The 24h window is a closed interval: the moment it elapses, an
    # unmet response obligation becomes "unaddressed", not still-pending.
    response = FilingResponse(exists=False)
    label = classify_rumour_status(mpm_trigger_at=T0, evaluated_at=T0 + timedelta(hours=24), response=response)
    assert label == "unaddressed"


def test_no_filing_after_deadline_is_unaddressed():
    response = FilingResponse(exists=False)
    label = classify_rumour_status(
        mpm_trigger_at=T0, evaluated_at=T0 + timedelta(hours=24, seconds=1), response=response
    )
    assert label == "unaddressed"


def test_non_committal_filing_before_deadline_is_not_yet_due():
    response = FilingResponse(exists=True, filed_at=T0 + timedelta(hours=2), determination="non_committal")
    label = classify_rumour_status(mpm_trigger_at=T0, evaluated_at=T0 + timedelta(hours=10), response=response)
    assert label == "not_yet_due"


def test_non_committal_filing_after_deadline_is_unaddressed():
    response = FilingResponse(exists=True, filed_at=T0 + timedelta(hours=2), determination="non_committal")
    label = classify_rumour_status(mpm_trigger_at=T0, evaluated_at=T0 + timedelta(hours=25), response=response)
    assert label == "unaddressed"


def test_custom_response_window_is_respected():
    response = FilingResponse(exists=False)
    label = classify_rumour_status(
        mpm_trigger_at=T0, evaluated_at=T0 + timedelta(hours=10), response=response, response_window_hours=8
    )
    assert label == "unaddressed"
