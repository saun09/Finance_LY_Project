"""Generate the reproducible model and event-completeness comparison report."""

from __future__ import annotations

import csv
import json
import platform
from pathlib import Path
from typing import Any

import joblib
import numpy
import sklearn
import shap
import scipy
import matplotlib


ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "research_artifacts" / "experiments" / "results_v2"
REPORT_PATH = RESULTS_DIR / "model_and_logging_results.md"

# Reproducibility configuration for this report generator.
CONFIG: dict[str, Any] = {
    "seed": 42,
    "models_metrics": RESULTS_DIR / "model_logging_model_metrics.json",
    "old_faithfulness": RESULTS_DIR / "model_faithfulness_old",
    "v2_faithfulness": RESULTS_DIR / "model_faithfulness_v2",
    "old_completeness": ROOT
    / "research_artifacts"
    / "experiments"
    / "results"
    / "faithfulness_trace_completeness.csv",
    "output": REPORT_PATH,
}

ORIGINAL_TRAINERS = {
    "rf_reduced": ("backend/scripts/train_risk_tier_reduced_model.py",),
}
MODEL_NAMES = (
    "rf_full",
    "rf_reduced",
    "gb_full",
    "gb_reduced",
    "mlp_full",
    "mlp_reduced",
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required experiment output not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"required experiment output not found: {path}")
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _number(value: float | int, digits: int = 6) -> str:
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def _metrics_table(metrics: dict[str, Any]) -> str:
    rows = []
    for model in metrics["models"]:
        labels = model["legacy"]["confusion_matrix_labels"]
        rows.append(
            [
                model["model"],
                _number(model["legacy"]["accuracy"]),
                _number(model["new"]["accuracy"]),
                _number(model["accuracy_change"]),
                _number(model["legacy"]["macro_f1"]),
                _number(model["new"]["macro_f1"]),
                _number(model["macro_f1_change"]),
                _number(model["prediction_agreement_rate"]),
                f"labels={labels}; matrix="
                + json.dumps(model["legacy"]["confusion_matrix"], separators=(",", ":")),
                f"labels={labels}; matrix="
                + json.dumps(model["new"]["confusion_matrix"], separators=(",", ":")),
            ]
        )
    return _table(
        [
            "Model",
            "Old accuracy",
            "New accuracy",
            "Accuracy change",
            "Old macro-F1",
            "New macro-F1",
            "Macro-F1 change",
            "Prediction agreement",
            "Old confusion matrix",
            "New confusion matrix",
        ],
        rows,
    )


def _training_inventory() -> str:
    rows: list[list[str]] = []
    for model in MODEL_NAMES:
        trainers = ORIGINAL_TRAINERS.get(model, ())
        available = [
            trainer
            for trainer in trainers
            if (ROOT / Path(trainer)).is_file()
        ]
        rows.append(
            [
                model,
                ", ".join(available) if available else "No original training script found",
            ]
        )
    return _table(["Original model", "Original training script"], rows)


def _shap_comparison() -> str:
    old_dir = Path(CONFIG["old_faithfulness"])
    new_dir = Path(CONFIG["v2_faithfulness"])
    old_add = {row["model"]: row for row in _read_csv(old_dir / "shap_additivity.csv")}
    new_add = {row["model"]: row for row in _read_csv(new_dir / "shap_additivity.csv")}
    old_stability = {row["model"]: row for row in _read_csv(old_dir / "shap_rank_stability.csv")}
    new_stability = {row["model"]: row for row in _read_csv(new_dir / "shap_rank_stability.csv")}
    old_deletion = _read_csv(old_dir / "shap_deletion_summary.csv")
    new_deletion = _read_csv(new_dir / "shap_deletion_summary.csv")
    old_delete = {
        (row["model"], row["method"]): row
        for row in old_deletion
    }
    new_delete = {
        (row["model"], row["method"]): row
        for row in new_deletion
    }

    rows: list[list[str]] = []
    for model in old_add:
        before, after = old_add[model], new_add[model]
        rows.append(
            [
                model,
                "additivity_mean_absolute_error",
                before["mean_absolute_error"],
                after["mean_absolute_error"],
                f'{before["mean_error_ci95_low"]} to {before["mean_error_ci95_high"]}',
                f'{after["mean_error_ci95_low"]} to {after["mean_error_ci95_high"]}',
            ]
        )
        rows.append(
            [
                model,
                "additivity_within_tolerance_share",
                before["within_tolerance_share"],
                after["within_tolerance_share"],
                f'{before["share_ci95_low"]} to {before["share_ci95_high"]}',
                f'{after["share_ci95_low"]} to {after["share_ci95_high"]}',
            ]
        )
        before, after = old_stability[model], new_stability[model]
        rows.append(
            [
                model,
                "rank_spearman_mean",
                before["rank_spearman_mean"],
                after["rank_spearman_mean"],
                f'{before["ci95_low"]} to {before["ci95_high"]}',
                f'{after["ci95_low"]} to {after["ci95_high"]}',
            ]
        )
        for method in dict.fromkeys(
            key[1] for key in old_delete if key[0] == model
        ):
            before = old_delete[(model, method)]
            after = new_delete[(model, method)]
            rows.append(
                [
                    model,
                    f"deletion_{method}",
                    before["mean_predicted_class_probability_drop"],
                    after["mean_predicted_class_probability_drop"],
                    before["ci95_low"] + " to " + before["ci95_high"],
                    after["ci95_low"] + " to " + after["ci95_high"],
                ]
            )
    return _table(
        [
            "Model",
            "SHAP metric",
            "Old value",
            "V2 value",
            "Old tolerance/95% interval",
            "V2 tolerance/95% interval",
        ],
        rows,
    )


