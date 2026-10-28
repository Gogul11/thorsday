"""Generate the publication-style planner tool-selection figure."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / "evaluations/planner/results/tool_selection_50_trial.json"
FIGURE_DIR = ROOT / "report/BTECH_2026/5/figures"
OUTPUT_PDF = FIGURE_DIR / "planner_tool_selection_results.pdf"
OUTPUT_PNG = FIGURE_DIR / "planner_tool_selection_results.png"


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    metrics = summary["category_metrics"]
    correct = sum(item["correct_trials"] for item in metrics.values())
    tool_failures = sum(item["tool_call_failures"] for item in metrics.values())
    incorrect = summary["trial_count"] - correct - tool_failures

    category_data = [
        (name, 100 * item["correct_trials"] / item["trial_count"])
        for name, item in metrics.items()
    ]
    category_data.sort(key=lambda item: item[1], reverse=True)
    category_labels = [name.replace("_", " ").title() for name, _ in category_data]
    category_accuracy = [value for _, value in category_data]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.titleweight": "bold"})
    figure, axes = plt.subplots(
        1, 2, figsize=(12.0, 5.0),
        gridspec_kw={"width_ratios": [0.88, 1.55], "wspace": 0.32},
        constrained_layout=True,
    )
    figure.suptitle("AgentOS planner tool-selection evaluation", fontsize=16, fontweight="bold", y=1.02)

    outcome_labels = ["Correct tool set", "Tool-call failure", "Incorrect selection"]
    outcome_values = [correct, tool_failures, incorrect]
    outcome_colors = ["#2F7D32", "#C43C39", "#8A8F98"]
    bars = axes[0].bar(outcome_labels, outcome_values, color=outcome_colors, width=0.62, edgecolor="white", linewidth=0.8)
    axes[0].set_title("(a) Overall outcomes", loc="left", pad=12)
    axes[0].set_ylabel("Number of trials")
    axes[0].set_ylim(0, 55)
    axes[0].set_yticks(range(0, 51, 10))
    axes[0].grid(axis="y", alpha=0.25, linewidth=0.8)
    axes[0].set_axisbelow(True)
    axes[0].tick_params(axis="x", labelrotation=18)
    for bar, value in zip(bars, outcome_values):
        percentage = 100 * value / summary["trial_count"]
        axes[0].text(bar.get_x() + bar.get_width() / 2, value + 1.1, f"{value} ({percentage:.0f}%)", ha="center", va="bottom", fontweight="bold")

    bars = axes[1].barh(category_labels[::-1], category_accuracy[::-1], color="#356A9A", height=0.62, edgecolor="white", linewidth=0.8)
    axes[1].set_title("(b) End-to-end exact-match accuracy", loc="left", pad=12)
    axes[1].set_xlabel("Accuracy (%)")
    axes[1].set_xlim(0, 108)
    axes[1].set_xticks(range(0, 101, 20))
    axes[1].grid(axis="x", alpha=0.25, linewidth=0.8)
    axes[1].set_axisbelow(True)
    for bar, value in zip(bars, category_accuracy[::-1]):
        axes[1].text(value + 2, bar.get_y() + bar.get_height() / 2, f"{value:.1f}%", va="center", fontweight="bold")

    for axis in axes:
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)

    figure.text(0.5, -0.035, "n = 50 trials; failures represent model tool-call failures and count as incorrect end-to-end outcomes.", ha="center", fontsize=9, color="#555555")
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PDF, bbox_inches="tight", pad_inches=0.12)
    figure.savefig(OUTPUT_PNG, dpi=220, bbox_inches="tight", pad_inches=0.12)
    print(f"Wrote {OUTPUT_PDF}")
    print(f"Wrote {OUTPUT_PNG}")


if __name__ == "__main__":
    main()
