"""Trains the reduced-4-item risk-tier RandomForestClassifier used when a
user answers only the 4 "main" questionnaire questions instead of all 7.

Why this exists: research_artifacts/models/ already had a reduced-4-item
model, but it was a GradientBoostingClassifier, and shap.TreeExplainer only
supports GradientBoostingClassifier for *binary* classification -- this is
a 5-class (tier 1-5) problem, same reason the full-7-item production model
(risk_tier_rf.pkl) is a RandomForestClassifier and not GradientBoosting.
This script trains the same algorithm choice for the reduced feature set,
so quick-mode predictions keep the same live SHAP-explained transparency
as full-mode ones.

Data source: Risk_questionnaire_400.xlsx's "Mock Responses" sheet (434
rows) -- free-text survey answers, not the app's internal option value
codes, so each column is mapped to this app's QUESTIONNAIRE_V2 option
codes below (see *_MAP functions). The target label (stated_tier) is
computed by calling the real compute_stated_tier() on ALL 7 mapped
answers -- the exact same deterministic formula the live app uses for a
full-7-answer submission -- so the model is trained to predict "what the
deterministic formula would have said," not a separately-invented label.
Only 4 of those 7 mapped answers (the reduced feature set) are used as
training *features*; the other 3 are used only to compute the target.

Run from the backend/ directory: python -m scripts.train_risk_tier_reduced_model
"""

from pathlib import Path

import joblib
import openpyxl
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from app.services.risk_profile import compute_stated_tier
from app.services.risk_profile_config import QUESTIONNAIRE_V2

XLSX_PATH = Path(__file__).resolve().parents[2] / "Risk_questionnaire_400.xlsx"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "app" / "ml_models" / "risk_tier_rf_reduced_4items.pkl"

# Column indices (0-based) in the "Mock Responses" sheet for each of the
# app's 7 questionnaire items.
COL_HORIZON = 14
COL_DRAWDOWN = 16
COL_EXPERIENCE = 17
COL_GOAL = 18
COL_WINDFALL = 19
COL_SURE_GAIN = 20
COL_FRIEND = 21

# The reduced feature set and the exact order the model is trained on --
# app/services/risk_profile_ml.py's FEATURE_ORDER_REDUCED must match this
# exactly, since the model only knows feature *position*, not name.
REDUCED_FEATURES = ("windfall_allocation", "friend_description", "drawdown_reaction", "sure_gain_tradeoff")


def _clean(s: str) -> str:
    return (s or "").strip()


def map_horizon(text: str) -> str:
    # Each option's distinguishing prefix sits before any dash character,
    # so this is robust to the sheet's mixed em-dash / mojibake encoding
    # (both "—" and the replacement-char "�" appear for the same option
    # across rows) without needing to normalize the whole string.
    t = _clean(text)
    if t.startswith("Within 1 year"):
        return "lt_1y"
    if t.startswith("1"):
        return "1_3y"
    if t.startswith("3"):
        return "3_7y"
    if t.startswith("7"):
        return "7_15y"
    if t.startswith("More than 15"):
        return "gt_15y"
    raise ValueError(f"unrecognized horizon answer: {text!r}")


def map_drawdown(text: str) -> str:
    t = _clean(text)
    return {
        "Sell everything immediately": "sell_all",
        "Sell some to limit further loss": "sell_some",
        "Hold and wait it out": "hold",
        "Buy a little more if I can": "buy_a_little",
        "Buy significantly more": "buy_a_lot",
    }[t]


def map_experience(text: str) -> str:
    t = _clean(text)
    if t == "None":
        return "none"
    if t.startswith("A little"):
        return "little"
    if t.startswith("Moderate"):
        return "moderate"
    if t.startswith("Significant"):
        return "significant"
    if t.startswith("Extensive"):
        return "extensive"
    raise ValueError(f"unrecognized experience answer: {text!r}")


def map_goal(text: str) -> str:
    t = _clean(text)
    if t.startswith("Preserve"):
        return "preserve"
    if t.startswith("Generate"):
        return "income"
    if t.startswith("Grow it at a reasonable pace"):
        return "balanced"
    if t.startswith("Grow it meaningfully"):
        return "growth"
    if t.startswith("Maximize"):
        return "maximize"
    raise ValueError(f"unrecognized goal answer: {text!r}")


