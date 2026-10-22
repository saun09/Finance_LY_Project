"""Module 3b: a genuinely trained, data-driven risk-tier predictor, kept
deliberately separate from Module 3's deterministic weighted-sum/threshold
logic in risk_profile.py. That module stays pure and model-free on
purpose (see its own docstring); this one is the one place in the app
that loads and runs an actual trained model (a scikit-learn
GradientBoostingClassifier, trained offline on Risk_questionnaire_400.xlsx
-- see research_artifacts/models/MANIFEST.json for training details and
held-out accuracy).

Per-prediction SHAP values are computed here, at prediction time, and
logged alongside the prediction via log_suggestion_event under
module_source="risk_profile_ml" -- Module 9 (transparency.py) then only
*reads* those already-computed numbers back out, the same as it does for
every other module source. Module 9 itself still never imports sklearn or
shap and still never recomputes a decision; the model call happens here,
once, at submission time, not on every later trace read.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import shap

from app.services.risk_profile_config import Questionnaire

MODEL_PATH = Path(__file__).resolve().parents[1] / "ml_models" / "risk_tier_rf.pkl"
MODEL_VERSION = "rf_classifier_full_7items_v1"
# RandomForestClassifier, not GradientBoostingClassifier: shap.TreeExplainer
# only supports sklearn's GradientBoostingClassifier for *binary*
# classification, and this is a 5-class (tier 1-5) problem. RandomForest
# has full multiclass TreeExplainer support and performed comparably in
# the offline research comparison (see research_artifacts/models).

# Exact order the model was trained on (backend/scripts or
# research_artifacts/models/MANIFEST.json's "full_7items" feature list) --
# a GradientBoostingClassifier only knows feature *position*, not name, so
# this order must never drift from training without retraining the model.
FEATURE_ORDER: tuple[str, ...] = (
    "horizon",
    "drawdown_reaction",
    "experience",
    "goal",
    "windfall_allocation",
    "sure_gain_tradeoff",
    "friend_description",
)

# Quick-mode: predicts a tier from only the 4 questions most predictive of
# the full-7 deterministic score (see backend/scripts/
# train_risk_tier_reduced_model.py), used when a user answers just the
# "main" questions instead of all 7 -- this prediction becomes the stated
# tier itself (see risk_profile_service.py), not just a logged second
# opinion, so the questionnaire can genuinely be shorter rather than only
# explaining a full-length answer differently. Held-out accuracy 78.16% on
# 434 training rows (Risk_questionnaire_400.xlsx) vs. the full-7 model's
# higher accuracy -- a real, disclosed trade-off for fewer questions, never
# presented as equally precise as a full-7 deterministic score.
MODEL_PATH_REDUCED = Path(__file__).resolve().parents[1] / "ml_models" / "risk_tier_rf_reduced_4items.pkl"
MODEL_VERSION_REDUCED = "rf_classifier_reduced_4items_v1"
FEATURE_ORDER_REDUCED: tuple[str, ...] = (
    "windfall_allocation",
    "friend_description",
    "drawdown_reaction",
    "sure_gain_tradeoff",
)


class MLModelUnavailableError(RuntimeError):
    """Raised when the trained model file is missing or fails to load.
    Callers should treat this as "ML explanation not available this time",
    not fail the user's static risk-profile submission over it."""


@lru_cache(maxsize=2)
def _load_model(model_path: Path):
    if not model_path.exists():
        raise MLModelUnavailableError(f"model file not found at {model_path}")
    try:
        return joblib.load(model_path)
    except Exception as exc:  # noqa: BLE001 -- any load failure is equally "unavailable"
        raise MLModelUnavailableError(f"failed to load model from {model_path}: {exc}") from exc


@lru_cache(maxsize=2)
def _get_explainer(model_path: Path):
    return shap.TreeExplainer(_load_model(model_path))


@dataclass(frozen=True)
class MLFeatureContribution:
    question_id: str
    selected_value: str
    selected_points: int
    shap_value: float
    direction: str  # "increases" | "decreases" | "neutral"


@dataclass(frozen=True)
class MLRiskPrediction:
    model_version: str
    predicted_tier: int
    class_probabilities: dict[str, float]
    feature_contributions: tuple[MLFeatureContribution, ...]


def _direction_of(shap_value: float) -> str:
    if shap_value > 1e-9:
        return "increases"
    if shap_value < -1e-9:
        return "decreases"
    return "neutral"


def predict_with_explanation(
    answers: dict[str, str],
    questionnaire: Questionnaire,
    *,
    feature_order: tuple[str, ...] = FEATURE_ORDER,
    model_path: Path = MODEL_PATH,
    model_version: str = MODEL_VERSION,
) -> MLRiskPrediction:
    """Predict a risk tier from `answers` and explain that specific
    prediction with per-feature SHAP values. Defaults to the full-7-item
    model; pass feature_order=FEATURE_ORDER_REDUCED, model_path=
    MODEL_PATH_REDUCED, model_version=MODEL_VERSION_REDUCED for a quick-
    mode (4-question) prediction instead -- same function, same SHAP
    explanation shape, different trained model underneath.

    Raises MLModelUnavailableError if the model can't be loaded, or
    ValueError if `answers` is missing one of the required questions
    (propagated from `questionnaire.option_points`, same as Module 3's own
    validation).
    """
    model = _load_model(model_path)
    explainer = _get_explainer(model_path)

    points = [questionnaire.option_points(qid, answers[qid]) for qid in feature_order]
    X = np.array([points], dtype=float)

    predicted_tier = int(model.predict(X)[0])
    proba = model.predict_proba(X)[0]
    class_probabilities = {str(cls): float(p) for cls, p in zip(model.classes_, proba)}

    # shap_values for a multiclass RandomForestClassifier: SHAP's output
    # shape has changed across versions (a list of one (n_samples,
    # n_features) array per class, vs. a single (n_samples, n_features,
    # n_classes) array) -- handle both so this doesn't silently break on a
    # shap upgrade. Explain the predicted class specifically ("why *this*
    # tier"), not an average across all five tiers.
    raw_shap = explainer.shap_values(X)
    class_index = list(model.classes_).index(predicted_tier)
    if isinstance(raw_shap, list):
        shap_row = np.asarray(raw_shap[class_index])[0]
    else:
        arr = np.asarray(raw_shap)
        shap_row = arr[0, :, class_index] if arr.ndim == 3 else arr[0]

    contributions = tuple(
        MLFeatureContribution(
            question_id=qid,
            selected_value=answers[qid],
            selected_points=int(points[i]),
            shap_value=float(shap_row[i]),
            direction=_direction_of(float(shap_row[i])),
        )
        for i, qid in enumerate(feature_order)
    )

    return MLRiskPrediction(
        model_version=model_version,
        predicted_tier=predicted_tier,
        class_probabilities=class_probabilities,
        feature_contributions=contributions,
    )
