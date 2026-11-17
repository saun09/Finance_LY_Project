"""Seeds one "normal" dummy user whose history touches EVERY part of the
app, against a REAL running server -- so each screen has something to show
instead of an empty state.

What it leaves behind, by screen:
    Home / Profile   identity (name, email, DOB, phone), full onboarding
    Profile manage   expenses, EMIs, insurance, holdings -- plus a removed
                     expense and a closed EMI so the history isn't empty
    Progress         6 months of snapshots (5 backdated) with positive
                     surplus, a growing buffer, earned milestones, lessons,
                     quizzes and checklist items
    Risk profile     two attempts: the first capped by a thin buffer, the
                     retake after a bonus lifts the capacity ceiling
    Allocation       a rejected plan, a funded edit, an accepted plan
                     marked "not invested yet" (Pending investments card),
                     and one fresh plan left open to respond to live
    Insights         debt avalanche (credit card, personal and home loans),
                     subscription + duplicate + fee leaks, idle cash,
                     personalization offset, transparency history/compare
                     and one contested decision
    Verify           one logged rumour check (local engine, else n8n)

The story: a salaried 29-year-old who spent five months building a buffer,
then got a bonus, cancelled two subscriptions and paid off a phone EMI.

Prerequisite: the backend is running FROM backend/ (so both use ./dev.db):
    uvicorn app.main:app --reload

Run from backend/:
    python -m scripts.seed_showcase_user        # creates demo_user_1
    python -m scripts.seed_showcase_user 2      # a fresh demo_user_2

Re-running with a number already used refuses rather than doubling every
expense/EMI/holding -- pick a new number for a clean slate.
"""

import os
import sys
from datetime import date
from decimal import Decimal

import httpx

from app.db import SessionLocal
from app.services.event_log import log_monthly_snapshot
from app.services.gamification_config import QUIZ_QUESTIONS

BASE_URL = os.environ.get("DEMO_API_URL", "http://127.0.0.1:8000")
PASSWORD = "demo1234"

IDENTITY = {
    "full_name": "Riya Menon",
    "email": "riya.menon@example.com",
    "date_of_birth": "1997-03-14",
    "phone_number": "9876543210",
}

# 54k cash against ~36k of essentials = 1.5 months: thin enough that the
# capacity cap binds on the first risk profile
PROFILE = {
    "income_paise": 1_20_000_00,
    "income_stability": "regular",
    "employment_type": "salaried",
    "dependents_count": 1,
    "cash_balance_paise": 54_000_00,
}
BONUS_CASH_PAISE = 2_80_000_00

EXPENSES = [
    {"category": "Rent", "amount_paise": 25_000_00, "frequency": "monthly", "is_essential": True},
    {"category": "Groceries", "amount_paise": 8_000_00, "frequency": "monthly", "is_essential": True},
    {"category": "Electricity and water", "amount_paise": 3_000_00, "frequency": "monthly", "is_essential": True},
    # near-duplicate pair -> "possible duplicate" leak
    {"category": "Phone bill", "amount_paise": 600_00, "frequency": "monthly", "is_essential": True},
    {"category": "Phone bills", "amount_paise": 400_00, "frequency": "monthly", "is_essential": True},
    {"category": "Dining out", "amount_paise": 6_000_00, "frequency": "monthly", "is_essential": False},
    # subscription-keyword leaks; the last two get cancelled later
    {"category": "Netflix streaming", "amount_paise": 650_00, "frequency": "monthly", "is_essential": False},
    {"category": "Gym membership", "amount_paise": 2_000_00, "frequency": "monthly", "is_essential": False},
    {"category": "Music subscription", "amount_paise": 120_00, "frequency": "monthly", "is_essential": False},
    {"category": "Cloud storage backup", "amount_paise": 1_300_00, "frequency": "annual", "is_essential": False},
    # fee-drag leak
    {"category": "Bank account maintenance charge", "amount_paise": 4_800_00, "frequency": "annual", "is_essential": False},
    {"category": "Annual vacation", "amount_paise": 60_000_00, "frequency": "annual", "is_essential": False},
]
CANCELLED_EXPENSES = ("Music subscription", "Cloud storage backup")

