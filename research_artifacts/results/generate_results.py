"""Generates presentation-ready figures and metric tables comparing the
risk-tier classifiers: the two research candidates in research_artifacts/
models/ (Gradient Boosting, MLP) and the two production Random Forests the
app actually serves from backend/app/ml_models/.

Reproduces the exact held-out split used at training time (434 rows from
Risk_questionnaire_400.xlsx, test_size=0.2, random_state=42, stratified on
stated_tier) and evaluates the saved .pkl models on it, so every research
number matches MANIFEST.json's held-out accuracies. The production models
were trained on this same training split (a fresh clone fit on it predicts
identically), so their test scores are equally held-out.

Run from anywhere: python research_artifacts/results/generate_results.py
"""

import json
import sys
import time
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.base import clone
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    auc,
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, learning_curve, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import label_binarize

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.risk_profile import compute_stated_tier  # noqa: E402
from app.services.risk_profile_config import QUESTIONNAIRE_V2  # noqa: E402
from scripts.train_risk_tier_reduced_model import load_training_rows  # noqa: E402

MODELS_DIR = ROOT / "research_artifacts" / "models"
PROD_DIR = ROOT / "backend" / "app" / "ml_models"
PROD_FILES = {"full_7items": "risk_tier_rf.pkl", "reduced_4items": "risk_tier_rf_reduced_4items.pkl"}
OUT = Path(__file__).resolve().parent
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

FEATURE_SETS = {
    "full_7items": (
        "horizon",
        "drawdown_reaction",
        "experience",
        "goal",
        "windfall_allocation",
        "sure_gain_tradeoff",
        "friend_description",
    ),
    "reduced_4items": ("windfall_allocation", "friend_description", "drawdown_reaction", "sure_gain_tradeoff"),
}
FEATURE_LABELS = {
    "horizon": "Investment horizon",
    "drawdown_reaction": "Drawdown reaction",
    "experience": "Experience",
    "goal": "Goal",
    "windfall_allocation": "Windfall allocation",
    "sure_gain_tradeoff": "Sure-gain trade-off",
    "friend_description": "Friend description",
}
SET_LABELS = {"full_7items": "Full (7 items)", "reduced_4items": "Reduced (4 items)"}
# Production model first everywhere so it reads as the headline.
MODEL_KEYS = ("rf", "gb", "mlp")
MODEL_LABELS = {"rf": "Random Forest ★ production", "gb": "Gradient Boosting", "mlp": "MLP Neural Net"}
SHORT_LABELS = {"rf": "Random Forest ★", "gb": "Gradient Boosting", "mlp": "MLP Neural Net"}
CLASSES = [1, 2, 3, 4, 5]
TIER_NAMES = ["T1 Conservative", "T2", "T3", "T4", "T5 Aggressive"]

# Palette: production is the one saturated accent; research candidates recede to neutral greys.
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
SERIES = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA]
MODEL_COLORS = {"rf": BLUE, "gb": "#b3b1a9", "mlp": "#6f6d66"}
TEXT, TEXT2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff"
HIGHLIGHT_BG = "#e8f1fc"
SEQ_CMAP = matplotlib.colors.LinearSegmentedColormap.from_list(
    "seq_blue", ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
)

plt.rcParams.update(
    {
        "figure.dpi": 100,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 12,
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 12,
        "axes.labelsize": 12,
        "axes.labelcolor": TEXT2,
        "axes.edgecolor": GRID,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT2,
        "ytick.color": TEXT2,
        "text.color": TEXT,
        "legend.frameon": False,
        "lines.linewidth": 2,
    }
)


def save(fig, name):
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)
    print(f"  saved figures/{name}.png")


def suptitle(fig, text, y=None):
    kw = dict(x=0.02, ha="left", fontsize=15, fontweight="bold")
    if y is not None:
        kw["y"] = y
    fig.suptitle(text, **kw)


def load_data():
    rows = load_training_rows()
    y = np.array([compute_stated_tier(a, QUESTIONNAIRE_V2).tier for a in rows])
    data = {}
    for fs, feats in FEATURE_SETS.items():
        X = np.array([[QUESTIONNAIRE_V2.option_points(q, a[q]) for q in feats] for a in rows], dtype=float)
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        data[fs] = dict(X=X, y=y, Xtr=Xtr, Xte=Xte, ytr=ytr, yte=yte)
    return y, data


