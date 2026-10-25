"""Generate the planner tool-selection figure used by the thesis report."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / "evaluations/planner/results/tool_selection_50_trial.json"
OUTPUT = ROOT / "report/BTECH_2026/5/figures/planner_tool_selection_results.pdf"


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    metrics = summary["category_metrics"]
    categories = list(metrics)
    correct = sum(item["correct_trials"] for item in metrics.values())
    tool_failures = sum(item["tool_call_failures"] for item in metrics.values())
    incorrect = summary["trial_count"] - correct - tool_failures
    category_accuracy = [100 * metrics[name]["correct_trials"] / metrics[name]["trial_count"] for name in categories]
    category_latency = [metrics[name]["mean_latency_ms"] for name in categories]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    figure, axes = plt.subplots(1, 3, figsize=(12.5, 4.6), gridspec_kw={"width_ratios": [0.85, 1.3, 1.3]})
    figure.suptitle("AgentOS tool-selection adapter: 50-trial evaluation", fontsize=13, fontweight="bold")

    outcome_labels = ["Correct\ntool set", "Tool-call\nfailure", "Incorrect\nselection"]
    outcome_values = [correct, tool_failures, incorrect]
    outcome_colors = ["#2E7D32", "#C62828", "#EF6C00"]
    axes[0].bar(outcome_labels, outcome_values, color=outcome_colors, width=0.65)
    axes[0].set_title("Overall outcome (n=50)")
    axes[0].set_ylabel("Trials")
    axes[0].set_ylim(0, max(outcome_values + [1]) + 2)
    axes[0].grid(axis="y", alpha=0.25)
    for index, value in enumerate(outcome_values):
        axes[0].text(index, value + 0.15, str(value), ha="center", fontweight="bold")

    bars = axes[1].barh(categories, category_accuracy, color="#356A9A")
    axes[1].set_title("Exact-match accuracy by category")
    axes[1].set_xlabel("Accuracy (%)")
    axes[1].set_xlim(0, 110)
    axes[1].grid(axis="x", alpha=0.25)
    for bar, value in zip(bars, category_accuracy):
        axes[1].text(value + 2, bar.get_y() + bar.get_height() / 2, f"{value:.0f}%", va="center")

    latency_bars = axes[2].barh(categories, category_latency, color="#7A5195")
    axes[2].set_title("Mean latency by category")
    axes[2].set_xlabel("Latency (ms)")
    axes[2].grid(axis="x", alpha=0.25)
    axes[2].set_xlim(0, max(category_latency) * 1.2)
    for bar, value in zip(latency_bars, category_latency):
        axes[2].text(value + 15, bar.get_y() + bar.get_height() / 2, f"{value:.0f}", va="center", fontsize=8)

    figure.text(
        0.5,
        0.01,
        "Required tool-call mode; failures count as incorrect end-to-end outcomes. Latency values are category means.",
        ha="center",
        fontsize=8,
        color="#444444",
    )
    figure.tight_layout(rect=(0, 0.05, 1, 0.93))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT, bbox_inches="tight")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
