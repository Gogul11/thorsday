"""Run a deterministic keyword-based tool-selection baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TASKS = ROOT / "evaluations/planner/datasets/tool_selection_tasks.json"
RESULTS = ROOT / "evaluations/planner/results"


def select_tools(task: str) -> list[str]:
    """Apply transparent, ordered keyword rules to a task description."""
    text = task.lower()
    selected: list[str] = []

    if "document" in text and "summar" in text:
        selected.extend(["a4", "content_creator"])
    elif ("research" in text or "recycling" in text or "investigat" in text) and "email" in text:
        selected.extend(["a3", "email_agent"])
    elif "email" in text or "send" in text and "message" in text:
        selected.append("email_agent")
    elif "cryptocurrency" in text or "crypto" in text or "profit and loss" in text:
        selected.append("crypto_pnl_agent")
    elif "emi" in text or ("loan" in text and "monthly" in text):
        selected.append("loan_emi_agent")
    elif "research" in text or "recycling" in text or "investigat" in text:
        selected.append("a3")
    elif "python" in text or "program" in text or "code" in text or "test" in text:
        selected.append("code_runner")
    elif "weather" in text or "forecast" in text:
        selected.append("weather_agent")
    elif "time" in text or "date" in text:
        selected.append("a2")
    elif "hardware" in text or "operating system" in text or "system information" in text:
        selected.append("a1")
    elif "summarise" in text or "summarize" in text:
        selected.append("a3")

    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()

    dataset = json.loads(DEFAULT_TASKS.read_text(encoding="utf-8"))
    rows = []
    for repetition in range(1, args.repetitions + 1):
        for case in dataset["cases"]:
            selected = select_tools(case["task"])
            expected = case["expected_tools"]
            rows.append(
                {
                    "trial_id": f"keyword-baseline-{case['case_id']}-{repetition}",
                    "case_id": case["case_id"],
                    "category": case.get("category", "uncategorized"),
                    "task": case["task"],
                    "expected_tools": expected,
                    "selected_tools": selected,
                    "exact_tool_set_match": selected == expected,
                    "required_tools_recalled": set(expected).issubset(selected),
                }
            )

    correct = sum(row["exact_tool_set_match"] for row in rows)
    recall = sum(row["required_tools_recalled"] for row in rows)
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["category"], []).append(row)
    category_metrics = {
        category: {
            "trial_count": len(category_rows),
            "correct_trials": sum(row["exact_tool_set_match"] for row in category_rows),
            "exact_tool_set_accuracy": sum(row["exact_tool_set_match"] for row in category_rows) / len(category_rows),
            "required_tool_recall": sum(row["required_tools_recalled"] for row in category_rows) / len(category_rows),
        }
        for category, category_rows in sorted(grouped.items())
    }
    summary = {
        "evaluation": "agentos_tool_selection_keyword_baseline",
        "dataset_id": dataset["dataset_id"],
        "trial_count": len(rows),
        "exact_tool_set_accuracy": correct / len(rows),
        "required_tool_recall": recall / len(rows),
        "category_metrics": category_metrics,
        "rules": "Ordered keyword rules; no model, provider, or external tool calls.",
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "tool_selection_keyword_baseline_trials.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    (RESULTS / "tool_selection_keyword_baseline.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