def load_models():
    models = {}
    for fs in FEATURE_SETS:
        models[(fs, "rf")] = dict(est=joblib.load(PROD_DIR / PROD_FILES[fs]), scaler=None)
        models[(fs, "gb")] = dict(est=joblib.load(MODELS_DIR / f"gb_classifier_{fs}.pkl"), scaler=None)
        models[(fs, "mlp")] = dict(
            est=joblib.load(MODELS_DIR / f"mlp_classifier_{fs}.pkl"), scaler=joblib.load(MODELS_DIR / f"mlp_scaler_{fs}.pkl")
        )
    return models


def prep(m, X):
    return m["scaler"].transform(X) if m["scaler"] is not None else X


def combos():
    return [(fs, mk) for fs in FEATURE_SETS for mk in MODEL_KEYS]


# ---------------------------------------------------------------- figures


def fig_class_distribution(y, data):
    d = data["full_7items"]
    tr = [np.sum(d["ytr"] == c) for c in CLASSES]
    te = [np.sum(d["yte"] == c) for c in CLASSES]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    x = np.arange(len(CLASSES))
    ax.bar(x, tr, 0.6, color=BLUE, label=f"Train (n={len(d['ytr'])})", edgecolor=SURFACE, linewidth=2)
    ax.bar(x, te, 0.6, bottom=tr, color=ORANGE, label=f"Test (n={len(d['yte'])})", edgecolor=SURFACE, linewidth=2)
    for i in range(len(CLASSES)):
        ax.text(x[i], tr[i] + te[i] + 2, f"{tr[i] + te[i]}", ha="center", va="bottom", color=TEXT, fontsize=12)
    ax.set_xticks(x, TIER_NAMES)
    ax.set_ylabel("Respondents")
    ax.grid(axis="x", visible=False)
    ax.set_title(f"Risk-tier distribution (N = {len(y)}, stratified 80/20 split)")
    ax.legend(loc="upper right")
    save(fig, "01_class_distribution")


def fig_accuracy_comparison(metrics):
    fig, ax = plt.subplots(figsize=(11, 5.8))
    x = np.arange(len(FEATURE_SETS))
    w = 0.26
    for i, mk in enumerate(MODEL_KEYS):
        vals = [metrics[(fs, mk)]["accuracy"] * 100 for fs in FEATURE_SETS]
        bars = ax.bar(x + (i - 1) * w, vals, w - 0.02, color=MODEL_COLORS[mk], label=MODEL_LABELS[mk])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}%", ha="center", va="bottom", fontsize=12.5,
                    fontweight="bold" if mk == "rf" else "normal", color=TEXT if mk == "rf" else TEXT2)
    ax.set_xticks(x, [SET_LABELS[fs] for fs in FEATURE_SETS])
    ax.set_ylim(0, 108)
    ax.set_ylabel("Held-out accuracy (%)")
    ax.grid(axis="x", visible=False)
    ax.set_title("Held-out test accuracy: production vs research models")
    ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.08))
    save(fig, "02_accuracy_comparison")


def fig_metrics_overview(metrics):
    names = [("accuracy", "Accuracy"), ("balanced_accuracy", "Balanced acc."), ("macro_f1", "Macro F1"),
             ("weighted_f1", "Weighted F1"), ("qwk", "Cohen's κ (QW)"), ("macro_auc", "Macro ROC-AUC")]
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.8), sharey=True)
    x = np.arange(len(names))
    w = 0.26
    for ax, fs in zip(axes, FEATURE_SETS):
        for i, mk in enumerate(MODEL_KEYS):
            vals = [metrics[(fs, mk)][k] * 100 for k, _ in names]
            ax.bar(x + (i - 1) * w, vals, w - 0.02, color=MODEL_COLORS[mk], label=MODEL_LABELS[mk])
        ax.set_xticks(x, [n for _, n in names], rotation=20, ha="right")
        ax.set_ylim(0, 105)
        ax.grid(axis="x", visible=False)
        ax.set_title(SET_LABELS[fs], fontsize=13)
    axes[0].set_ylabel("Score (%)")
    suptitle(fig, "Evaluation metrics on the held-out test set (n = 87)")
    fig.tight_layout()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, bbox_to_anchor=(0.99, 1.0))
    save(fig, "03_metrics_overview")


