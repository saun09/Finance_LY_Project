"""Draws a simplified, slide-ready overview of how the risk-profiling module
works: offline model training on the left, the live questionnaire flow on
the right.

Run from anywhere: python research_artifacts/results/architecture_diagram.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch, Polygon

OUT = Path(__file__).resolve().parent / "figures" / "15_system_architecture.png"

TEXT, TEXT2, ARROW, BLUE = "#0b0b0b", "#52514e", "#52514e", "#2a78d6"
ROLE = {  # fill, border
    "ml": ("#e8f1fc", BLUE),
    "rule": ("#f3f2ef", "#6f6d66"),
    "data": ("#e6f6ef", "#1baf7a"),
    "io": ("#ffffff", "#9c9a92"),
}

fig, ax = plt.subplots(figsize=(20, 12.4))
ax.set_xlim(0, 100)
ax.set_ylim(0, 62)
ax.axis("off")


def box(cx, cy, w, h, title, body="", role="rule", bold=False, dashed=False):
    fill, edge = ROLE[role]
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.8",
                                fc=fill, ec=edge, lw=2.6 if bold else 1.6, ls="--" if dashed else "-", zorder=3))
    ty = cy + h * 0.17 if body else cy
    ax.text(cx, ty, title, ha="center", va="center", fontsize=12, fontweight="bold", color=TEXT, zorder=4)
    if body:
        ax.text(cx, cy - h * 0.2, body, ha="center", va="center", fontsize=10.5, color=TEXT2, zorder=4, linespacing=1.3)
    return dict(l=cx - w / 2, r=cx + w / 2, t=cy + h / 2, b=cy - h / 2, cx=cx, cy=cy)


def arrow(p1, p2, label=None, dashed=False, color=ARROW, loff=(0, 0.7), lw=1.7):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=16, lw=lw, color=color,
                                 ls=(0, (5, 4)) if dashed else "-", zorder=2, shrinkA=2, shrinkB=2))
    if label:
        x, y = (p1[0] + p2[0]) / 2 + loff[0], (p1[1] + p2[1]) / 2 + loff[1]
        ax.text(x, y, label, ha="center", va="center", fontsize=10, color=color, style="italic", zorder=5,
                bbox=dict(fc="white", ec="none", pad=1.2, alpha=0.9))


# title and the two lanes
ax.text(0.5, 61, "Risk Profiling Module — how it works", fontsize=20, fontweight="bold", va="center", color=TEXT)
for x, w in ((0.5, 29.5), (33, 66.5)):
    ax.add_patch(FancyBboxPatch((x, 0.8), w, 57.4, boxstyle="round,pad=0,rounding_size=1.2", fc="#fafaf8", ec="#e4e3df", zorder=0))
ax.text(1.8, 56.6, "OFFLINE  ·  TRAINING THE MODEL", fontsize=13, fontweight="bold", color=BLUE, va="center")
ax.text(34.3, 56.6, "ONLINE  ·  WHEN A USER TAKES THE QUESTIONNAIRE", fontsize=13, fontweight="bold", color=TEXT2, va="center")

# offline: training pipeline
steps = [
    ("Survey data", "434 questionnaire responses", "data"),
    ("Answer scoring", "each answer converted\ninto a risk score", "rule"),
    ("Labelling", "rule-based formula gives each\nrespondent a risk tier (1–5)", "rule"),
    ("Train / test split", "80% to train · 20% to test", "rule"),
    ("Train models", "Random Forest, Gradient Boosting\nand a Neural Net", "ml"),
    ("Evaluate & choose", "compare accuracy and explainability\n→ Random Forest chosen", "ml"),
]
offline = [box(15.25, 50.5 - i * 6.9, 26, 5.4, t, b, r) for i, (t, b, r) in enumerate(steps)]
saved = box(15.25, 7.6, 26, 6.0, "Trained models", "one for all 7 questions,\none for 4 quick-mode questions", "data", bold=True)
for a, b in zip(offline, offline[1:] + [saved]):
    arrow((a["cx"], a["b"]), (b["cx"], b["t"]))

# online: request flow
app = box(45, 50.5, 19, 5.4, "Mobile app", "user answers 7 questions,\nor 4 in quick mode", "io")
server = box(68, 50.5, 19, 5.4, "Backend server", "receives the answers,\nreturns the risk tier", "io")
qs = box(90.5, 50.5, 15, 5.4, "Questionnaire", "questions, options\nand their weights", "data")
arrow((app["r"], app["cy"] + 0.8), (server["l"], server["cy"] + 0.8), "answers")
arrow((server["l"], server["cy"] - 1.2), (app["r"], app["cy"] - 1.2), "risk tier", loff=(0, -0.9))
arrow((qs["l"], qs["cy"]), (server["r"], server["cy"]))

dcx, dcy, dw, dh = 68, 39.5, 9, 3.6
ax.add_patch(Polygon([(dcx, dcy + dh), (dcx + dw, dcy), (dcx, dcy - dh), (dcx - dw, dcy)], fc="#fff8e6", ec="#c98500", lw=1.8, zorder=3))
ax.text(dcx, dcy, "How many questions\nwere answered?", ha="center", va="center", fontsize=11, fontweight="bold", zorder=4)
arrow((server["cx"], server["b"]), (dcx, dcy + dh))

quick = box(45, 30.5, 20, 6.2, "ML prediction", "Random Forest predicts the tier\nand explains why (SHAP)", "ml", bold=True)
rules = box(90.5, 30.5, 15, 6.2, "Rule-based scoring", "adds up weighted\nanswers → tier", "rule")
arrow((dcx - dw, dcy), (quick["cx"], quick["t"]), "4 answers\n(quick mode)", loff=(-2.5, 1.4))
arrow((dcx + dw, dcy), (rules["cx"], rules["t"]), "all 7 answers\n(full mode)", loff=(2.5, 1.4))

stated = box(68, 24, 15, 4.2, "Stated risk tier (1–5)")
arrow((quick["r"], quick["cy"] - 1), (stated["l"], stated["cy"] + 0.6))
arrow((rules["l"], rules["cy"] - 1), (stated["r"], stated["cy"] + 0.6))

check = box(45, 16.2, 20, 6.2, "ML cross-check", "Random Forest double-checks\nthe tier and explains it (SHAP)", "ml", dashed=True)
arrow((stated["l"], stated["cy"] - 1), (check["r"], check["t"] - 1.2), "full mode", loff=(-1.5, 0.9))

capacity = box(90.5, 16.2, 15, 6.2, "Risk capacity", "how much risk the user\ncan afford: savings,\nloans, income, insurance")
final = box(68, 16.2, 17, 6.2, "Final risk tier", "lower of stated tier\nand risk capacity", bold=True)
arrow((stated["cx"], stated["b"]), (final["cx"], final["t"]))
arrow((capacity["l"], capacity["cy"]), (final["r"], final["cy"]))

db = box(68, 6.6, 26, 5.6, "Saved to database", "tier, answers and the reasons behind it", "data")
arrow((final["cx"], final["b"]), (db["cx"], db["t"]))
arrow((check["cx"], check["b"]), (db["l"] + 3, db["t"]))

uses = box(90.5, 6.6, 15, 5.6, "Used by", "investment plan · alerts\n\"why this tier\" screen", "io")
arrow((db["r"], db["cy"]), (uses["l"], uses["cy"]))

# trained models feed both ML boxes
bus = 31.5
ax.plot([saved["r"], bus, bus], [saved["cy"], saved["cy"], quick["cy"]], color=BLUE, lw=2, ls=(0, (5, 4)), zorder=1)
arrow((bus, quick["cy"]), (quick["l"], quick["cy"]), dashed=True, color=BLUE, lw=2)
arrow((bus, check["cy"]), (check["l"], check["cy"]), dashed=True, color=BLUE, lw=2)

handles = [Patch(fc=ROLE[k][0], ec=ROLE[k][1], lw=1.6, label=l) for k, l in
           [("ml", "Machine learning"), ("rule", "Rule-based logic"), ("data", "Data"), ("io", "App / server")]]
handles.append(Patch(fc="white", ec=BLUE, lw=1.6, ls="--", label="Dashed = optional step / model loading"))
ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.012), ncol=5, frameon=False, fontsize=11.5, handlelength=1.6)

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
print(f"saved {OUT}")