EMIS = [
    {"lender": "SBI Home Loan", "amount_paise": 22_000_00, "remaining_tenure_months": 216, "annual_rate_bps": 850, "purpose": "home"},
    {"lender": "HDFC Credit Card EMI", "amount_paise": 4_500_00, "remaining_tenure_months": 18, "annual_rate_bps": 3600, "purpose": "credit_card"},
    {"lender": "Bajaj Personal Loan", "amount_paise": 6_000_00, "remaining_tenure_months": 30, "annual_rate_bps": 1400, "purpose": "personal"},
    {"lender": "Phone EMI", "amount_paise": 2_500_00, "remaining_tenure_months": 2, "annual_rate_bps": 1500, "purpose": "electronics"},
]
CLOSED_EMI = "Phone EMI"

INSURANCE = [
    {"policy_type": "life", "sum_assured_paise": 1_00_00_000_00},
    {"policy_type": "health", "sum_assured_paise": 5_00_000_00},
]

HOLDINGS = [
    {"description": "Savings account", "value_paise": 40_000_00, "holding_type": "savings_account"},
    {"description": "Fixed deposit", "value_paise": 1_00_000_00, "holding_type": "fixed_deposit"},
    {"description": "Nifty 50 index fund", "value_paise": 1_50_000_00, "holding_type": "equity_mutual_fund"},
    {"description": "ELSS tax saver", "value_paise": 60_000_00, "holding_type": "elss"},
    {"description": "EPF balance", "value_paise": 2_20_000_00, "holding_type": "epf"},
    {"description": "PPF account", "value_paise": 80_000_00, "holding_type": "ppf"},
    {"description": "Sovereign gold bond", "value_paise": 45_000_00, "holding_type": "sovereign_gold_bond"},
    {"description": "Endowment policy", "value_paise": 70_000_00, "holding_type": "endowment_or_moneyback_policy"},
]

RISK_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "moderate",
    "goal": "growth",
    "windfall_allocation": "split_debt_equity",
    "sure_gain_tradeoff": "chance_50pct_10000",
    "friend_description": "calculated_after_research",
}

# all of levels 1-2 (foundations-complete) plus the investing-101 trio
LESSONS = (
    "income-expenses", "needs-wants", "budgeting", "emergency-fund", "inflation-interest",
    "buffer-insurance", "health-life-insurance", "high-interest-debt", "credit-score", "subscriptions-documents",
    "saving-investing", "risk-return", "funds-etfs", "diversification-allocation",
)
QUIZZES_PASSED = ("income-expenses", "budgeting", "emergency-fund", "high-interest-debt", "diversification-allocation")
QUIZ_FAILED = "inflation-interest"  # answered wrong, so its explanation shows and it stays open
CHECKLIST_DONE = ("foundation", "budget", "recurring-costs", "debt-plan", "initial-buffer", "health-cover", "risk-tolerance")

RUMOUR = {
    "rumour_text": "Adani Enterprises shares rally 4% on $686 million investment in not-for-profit healthcare initiative",
    "rumour_date": "2025-02-11",
}


def _step(label: str) -> None:
    print(f"\n--- {label} ---")


