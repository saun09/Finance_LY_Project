"""Compare V2 stated-risk measures with workbook self-rated willingness."""

from __future__ import annotations

import csv
import json
import math
import platform
import sys
import warnings
from pathlib import Path
from typing import Any, Callable

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import scipy
from scipy import stats


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.risk_profile import compute_stated_tier  # noqa: E402
from app.services.risk_profile_config import QUESTIONNAIRE_V2  # noqa: E402
from app.services.risk_profile_ml import FEATURE_ORDER_REDUCED  # noqa: E402
from scripts.train_risk_tier_reduced_model import (  # noqa: E402
    COL_HORIZON,
    XLSX_PATH,
    load_training_rows,
    load_training_rows_with_source_rows,
)


# All analysis parameters and source locations are kept in this config block.
ANALYSIS_CONFIG: dict[str, Any] = {
    "workbook_path": XLSX_PATH,
    "worksheet_name": "Mock Responses",
    "self_rating_header": "On a scale of 0 to 10, how willing are you to take financial risks, in general?",
    "production_reduced_model": BACKEND_DIR / "app" / "ml_models" / "risk_tier_rf_reduced_4items.pkl",
    "results_dir": ROOT / "research_artifacts" / "experiments" / "results",
    "bootstrap_replicates": 2000,
    "bootstrap_seed": 20261108,
    "confidence_level": 0.95,
    "heatmap_dpi": 160,
    "reported_source_composition": {"real": 130, "synthetic": 304},
    "source_has_row_level_flag": False,
    "risk_tolerance_items": (
        "windfall_allocation",
        "sure_gain_tradeoff",
        "drawdown_reaction",
        "friend_description",
    ),
    "contextual_items": ("horizon", "experience", "goal"),
}

QUESTION_IDS = tuple(question.id for question in QUESTIONNAIRE_V2.questions)
ITEM_LABELS = {
    "horizon": "Investment horizon",
    "drawdown_reaction": "Drawdown reaction",
    "experience": "Investment experience",
    "goal": "Primary goal",
    "windfall_allocation": "Windfall allocation",
    "sure_gain_tradeoff": "Sure-gain trade-off",
    "friend_description": "Friend description",
}
MEASURE_LABELS = {
    "weighted_score": "V2 weighted score",
    "stated_tier": "V2 stated tier",
    "reduced_rf_tier": "Reduced 4-item RF predicted tier",
    **{question_id: ITEM_LABELS[question_id] for question_id in QUESTION_IDS},
}
CORRELATION_METHODS: dict[str, Callable[..., Any]] = {
    "spearman": stats.spearmanr,
    "kendall": stats.kendalltau,
}


def parse_self_rating(value: Any) -> tuple[float | None, str | None]:
    """Parse a numeric self-rating in the inclusive 0-10 range."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, "missing"
    if isinstance(value, bool):
        return None, "non_numeric"
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None, "non_numeric"
    if not math.isfinite(rating):
        return None, "non_numeric"
    if not 0 <= rating <= 10:
        return None, "out_of_range"
    return rating, None


def cronbach_alpha(values: np.ndarray) -> float:
    """Compute Cronbach's alpha from rows of item-point scores."""
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        raise ValueError("values must be a 2D array with at least two items")
    if matrix.shape[0] < 2 or not np.isfinite(matrix).all():
        raise ValueError("values must contain at least two complete finite rows")
    item_variances = np.var(matrix, axis=0, ddof=1)
    total_variance = np.var(matrix.sum(axis=1), ddof=1)
    if total_variance == 0:
        return float("nan")
    item_count = matrix.shape[1]
    return float(item_count / (item_count - 1) * (1 - item_variances.sum() / total_variance))