def map_windfall(text: str) -> str:
    # The survey offers two distinct "split" phrasings (debt-heavy vs.
    # equity-heavy) where the app has one "split" option plus a separate
    # plain "equity_funds" option. Preserving the survey's own monotonic
    # risk ordering (FD < debt < split-debt-heavy < split-equity-heavy <
    # equity+borrow) matters more for a usable training signal than an
    # exact text match, so the equity-heavy split is mapped to the app's
    # "equity_funds" option -- both represent "mostly equity" -- rather
    # than left unmapped.
    t = _clean(text)
    if t.startswith("Put it in a bank FD"):
        return "fd_or_savings"
    if t.startswith("Invest it in high-quality debt"):
        return "debt_funds"
    if t.startswith("Split it, keeping more in debt"):
        return "split_debt_equity"
    if t.startswith("Split it, keeping more in equity"):
        return "equity_funds"
    if t.startswith("Invest it fully in equity"):
        return "equity_plus_borrow"
    raise ValueError(f"unrecognized windfall answer: {text!r}")


def map_sure_gain(text: str) -> str:
    t = _clean(text)
    return {
        "A guaranteed Rs 5,000": "guaranteed_5000",
        "A 70% chance at Rs 7,000, otherwise nothing": "chance_70pct_7000",
        "A 50% chance at Rs 10,000, otherwise nothing": "chance_50pct_10000",
        "A 30% chance at Rs 17,000, otherwise nothing": "chance_30pct_17000",
        "A 10% chance at Rs 50,000, otherwise nothing": "chance_10pct_50000",
    }[t]


def map_friend(text: str) -> str:
    t = _clean(text)
    if t.startswith("Very risk-averse"):
        return "real_risk_avoider"
    if t == "Cautious":
        return "cautious"
    if t.startswith("Willing to take calculated risks"):
        return "calculated_after_research"
    if t.startswith("Comfortable taking risks"):
        return "comfortable_for_bigger_rewards"
    if t.startswith("A speculator"):
        return "real_gambler"
    raise ValueError(f"unrecognized friend-description answer: {text!r}")


def load_training_rows() -> list[dict[str, str]]:
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True)
    ws = wb["Mock Responses"]
    rows = list(ws.iter_rows(values_only=True))
    data_rows = rows[1:]

    mapped: list[dict[str, str]] = []
    skipped = 0
    for row in data_rows:
        if row[COL_HORIZON] is None:
            continue
        try:
            mapped.append(
                {
                    "horizon": map_horizon(row[COL_HORIZON]),
                    "drawdown_reaction": map_drawdown(row[COL_DRAWDOWN]),
                    "experience": map_experience(row[COL_EXPERIENCE]),
                    "goal": map_goal(row[COL_GOAL]),
                    "windfall_allocation": map_windfall(row[COL_WINDFALL]),
                    "sure_gain_tradeoff": map_sure_gain(row[COL_SURE_GAIN]),
                    "friend_description": map_friend(row[COL_FRIEND]),
                }
            )
        except (ValueError, KeyError):
            skipped += 1
    print(f"mapped {len(mapped)} rows, skipped {skipped} unparseable rows")
    return mapped


def main() -> None:
    rows = load_training_rows()

    X: list[list[int]] = []
    y: list[int] = []
    for answers in rows:
        target = compute_stated_tier(answers, QUESTIONNAIRE_V2)
        X.append([QUESTIONNAIRE_V2.option_points(qid, answers[qid]) for qid in REDUCED_FEATURES])
        y.append(target.tier)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = RandomForestClassifier(n_estimators=300, random_state=42, max_depth=None)
    model.fit(X_train, y_train)

    train_acc = accuracy_score(y_train, model.predict(X_train))
    test_acc = accuracy_score(y_test, model.predict(X_test))
    print(f"reduced-4-item RandomForestClassifier: train n={len(X_train)}, test n={len(X_test)}")
    print(f"train accuracy: {train_acc:.4f}")
    print(f"held-out test accuracy: {test_acc:.4f}")
    print(f"feature order: {REDUCED_FEATURES}")
    print(f"classes_: {list(model.classes_)}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, OUTPUT_PATH)
    print(f"saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