def _ok(resp: httpx.Response) -> dict | list:
    if resp.is_error:
        print(f"  !! {resp.request.method} {resp.request.url.path} -> {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    return resp.json()


def _months_back(n: int) -> date:
    today = date.today().replace(day=1)
    y, m = divmod(today.year * 12 + today.month - 1 - n, 12)
    return date(y, m + 1, 1)


def _mix_with_equity(shown: dict[str, str], equity: Decimal) -> dict[str, str]:
    """The displayed mix with equity set to `equity`, the other classes
    rescaled in proportion so it still sums to 100 (the outcome endpoint
    rejects one that doesn't)."""
    mix = {k: Decimal(v) for k, v in shown.items()}
    others = [k for k in mix if k != "equity"]
    others_total = sum(mix[k] for k in others)
    out = {k: (mix[k] * (100 - equity) / others_total).quantize(Decimal("0.01")) for k in others}
    out["equity"] = equity
    largest = max(others, key=lambda k: out[k])
    out[largest] += 100 - sum(out.values())
    return {k: str(v) for k, v in out.items()}


def backdate_snapshots(user_id: str, position: dict) -> None:
    """Five earlier months with a positive surplus and a buffer growing
    towards today's. The API only ever writes the current month, so these
    go straight into the same database the server uses."""
    surplus = position["monthly_surplus_paise"]
    with SessionLocal() as session:
        for n in range(5, 0, -1):
            cash = PROFILE["cash_balance_paise"] - n * 6_000_00
            log_monthly_snapshot(
                session,
                user_id=user_id,
                month=_months_back(n),
                income=PROFILE["income_paise"],
                surplus=surplus - n * 1_500_00,
                cash=cash,
                debt_to_income_ratio=Decimal(position["emi_to_income_ratio"]),
                buffer_coverage_months=(
                    Decimal(position["buffer_coverage_months"]) * cash / PROFILE["cash_balance_paise"]
                ).quantize(Decimal("0.01")),
            )


def main() -> None:
    n = sys.argv[1] if len(sys.argv) > 1 else "1"
    username = f"demo_user_{n}"

    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        try:
            client.get("/health").raise_for_status()
        except httpx.RequestError:
            print(f"Could not reach {BASE_URL} -- start the backend first (uvicorn app.main:app --reload).")
            sys.exit(1)

        _step("Sign up")
        resp = client.post("/auth/signup", json={"username": username, "password": PASSWORD})
        if resp.status_code == 409:
            print(f"{username!r} already exists -- run with a new number, e.g. python -m scripts.seed_showcase_user {int(n) + 1}")
            sys.exit(1)
        user_id = _ok(resp)["user_id"]
        u = f"/users/{user_id}"
        print(f"{username} -> {user_id}")

        _step("Onboarding")
        _ok(client.put(f"{u}/profile", json=PROFILE))
        _ok(client.put(f"{u}/profile/identity", json=IDENTITY))
        _ok(client.put(f"{u}/expense-source-decision", json={"decision": "manual_only"}))
        expense_ids = {e["category"]: _ok(client.post(f"{u}/expenses", json=e))["id"] for e in EXPENSES}
        emi_ids = {e["lender"]: _ok(client.post(f"{u}/emis", json=e))["id"] for e in EMIS}
        for p in INSURANCE:
            _ok(client.post(f"{u}/insurance-policies", json=p))
        for h in HOLDINGS:
            _ok(client.post(f"{u}/holdings", json=h))
        _ok(client.post(f"{u}/complete-onboarding"))
        position = _ok(client.get(f"{u}/financial-position"))
        print(
            f"{len(EXPENSES)} expenses, {len(EMIS)} EMIs, {len(INSURANCE)} policies, {len(HOLDINGS)} holdings; "
            f"surplus Rs {position['monthly_surplus_paise'] / 100:,.0f}/mo, buffer {position['buffer_coverage_months']} months"
        )

        _step("Five months of history")
        backdate_snapshots(user_id, position)
        print(f"snapshots from {_months_back(5):%b %Y} to {_months_back(1):%b %Y}, all with positive surplus")

        _step("Risk profile #1 (thin buffer)")
        risk = _ok(client.post(f"{u}/risk-profile", json={"answers": RISK_ANSWERS}))
        print(f"stated {risk['stated_tier']}, ceiling {risk['capacity_ceiling']}, final {risk['final_tier']}, capped={risk['capped']}")

        _step("Plan #1 -> rejected")
        alloc = _ok(client.get(f"{u}/allocation"))
        _ok(client.post(f"{u}/allocation/{alloc['event_id']}/outcome", json={"action_taken": "rejected", "reason_code": "too_risky"}))
        print("turned down as 'Too risky for me'")

        _step("This month: bonus, two subscriptions cancelled, phone EMI paid off")
        _ok(client.put(f"{u}/profile", json={**PROFILE, "cash_balance_paise": BONUS_CASH_PAISE}))
        for category in CANCELLED_EXPENSES:
            _ok(client.post(f"{u}/expenses/{expense_ids[category]}/remove"))
        _ok(client.post(f"{u}/emis/{emi_ids[CLOSED_EMI]}/close"))
        position = _ok(client.get(f"{u}/financial-position"))
        print(f"buffer now {position['buffer_coverage_months']} months")

        _step("Risk profile #2 (retake)")
        risk = _ok(client.post(f"{u}/risk-profile", json={"answers": RISK_ANSWERS}))
        print(f"stated {risk['stated_tier']}, ceiling {risk['capacity_ceiling']}, final {risk['final_tier']}, capped={risk['capped']}")

        _step("Plan #2 -> own mix, invested")
        alloc = _ok(client.get(f"{u}/allocation"))
        shown_equity = Decimal(alloc["displayed_target_pct"]["equity"])
        mix = _mix_with_equity(alloc["displayed_target_pct"], max(Decimal(0), shown_equity - 5))
        _ok(client.post(
            f"{u}/allocation/{alloc['event_id']}/outcome",
            json={"action_taken": "edited", "chosen_target_pct": mix, "funded": True},
        ))
        print(f"equity {shown_equity}% -> {mix['equity']}%, funded")

        _step("Plan #3 -> accepted, not invested yet")
        alloc = _ok(client.get(f"{u}/allocation"))
        _ok(client.post(f"{u}/allocation/{alloc['event_id']}/outcome", json={"action_taken": "accepted", "funded": False}))
        print("shows on the Pending investments card")

        _step("Plan #4 -> left open for a live response")
        alloc = _ok(client.get(f"{u}/allocation"))
        print(f"displayed mix {alloc['displayed_target_pct']}")

        _step("Personalization, debt & leaks")
        pers = _ok(client.get(f"{u}/personalization"))
        print(f"offset {pers['offset_pct_points']} pts from {pers['edits_considered']} choices")
        leak = _ok(client.get(f"{u}/debt-leak"))
        print(f"recoverable Rs {leak['total_recoverable_annual_paise'] / 100:,.0f}/year")

        _step("Learning")
        for topic in LESSONS:
            _ok(client.post(f"{u}/gamification/education/complete", json={"item_id": topic, "kind": "lesson"}))
        answers = {q.topic_id: q for q in QUIZ_QUESTIONS}
        for topic in QUIZZES_PASSED:
            _ok(client.post(
                f"{u}/gamification/education/complete",
                json={"item_id": topic, "kind": "quiz", "answer_index": answers[topic].answer_index},
            ))
        wrong = (answers[QUIZ_FAILED].answer_index + 1) % len(answers[QUIZ_FAILED].options)
        _ok(client.post(f"{u}/gamification/education/complete", json={"item_id": QUIZ_FAILED, "kind": "quiz", "answer_index": wrong}))
        for item in CHECKLIST_DONE:
            _ok(client.post(f"{u}/gamification/education/complete", json={"item_id": item, "kind": "checklist"}))
        edu = _ok(client.get(f"{u}/gamification/education"))
        print(f"{len(LESSONS)} lessons, {len(QUIZZES_PASSED)} quizzes passed, 1 failed, {len(CHECKLIST_DONE)} checklist items -> {edu['progress_pct']}%")

        _step("Milestones")
        awarded = _ok(client.post(f"{u}/gamification/check"))
        for m in awarded:
            print(f"  * {m['headline']}")

        _step("Rumour check")
        resp = client.post(f"{u}/rumour-verification/explain", json=RUMOUR)
        if resp.status_code == 503:
            resp = client.post(f"{u}/rumour-verification", json=RUMOUR)
        if resp.is_error:
            print(f"skipped -- neither engine is available ({resp.status_code}: {resp.text[:120]})")
        else:
            body = resp.json()
            print(f"{body['engine']}: {body['status']}")

        _step("Transparency")
        history = _ok(client.get(f"{u}/transparency/risk_profile/history"))
        if len(history) >= 2:
            _ok(client.get(
                f"{u}/transparency/risk_profile/compare",
                params={"before_event_id": history[1]["event_id"], "after_event_id": history[0]["event_id"]},
            ))
        _ok(client.post(
            f"{u}/transparency/risk_profile/contest",
            json={
                "event_id": history[-1]["event_id"],
                "reason_code": "outcome_unfair",
                "note": "My buffer was about to be topped up by my bonus.",
            },
        ))
        counts = _ok(client.get(f"{u}/transparency"))["counts_by_module_source"]
        print(f"decisions logged: {counts}; first risk profile contested")

        print("\n=== Done ===")
        print(f"Log in with username={username!r} password={PASSWORD!r}")


if __name__ == "__main__":
    main()
