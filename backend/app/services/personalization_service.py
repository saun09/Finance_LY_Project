"""Wires Module 7's pure EWMA/offset logic to Module 1's event log and
Module 4's allocation suggestions. No new tables: the offset is always
replayed from suggestion_event history (module_source="allocation" events
that have a recorded outcome), the same "read the event log, don't store
derived state" pattern Modules 3/4/6 already use.

The loop, end to end:

1. Module 4 computes the tier's base target, then asks
   `compute_personalized_target` for the offset and the displayed mix,
   and logs both on one allocation event (allocation_service.py).
2. The user responds to *that* event (`record_allocation_outcome`):
   accept, set their own mix, or reject with a reason. Whether they
   actually invested can be added later (`mark_allocation_funded`).
3. The next computation replays every recorded response, so the new
   evidence -- and any later funded update -- is reflected automatically.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.suggestion_event import ActionTaken, SuggestionEvent
from app.services.allocation import compute_target_allocation
from app.services.asset_classification_config import AssetClass
from app.services.event_log import (
    get_user_event_history,
    log_suggestion_event_if_changed,
    record_suggestion_outcome,
)
from app.services.personalization import (
    DEFAULT_ALPHA,
    REJECT_REASON_CODES,
    AllocationEdit,
    EditActionTaken,
    OffsetCapResult,
    OffsetStep,
    apply_personalization_offset,
    compute_offset_from_edits,
    describe_offset_cap,
)

# A user-entered mix may be off 100 by a rounding hair (five classes, each
# rounded to 2 dp on the client); anything further off is a broken request.
_CHOSEN_SUM_TOLERANCE = Decimal("0.05")


class NoAllocationSuggestionError(ValueError):
    pass


class NoRiskTierError(ValueError):
    pass


class AllocationEventNotFoundError(ValueError):
    pass


class InvalidAllocationOutcomeError(ValueError):
    pass


@dataclass(frozen=True)
class PersonalizedTarget:
    offset_pct_points: Decimal
    trace: tuple[OffsetStep, ...]
    edits_considered: int
    base_target_pct: dict[AssetClass, Decimal]
    displayed_target_pct: dict[AssetClass, Decimal]
    cap: OffsetCapResult
    capacity_ceiling: int
    # the Module 3 capacity components sitting at the ceiling -- what the
    # user would have to improve for the cap to lift
    capacity_binding_constraints: tuple[str, ...]
    final_tier: int
    alpha: Decimal


# Kept as a name for existing callers; it's the same shape.
PersonalizationResult = PersonalizedTarget


def _base_equity_of(suggested_value: dict) -> Decimal:
    # `target_pct` on an allocation event is always the tier's base target
    # (the offset-adjusted mix is stored separately as
    # `displayed_target_pct`), so this reads correctly for events logged
    # both before and after the display was personalized.
    return Decimal(suggested_value["target_pct"]["equity"])


def _load_allocation_edits(session: Session, user_id: str) -> list[AllocationEdit]:
    events = get_user_event_history(session, user_id, module_source="allocation", limit=500)
    # get_user_event_history returns most-recent-first; the EWMA must
    # replay in chronological order
    events = sorted(events, key=lambda e: e.timestamp)

    edits = []
    for e in events:
        if e.action_taken is None:
            continue  # no outcome recorded yet -- not evidence
        chosen_equity = Decimal(e.chosen_value["equity"]) if e.chosen_value and "equity" in e.chosen_value else None
        edits.append(
            AllocationEdit(
                suggested_equity_pct=_base_equity_of(e.suggested_value),
                chosen_equity_pct=chosen_equity,
                action_taken=EditActionTaken(e.action_taken.value),
                funded=e.funded,
                timestamp=e.timestamp,
                event_id=e.event_id,
                reason_code=e.reason_code,
            )
        )
    return edits


def _latest_risk_profile(session: Session, user_id: str) -> dict:
    risk_events = get_user_event_history(session, user_id, module_source="risk_profile", limit=1)
    if not risk_events:
        raise NoRiskTierError(f"no risk_profile computation found for user_id={user_id!r}; compute Module 3's tier first")
    return risk_events[0].suggested_value


def _binding_capacity_components(risk_value: dict) -> tuple[str, ...]:
    ceiling = risk_value["capacity_ceiling"]
    return tuple(
        c["name"]
        for c in risk_value.get("capacity_components") or []
        if c.get("applicable") and c.get("ceiling") == ceiling
    )


def compute_personalized_target(
    session: Session,
    user_id: str,
    base_target_pct: dict[AssetClass, Decimal],
    final_tier: int,
    alpha: Decimal = DEFAULT_ALPHA,
) -> PersonalizedTarget:
    """Pure read: replay the user's allocation outcomes and apply the
    offset to `base_target_pct`. Logs nothing -- callers decide whether
    the result is a new suggestion."""
    risk_value = _latest_risk_profile(session, user_id)
    capacity_ceiling = risk_value["capacity_ceiling"]

    edits = _load_allocation_edits(session, user_id)
    offset, trace = compute_offset_from_edits(edits, alpha=alpha)

    capacity_ceiling_target = compute_target_allocation(capacity_ceiling).target_pct
    displayed = apply_personalization_offset(base_target_pct, capacity_ceiling_target, offset)
    cap = describe_offset_cap(base_target_pct, capacity_ceiling_target, offset, displayed)

    return PersonalizedTarget(
        offset_pct_points=offset,
        trace=tuple(trace),
        edits_considered=len(edits),
        base_target_pct=base_target_pct,
        displayed_target_pct=displayed,
        cap=cap,
        capacity_ceiling=capacity_ceiling,
        capacity_binding_constraints=_binding_capacity_components(risk_value) if cap.cap_reason == "capacity_ceiling" else (),
        final_tier=final_tier,
        alpha=alpha,
    )


def _validated_chosen_mix(chosen_target_pct: dict[str, Decimal | str] | None) -> dict[str, Decimal]:
    if not chosen_target_pct:
        raise InvalidAllocationOutcomeError("setting your own mix needs the mix itself (chosen_target_pct)")
    try:
        chosen_target_pct = {k: Decimal(str(v)) for k, v in chosen_target_pct.items()}
    except ArithmeticError as exc:
        raise InvalidAllocationOutcomeError(f"chosen_target_pct values must be numbers: {exc}") from exc
    expected = {ac.value for ac in AssetClass}
    if set(chosen_target_pct) != expected:
        raise InvalidAllocationOutcomeError(f"chosen_target_pct must have exactly these classes: {sorted(expected)}")
    if any(v < 0 or v > 100 for v in chosen_target_pct.values()):
        raise InvalidAllocationOutcomeError("each class in chosen_target_pct must be between 0 and 100")
    total = sum(chosen_target_pct.values())
    if abs(total - 100) > _CHOSEN_SUM_TOLERANCE:
        raise InvalidAllocationOutcomeError(f"chosen_target_pct must add up to 100, got {total}")
    return chosen_target_pct


def _load_own_allocation_event(session: Session, user_id: str, event_id: str) -> SuggestionEvent:
    event = session.get(SuggestionEvent, event_id)
    if event is None or event.user_id != user_id or event.module_source != "allocation":
        raise AllocationEventNotFoundError(f"no allocation suggestion_event id={event_id!r} for user_id={user_id!r}")
    return event


def record_allocation_outcome(
    session: Session,
    user_id: str,
    event_id: str,
    action_taken: EditActionTaken,
    chosen_target_pct: dict[str, Decimal | str] | None,
    funded: bool | None,
    reason_code: str | None = None,
    commit: bool = True,
) -> SuggestionEvent:
    """Attach a user's reaction to one of their own Module 4 allocation
    suggestion_events. This is the only source of new evidence for the
    EWMA -- Module 7 never invents edits, it only reads what's recorded
    here.

    - accepted: the chosen mix is what the event *displayed* (base plus
      offset), filled in here rather than trusted from the client, so an
      accept reinforces the current offset instead of pulling it to zero.
    - edited: the user's own mix is required and must add up to 100.
    - rejected: a reason from REJECT_REASON_CODES is required.
    - ignored: nothing else is recorded.
    """
    event = _load_own_allocation_event(session, user_id, event_id)
    value = event.suggested_value

    chosen: dict[str, str] | None = None
    if action_taken == EditActionTaken.ACCEPTED:
        shown = value.get("displayed_target_pct") or value["target_pct"]
        chosen = {k: str(v) for k, v in shown.items()}
        reason_code = None
    elif action_taken == EditActionTaken.EDITED:
        chosen = {k: str(v) for k, v in _validated_chosen_mix(chosen_target_pct).items()}
        reason_code = None
    elif action_taken == EditActionTaken.REJECTED:
        if reason_code not in REJECT_REASON_CODES:
            raise InvalidAllocationOutcomeError(
                f"a rejection needs a reason, one of {list(REJECT_REASON_CODES)}; got {reason_code!r}"
            )
        funded = None  # nothing was chosen, so there is nothing to have funded
    else:
        reason_code = None
        funded = None

    delta = None
    if chosen is not None:
        # Module 1's `delta`: how far the user's choice sits from the
        # tier's base target, the same quantity the EWMA averages.
        delta = {"equity_pct_points": str(Decimal(chosen["equity"]) - _base_equity_of(value))}

    return record_suggestion_outcome(
        session,
        event_id=event_id,
        action_taken=ActionTaken(action_taken.value),
        chosen_value=chosen,
        delta=delta,
        reason_code=reason_code,
        funded=funded,
        commit=commit,
    )


def mark_allocation_funded(
    session: Session, user_id: str, event_id: str, funded: bool = True, commit: bool = True
) -> SuggestionEvent:
    """Follow-up for a choice recorded as "not invested yet". Only the
    funded flag changes; because the offset is replayed from history, the
    choice's weight goes from 0.5 to 1.0 on the next computation."""
    event = _load_own_allocation_event(session, user_id, event_id)
    if event.action_taken not in (ActionTaken.ACCEPTED, ActionTaken.EDITED):
        raise InvalidAllocationOutcomeError(
            "only an accepted or self-set mix can be marked as invested; record a choice first"
        )
    return record_suggestion_outcome(session, event_id=event_id, funded=funded, commit=commit)


