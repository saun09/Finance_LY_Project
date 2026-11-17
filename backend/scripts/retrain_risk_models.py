"""Reproduce the full and reduced RF, GB, and MLP risk-tier estimators.

Run from the repository root with ``python backend/scripts/retrain_risk_models.py``.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import warnings
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
for import_path in (ROOT, BACKEND_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import joblib
import numpy as np
import openpyxl
import sklearn
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.services.model_artifacts import runtime_versions
from app.services.risk_profile import compute_stated_tier
from app.services.risk_profile_config import QUESTIONNAIRE_V2
from scripts.train_risk_tier_reduced_model import (
    XLSX_PATH,
    load_training_rows_with_source_rows,
)


# Reproducibility configuration; the split and estimator seeds are recorded.
CONFIG: dict[str, Any] = {
    "seed": 42,
    "test_size": 0.20,
    "stratify": True,
    "output_dir": BACKEND_DIR / "app" / "ml_models" / "v2",
    "results_dir": ROOT / "research_artifacts" / "experiments" / "results_v2",
    "legacy_models": {
        "rf_full": BACKEND_DIR / "app" / "ml_models" / "risk_tier_rf.pkl",
        "rf_reduced": BACKEND_DIR / "app" / "ml_models" / "risk_tier_rf_reduced_4items.pkl",
        "gb_full": ROOT / "research_artifacts" / "models" / "gb_classifier_full_7items.pkl",
        "gb_reduced": ROOT / "research_artifacts" / "models" / "gb_classifier_reduced_4items.pkl",
        "mlp_full": ROOT / "research_artifacts" / "models" / "mlp_classifier_full_7items.pkl",
        "mlp_reduced": ROOT / "research_artifacts" / "models" / "mlp_classifier_reduced_4items.pkl",
        "mlp_scaler_full": ROOT / "research_artifacts" / "models" / "mlp_scaler_full_7items.pkl",
        "mlp_scaler_reduced": ROOT / "research_artifacts" / "models" / "mlp_scaler_reduced_4items.pkl",
    },
    "features": {
        "full_7items": (
            "horizon",
            "drawdown_reaction",
            "experience",
            "goal",
            "windfall_allocation",
            "sure_gain_tradeoff",
            "friend_description",
        ),
        "reduced_4items": (
            "windfall_allocation",
            "friend_description",
            "drawdown_reaction",
            "sure_gain_tradeoff",
        ),
    },
    "estimators": {
        "rf_full": {
            "type": "random_forest",
            "feature_set": "full_7items",
            "hyperparameters": {
                "n_estimators": 300,
                "random_state": 42,
                "max_depth": 6,
                "class_weight": "balanced",
            },
        },
        "rf_reduced": {
            "type": "random_forest",
            "feature_set": "reduced_4items",
            "hyperparameters": {
                "n_estimators": 300,
                "random_state": 42,
                "max_depth": None,
            },
        },
        "gb_full": {
            "type": "gradient_boosting",
            "feature_set": "full_7items",
            "hyperparameters": {
                "n_estimators": 200,
                "learning_rate": 0.05,
                "max_depth": 3,
                "random_state": 42,
            },
        },
        "gb_reduced": {
            "type": "gradient_boosting",
            "feature_set": "reduced_4items",
            "hyperparameters": {
                "n_estimators": 200,
                "learning_rate": 0.05,
                "max_depth": 3,
                "random_state": 42,
            },
        },
        "mlp_full": {
            "type": "mlp",
            "feature_set": "full_7items",
            "hyperparameters": {
                "hidden_layer_sizes": (16, 8),
                "max_iter": 2000,
                "random_state": 42,
            },
        },
        "mlp_reduced": {
            "type": "mlp",
            "feature_set": "reduced_4items",
            "hyperparameters": {
                "hidden_layer_sizes": (16, 8),
                "max_iter": 2000,
                "random_state": 42,
            },
        },
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _training_arrays() -> tuple[list[int], dict[str, np.ndarray], np.ndarray]:
    rows = load_training_rows_with_source_rows()
    source_rows = [source_row for source_row, _ in rows]
    answers_list = [answers for _, answers in rows]
    labels = np.asarray(
        [compute_stated_tier(answers, QUESTIONNAIRE_V2).tier for answers in answers_list],
        dtype=int,
    )
    feature_arrays = {
        feature_set: np.asarray(
            [
                [
                    QUESTIONNAIRE_V2.option_points(feature, answers[feature])
                    for feature in features
                ]
                for answers in answers_list
            ],
            dtype=float,
        )
        for feature_set, features in CONFIG["features"].items()
    }
    return source_rows, feature_arrays, labels


def _new_estimator(specification: dict[str, Any]):
    params = dict(specification["hyperparameters"])
    estimator_type = specification["type"]
    if estimator_type == "random_forest":
        return RandomForestClassifier(**params)
    if estimator_type == "gradient_boosting":
        return GradientBoostingClassifier(**params)
    if estimator_type == "mlp":
        return make_pipeline(StandardScaler(), MLPClassifier(**params))
    raise ValueError(f"unsupported model type: {estimator_type}")


def _legacy_estimator(name: str):
    path = Path(CONFIG["legacy_models"][name])
    if not path.is_file():
        raise FileNotFoundError(f"original model artifact not found: {path}")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        estimator = joblib.load(path)
    for warning in caught:
        print(f"legacy_load_warning[{name}]: {warning.message}")
    if name.startswith("mlp_"):
        scaler_name = "mlp_scaler_full" if name.endswith("_full") else "mlp_scaler_reduced"
        scaler_path = Path(CONFIG["legacy_models"][scaler_name])
        if not scaler_path.is_file():
            raise FileNotFoundError(f"original MLP scaler not found: {scaler_path}")
        scaler = joblib.load(scaler_path)
        return make_pipeline(scaler, estimator)
    return estimator


def _metrics(model, X_test: np.ndarray, y_test: np.ndarray) -> dict[str, Any]:
    predictions = np.asarray(model.predict(X_test), dtype=int)
    return {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "macro_f1": float(f1_score(y_test, predictions, average="macro", zero_division=0)),
        "confusion_matrix_labels": [1, 2, 3, 4, 5],
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=[1, 2, 3, 4, 5]).tolist(),
        "predictions": predictions.tolist(),
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def train_all() -> dict[str, Path]:
    if not XLSX_PATH.is_file():
        raise FileNotFoundError(f"training workbook not found: {XLSX_PATH}")
    feature_name_by_model = {
        "rf_full": "risk_tier_rf.pkl",
        "rf_reduced": "risk_tier_rf_reduced_4items.pkl",
        "gb_full": "gb_classifier_full_7items.pkl",
        "gb_reduced": "gb_classifier_reduced_4items.pkl",
        "mlp_full": "mlp_classifier_full_7items.pkl",
        "mlp_reduced": "mlp_classifier_reduced_4items.pkl",
    }
    output_dir = Path(CONFIG["output_dir"])
    results_dir = Path(CONFIG["results_dir"])
    planned_model_outputs = [
        output_dir / filename
        for filename in (
            "split_indices.json",
            *feature_name_by_model.values(),
            *(Path(name).with_suffix(".json").name for name in feature_name_by_model.values()),
            "mlp_scaler_full.pkl",
            "mlp_scaler_reduced.pkl",
        )
    ]
    planned_result_outputs = [
        results_dir / "model_logging_model_metrics.csv",
        results_dir / "model_logging_model_metrics.json",
    ]
    existing_outputs = [
        path for path in (*planned_model_outputs, *planned_result_outputs) if path.exists()
    ]
    if existing_outputs:
        raise FileExistsError(
            "refusing to overwrite existing model experiment outputs: "
            + ", ".join(str(path) for path in existing_outputs)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    source_rows, feature_arrays, labels = _training_arrays()
    mapped_indices = np.arange(len(source_rows))
    train_indices, test_indices = train_test_split(
        mapped_indices,
        test_size=float(CONFIG["test_size"]),
        random_state=int(CONFIG["seed"]),
        stratify=labels,
    )
    split = {
        "seed": CONFIG["seed"],
        "test_size": CONFIG["test_size"],
        "stratified": CONFIG["stratify"],
        "mapped_row_count": len(source_rows),
        "training_data_sha256": _sha256(XLSX_PATH),
        "train_mapped_indices": train_indices.tolist(),
        "test_mapped_indices": test_indices.tolist(),
        "train_worksheet_rows": [source_rows[int(index)] for index in train_indices],
        "test_worksheet_rows": [source_rows[int(index)] for index in test_indices],
    }
    split_path = output_dir / "split_indices.json"
    split_path.write_text(json.dumps(split, indent=2) + "\n", encoding="utf-8")

    metric_rows: list[dict[str, Any]] = []
    model_paths: dict[str, Path] = {"split_indices": split_path}
    old_new_report: list[dict[str, Any]] = []
    versions = runtime_versions()

    for name, specification in CONFIG["estimators"].items():
        feature_set = str(specification["feature_set"])
        X = feature_arrays[feature_set]
        X_train, X_test = X[train_indices], X[test_indices]
        y_train, y_test = labels[train_indices], labels[test_indices]
        estimator = _new_estimator(specification)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            estimator.fit(X_train, y_train)
        for warning in captured:
            print(f"training_warning[{name}]: {warning.message}")

        model_path = output_dir / feature_name_by_model[name]
        joblib.dump(estimator, model_path)
        model_paths[name] = model_path
        current_metrics = _metrics(estimator, X_test, y_test)
        legacy = _legacy_estimator(name)
        legacy_metrics = _metrics(legacy, X_test, y_test)
        agreement = float(
            np.mean(
                np.asarray(current_metrics["predictions"])
                == np.asarray(legacy_metrics["predictions"])
            )
        )
        current_metrics.pop("predictions")
        legacy_metrics.pop("predictions")
        sidecar = {
            "model": name,
            "artifact": model_path.name,
            "feature_set": feature_set,
            "features_in_order": CONFIG["features"][feature_set],
            "versions": versions,
            "seed": CONFIG["seed"],
            "hyperparameters": _jsonable(specification["hyperparameters"]),
            "training_data_sha256": split["training_data_sha256"],
            "split_sizes": {"train": len(train_indices), "test": len(test_indices)},
            "metrics": current_metrics,
            "legacy_comparison": {
                "prediction_agreement_rate": agreement,
                "legacy_metrics": legacy_metrics,
                "accuracy_change": current_metrics["accuracy"] - legacy_metrics["accuracy"],
                "macro_f1_change": current_metrics["macro_f1"] - legacy_metrics["macro_f1"],
            },
        }
        sidecar_path = model_path.with_suffix(".json")
        sidecar_path.write_text(
            json.dumps(_jsonable(sidecar), indent=2) + "\n",
            encoding="utf-8",
        )
        model_paths[f"{name}_sidecar"] = sidecar_path
        metric_rows.append(
            {
                "model": name,
                "feature_set": feature_set,
                "legacy_accuracy": legacy_metrics["accuracy"],
                "new_accuracy": current_metrics["accuracy"],
                "accuracy_change": current_metrics["accuracy"] - legacy_metrics["accuracy"],
                "legacy_macro_f1": legacy_metrics["macro_f1"],
                "new_macro_f1": current_metrics["macro_f1"],
                "macro_f1_change": current_metrics["macro_f1"] - legacy_metrics["macro_f1"],
                "prediction_agreement_rate": agreement,
                "legacy_confusion_matrix": legacy_metrics["confusion_matrix"],
                "new_confusion_matrix": current_metrics["confusion_matrix"],
            }
        )
        old_new_report.append(
            {
                "model": name,
                "legacy": legacy_metrics,
                "new": current_metrics,
                "prediction_agreement_rate": agreement,
                "accuracy_change": current_metrics["accuracy"] - legacy_metrics["accuracy"],
                "macro_f1_change": current_metrics["macro_f1"] - legacy_metrics["macro_f1"],
            }
        )
        if name.startswith("mlp_"):
            scaler_path = output_dir / f"{name.replace('mlp_', 'mlp_scaler_')}.pkl"
            joblib.dump(estimator.named_steps["standardscaler"], scaler_path)
            model_paths[f"{name}_scaler"] = scaler_path

    import csv

    metrics_path = results_dir / "model_logging_model_metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8") as file:
        fieldnames = [
            "model", "feature_set", "legacy_accuracy", "new_accuracy", "accuracy_change",
            "legacy_macro_f1", "new_macro_f1", "macro_f1_change",
            "prediction_agreement_rate", "legacy_confusion_matrix", "new_confusion_matrix",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in metric_rows:
            encoded = dict(row)
            encoded["legacy_confusion_matrix"] = json.dumps(row["legacy_confusion_matrix"])
            encoded["new_confusion_matrix"] = json.dumps(row["new_confusion_matrix"])
            writer.writerow(encoded)
    metric_json_path = results_dir / "model_logging_model_metrics.json"
    metric_json_path.write_text(
        json.dumps(
            {
                "versions": versions,
                "config": {
                    "seed": CONFIG["seed"],
                    "test_size": CONFIG["test_size"],
                    "training_data_sha256": split["training_data_sha256"],
                    "train_rows": len(train_indices),
                    "test_rows": len(test_indices),
                },
                "models": old_new_report,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "versions": versions,
                "training_data_sha256": split["training_data_sha256"],
                "split_sizes": {"train": len(train_indices), "test": len(test_indices)},
                "models": {
                    row["model"]: {
                        "legacy_accuracy": row["legacy"]["accuracy"],
                        "new_accuracy": row["new"]["accuracy"],
                        "prediction_agreement_rate": row["prediction_agreement_rate"],
                    }
                    for row in old_new_report
                },
                "outputs": {
                    "model_dir": str(output_dir),
                    "metrics": str(metrics_path),
                    "metrics_json": str(metric_json_path),
                },
            },
            indent=2,
        )
    )
    model_paths["metrics"] = metrics_path
    model_paths["metrics_json"] = metric_json_path
    return model_paths


if __name__ == "__main__":
    train_all()
