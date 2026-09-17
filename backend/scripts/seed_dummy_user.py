"""Seeds one realistic dummy user through the ENTIRE workflow, against a
REAL running server (not an in-memory DB like the other scripts/*.py demos)
-- signup, full onboarding, risk profile, allocation, a personalization
edit, debt/leak, gamification, and transparency. Run this, then log into
the Expo app with the printed username/password to see every screen
populated with real, backend-computed data.

Prerequisites: the backend must already be running, e.g.
    uvicorn app.main:app --reload
(from backend/, in another terminal).

Run with (from backend/):
    python -m scripts.seed_dummy_user

Re-running reuses the same account (logs in instead of signing up again)
but will ADD a second copy of every expense/EMI/holding, since those are
plain add-only endpoints -- change DUMMY_USERNAME below for a clean slate
instead of re-running against the same one.
"""

import sys

import httpx

BASE_URL = "http://127.0.0.1:8000"
DUMMY_USERNAME = "dummy_investor"
DUMMY_PASSWORD = "dummydata123"


def _print_step(label: str) -> None:
    print(f"\n--- {label} ---")


def signup_or_login(client: httpx.Client) -> str:
    resp = client.post("/auth/signup", json={"username": DUMMY_USERNAME, "password": DUMMY_PASSWORD})
    if resp.status_code == 201:
        print(f"signed up new user {DUMMY_USERNAME!r}")
    elif resp.status_code == 409:
        resp = client.post("/auth/login", json={"username": DUMMY_USERNAME, "password": DUMMY_PASSWORD})
        resp.raise_for_status()
        print(f"{DUMMY_USERNAME!r} already existed -- logged in instead")
    else:
        resp.raise_for_status()
    return resp.json()["user_id"]


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        try:
            client.get("/health").raise_for_status()
        except httpx.RequestError:
            print(f"Could not reach {BASE_URL} -- start the backend first (uvicorn app.main:app --reload).")
            sys.exit(1)

        _print_step("Sign up / log in")
        user_id = signup_or_login(client)
        print(f"user_id = {user_id}")
        u = f"/users/{user_id}"

        _print_step("Profile")
        client.put(f"{u}/profile", json={
            "income_paise": 120_000_00,
            "income_stability": "regular",
            "employment_type": "salaried",
            "dependents_count": 1,
            "cash_balance_paise": 300_000_00,
        }).raise_for_status()
        print("profile saved: Rs 1,20,000/mo income, Rs 3,00,000 cash, 1 dependent")

        _print_step("Expenses")
        expenses = [
            {"category": "rent", "amount_paise": 25_000_00, "frequency": "monthly", "is_essential": True},
            {"category": "groceries", "amount_paise": 8_000_00, "frequency": "monthly", "is_essential": True},
            {"category": "utilities", "amount_paise": 3_000_00, "frequency": "monthly", "is_essential": True},
            {"category": "dining_out", "amount_paise": 6_000_00, "frequency": "monthly", "is_essential": False},
            {"category": "subscriptions", "amount_paise": 1_500_00, "frequency": "monthly", "is_essential": False},
            {"category": "annual_vacation", "amount_paise": 60_000_00, "frequency": "annual", "is_essential": False},
        ]
        for e in expenses:
            client.post(f"{u}/expenses", json=e).raise_for_status()
        print(f"added {len(expenses)} expense items")

        _print_step("Loans / EMIs")
        emis = [
            {
                "lender": "HDFC Home Loan", "amount_paise": 22_000_00, "remaining_tenure_months": 180,
                "annual_rate_bps": 850, "purpose": "home",
            },
            {
                "lender": "Bajaj Finserv", "amount_paise": 8_000_00, "remaining_tenure_months": 36,
                "annual_rate_bps": 1100, "purpose": "vehicle",
            },
        ]
        for e in emis:
            client.post(f"{u}/emis", json=e).raise_for_status()
        print(f"added {len(emis)} EMIs (home loan + vehicle loan)")

        _print_step("Insurance")
        policies = [
            {"policy_type": "life", "sum_assured_paise": 1_50_00_000_00},
            {"policy_type": "health", "sum_assured_paise": 10_00_000_00},
        ]
        for p in policies:
            client.post(f"{u}/insurance-policies", json=p).raise_for_status()
        print("added life (Rs 1.5 crore) + health (Rs 10 lakh) cover")

        _print_step("Holdings")
        holdings = [
            {"description": "Savings balance", "value_paise": 150_000_00, "holding_type": "savings_account"},
            {"description": "Equity mutual fund", "value_paise": 300_000_00, "holding_type": "equity_mutual_fund"},
            {"description": "Direct stocks", "value_paise": 80_000_00, "holding_type": "direct_equity"},
            {"description": "PPF account", "value_paise": 200_000_00, "holding_type": "ppf"},
            {"description": "ELSS tax-saver fund", "value_paise": 100_000_00, "holding_type": "elss"},
            {"description": "Gold ETF", "value_paise": 50_000_00, "holding_type": "gold_etf"},
            {"description": "ULIP policy", "value_paise": 150_000_00, "holding_type": "ulip"},
        ]
        for h in holdings:
            client.post(f"{u}/holdings", json=h).raise_for_status()
        print(f"added {len(holdings)} holdings (every holding_type set, so allocation can classify all of them)")

        _print_step("Complete onboarding")
        snap = client.post(f"{u}/complete-onboarding")
        snap.raise_for_status()
        print(f"onboarding completed, first snapshot logged for {snap.json()['month']}")

        _print_step("Risk questionnaire (v2, 7 questions)")
        answers = {
            "horizon": "7_15y",
            "drawdown_reaction": "hold",
            "experience": "moderate",
            "goal": "growth",
            "windfall_allocation": "split_debt_equity",
            "sure_gain_tradeoff": "chance_50pct_10000",
            "friend_description": "calculated_after_research",
        }
        risk = client.post(f"{u}/risk-profile", json={"answers": answers})
        risk.raise_for_status()
        risk_body = risk.json()
        print(
            f"stated_tier={risk_body['stated_tier']}, capacity_ceiling={risk_body['capacity_ceiling']}, "
            f"final_tier={risk_body['final_tier']}, capped={risk_body['capped']}"
        )

        _print_step("Allocation")
        alloc = client.get(f"{u}/allocation")
        alloc.raise_for_status()
        alloc_body = alloc.json()
        print(f"target_pct = {alloc_body['target_pct']}")

        _print_step("Personalization (simulate an edited allocation outcome)")
        events = client.get(f"{u}/events", params={"module_source": "allocation"}).json()
        if events:
            event_id = events[0]["event_id"]
            chosen = {k: v for k, v in alloc_body["target_pct"].items()}
            # nudge equity up a little relative to the suggestion, funded=True,
            # so the personalization EWMA has real evidence to show.
            chosen["equity"] = str(float(chosen["equity"]) + 5)
            client.post(
                f"{u}/allocation/{event_id}/outcome",
                json={"action_taken": "edited", "chosen_target_pct": chosen, "funded": True},
            ).raise_for_status()
            print("recorded a funded 'edited' outcome on the allocation suggestion")

        personalization = client.get(f"{u}/personalization")
        if personalization.status_code == 200:
            print(f"personalization offset = {personalization.json()['offset_pct_points']} pts")
        else:
            print(f"personalization not available yet: {personalization.status_code} {personalization.text}")

        _print_step("Debt & leak")
        debt_leak = client.get(f"{u}/debt-leak")
        if debt_leak.status_code == 200:
            body = debt_leak.json()
            print(f"total recoverable/year = Rs {body['total_recoverable_annual_paise'] / 100:.2f}")
        else:
            print(f"debt-leak not available: {debt_leak.status_code} {debt_leak.text}")

        _print_step("Gamification")
        newly_awarded = client.post(f"{u}/gamification/check")
        if newly_awarded.status_code == 200:
            print(f"newly awarded milestones: {[m['headline'] for m in newly_awarded.json()]}")
        education = client.get(f"{u}/gamification/education")
        if education.status_code == 200:
            print(f"education progress: {education.json()['progress_pct']}%")

        _print_step("Transparency")
        index = client.get(f"{u}/transparency")
        if index.status_code == 200:
            print(f"decision types available to trace: {list(index.json()['counts_by_module_source'].keys())}")
            trace = client.get(f"{u}/transparency/allocation")
            if trace.status_code == 200:
                print(f"allocation trace headline: {trace.json()['headline']}")

        print("\n=== Done ===")
        print(f"Log into the app with username={DUMMY_USERNAME!r} password={DUMMY_PASSWORD!r}")
        print(f"user_id = {user_id}")


if __name__ == "__main__":
    main()
