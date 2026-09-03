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
    BADGES,
    BUFFER_MONTHS_THRESHOLDS,
    CHECKLIST,
    CONFIG_VERSION,
    CONSISTENCY_MONTH_THRESHOLDS,
    ROADMAP,
    QUIZ_QUESTIONS,
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


EDUCATION_SOURCE = "gamification_education"


def _education_events(session: Session, user_id: str):
    return get_user_event_history(session, user_id, module_source=EDUCATION_SOURCE, limit=5000)


def complete_education_item(session: Session, user_id: str, item_id: str, kind: str, correct: bool | None = None, answer_index: int | None = None) -> dict | None:
    valid_ids = {topic.topic_id for level in ROADMAP for topic in level.topics} | {item[0] for item in CHECKLIST}
    if item_id not in valid_ids or kind not in {"lesson", "quiz", "checklist"}:
        raise ValueError("unknown education item or completion type")
    question = next((item for item in QUIZ_QUESTIONS if item.topic_id == item_id), None)
    if kind == "quiz" and (question is None or answer_index is None or answer_index < 0 or answer_index >= len(question.options)):
        raise ValueError("a valid answer is required for this quiz")
    if kind == "quiz":
        is_correct = answer_index == question.answer_index
        if not is_correct:
            return {"correct": False, "explanation": question.explanation}
        correct = True
    existing = [
        event for event in _education_events(session, user_id)
        if event.suggested_value.get("item_id") == item_id and event.suggested_value.get("kind") == kind
    ]
    if existing:
        return {"correct": True, "explanation": question.explanation} if kind == "quiz" and question else None
    log_suggestion_event(
        session, user_id=user_id, module_source=EDUCATION_SOURCE,
        suggested_value={"item_id": item_id, "kind": kind, "correct": correct, "answer_index": answer_index},
        market_context={"config_version": CONFIG_VERSION},
    )
    return {"correct": True, "explanation": question.explanation} if kind == "quiz" and question else None


def get_education_progress(session: Session, user_id: str) -> dict:
    events = _education_events(session, user_id)
    completed_topics = {e.suggested_value["item_id"] for e in events if e.suggested_value.get("kind") == "lesson"}
    completed_checklist = {e.suggested_value["item_id"] for e in events if e.suggested_value.get("kind") == "checklist"}
    passed_quizzes = {e.suggested_value["item_id"] for e in events if e.suggested_value.get("kind") == "quiz" and e.suggested_value.get("correct") is True}
    quiz_by_topic = {question.topic_id: question for question in QUIZ_QUESTIONS}
    total_topics = sum(len(level.topics) for level in ROADMAP)
    earned = {
        "budget-beginner": "budgeting" in completed_topics,
        "emergency-ready": "emergency-fund" in completed_topics,
        "debt-aware": "high-interest-debt" in completed_topics,
        "investing-101": {"saving-investing", "risk-return", "funds-etfs"}.issubset(completed_topics),
        "tax-smart": {"income-tax", "tax-saving-capital-gains"}.issubset(completed_topics),
        "diversification-pro": "diversification-allocation" in passed_quizzes,
        "foundations-complete": all(topic.topic_id in completed_topics for level in ROADMAP[:2] for topic in level.topics),
    }
    dates = sorted({event.timestamp.date() for event in events if event.suggested_value.get("kind") in {"lesson", "quiz"}}, reverse=True)
    streak = 0
    if dates:
        from datetime import timedelta
        expected = dates[0]
        for learning_date in dates:
            if learning_date != expected:
                break
            streak += 1
            expected -= timedelta(days=1)
    return {
        "roadmap": [{"level": level.level, "title": level.title, "topics": [{"topic_id": topic.topic_id, "title": topic.title, "description": topic.description, "completed": topic.topic_id in completed_topics, "quiz_question": ({"question_id": quiz.topic_id, "prompt": quiz.prompt, "options": list(quiz.options), "passed": quiz.topic_id in passed_quizzes} if (quiz := quiz_by_topic.get(topic.topic_id)) else None)} for topic in level.topics]} for level in ROADMAP],
        "checklist": [{"item_id": item_id, "title": title, "section": section, "completed": item_id in completed_checklist} for item_id, title, section in CHECKLIST],
        "badges": [{"badge_id": badge_id, "title": title, "description": description, "earned": earned[badge_id]} for badge_id, title, description in BADGES],
        "completed_topics": len(completed_topics), "total_topics": total_topics,
        "progress_pct": round(len(completed_topics) * 100 / total_topics) if total_topics else 0,
        "learning_streak_days": streak,
    }


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
