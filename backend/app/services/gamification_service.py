"""Wires Module 10's pure milestone-detection logic to Module 2's
snapshots/EMIs/expenses, Module 3's capacity ceiling, and Module 6's
subscription-keyword list, logging awarded milestones via Module 1's
event log. No new "achieved milestones" table: which milestones a user
has already earned is read back from their own past
`module_source="gamification"` suggestion_events — the same
replay-from-the-event-log pattern Modules 3/4/6/7/9 all use, so there's no
separate state that could drift out of sync with the log.

Every function here reads exactly one user's own data and nothing else's
-- no cross-user query exists in this file, which is how the "no
leaderboards, no cross-user comparison" exclusion is actually enforced,
not just promised.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.onboarding import EmiEntry, ExpenseItem
from app.services.allocation import compute_target_allocation
from app.services.asset_classification_config import AssetClass
from app.services.event_log import get_user_event_history, get_user_snapshot_history, log_suggestion_event
from app.services.financial_position import MAX_BUFFER_MONTHS, EmiInput, compute_outstanding_principal
from app.services.gamification import crossed_thresholds, longest_trailing_positive_streak
from app.services.gamification_config import (
    BUFFER_MONTHS_THRESHOLDS,
    CONFIG_VERSION,
    CONSISTENCY_MONTH_THRESHOLDS,
    SUBSCRIPTION_CANCELLED_COUNT_THRESHOLDS,
    Category,
)
from app.services.leak_engine import is_subscription_like
from app.services.onboarding import ProfileNotFoundError, get_profile


@dataclass(frozen=True)
class AwardedMilestone:
    milestone_id: str
    category: str
    headline: str
    details: dict


def _awarded_milestone_ids(session: Session, user_id: str) -> set[str]:
    events = get_user_event_history(session, user_id, module_source="gamification", limit=1000)
    return {e.suggested_value["milestone_id"] for e in events}


def _check_buffer_milestones(session: Session, user_id: str, awarded: set[str]) -> list[AwardedMilestone]:
    snapshots = get_user_snapshot_history(session, user_id, limit=1)
    if not snapshots:
        return []
    current = snapshots[0].buffer_coverage_months
    if current >= MAX_BUFFER_MONTHS:
        # Module 2's documented sentinel for "no essential expenses
        # recorded yet, coverage not meaningfully measurable" -- not a
        # real 9999-month buffer. Awarding milestones off this would
        # reward an empty profile, not an achievement.
        return []
    return [
        AwardedMilestone(
            milestone_id=mid,
            category=Category.BUFFER.value,
            headline=f"Reached {t} month(s) of emergency buffer",
            details={"buffer_coverage_months": str(current), "threshold_months": t},
        )
        for t, mid in crossed_thresholds(current, BUFFER_MONTHS_THRESHOLDS, awarded, lambda t: f"buffer_months_{t}")
    ]


def _check_capacity_unlock(session: Session, user_id: str, awarded: set[str]) -> list[AwardedMilestone]:
    """The one 'real' progression mechanic (per the module brief): Module
    3's capacity ceiling rising, tied to the real before/after equity
    figures Module 4's own rule table assigns to each ceiling -- not a
    cosmetic badge with an arbitrary label."""
    risk_events = sorted(
        get_user_event_history(session, user_id, module_source="risk_profile", limit=500), key=lambda e: e.timestamp
    )
    if not risk_events:
        return []

    awarded_local = set(awarded)
    results: list[AwardedMilestone] = []
    peak_ceiling_ever = risk_events[0].suggested_value["capacity_ceiling"]

    for e in risk_events[1:]:
        ceiling = e.suggested_value["capacity_ceiling"]
        if ceiling > peak_ceiling_ever:
            mid = f"capacity_unlock_ceiling_{ceiling}"
            if mid not in awarded_local:
                old_equity = compute_target_allocation(peak_ceiling_ever).target_pct[AssetClass.EQUITY]
                new_equity = compute_target_allocation(ceiling).target_pct[AssetClass.EQUITY]
                results.append(
                    AwardedMilestone(
                        milestone_id=mid,
                        category=Category.CAPACITY_UNLOCK.value,
                        headline=(
                            f"Capacity ceiling rose from {peak_ceiling_ever} to {ceiling} -- "
                            f"capped equity target rose from {old_equity}% to {new_equity}%"
                        ),
                        details={
                            "old_ceiling": peak_ceiling_ever,
                            "new_ceiling": ceiling,
                            "old_capped_equity_pct": str(old_equity),
                            "new_capped_equity_pct": str(new_equity),
                            "binding_constraints_now": e.suggested_value.get("binding_constraints"),
                        },
                    )
                )
                awarded_local.add(mid)
        peak_ceiling_ever = max(peak_ceiling_ever, ceiling)

    return results


def _check_debt_free(session: Session, user_id: str, awarded: set[str]) -> list[AwardedMilestone]:
    mid = "debt_free"
    if mid in awarded:
        return []

    all_emis = session.execute(select(EmiEntry).where(EmiEntry.user_id == user_id)).scalars().all()
    if not all_emis:
        return []  # never had any recorded debt -- not an achievement to award

    active = [e for e in all_emis if e.closed_at is None]
    total_outstanding = sum(
        compute_outstanding_principal(EmiInput(e.amount_paise, e.remaining_tenure_months, e.annual_rate_bps))
        for e in active
    )
    if total_outstanding > 0:
        return []

    return [
        AwardedMilestone(
            milestone_id=mid,
            category=Category.DEBT.value,
            headline="All EMI debt cleared",
            details={"emi_count_ever_recorded": len(all_emis)},
        )
    ]


def _check_subscriptions_cancelled(session: Session, user_id: str, awarded: set[str]) -> list[AwardedMilestone]:
    removed_items = session.execute(
        select(ExpenseItem).where(ExpenseItem.user_id == user_id, ExpenseItem.removed_at.is_not(None))
    ).scalars().all()
    count = sum(1 for item in removed_items if is_subscription_like(item.category))

    return [
        AwardedMilestone(
            milestone_id=mid,
            category=Category.SUBSCRIPTIONS.value,
            headline=f"Cancelled {t} subscription-like recurring charge(s)",
            details={"cancelled_count": count, "threshold": t},
        )
        for t, mid in crossed_thresholds(count, SUBSCRIPTION_CANCELLED_COUNT_THRESHOLDS, awarded, lambda t: f"subscriptions_cancelled_{t}")
    ]


def _check_consistency(session: Session, user_id: str, awarded: set[str]) -> list[AwardedMilestone]:
    snapshots = get_user_snapshot_history(session, user_id, limit=24)
    if not snapshots:
        return []
    ordered = sorted(snapshots, key=lambda s: s.month)  # oldest to newest
    streak = longest_trailing_positive_streak([s.surplus for s in ordered])

    return [
        AwardedMilestone(
            milestone_id=mid,
            category=Category.CONSISTENCY.value,
            headline=f"{t} consecutive month(s) of positive surplus",
            details={"current_streak_months": streak, "threshold": t},
        )
        for t, mid in crossed_thresholds(streak, CONSISTENCY_MONTH_THRESHOLDS, awarded, lambda t: f"consistency_{t}_months")
    ]


def check_milestones(session: Session, user_id: str, commit: bool = True) -> list[AwardedMilestone]:
    profile = get_profile(session, user_id)
    if profile is None:
        raise ProfileNotFoundError(f"no user_profile for user_id={user_id!r}; complete Module 2 onboarding first")

    awarded = _awarded_milestone_ids(session, user_id)

    newly: list[AwardedMilestone] = []
    newly += _check_buffer_milestones(session, user_id, awarded)
    newly += _check_capacity_unlock(session, user_id, awarded)
    newly += _check_debt_free(session, user_id, awarded)
    newly += _check_subscriptions_cancelled(session, user_id, awarded)
    newly += _check_consistency(session, user_id, awarded)

    for m in newly:
        log_suggestion_event(
            session,
            user_id=user_id,
            module_source="gamification",
            suggested_value={
                "milestone_id": m.milestone_id,
                "category": m.category,
                "headline": m.headline,
                "details": m.details,
            },
            market_context={"config_version": CONFIG_VERSION},
            commit=commit,
        )

    return newly


def get_milestone_history(session: Session, user_id: str) -> list[AwardedMilestone]:
    """All milestones this one user has ever earned, oldest first -- read
    straight back from Module 1's log, no recomputation."""
    events = get_user_event_history(session, user_id, module_source="gamification", limit=1000)
    return [
        AwardedMilestone(
            milestone_id=e.suggested_value["milestone_id"],
            category=e.suggested_value["category"],
            headline=e.suggested_value["headline"],
            details=e.suggested_value["details"],
        )
        for e in sorted(events, key=lambda e: e.timestamp)
    ]