def draw_cm(ax, cm, title, normalize, production=False):
    disp = cm.astype(float) / cm.sum(axis=1, keepdims=True) if normalize else cm
    ax.imshow(disp, cmap=SEQ_CMAP, vmin=0, vmax=1 if normalize else cm.max())
    ax.grid(False)
    thresh = (1 if normalize else cm.max()) * 0.55
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            v = disp[i, j]
            label = f"{v:.0%}\n({cm[i, j]})" if normalize else f"{cm[i, j]}"
            ax.text(j, i, label, ha="center", va="center", fontsize=10.5 if normalize else 13,
                    color="white" if v > thresh else TEXT, fontweight="bold" if i == j else "normal")
    ax.set_xticks(range(5), [f"T{c}" for c in CLASSES])
    ax.set_yticks(range(5), [f"T{c}" for c in CLASSES])
    ax.set_xlabel("Predicted tier")
    ax.set_ylabel("True tier")
    ax.set_title(title, fontsize=12.5, color=BLUE if production else TEXT)
    for s in ax.spines.values():
        s.set_visible(production)
        s.set_color(BLUE)
        s.set_linewidth(3)


def fig_confusion_matrices(metrics):
    for (fs, mk), m in metrics.items():
        cm = m["cm"]
        fig, axes = plt.subplots(1, 2, figsize=(12, 5.4))
        draw_cm(axes[0], cm, "Counts", False)
        draw_cm(axes[1], cm, "Row-normalised (recall)", True)
        suptitle(fig, f"Confusion matrix — {MODEL_LABELS[mk]}, {SET_LABELS[fs]}  (accuracy {m['accuracy']:.1%})")
        fig.tight_layout()
        save(fig, f"04_confusion_matrix_{mk}_{fs}")

    fig, axes = plt.subplots(2, 3, figsize=(17, 11.5))
    for r, fs in enumerate(FEATURE_SETS):
        for c, mk in enumerate(MODEL_KEYS):
            m = metrics[(fs, mk)]
            draw_cm(axes[r, c], m["cm"], f"{SHORT_LABELS[mk]} · {SET_LABELS[fs]}  ({m['accuracy']:.1%})", True, production=mk == "rf")
    suptitle(fig, "Confusion matrices (row-normalised) — production model outlined in blue", y=1.0)
    fig.tight_layout()
    save(fig, "04_confusion_matrix_grid")


def fig_roc(metrics):
    for (fs, mk), m in metrics.items():
        fig, ax = plt.subplots(figsize=(8, 7))
        for k, c in enumerate(CLASSES):
            fpr, tpr = m["roc"][c]
            ax.plot(fpr, tpr, color=SERIES[k], label=f"{TIER_NAMES[k]}  (AUC {auc(fpr, tpr):.3f})")
        ax.plot([0, 1], [0, 1], ls="--", color=TEXT2, lw=1, label="Chance")
        ax.set_xlabel("False positive rate")
        ax.set_ylabel("True positive rate")
        ax.set_xlim(-0.01, 1.01)
        ax.set_ylim(-0.01, 1.02)
        ax.set_title(f"ROC (one-vs-rest) — {MODEL_LABELS[mk]}, {SET_LABELS[fs]}", fontsize=13)
        ax.legend(loc="lower right", fontsize=11)
        save(fig, f"05_roc_{mk}_{fs}")

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.8), sharey=True)
    for ax, fs in zip(axes, FEATURE_SETS):
        for mk in reversed(MODEL_KEYS):  # production drawn last, on top
            fpr, tpr = metrics[(fs, mk)]["roc_micro"]
            ax.plot(fpr, tpr, color=MODEL_COLORS[mk], lw=3 if mk == "rf" else 2,
                    label=f"{MODEL_LABELS[mk]}  (AUC {auc(fpr, tpr):.3f})")
        ax.plot([0, 1], [0, 1], ls="--", color=TEXT2, lw=1, label="Chance")
        ax.set_xlabel("False positive rate")
        ax.set_title(SET_LABELS[fs], fontsize=13)
        handles, labels = ax.get_legend_handles_labels()
        order = [2, 1, 0, 3]
        ax.legend([handles[i] for i in order], [labels[i] for i in order], loc="lower right", fontsize=10.5)
    axes[0].set_ylabel("True positive rate")
    suptitle(fig, "Micro-averaged ROC — production vs research models")
    fig.tight_layout()
    save(fig, "05_roc_comparison")