def _completeness_comparison() -> str:
    before_rows = _read_csv(Path(CONFIG["old_completeness"]))
    after_summary = _read_json(Path(CONFIG["v2_faithfulness"]) / "faithfulness_summary.json")
    after_rows = {
        row["dataset"]: row
        for row in after_summary["trace_completeness"]
    }
    before = {row["dataset"]: row for row in before_rows}
    rows = []
    for dataset, current in after_rows.items():
        previous = before[dataset]
        rows.append(
            [
                dataset,
                previous["traces"],
                previous["gaps"],
                current["traces"],
                current["gaps"],
                current["complete"],
            ]
        )
    return _table(
        [
            "Dataset",
            "Before traces",
            "Before gaps",
            "After traces",
            "After gaps",
            "After complete",
        ],
        rows,
    )


def generate_report() -> Path:
    if REPORT_PATH.exists():
        raise FileExistsError(f"refusing to overwrite existing results report: {REPORT_PATH}")
    metrics = _read_json(Path(CONFIG["models_metrics"]))
    old_summary = _read_json(Path(CONFIG["old_faithfulness"]) / "faithfulness_summary.json")
    new_summary = _read_json(Path(CONFIG["v2_faithfulness"]) / "faithfulness_summary.json")
    versions = {
        "Python": platform.python_version(),
        "NumPy": numpy.__version__,
        "SciPy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
        "joblib": joblib.__version__,
        "SHAP": shap.__version__,
        "Matplotlib": matplotlib.__version__,
    }
    old_gaps = {
        row["dataset"]: row for row in old_summary["trace_completeness"]
    }
    new_gaps = {
        row["dataset"]: row for row in new_summary["trace_completeness"]
    }
    original_gaps = {
        row["dataset"]: row for row in _read_csv(Path(CONFIG["old_completeness"]))
    }
    old_replay = {row["dataset"]: row for row in old_summary["replay_summary"]}
    new_replay = {row["dataset"]: row for row in new_summary["replay_summary"]}
    lines = [
        "# Model and logging results",
        "",
        "Data source: SOURCE_TO_FILL.",
        "",
        "## Original training-script inventory",
        "",
        _training_inventory(),
        "",
        "## Test-split model metrics",
        "",
        "Each confusion matrix uses tier labels in ascending order as rows (actual) and columns (predicted).",
        "",
        _metrics_table(metrics),
        "",
        "## SHAP faithfulness: old vs v2",
        "",
        _shap_comparison(),
        "",
        "## Trace completeness: before vs after",
        "",
        _completeness_comparison(),
        "",
        "## Replay totals",
        "",
        _table(
            ["Dataset", "Old replay mismatches", "V2 replay mismatches"],
            [
                [
                    dataset,
                    str(old_replay[dataset]["mismatched"]),
                    str(new_replay[dataset]["mismatched"]),
                ]
                for dataset in old_gaps
            ],
        ),
        "",
        "## Split and runtime",
        "",
        _table(
            ["Item", "Value"],
            [
                ["Seed", str(metrics["config"]["seed"])],
                ["Training rows", str(metrics["config"]["train_rows"])],
                ["Test rows", str(metrics["config"]["test_rows"])],
                ["Training-data SHA256", metrics["config"]["training_data_sha256"]],
                *[[name, version] for name, version in versions.items()],
            ],
        ),
        "",
        "## Source and execution",
        "",
        "Original models without a training script are retrained by `backend/scripts/retrain_risk_models.py`.",
        "",
        "Commands:",
        "",
        "```powershell",
        "python backend\\scripts\\retrain_risk_models.py",
        "python research_artifacts\\experiments\\faithfulness.py --model-version old",
        "python research_artifacts\\experiments\\faithfulness.py --model-version v2",
        "python research_artifacts\\experiments\\model_logging_analysis.py",
        "```",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"versions: {json.dumps(versions, sort_keys=True)}")
    print(f"report: {REPORT_PATH}")
    print(
        "trace_gaps: "
        + json.dumps(
            {
                dataset: {
                    "before": int(original_gaps[dataset]["gaps"]),
                    "after": int(new_gaps[dataset]["gaps"]),
                }
                for dataset in new_gaps
            },
            sort_keys=True,
        )
    )
    return REPORT_PATH


if __name__ == "__main__":
    generate_report()
