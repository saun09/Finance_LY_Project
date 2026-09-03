"""Timeline logic for labeling a rumour's verification status.

Implements the confirmed / denied / unaddressed framing derived from SEBI
LODR Regulation 30(11) (see ../README.md for the full regulatory write-up):
a covered listed entity must confirm, deny, or clarify a qualifying market
rumour within 24 hours of the triggering material price movement (MPM).

This module is a pure, deterministic function plus its supporting types —
no I/O, no model calls — per the project's convention that scoring/labeling
logic must be independently unit-testable.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

RumourLabel = Literal["confirmed", "denied", "unaddressed", "not_yet_due"]
ResponseDetermination = Literal["confirms", "denies", "non_committal"]

RESPONSE_WINDOW_HOURS = 24  # SEBI LODR Regulation 30(11)


@dataclass(frozen=True)
class FilingResponse:
    """What (if anything) the company has filed in reply to the rumour.

    `determination` is None when no filing exists yet, or "non_committal"
    when a filing exists but does not confirm or deny the rumoured fact
    (e.g. "not in a position to confirm or deny", or a generic statement
    that doesn't engage with the specific claim).
    """

    exists: bool
    filed_at: datetime | None = None
    determination: ResponseDetermination | None = None


def classify_rumour_status(
    *,
    mpm_trigger_at: datetime,
    evaluated_at: datetime,
    response: FilingResponse,
    response_window_hours: int = RESPONSE_WINDOW_HOURS,
) -> RumourLabel:
    """Determine a rumour's status as of `evaluated_at`.

    Precedence:
    1. A substantive confirm/deny always wins, regardless of whether it
       arrived inside the 24-hour window — a late confirmation is still
       ground truth about what happened, even though the company was
       non-compliant with the timeline in filing it late.
    2. Otherwise, if the 24-hour deadline has not yet elapsed, the rumour
       is simply "not_yet_due" — there is no failure to explain yet.
    3. Otherwise (deadline elapsed, no substantive confirm/deny — whether
       because nothing was filed, or because what was filed was
       non-committal), the rumour is "unaddressed".
    """
    if response.exists and response.determination in ("confirms", "denies"):
        return "confirmed" if response.determination == "confirms" else "denied"

    deadline = mpm_trigger_at + timedelta(hours=response_window_hours)
    if evaluated_at < deadline:
        return "not_yet_due"

    return "unaddressed"