def fig_per_class_f1(metrics):
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.4), sharey=True)
    x = np.arange(len(CLASSES))
    w = 0.26
    for ax, fs in zip(axes, FEATURE_SETS):
        for i, mk in enumerate(MODEL_KEYS):
            f1 = metrics[(fs, mk)]["per_class"]["f1"] * 100
            ax.bar(x + (i - 1) * w, f1, w - 0.02, color=MODEL_COLORS[mk], label=MODEL_LABELS[mk])
        ax.set_xticks(x, [f"T{c}" for c in CLASSES])
        ax.set_xlabel("Risk tier")
        ax.set_ylim(0, 105)
        ax.grid(axis="x", visible=False)
        ax.set_title(SET_LABELS[fs], fontsize=13)
    axes[0].set_ylabel("F1 score (%)")
    suptitle(fig, "Per-tier F1 score on the held-out test set")
    fig.tight_layout()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, bbox_to_anchor=(0.99, 1.0))
    save(fig, "06_per_class_f1")


def fig_mlp_loss(models):
    fig, ax = plt.subplots(figsize=(10, 5.6))
    for fs, color in zip(FEATURE_SETS, (BLUE, ORANGE)):
        mlp = models[(fs, "mlp")]["est"]
        lc = mlp.loss_curve_
        ax.plot(np.arange(1, len(lc) + 1), lc, color=color, label=f"{SET_LABELS[fs]}  (final {lc[-1]:.3f}, {len(lc)} epochs)")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Training loss (cross-entropy)")
    ax.set_title(f"MLP training loss curve — hidden layers {models[('full_7items', 'mlp')]['est'].hidden_layer_sizes}")
    ax.legend(loc="upper right")
    save(fig, "07_mlp_loss_curve")


def fig_gb_staged(models, data):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4))
    for fs, color in zip(FEATURE_SETS, (BLUE, ORANGE)):
        gb = models[(fs, "gb")]["est"]
        d = data[fs]
        axes[0].plot(np.arange(1, len(gb.train_score_) + 1), gb.train_score_, color=color, label=SET_LABELS[fs])
        tr_acc = [accuracy_score(d["ytr"], p) for p in gb.staged_predict(d["Xtr"])]
        te_acc = [accuracy_score(d["yte"], p) for p in gb.staged_predict(d["Xte"])]
        it = np.arange(1, len(te_acc) + 1)
        axes[1].plot(it, np.array(tr_acc) * 100, color=color, ls="--", lw=1.5, label=f"{SET_LABELS[fs]} · train")
        axes[1].plot(it, np.array(te_acc) * 100, color=color, label=f"{SET_LABELS[fs]} · test")
    axes[0].set_xlabel("Boosting iteration")
    axes[0].set_ylabel("Training deviance (log-loss)")
    axes[0].set_title("Training deviance", fontsize=13)
    axes[0].legend(loc="upper right")
    axes[1].set_xlabel("Boosting iteration")
    axes[1].set_ylabel("Accuracy (%)")
    axes[1].set_title("Train vs test accuracy per stage", fontsize=13)
    axes[1].legend(loc="lower right", fontsize=10.5)
    suptitle(fig, "Gradient Boosting — staged training curves")
    fig.tight_layout()
    save(fig, "08_gb_training_curves")