def _correlation(method: str, x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    result = CORRELATION_METHODS[method](x, y)
    return float(result.statistic), float(result.pvalue)


def bootstrap_correlation_interval(
    x: np.ndarray,
    y: np.ndarray,
    method: str,
    seed: int,
    n_resamples: int = int(ANALYSIS_CONFIG["bootstrap_replicates"]),
) -> tuple[float, float]:
    """Return a paired percentile bootstrap interval for a correlation."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or len(x) < 3:
        raise ValueError("x and y must be equal-length vectors with at least 3 values")
    if method not in CORRELATION_METHODS:
        raise ValueError(f"unsupported correlation method: {method}")
    if n_resamples <= 0:
        raise ValueError("n_resamples must be positive")

    rng = np.random.default_rng(seed)
    samples = np.empty(n_resamples, dtype=float)
    for index in range(n_resamples):
        sample_indices = rng.integers(0, len(x), size=len(x))
        samples[index] = _correlation(method, x[sample_indices], y[sample_indices])[0]
    finite_samples = samples[np.isfinite(samples)]
    if not len(finite_samples):
        return float("nan"), float("nan")
    tail = (1 - float(ANALYSIS_CONFIG["confidence_level"])) / 2
    return (
        float(np.quantile(finite_samples, tail)),
        float(np.quantile(finite_samples, 1 - tail)),
    )


def _load_workbook_source_rows() -> tuple[list[tuple[int, Any]], list[tuple[int, Any]], int]:
    workbook = openpyxl.load_workbook(ANALYSIS_CONFIG["workbook_path"], read_only=True, data_only=True)
    try:
        worksheet = workbook[ANALYSIS_CONFIG["worksheet_name"]]
        rows = list(worksheet.iter_rows(values_only=True))
    finally:
        workbook.close()
    headers = rows[0]
    try:
        rating_index = headers.index(ANALYSIS_CONFIG["self_rating_header"])
    except ValueError as exc:
        raise ValueError(
            f"self-rating column not found: {ANALYSIS_CONFIG['self_rating_header']!r}"
        ) from exc
    source_rows = [(excel_row, row) for excel_row, row in enumerate(rows[1:], start=2)]
    ratings = [(excel_row, row[rating_index] if rating_index < len(row) else None) for excel_row, row in source_rows]
    return source_rows, ratings, rating_index


def load_aligned_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Join canonical mapped answers to self-ratings using worksheet row IDs."""
    mapped_with_rows = load_training_rows_with_source_rows()
    canonical_answers = load_training_rows()
    if canonical_answers != [answers for _, answers in mapped_with_rows]:
        raise RuntimeError("row-indexed loader output differs from canonical load_training_rows output")

    source_rows, ratings, rating_index = _load_workbook_source_rows()
    source_by_number = dict(source_rows)
    rating_by_number = dict(ratings)
    mapped_row_numbers = {row_number for row_number, _ in mapped_with_rows}
    if len(mapped_with_rows) != len(mapped_row_numbers):
        raise RuntimeError("canonical loader returned duplicate source row numbers")

    mapped_drop_reasons = {"missing_horizon": 0, "unparseable_mapped_answers": 0}
    for row_number, row in source_rows:
        if row_number not in mapped_row_numbers:
            if row[COL_HORIZON] is None or (isinstance(row[COL_HORIZON], str) and not row[COL_HORIZON].strip()):
                mapped_drop_reasons["missing_horizon"] += 1
            else:
                mapped_drop_reasons["unparseable_mapped_answers"] += 1

    worksheet_rating_counts = {"valid": 0, **{"missing": 0, "non_numeric": 0, "out_of_range": 0}}
    for _, value in ratings:
        _, reason = parse_self_rating(value)
        worksheet_rating_counts["valid" if reason is None else str(reason)] += 1

    rating_drop_reasons = {"missing": 0, "non_numeric": 0, "out_of_range": 0}
    valid_rows: list[dict[str, Any]] = []
    for row_number, answers in mapped_with_rows:
        rating, reason = parse_self_rating(rating_by_number[row_number])
        if reason is not None:
            rating_drop_reasons[reason] += 1
            continue
        if rating is None:
            raise RuntimeError("valid self-rating parser result unexpectedly has no value")
        valid_rows.append(
            {
                "excel_row": row_number,
                "answers": answers,
                "self_rating": rating,
                "raw_row": source_by_number[row_number],
            }
        )

    accounting = {
        "worksheet_data_rows": len(source_rows),
        "mapped_rows": len(mapped_with_rows),
        "mapped_drop_reasons": mapped_drop_reasons,
        "worksheet_self_rating_counts": worksheet_rating_counts,
        "mapped_rows_with_valid_self_rating": len(valid_rows),
        "self_rating_drop_reasons_on_mapped_rows": rating_drop_reasons,
        "rating_column_index_zero_based": rating_index,
        "rating_column_header": ANALYSIS_CONFIG["self_rating_header"],
    }
    return valid_rows, accounting


def _score_rows(
    valid_rows: list[dict[str, Any]],
    model: Any,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Score only mapped questionnaire answers; self-rating is not model input."""
    ratings = np.asarray([row["self_rating"] for row in valid_rows], dtype=float)
    measures: dict[str, list[float]] = {
        "weighted_score": [],
        "stated_tier": [],
        "reduced_rf_tier": [],
        **{question_id: [] for question_id in QUESTION_IDS},
    }
    reduced_features: list[list[int]] = []
    for row in valid_rows:
        answers = row["answers"]
        stated = compute_stated_tier(answers, QUESTIONNAIRE_V2)
        measures["weighted_score"].append(float(stated.score))
        measures["stated_tier"].append(float(stated.tier))
        for question_id in QUESTION_IDS:
            measures[question_id].append(
                float(QUESTIONNAIRE_V2.option_points(question_id, answers[question_id]))
            )
        reduced_features.append(
            [
                QUESTIONNAIRE_V2.option_points(question_id, answers[question_id])
                for question_id in FEATURE_ORDER_REDUCED
            ]
        )

    # This matrix contains the four questionnaire features only. The self-rating
    # is intentionally absent from both model input and the model's target.
    model_inputs = np.asarray(reduced_features, dtype=float)
    predicted_tiers = model.predict(model_inputs)
    measures["reduced_rf_tier"] = [float(value) for value in predicted_tiers]
    return ratings, {key: np.asarray(values, dtype=float) for key, values in measures.items()}


def _correlation_rows(
    ratings: np.ndarray,
    measures: dict[str, np.ndarray],
    dataset_label: str,
    seed_offset: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for measure_index, (measure, values) in enumerate(measures.items()):
        for method_index, method in enumerate(CORRELATION_METHODS):
            estimate, p_value = _correlation(method, ratings, values)
            ci_low, ci_high = bootstrap_correlation_interval(
                ratings,
                values,
                method,
                seed=int(ANALYSIS_CONFIG["bootstrap_seed"]) + seed_offset + measure_index * 17 + method_index,
            )
            rows.append(
                {
                    "dataset": dataset_label,
                    "measure": measure,
                    "measure_label": MEASURE_LABELS[measure],
                    "method": method,
                    "n": len(ratings),
                    "coefficient": estimate,
                    "ci95_low": ci_low,
                    "ci95_high": ci_high,
                    "p_value": p_value,
                }
            )
    return rows


def _item_total_rows(item_matrix: np.ndarray, item_names: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item_name in enumerate(item_names):
        other_total = item_matrix[:, [j for j in range(len(item_names)) if j != index]].sum(axis=1)
        item_values = item_matrix[:, index]
        result = stats.pearsonr(item_values, other_total)
        # Item-total is conventionally Pearson; percentile bootstrap the
        # Pearson coefficient directly on paired rows.
        ci_low, ci_high = _bootstrap_pearson_interval(
            item_values,
            other_total,
            seed=int(ANALYSIS_CONFIG["bootstrap_seed"]) + 100 + index,
        )
        rows.append(
            {
                "item": item_name,
                "item_label": ITEM_LABELS[item_name],
                "n": len(item_values),
                "item_total_pearson": float(result.statistic),
                "ci95_low": ci_low,
                "ci95_high": ci_high,
                "p_value": float(result.pvalue),
            }
        )
    return rows


def _bootstrap_pearson_interval(x: np.ndarray, y: np.ndarray, seed: int) -> tuple[float, float]:
    if len(x) != len(y) or len(x) < 3:
        raise ValueError("x and y must have equal length of at least 3")
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(int(ANALYSIS_CONFIG["bootstrap_replicates"])):
        indices = rng.integers(0, len(x), size=len(x))
        result = stats.pearsonr(x[indices], y[indices]).statistic
        if np.isfinite(result):
            samples.append(float(result))
    if not samples:
        return float("nan"), float("nan")
    tail = (1 - float(ANALYSIS_CONFIG["confidence_level"])) / 2
    return float(np.quantile(samples, tail)), float(np.quantile(samples, 1 - tail))


def _matrix_and_heatmap(
    ratings: np.ndarray,
    measures: dict[str, np.ndarray],
    output_dir: Path,
) -> tuple[list[dict[str, Any]], Path]:
    matrix_names = list(QUESTION_IDS) + ["self_rating"]
    matrix_values = np.column_stack(
        [
            measures[question_id]
            for question_id in QUESTION_IDS
        ]
        + [ratings]
    )
    correlation = stats.spearmanr(matrix_values, axis=0).statistic
    rows = [
        {"variable": name, **{column: float(correlation[i, j]) for j, column in enumerate(matrix_names)}}
        for i, name in enumerate(matrix_names)
    ]

    fig, axis = plt.subplots(figsize=(10, 8))
    image = axis.imshow(correlation, cmap="coolwarm", vmin=-1, vmax=1)
    fig.colorbar(image, ax=axis, label="Spearman correlation")
    labels = [ITEM_LABELS[name] if name != "self_rating" else "Self-rating (0-10)" for name in matrix_names]
    axis.set_xticks(np.arange(len(labels)), labels, rotation=45, ha="right")
    axis.set_yticks(np.arange(len(labels)), labels)
    axis.set_title("Spearman correlation matrix")
    for i in range(len(labels)):
        for j in range(len(labels)):
            axis.text(j, i, f"{correlation[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.tight_layout()
    output_path = output_dir / "spearman_correlation_heatmap.png"
    fig.savefig(output_path, dpi=int(ANALYSIS_CONFIG["heatmap_dpi"]))
    plt.close(fig)
    return rows, output_path


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty results table: {path.name}")
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_report(
    accounting: dict[str, Any],
    correlation_rows: list[dict[str, Any]],
    item_total_rows: list[dict[str, Any]],
    alpha_rows: list[dict[str, Any]],
    matrix_rows: list[dict[str, Any]],
    sensitivity_accounting: dict[str, Any],
    model_load_warnings: list[str],
    output_path: Path,
) -> None:
    versions = {
        "Python": platform.python_version(),
        "NumPy": np.__version__,
        "SciPy": scipy.__version__,
        "scikit-learn": __import__("sklearn").__version__,
        "openpyxl": openpyxl.__version__,
        "Matplotlib": matplotlib.__version__,
    }
    lines = [
        "# Convergent validity: stated risk and self-rated willingness",
        "",
        "## Data scope and limitations",
        "",
        f"This workbook is a mixed set of {ANALYSIS_CONFIG['reported_source_composition']['real']} real and "
        f"{ANALYSIS_CONFIG['reported_source_composition']['synthetic']} synthetic responses, with no row-level "
        "source flag. These results therefore cannot be attributed to real participants.",
        "The self-rated willingness response is used only as an analysis outcome. It is not used as a model feature "
        "or label; the reduced Random Forest receives only the four mapped questionnaire item scores.",
        "",
        "## Row accounting",
        "",
        f"- Worksheet data rows: {accounting['worksheet_data_rows']}.",
        f"- Rows mapped by the canonical training loader: {accounting['mapped_rows']}.",
        f"- Worksheet rows with a valid numeric 0-10 self-rating: {accounting['worksheet_self_rating_counts']['valid']}.",
        f"- Rows with valid mapped fields and valid self-rating used in main correlations: "
        f"{accounting['mapped_rows_with_valid_self_rating']}.",
        f"- Dropped for missing horizon: {accounting['mapped_drop_reasons']['missing_horizon']}.",
        f"- Dropped for unparseable mapped answers: {accounting['mapped_drop_reasons']['unparseable_mapped_answers']}.",
        f"- Among loader-mapped rows, dropped for missing self-rating: "
        f"{accounting['self_rating_drop_reasons_on_mapped_rows']['missing']}.",
        f"- Among loader-mapped rows, dropped for non-numeric self-rating: "
        f"{accounting['self_rating_drop_reasons_on_mapped_rows']['non_numeric']}.",
        f"- Among loader-mapped rows, dropped for out-of-range self-rating: "
        f"{accounting['self_rating_drop_reasons_on_mapped_rows']['out_of_range']}.",
        "",
        "## Correlations with self-rating",
        "",
        "Coefficients are Spearman rho and Kendall tau-b, with paired row-bootstrap percentile 95% confidence intervals "
        "and two-sided asymptotic p-values. The outcome scale is the workbook's numeric 0-10 self-rating.",
        "",
        "| Analysis | Measure | Method | n | Coefficient | 95% bootstrap CI | p-value |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in correlation_rows:
        lines.append(
            f"| {row['dataset']} | {row['measure_label']} | {row['method']} | {row['n']} | {row['coefficient']:.4f} "
            f"| [{row['ci95_low']:.4f}, {row['ci95_high']:.4f}] | {row['p_value']:.6g} |"
        )
    sensitivity_correlation_rows = [
        row
        for row in correlation_rows
        if row["dataset"] == "complete_mapped_fields_sensitivity"
    ]
    lines.extend(
        [
            "",
            "### Complete-mapped-field sensitivity results",
            "",
            "These are the main correlations recomputed after filtering for rows with all mapped fields present.",
            "",
            "| Measure | Method | n | Coefficient | 95% bootstrap CI | p-value |",
            "|---|---|---:|---:|---:|---:|",
            *[
                f"| {row['measure_label']} | {row['method']} | {row['n']} | {row['coefficient']:.4f} "
                f"| [{row['ci95_low']:.4f}, {row['ci95_high']:.4f}] | {row['p_value']:.6g} |"
                for row in sensitivity_correlation_rows
            ],
            "",
            "",
            "## Item-total correlations",
            "",
            "Corrected item-total correlations use Pearson correlation between the item's unweighted 1-5 option points "
            "and the sum of the other six items, on complete mapped rows. Intervals use paired row bootstrap; p-values are two-sided.",
            "",
            "| Item | n | Pearson item-total r | 95% bootstrap CI | p-value |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in item_total_rows:
        lines.append(
            f"| {row['item_label']} | {row['n']} | {row['item_total_pearson']:.4f} "
            f"| [{row['ci95_low']:.4f}, {row['ci95_high']:.4f}] | {row['p_value']:.6g} |"
        )
    lines.extend(
        [
            "",
            "## Internal consistency",
            "",
            "Cronbach's alpha is calculated on mapped 1-5 item points for complete mapped rows. The three-item "
            "contextual set comprises investment horizon, investment experience, and primary goal; these are contextual "
            "items and are not represented as risk-tolerance indicators.",
            "",
            "| Item set | n | Items | Cronbach's alpha |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in alpha_rows:
        lines.append(
            f"| {row['item_set']} | {row['n']} | {row['items']} | {row['cronbach_alpha']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Spearman correlation matrix",
            "",
            "The matrix uses valid-self-rating rows and the seven mapped items plus self-rating.",
            "",
            "| Variable | " + " | ".join(row["variable"] for row in matrix_rows) + " |",
            "|---|" + "---:|" * len(matrix_rows),
        ]
    )
    for row in matrix_rows:
        lines.append(
            "| "
            + row["variable"]
            + " | "
            + " | ".join(f"{row[column]:.4f}" for column in (entry["variable"] for entry in matrix_rows))
            + " |"
        )
    lines.extend(
        [
            "",
            "![Spearman correlation heatmap](./spearman_correlation_heatmap.png)",
            "",
            "## Missing-mapped-field sensitivity",
            "",
            f"Repeating the main correlations after dropping any row with a missing mapped field leaves "
            f"{sensitivity_accounting['sensitivity_n']} rows, compared with {accounting['mapped_rows_with_valid_self_rating']} "
            f"in the main analysis. Rows removed by this additional filter: {sensitivity_accounting['dropped_for_missing_mapped_fields']}. "
            "The sensitivity coefficients and intervals are included as a separate analysis label in `correlations.csv`.",
            "",
            "## Software versions",
            "",
            "| Component | Version |",
            "|---|---|",
        ]
    )
    for name, version in versions.items():
        lines.append(f"| {name} | {version} |")
    if model_load_warnings:
        lines.extend(["", "### Model loading warnings", ""])
        lines.extend(f"- {warning}" for warning in model_load_warnings)
    lines.extend(
        [
            "",
            "## Generated files",
            "",
            "- `correlations.csv` — Spearman/Kendall associations with bootstrap intervals and p-values.",
            "- `item_total_correlations.csv` — corrected item-total results.",
            "- `internal_consistency.csv` — Cronbach alpha results.",
            "- `spearman_correlation_matrix.csv` and `spearman_correlation_heatmap.png`.",
            "- `row_accounting.json` — workbook row counts and exclusion reasons.",
            "- `validity_summary.json` — machine-readable analysis results and provenance note.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_analysis() -> dict[str, Path]:
    """Run the workbook analysis without exporting personal workbook fields."""
    valid_rows, accounting = load_aligned_rows()
    if not valid_rows:
        raise ValueError("no rows have both canonical mapped answers and a valid self-rating")

    model_path = Path(ANALYSIS_CONFIG["production_reduced_model"])
    if not model_path.is_file():
        raise FileNotFoundError(f"production reduced risk model not found: {model_path}")
    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        model = joblib.load(model_path)
    model_load_warnings = list(dict.fromkeys(str(item.message) for item in captured_warnings))
    for warning_message in model_load_warnings:
        print(f"model_load_warning: {warning_message}")
    ratings, measures = _score_rows(valid_rows, model)
    correlation_rows = _correlation_rows(ratings, measures, "main_valid_rating", 0)

    mapped_features = np.asarray(
        [
            [
                QUESTIONNAIRE_V2.option_points(question_id, row["answers"][question_id])
                for question_id in QUESTION_IDS
            ]
            for row in valid_rows
        ],
        dtype=float,
    )
    complete_mask = np.isfinite(mapped_features).all(axis=1)
    sensitivity_rows = [row for row, keep in zip(valid_rows, complete_mask) if keep]
    sensitivity_ratings, sensitivity_measures = _score_rows(sensitivity_rows, model)
    sensitivity_correlation_rows = _correlation_rows(
        sensitivity_ratings,
        sensitivity_measures,
        "complete_mapped_fields_sensitivity",
        10_000,
    )
    correlation_rows.extend(sensitivity_correlation_rows)
    sensitivity_accounting = {
        "sensitivity_n": len(sensitivity_rows),
        "dropped_for_missing_mapped_fields": int(len(valid_rows) - len(sensitivity_rows)),
    }

    complete_answers = np.asarray(
        [
            [
                QUESTIONNAIRE_V2.option_points(question_id, row["answers"][question_id])
                for question_id in QUESTION_IDS
            ]
            for row in valid_rows
        ],
        dtype=float,
    )
    risk_tolerance_items = ANALYSIS_CONFIG["risk_tolerance_items"]
    contextual_items = ANALYSIS_CONFIG["contextual_items"]
    question_index = {question_id: index for index, question_id in enumerate(QUESTION_IDS)}
    scale_items = complete_answers[
        :, [question_index[question_id] for question_id in risk_tolerance_items]
    ]
    contextual_matrix = complete_answers[
        :, [question_index[question_id] for question_id in contextual_items]
    ]
    all_seven_alpha = cronbach_alpha(complete_answers)
    alpha_rows = [
        {
            "item_set": "Four risk-tolerance items",
            "n": len(complete_answers),
            "items": ", ".join(risk_tolerance_items),
            "cronbach_alpha": cronbach_alpha(scale_items),
        },
        {
            "item_set": "All seven items",
            "n": len(complete_answers),
            "items": ", ".join(QUESTION_IDS),
            "cronbach_alpha": all_seven_alpha,
        },
        {
            "item_set": "Three contextual items (reported separately)",
            "n": len(complete_answers),
            "items": ", ".join(contextual_items),
            "cronbach_alpha": cronbach_alpha(contextual_matrix),
        },
    ]
    item_total_rows = _item_total_rows(complete_answers, QUESTION_IDS)

    results_dir = Path(ANALYSIS_CONFIG["results_dir"])
    results_dir.mkdir(parents=True, exist_ok=True)
    matrix_rows, heatmap_path = _matrix_and_heatmap(ratings, measures, results_dir)
    paths = {
        "correlations": results_dir / "correlations.csv",
        "item_total": results_dir / "item_total_correlations.csv",
        "internal_consistency": results_dir / "internal_consistency.csv",
        "correlation_matrix": results_dir / "spearman_correlation_matrix.csv",
        "heatmap": heatmap_path,
        "row_accounting": results_dir / "row_accounting.json",
        "summary": results_dir / "validity_summary.json",
        "report": results_dir / "results.md",
    }
    _write_csv(paths["correlations"], correlation_rows)
    _write_csv(paths["item_total"], item_total_rows)
    _write_csv(paths["internal_consistency"], alpha_rows)
    _write_csv(paths["correlation_matrix"], matrix_rows)

    accounting.update(sensitivity_accounting)
    versions = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": __import__("sklearn").__version__,
        "openpyxl": openpyxl.__version__,
        "matplotlib": matplotlib.__version__,
        "questionnaire": QUESTIONNAIRE_V2.version,
        "model_file": str(model_path.relative_to(ROOT)),
    }
    paths["row_accounting"].write_text(json.dumps(accounting, indent=2), encoding="utf-8")
    paths["summary"].write_text(
        json.dumps(
            {
                "provenance": {
                    "reported_source_composition": ANALYSIS_CONFIG["reported_source_composition"],
                    "row_level_source_flag_available": ANALYSIS_CONFIG["source_has_row_level_flag"],
                    "attributable_to_real_participants": False,
                    "self_rating_used_as_feature_or_label": False,
                },
                "versions": versions,
                "model_load_warnings": model_load_warnings,
                "row_accounting": accounting,
                "correlations": correlation_rows,
                "item_total_correlations": item_total_rows,
                "internal_consistency": alpha_rows,
                "spearman_correlation_matrix": matrix_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_report(
        accounting,
        correlation_rows,
        item_total_rows,
        alpha_rows,
        matrix_rows,
        sensitivity_accounting,
        model_load_warnings,
        paths["report"],
    )
    return paths


if __name__ == "__main__":
    for output_name, output_path in run_analysis().items():
        print(f"{output_name}: {output_path}")
