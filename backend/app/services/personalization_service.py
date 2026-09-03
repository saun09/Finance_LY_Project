"""Wires Module 7's pure EWMA/offset logic to Module 1's event log and
Module 4's allocation suggestions. No new tables: the offset is always
replayed from suggestion_event history (module_source="allocation" events
that have a recorded outcome), the same "read the event log, don't store
derived state" pattern Modules 3/4/6 already use.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.suggestion_event import ActionTaken, SuggestionEvent
from app.services.allocation import compute_target_allocation
from app.services.asset_classification_config import AssetClass
from app.services.event_log import get_user_event_history, log_suggestion_event, record_suggestion_outcome
from app.services.personalization import (
    DEFAULT_ALPHA,
    AllocationEdit,
    EditActionTaken,
    OffsetStep,
    apply_personalization_offset,
    compute_offset_from_edits,
)


class NoAllocationSuggestionError(ValueError):
    pass


class NoRiskTierError(ValueError):
    pass


class AllocationEventNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class PersonalizationResult:
    offset_pct_points: Decimal
    trace: tuple[OffsetStep, ...]
    edits_considered: int
    base_target_pct: dict[AssetClass, Decimal]
    displayed_target_pct: dict[AssetClass, Decimal]
    capacity_ceiling: int
    final_tier: int


def record_allocation_outcome(
    session: Session,
    user_id: str,
    event_id: str,
    action_taken: EditActionTaken,
    chosen_target_pct: dict[str, Decimal] | None,
    funded: bool | None,
    commit: bool = True,
) -> SuggestionEvent:
    """Attach a user's reaction (accept/edit/reject/ignore, plus whether
    they actually funded it) to one of their own Module 4 allocation
    suggestion_events. This is the only source of new evidence for the
    EWMA -- Module 7 never invents edits, it only reads what's recorded
    here."""
    event = session.get(SuggestionEvent, event_id)
    if event is None or event.user_id != user_id or event.module_source != "allocation":
        raise AllocationEventNotFoundError(f"no allocation suggestion_event id={event_id!r} for user_id={user_id!r}")

    return record_suggestion_outcome(
        session,
        event_id=event_id,
        action_taken=ActionTaken(action_taken.value),
        chosen_value=None if chosen_target_pct is None else {k: str(v) for k, v in chosen_target_pct.items()},
        funded=funded,
        commit=commit,
    )


def _load_allocation_edits(session: Session, user_id: str) -> list[AllocationEdit]:
    events = get_user_event_history(session, user_id, module_source="allocation", limit=500)
    # get_user_event_history returns most-recent-first; the EWMA must
    # replay in chronological order
    events = sorted(events, key=lambda e: e.timestamp)

    edits = []
    for e in events:
        if e.action_taken is None:
            continue  # no outcome recorded yet -- not evidence
        suggested_equity = Decimal(e.suggested_value["target_pct"]["equity"])
        chosen_equity = Decimal(e.chosen_value["equity"]) if e.chosen_value else None
        edits.append(
            AllocationEdit(
                suggested_equity_pct=suggested_equity,
                chosen_equity_pct=chosen_equity,
                action_taken=EditActionTaken(e.action_taken.value),
                funded=e.funded,
            )
        )
    return edits


def compute_and_log_personalization(
    session: Session, user_id: str, alpha: Decimal = DEFAULT_ALPHA, commit: bool = True
) -> PersonalizationResult:
    allocation_events = get_user_event_history(session, user_id, module_source="allocation", limit=1)
    if not allocation_events:
        raise NoAllocationSuggestionError(f"no allocation suggestion found for user_id={user_id!r}; compute Module 4's allocation first")
    latest_allocation = allocation_events[0]
    base_target_pct = {AssetClass(k): Decimal(v) for k, v in latest_allocation.suggested_value["target_pct"].items()}
    final_tier = latest_allocation.suggested_value["final_tier"]

    risk_events = get_user_event_history(session, user_id, module_source="risk_profile", limit=1)
    if not risk_events:
        raise NoRiskTierError(f"no risk_profile computation found for user_id={user_id!r}; compute Module 3's tier first")
    capacity_ceiling = risk_events[0].suggested_value["capacity_ceiling"]

    edits = _load_allocation_edits(session, user_id)
    offset, trace = compute_offset_from_edits(edits, alpha=alpha)

    capacity_ceiling_target = compute_target_allocation(capacity_ceiling).target_pct
    displayed = apply_personalization_offset(base_target_pct, capacity_ceiling_target, offset)

    log_suggestion_event(
        session,
        user_id=user_id,
        module_source="personalization",
        tier=str(final_tier),
        suggested_value={
            "offset_pct_points": str(offset),
            "alpha": str(alpha),
            "edits_considered": len(edits),
            "base_target_pct": {ac.value: str(v) for ac, v in base_target_pct.items()},
            "displayed_target_pct": {ac.value: str(v) for ac, v in displayed.items()},
            "capacity_ceiling": capacity_ceiling,
            "final_tier": final_tier,
        },
        market_context={
            "trace": [
                {
                    "step": s.step,
                    "weight": str(s.weight),
                    "delta_pct": str(s.delta_pct),
                    "offset_before": str(s.offset_before),
                    "offset_after": str(s.offset_after),
                }
                for s in trace
            ],
        },
        commit=commit,
    )

    return PersonalizationResult(
        offset_pct_points=offset,
        trace=tuple(trace),
        edits_considered=len(edits),
        base_target_pct=base_target_pct,
        displayed_target_pct=displayed,
        capacity_ceiling=capacity_ceiling,
        final_tier=final_tier,
    )