def compute_and_log_personalization(
    session: Session, user_id: str, alpha: Decimal = DEFAULT_ALPHA, commit: bool = True
) -> PersonalizedTarget:
    allocation_events = get_user_event_history(session, user_id, module_source="allocation", limit=1)
    if not allocation_events:
        raise NoAllocationSuggestionError(f"no allocation suggestion found for user_id={user_id!r}; compute Module 4's allocation first")
    latest_allocation = allocation_events[0]
    base_target_pct = {AssetClass(k): Decimal(v) for k, v in latest_allocation.suggested_value["target_pct"].items()}
    final_tier = latest_allocation.suggested_value["final_tier"]

    result = compute_personalized_target(session, user_id, base_target_pct, final_tier, alpha=alpha)

    # Read-mostly: this endpoint is opened far more often than the offset
    # changes, so a row is written only when the result differs from the
    # last one logged.
    log_suggestion_event_if_changed(
        session,
        user_id=user_id,
        module_source="personalization",
        tier=str(final_tier),
        offset_pct_points=result.cap.applied_offset_pct_points,
        suggested_value={
            "offset_pct_points": str(result.offset_pct_points),
            "applied_offset_pct_points": str(result.cap.applied_offset_pct_points),
            "offset_capped": result.cap.capped,
            "cap_reason": result.cap.cap_reason,
            "capacity_binding_constraints": list(result.capacity_binding_constraints),
            "alpha": str(alpha),
            "edits_considered": result.edits_considered,
            "base_target_pct": {ac.value: str(v) for ac, v in base_target_pct.items()},
            "displayed_target_pct": {ac.value: str(v) for ac, v in result.displayed_target_pct.items()},
            "capacity_ceiling": result.capacity_ceiling,
            "final_tier": final_tier,
        },
        market_context={"trace": trace_as_json(result.trace)},
        compare_market_context=True,
        commit=commit,
    )

    return result


def trace_as_json(trace: tuple[OffsetStep, ...]) -> list[dict]:
    return [
        {
            "step": s.step,
            "weight": str(s.weight),
            "delta_pct": str(s.delta_pct),
            "offset_before": str(s.offset_before),
            "offset_after": str(s.offset_after),
            "action_taken": s.action_taken.value if s.action_taken else None,
            "funded": s.funded,
            "reason_code": s.reason_code,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            "event_id": s.event_id,
            "suggested_equity_pct": str(s.suggested_equity_pct) if s.suggested_equity_pct is not None else None,
            "chosen_equity_pct": str(s.chosen_equity_pct) if s.chosen_equity_pct is not None else None,
        }
        for s in trace
    ]
