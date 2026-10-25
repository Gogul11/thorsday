"""Generate report figures from the checked-in scheduler benchmark summary."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / "evaluations" / "agent_scheduler" / "results" / "benchmark_summary.json"
OUT = ROOT / "report" / "BTECH_2026" / "5" / "figures"


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    profiles = ["steady_state", "queue_contention"]
    labels = ["Steady state", "Queue contention"]
    colors = {"priority": "#1f4e79", "fifo": "#a65e1f"}
    OUT.mkdir(parents=True, exist_ok=True)

    x = np.arange(len(profiles))
    width = 0.34
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=180)
    for offset, policy in [(-width / 2, "priority"), (width / 2, "fifo")]:
        values = [summary["profiles"][f"{profile}/{policy}"]["throughput_jobs_per_sec"]["mean"] for profile in profiles]
        bars = ax.bar(x + offset, values, width, label="Priority aging" if policy == "priority" else "FIFO", color=colors[policy])
        ax.bar_label(bars, fmt="%.1f", padding=2, fontsize=8)
    ax.set_ylabel("Throughput (jobs/s)")
    ax.set_title("Scheduler throughput under seeded workloads")
    ax.set_xticks(x, labels)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncol=2, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "scheduler_throughput_baseline.png", bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.9), dpi=180, sharey=False)
    for axis, profile, label in zip(axes, profiles, labels):
        metrics = [summary["profiles"][f"{profile}/{policy}"] for policy in ("priority", "fifo")]
        high = [metric["high_priority_queue_p95_ms"] for metric in metrics]
        low = [metric["low_priority_queue_p95_ms"] for metric in metrics]
        bar_x = np.arange(2)
        bars_high = axis.bar(bar_x - width / 2, high, width, label="High priority", color="#1f4e79")
        bars_low = axis.bar(bar_x + width / 2, low, width, label="Low priority", color="#b7c9d6")
        axis.bar_label(bars_high, fmt="%.0f", padding=2, fontsize=7)
        axis.bar_label(bars_low, fmt="%.0f", padding=2, fontsize=7)
        axis.set_title(label)
        axis.set_xticks(bar_x, ["Priority", "FIFO"])
        axis.set_ylabel("Queue wait p95 (ms)")
        axis.grid(axis="y", alpha=0.25)
        axis.spines[["top", "right"]].set_visible(False)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, frameon=False, fontsize=8, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.96))
    fig.suptitle("Priority-aware latency versus FIFO baseline", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(OUT / "scheduler_priority_latency.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