def fig_rf_trees(models, data):
    """Accuracy of the production forests as trees are added -- the RF
    analogue of a training curve (averaging the first k trees' votes)."""
    fig, ax = plt.subplots(figsize=(10, 5.6))
    for fs, color in zip(FEATURE_SETS, (BLUE, ORANGE)):
        rf = models[(fs, "rf")]["est"]
        d = data[fs]
        ks = np.unique(np.linspace(1, len(rf.estimators_), 60).astype(int))
        cum_tr = np.cumsum([t.predict_proba(d["Xtr"]) for t in rf.estimators_], axis=0)
        cum_te = np.cumsum([t.predict_proba(d["Xte"]) for t in rf.estimators_], axis=0)
        tr = [accuracy_score(d["ytr"], rf.classes_[cum_tr[k - 1].argmax(1)]) * 100 for k in ks]
        te = [accuracy_score(d["yte"], rf.classes_[cum_te[k - 1].argmax(1)]) * 100 for k in ks]
        ax.plot(ks, tr, color=color, ls="--", lw=1.5, label=f"{SET_LABELS[fs]} · train")
        ax.plot(ks, te, color=color, label=f"{SET_LABELS[fs]} · test  (final {te[-1]:.1f}%)")
    ax.set_xlabel("Number of trees")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Production Random Forest — accuracy vs number of trees")
    ax.legend(loc="lower right", fontsize=11)
    save(fig, "08b_rf_trees_curve")


def fig_feature_importance(models, data):
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.4))
    for ax, fs in zip(axes, FEATURE_SETS):
        feats = FEATURE_SETS[fs]
        d = data[fs]
        perm = {}
        for mk in MODEL_KEYS:
            m = models[(fs, mk)]
            r = permutation_importance(m["est"], prep(m, d["Xte"]), d["yte"], n_repeats=30, random_state=42, scoring="accuracy")
            perm[mk] = r.importances_mean
        order = np.argsort(perm["rf"])
        y = np.arange(len(feats))
        h = 0.27
        for i, mk in enumerate(MODEL_KEYS):
            ax.barh(y + (1 - i) * h, perm[mk][order] * 100, h - 0.03, color=MODEL_COLORS[mk], label=MODEL_LABELS[mk])
        ax.set_yticks(y, [FEATURE_LABELS[feats[i]] for i in order])
        ax.set_xlabel("Accuracy drop when shuffled (pp)")
        ax.grid(axis="y", visible=False)
        ax.set_title(SET_LABELS[fs], fontsize=13)
        for i, f in enumerate(feats):
            rows.append(dict(feature_set=fs, feature=f,
                             rf_impurity_importance=models[(fs, "rf")]["est"].feature_importances_[i],
                             gb_impurity_importance=models[(fs, "gb")]["est"].feature_importances_[i],
                             **{f"{mk}_permutation_importance": perm[mk][i] for mk in MODEL_KEYS}))
    suptitle(fig, "Permutation feature importance on the held-out test set")
    fig.tight_layout()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, bbox_to_anchor=(0.99, 1.0))
    save(fig, "09_permutation_importance")

    df = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4))
    for ax, fs in zip(axes, FEATURE_SETS):
        sub = df[df.feature_set == fs].sort_values("rf_impurity_importance")
        ax.barh([FEATURE_LABELS[f] for f in sub.feature], sub.rf_impurity_importance * 100, 0.6, color=BLUE)
        for yv, v in enumerate(sub.rf_impurity_importance * 100):
            ax.text(v + 0.8, yv, f"{v:.1f}%", va="center", fontsize=11)
        ax.set_xlabel("Share of total impurity reduction (%)")
        ax.set_xlim(0, sub.rf_impurity_importance.max() * 100 * 1.18)
        ax.grid(axis="y", visible=False)
        ax.set_title(SET_LABELS[fs], fontsize=13)
    suptitle(fig, "Production Random Forest — feature importance (impurity-based)")
    fig.tight_layout()
    save(fig, "10_rf_feature_importance")
    return df


