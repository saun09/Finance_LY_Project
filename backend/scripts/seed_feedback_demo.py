"""Seeds two clean accounts for a live Module 7 (feedback loop) demo,
against a REAL running server. Both are fully onboarded and risk-profiled,
but NO allocation response is recorded -- every step of the loop is left
for the presenter to do live in the app.

    fl_growth_<n>  cautious answers (tier 1) but strong finances (capacity
                   ceiling 5): equity can move from 15% up to the +10 point
                   bound, so the offset is visible on screen.
    fl_capped_<n>  eager answers (stated tier 5) but only 1.5 months of
                   emergency buffer: capped at tier 2, so any learned
                   offset is held back by the cap -- and the screen says so.

Prerequisite: the backend is running (uvicorn app.main:app --reload).

Run from backend/:
    python -m scripts.seed_feedback_demo          # creates fl_growth_1 / fl_capped_1
    python -m scripts.seed_feedback_demo 2        # a fresh pair for a rehearsal or retake

Every run with a new number gives a clean slate; re-running with a number
already used just logs in and reports where that account stands.
"""

import os
import sys

import httpx

BASE_URL = os.environ.get("DEMO_API_URL", "http://127.0.0.1:8000")
PASSWORD = "demo1234"

CAUTIOUS_ANSWERS = {
    "horizon": "lt_1y",
    "drawdown_reaction": "sell_all",
    "experience": "none",
    "goal": "preserve",
    "windfall_allocation": "fd_or_savings",
    "sure_gain_tradeoff": "guaranteed_5000",
    "friend_description": "real_risk_avoider",
}

EAGER_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "extensive",
    "goal": "maximize",
    "windfall_allocation": "equity_plus_borrow",
    "sure_gain_tradeoff": "chance_10pct_50000",
    "friend_description": "real_gambler",
}

ACCOUNTS = (
    {
        "prefix": "fl_growth",
        "story": "cautious answers, strong finances -- room for the plan to move",
        "profile": {
            "income_paise": 1_00_000_00,  # Rs 1,00,000 / month
            "income_stability": "regular",
            "employment_type": "salaried",
            "dependents_count": 0,
            "cash_balance_paise": 5_00_000_00,  # Rs 5,00,000 = 20 months of essentials
        },
        "expenses": [
            {"category": "Rent", "amount_paise": 20_000_00, "frequency": "monthly", "is_essential": True},
            {"category": "Groceries", "amount_paise": 5_000_00, "frequency": "monthly", "is_essential": True},
        ],
        "holdings": [
            {"description": "Fixed deposit", "value_paise": 3_00_000_00, "holding_type": "fixed_deposit"},
            {"description": "Equity mutual fund", "value_paise": 1_00_000_00, "holding_type": "equity_mutual_fund"},
        ],
        "answers": CAUTIOUS_ANSWERS,
    },
    {
        "prefix": "fl_capped",
        "story": "eager answers, thin emergency buffer -- the capacity cap binds",
        "profile": {
            "income_paise": 1_00_000_00,  # Rs 1,00,000 / month
            "income_stability": "regular",
            "employment_type": "salaried",
            "dependents_count": 0,
            "cash_balance_paise": 30_000_00,  # Rs 30,000 = 1.5 months of essentials
        },
        "expenses": [
            {"category": "Rent", "amount_paise": 20_000_00, "frequency": "monthly", "is_essential": True},
        ],
        "holdings": [
            {"description": "Equity mutual fund", "value_paise": 1_00_000_00, "holding_type": "equity_mutual_fund"},
        ],
        "answers": EAGER_ANSWERS,
    },
)


def _signup(client: httpx.Client, username: str) -> tuple[str, bool]:
    resp = client.post("/auth/signup", json={"username": username, "password": PASSWORD})
    if resp.status_code == 201:
        return resp.json()["user_id"], True
    if resp.status_code == 409:
        resp = client.post("/auth/login", json={"username": username, "password": PASSWORD})
        resp.raise_for_status()
        return resp.json()["user_id"], False
    resp.raise_for_status()
    raise RuntimeError("unreachable")


def _seed(client: httpx.Client, user_id: str, account: dict) -> None:
    u = f"/users/{user_id}"
    client.put(f"{u}/profile", json=account["profile"]).raise_for_status()
    for e in account["expenses"]:
        client.post(f"{u}/expenses", json=e).raise_for_status()
    for h in account["holdings"]:
        client.post(f"{u}/holdings", json=h).raise_for_status()
    client.post(f"{u}/complete-onboarding").raise_for_status()
    client.post(f"{u}/risk-profile", json={"answers": account["answers"]}).raise_for_status()


def _report(client: httpx.Client, user_id: str) -> str:
    u = f"/users/{user_id}"
    risk = client.get(f"{u}/risk-profile/latest").json()
    alloc = client.get(f"{u}/allocation")
    alloc.raise_for_status()
    a = alloc.json()
    p = a["personalization"]
    return (
        f"stated tier {risk['stated_tier']}, capacity ceiling {risk['capacity_ceiling']}, final tier {a['final_tier']}; "
        f"equity: tier's plan {float(a['target_pct']['equity']):g}%, shown {float(a['displayed_target_pct']['equity']):g}%, "
        f"max allowed {float(p['max_equity_pct']):g}%; {p['edits_considered']} choices recorded"
    )


def main() -> None:
    suffix = sys.argv[1] if len(sys.argv) > 1 else "1"
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        try:
            client.get("/health").raise_for_status()
        except httpx.RequestError:
            print(f"Could not reach {BASE_URL} -- start the backend first (uvicorn app.main:app --reload).")
            sys.exit(1)

        for account in ACCOUNTS:
            username = f"{account['prefix']}_{suffix}"
            user_id, created = _signup(client, username)
            if created:
                _seed(client, user_id, account)
            print(f"\n{username}  /  password: {PASSWORD}   ({'created' if created else 'already existed -- left as is'})")
            print(f"  {account['story']}")
            print(f"  {_report(client, user_id)}")

    print("\nLog into the app with either account. Nothing has been answered yet -- the loop is yours to run live.")


if __name__ == "__main__":
    main()