def fig_learning_curves(models, data):
    """Re-fits clones of the saved models' exact hyperparameters on growing
    subsets with 5-fold CV -- the saved .pkl weights themselves are not
    changed; this only shows how each configuration scales with data."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6), sharey=True)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    sizes = np.linspace(0.15, 1.0, 8)
    for ax, fs in zip(axes, FEATURE_SETS):
        d = data[fs]
        for mk in reversed(MODEL_KEYS):
            m = models[(fs, mk)]
            est = clone(m["est"])
            if m["scaler"] is not None:
                est = make_pipeline(clone(m["scaler"]), est)
            n, _, va = learning_curve(est, d["X"], d["y"], cv=cv, train_sizes=sizes, scoring="accuracy", n_jobs=-1)
            c = MODEL_COLORS[mk]
            ax.plot(n, va.mean(1) * 100, color=c, marker="o", ms=6, lw=3 if mk == "rf" else 2, label=f"{MODEL_LABELS[mk]}")
            ax.fill_between(n, (va.mean(1) - va.std(1)) * 100, (va.mean(1) + va.std(1)) * 100, color=c, alpha=0.12, lw=0)
        ax.set_xlabel("Training examples")
        ax.set_title(SET_LABELS[fs], fontsize=13)
    axes[0].set_ylabel("Cross-validated accuracy (%)")
    suptitle(fig, "Learning curves (5-fold stratified CV, same hyperparameters; band = ±1 SD)")
    fig.tight_layout()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[::-1], labels[::-1], loc="upper right", ncol=3, bbox_to_anchor=(0.99, 0.95))
    save(fig, "11_learning_curves")


def measure_explainability(models, data):
    """Can each model produce an exact per-prediction SHAP explanation, and
    how long does one take? The app explains every single prediction, so
    this is a hard requirement, not a nice-to-have."""
    results = {}
    for (fs, mk), m in models.items():
        d = data[fs]
        sample = d["Xte"][:10]
        r = dict(method=None, exact=False, ms=None, note="")
        try:
            explainer = shap.TreeExplainer(m["est"])
            explainer.shap_values(sample[:1])  # warm-up; the app caches the explainer
            t = time.perf_counter()
            for row in sample:
                explainer.shap_values(row[None, :])
            r.update(method="TreeExplainer", exact=True, ms=(time.perf_counter() - t) * 1000 / len(sample))
        except Exception as exc:  # noqa: BLE001
            r["note"] = f"TreeExplainer unsupported: {exc}"
            f = (lambda X, m=m: m["est"].predict_proba(prep(m, X)))
            explainer = shap.KernelExplainer(f, shap.kmeans(d["Xtr"], 20))
            t = time.perf_counter()
            for row in sample[:5]:
                explainer.shap_values(row[None, :], silent=True)
            r.update(method="KernelExplainer", exact=False, ms=(time.perf_counter() - t) * 1000 / 5)
        results[(fs, mk)] = r
        print(f"  explain {mk:>3} {fs:<15} {r['method']:<16} exact={r['exact']} {r['ms']:.1f} ms")
    return results


def fig_shap_example(models, data, metrics):
    """One real test respondent, explained exactly as the app explains it."""
    fs = "full_7items"
    m = models[(fs, "rf")]["est"]
    d = data[fs]
    idx = int(np.flatnonzero(d["yte"] == 3)[0])
    x = d["Xte"][idx : idx + 1]
    pred = int(m.predict(x)[0])
    raw = np.asarray(shap.TreeExplainer(m).shap_values(x))
    k = list(m.classes_).index(pred)
    sv = raw[0, :, k] if raw.ndim == 3 else np.asarray(raw[k])[0]
    feats = FEATURE_SETS[fs]
    order = np.argsort(np.abs(sv))
    fig, ax = plt.subplots(figsize=(11, 5.6))
    colors = [BLUE if sv[i] > 0 else ORANGE for i in order]
    ax.barh(range(len(feats)), sv[order], 0.6, color=colors)
    for yv, i in enumerate(order):
        ax.text(sv[i] + (0.004 if sv[i] >= 0 else -0.004), yv, f"{sv[i]:+.3f}", va="center",
                ha="left" if sv[i] >= 0 else "right", fontsize=11)
    ax.set_yticks(range(len(feats)), [f"{FEATURE_LABELS[feats[i]]} = {int(x[0, i])} pts" for i in order])
    ax.axvline(0, color=TEXT2, lw=1)
    lim = np.abs(sv).max() * 1.35
    ax.set_xlim(-lim, lim)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(f"SHAP contribution to P(tier {pred})   ·   blue pushes towards tier {pred}, orange pushes away")
    proba = m.predict_proba(x)[0][k]
    ax.set_title(f"Example explanation from the production model: predicted tier {pred} ({proba:.0%} confidence), true tier {d['yte'][idx]}",
                 fontsize=13)
    save(fig, "13_shap_example_production")


def fig_decision_table(metrics, explain):
    cols = ["Model", "7-item\naccuracy", "4-item\naccuracy", "Exact per-prediction\nSHAP explanation", "Background\nsample needed", "Role in the app"]
    roles = {"rf": "Deployed: quick-mode tier\n+ full-mode explanation", "gb": "Research candidate", "mlp": "Research candidate"}
    body = []
    for mk in MODEL_KEYS:
        f, r = metrics[("full_7items", mk)], metrics[("reduced_4items", mk)]
        ef = explain[("full_7items", mk)]
        shap_txt = "Yes (TreeSHAP)" if ef["exact"] else ("No: multiclass unsupported" if mk == "gb" else "No: approximate only")
        body.append([SHORT_LABELS[mk], f"{f['accuracy']:.1%}", f"{r['accuracy']:.1%}", shap_txt,
                     "No" if ef["exact"] else "Yes (KernelSHAP)", roles[mk]])
    fig, ax = plt.subplots(figsize=(15, 3.6))
    ax.axis("off")
    t = ax.table(cellText=body, colLabels=cols, loc="center", cellLoc="center",
                 colWidths=[0.15, 0.09, 0.12, 0.21, 0.14, 0.22])
    t.auto_set_font_size(False)
    t.set_fontsize(12)
    t.scale(1, 3.0)
    best4 = max(MODEL_KEYS, key=lambda k: metrics[("reduced_4items", k)]["accuracy"])
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor(GRID)
        if r == 0:
            cell.set_facecolor("#184f95")
            cell.set_text_props(color="white", fontweight="bold")
        elif MODEL_KEYS[r - 1] == "rf":
            cell.set_facecolor(HIGHLIGHT_BG)
            cell.set_text_props(fontweight="bold", color="#184f95")
        else:
            cell.set_facecolor(SURFACE)
            cell.set_text_props(color=TEXT2)
        if r > 0 and c == 2 and MODEL_KEYS[r - 1] == best4:
            cell.get_text().set_text(cell.get_text().get_text() + "  (best)")
    ax.set_title("Model selection: why the Random Forest is in production", pad=4)
    save(fig, "14_model_selection_table")


def fig_summary_table(metrics):
    cols = ["Model", "Items", "Accuracy", "Balanced\naccuracy", "Macro\nF1", "Weighted\nF1", "Cohen's κ\n(quadratic)", "Within\n±1 tier", "Macro\nROC-AUC"]
    body, prod_rows = [], []
    for fs, mk in combos():
        m = metrics[(fs, mk)]
        if mk == "rf":
            prod_rows.append(len(body) + 1)
        body.append([SHORT_LABELS[mk], SET_LABELS[fs].split("(")[1].rstrip(")"), f"{m['accuracy']:.1%}", f"{m['balanced_accuracy']:.1%}",
                     f"{m['macro_f1']:.3f}", f"{m['weighted_f1']:.3f}", f"{m['qwk']:.3f}", f"{m['within_one_tier']:.1%}", f"{m['macro_auc']:.3f}"])
    fig, ax = plt.subplots(figsize=(14, 4.2))
    ax.axis("off")
    widths = [0.17, 0.07, 0.09, 0.11, 0.09, 0.10, 0.12, 0.12, 0.10]
    t = ax.table(cellText=body, colLabels=cols, loc="center", cellLoc="center", colWidths=widths)
    t.auto_set_font_size(False)
    t.set_fontsize(12)
    t.scale(1, 2.1)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor(GRID)
        if r == 0:
            cell.set_height(cell.get_height() * 1.6)
            cell.set_facecolor("#184f95")
            cell.set_text_props(color="white", fontweight="bold")
        elif r in prod_rows:
            cell.set_facecolor(HIGHLIGHT_BG)
            cell.set_text_props(fontweight="bold", color="#184f95")
        else:
            cell.set_facecolor(SURFACE)
    ax.set_title("Held-out test performance (n_train = 347, n_test = 87) — ★ = production model", pad=6)
    save(fig, "00_summary_table")


# ---------------------------------------------------------------- main


def evaluate(models, data):
    metrics = {}
    reports = []
    for fs, mk in combos():
        m = models[(fs, mk)]
        d = data[fs]
        Xte = prep(m, d["Xte"])
        yp = m["est"].predict(Xte)
        proba = m["est"].predict_proba(Xte)
        yb = label_binarize(d["yte"], classes=CLASSES)
        roc = {c: roc_curve(yb[:, k], proba[:, k])[:2] for k, c in enumerate(CLASSES)}
        fpr_mi, tpr_mi, _ = roc_curve(yb.ravel(), proba.ravel())
        p, r, f, s = precision_recall_fscore_support(d["yte"], yp, labels=CLASSES, zero_division=0)
        metrics[(fs, mk)] = dict(
            accuracy=accuracy_score(d["yte"], yp),
            train_accuracy=accuracy_score(d["ytr"], m["est"].predict(prep(m, d["Xtr"]))),
            balanced_accuracy=float(np.mean(r)),
            macro_f1=f1_score(d["yte"], yp, average="macro"),
            weighted_f1=f1_score(d["yte"], yp, average="weighted"),
            qwk=cohen_kappa_score(d["yte"], yp, weights="quadratic"),
            within_one_tier=float(np.mean(np.abs(d["yte"] - yp) <= 1)),
            macro_auc=float(np.mean([auc(*roc[c]) for c in CLASSES])),
            micro_auc=auc(fpr_mi, tpr_mi),
            cm=confusion_matrix(d["yte"], yp, labels=CLASSES),
            roc=roc,
            roc_micro=(fpr_mi, tpr_mi),
            per_class=dict(precision=p, recall=r, f1=f, support=s),
        )
        reports.append(f"=== {MODEL_LABELS[mk]} | {SET_LABELS[fs]} ===\n"
                       + classification_report(d["yte"], yp, labels=CLASSES, target_names=TIER_NAMES, digits=4))
    return metrics, reports


def write_tables(metrics, reports, importance_df, explain):
    summary = []
    per_class = []
    for (fs, mk), m in metrics.items():
        e = explain[(fs, mk)]
        summary.append(dict(model=MODEL_LABELS[mk], production=mk == "rf", feature_set=fs,
                            **{k: round(float(m[k]), 4) for k in ("train_accuracy", "accuracy", "balanced_accuracy", "macro_f1",
                                                                  "weighted_f1", "qwk", "within_one_tier", "macro_auc", "micro_auc")},
                            shap_method=e["method"], shap_exact=e["exact"], shap_ms_per_prediction=round(e["ms"], 2)))
        for k, c in enumerate(CLASSES):
            per_class.append(dict(model=MODEL_LABELS[mk], feature_set=fs, tier=c,
                                  **{n: round(float(m["per_class"][n][k]), 4) for n in ("precision", "recall", "f1")},
                                  support=int(m["per_class"]["support"][k])))
        pd.DataFrame(m["cm"], index=[f"true_T{c}" for c in CLASSES], columns=[f"pred_T{c}" for c in CLASSES]).to_csv(
            OUT / f"confusion_matrix_{mk}_{fs}.csv")
    pd.DataFrame(summary).to_csv(OUT / "metrics_summary.csv", index=False)
    pd.DataFrame(per_class).to_csv(OUT / "per_class_metrics.csv", index=False)
    importance_df.round(4).to_csv(OUT / "feature_importance.csv", index=False)
    (OUT / "classification_reports.txt").write_text("\n".join(reports), encoding="utf-8")
    (OUT / "metrics_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main():
    y, data = load_data()
    models = load_models()
    metrics, reports = evaluate(models, data)
    for (fs, mk), m in metrics.items():
        print(f"{mk:>3} {fs:<15} test acc {m['accuracy']:.4f}")
    explain = measure_explainability(models, data)

    for old in FIG.glob("*.png"):
        old.unlink()
    fig_summary_table(metrics)
    fig_class_distribution(y, data)
    fig_accuracy_comparison(metrics)
    fig_metrics_overview(metrics)
    fig_confusion_matrices(metrics)
    fig_roc(metrics)
    fig_per_class_f1(metrics)
    fig_mlp_loss(models)
    fig_gb_staged(models, data)
    fig_rf_trees(models, data)
    importance_df = fig_feature_importance(models, data)
    fig_learning_curves(models, data)
    fig_shap_example(models, data, metrics)
    fig_decision_table(metrics, explain)
    write_tables(metrics, reports, importance_df, explain)


if __name__ == "__main__":
    main()
