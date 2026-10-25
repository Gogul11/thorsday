"""Offline smoke evaluation for planner routing and plan validation."""

from __future__ import annotations

import argparse
import json
import sys
import time
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server" / "kernel"))
DATASET_DEFAULT = ROOT / "evaluations" / "planner" / "datasets" / "smoke_tasks.json"
CONFIG_DEFAULT = ROOT / "evaluations" / "planner" / "configs" / "smoke.json"
RESULTS = ROOT / "evaluations" / "planner" / "results"

AGENT_DESCRIPTIONS = {
    "a1": "Inspect system and hardware information.",
    "a2": "Provide date, time, timezone, and calendar information.",
    "a3": "Research factual and technical topics.",
    "a4": "Read and operate on files and documents.",
    "content_creator": "Write and generate reports.",
    "email_agent": "Compose and send email.",
    "weather_agent": "Retrieve weather and forecast information.",
    "agent_creator": "Create new specialized agents.",
    "code_runner": "Generate, test, and repair Python code.",
    "loan_emi_agent": "Calculate loan EMI and amortization.",
    "crypto_pnl_agent": "Analyze cryptocurrency profit and loss.",
}
CASES_BY_TASK: dict[str, dict[str, Any]] = {}

# The planner helpers are imported without heavyweight app/provider packages.
# Candidate retrieval is replaced with the dataset's explicit candidate list;
# all prompt construction and plan validation below use production functions.
agents_package = types.ModuleType("Agents")
agents_package.__path__ = []
registry = types.ModuleType("Agents.agent_registry")
registry.get_agent_descriptions = lambda: dict(AGENT_DESCRIPTIONS)
registry.list_agent_types = lambda: list(AGENT_DESCRIPTIONS)
sys.modules["Agents"] = agents_package
sys.modules["Agents.agent_registry"] = registry
retriever = types.ModuleType("planning.agent_retriever")
def retrieve_agent_candidates(task: str) -> tuple[dict[str, Any], ...]:
    case = CASES_BY_TASK[task]
    return tuple({
        "name": name,
        "description": f"Agent: {name}\nCapabilities:\n{AGENT_DESCRIPTIONS.get(name, 'Unregistered fixture agent.')}",
        "similarity": round(0.9 - index * 0.05, 4),
    } for index, name in enumerate(case["retrieved_candidates"]))
retriever.retrieve_agent_candidates = retrieve_agent_candidates
sys.modules["planning.agent_retriever"] = retriever

from graphs.constant import build_planner_context, get_explicit_agent_hints  # noqa: E402
from planning.diagram import chain_steps, to_mermaid, validate_steps  # noqa: E402


def run_case(case: dict[str, Any], repetition: int) -> dict[str, Any]:
    started = time.perf_counter()
    task = case["task"]
    prompt, candidates = build_planner_context(task)
    hints = get_explicit_agent_hints(task)
    valid_agents = set(AGENT_DESCRIPTIONS)

    # Simulate structured-output planner fields from the fixed dataset fixture.
    selected = []
    for name in case.get("proposed_agents", case["expected_agents"]):
        if name in valid_agents and name in candidates and name not in selected:
            selected.append(name)
    steps = validate_steps(case["plan_steps"], valid_agents, set(candidates))
    invalid_plan_fallback = not steps
    if not steps:
        steps = chain_steps(selected)
    selected = [step["agent"] for step in steps]

    # Match the production planner's explicit-intent guard: if a requested
    # capability was omitted, preserve it and rebuild an ordered dependency chain.
    missing_hints = [name for name in hints if name in candidates and name not in selected]
    if missing_hints:
        ordered = [name for name in hints if name in candidates and name in selected + missing_hints]
        ordered.extend(name for name in selected if name not in ordered)
        selected = ordered
        steps = chain_steps(selected)

    mermaid = to_mermaid(steps)
    expected = case["expected_agents"]
    graph_ids = {step["id"] for step in steps}
    graph_valid = all(set(step["depends_on"]).issubset(graph_ids) for step in steps)
    trial = {
        "trial_id": f"planner-{case['case_id']}-{repetition}",
        "case_id": case["case_id"],
        "repetition": repetition,
        "task": task,
        "retrieved_candidates": case["retrieved_candidates"],
        "planner_candidates": candidates,
        "expected_hints": case["expected_hints"],
        "detected_hints": hints,
        "proposed_agents": case.get("proposed_agents", expected),
        "selected_agents": selected,
        "expected_agents": expected,
        "plan_steps": steps,
        "invalid_plan_fallback": invalid_plan_fallback,
        "explicit_hint_repair": bool(missing_hints),
        "candidate_coverage": set(expected).issubset(candidates),
        "explicit_hint_match": set(hints) == set(case["expected_hints"]),
        "plan_match": selected == expected,
        "plan_graph_valid": graph_valid,
        "mermaid_rendered": mermaid.startswith("flowchart TD") and all(step["id"] in mermaid for step in steps),
        "prompt_chars": len(prompt),
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "mermaid": mermaid,
    }
    trial["success"] = all(trial[key] for key in (
        "candidate_coverage", "explicit_hint_match", "plan_match", "plan_graph_valid", "mermaid_rendered"
    )) and invalid_plan_fallback == bool(case.get("expect_fallback", False))
    return trial


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET_DEFAULT)
    parser.add_argument("--config", type=Path, default=CONFIG_DEFAULT)
    parser.add_argument("--repetitions", type=int)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    cases = dataset["cases"]
    if not cases:
        parser.error("dataset must include at least one case")
    repetitions = args.repetitions if args.repetitions is not None else int(config["repetitions"])
    if repetitions < 1:
        parser.error("--repetitions must be at least 1")
    CASES_BY_TASK.update({case["task"]: case for case in cases})
    trials = [run_case(case, repetition) for repetition in range(1, repetitions + 1) for case in cases]
    RESULTS.mkdir(parents=True, exist_ok=True)
    trials_path = RESULTS / "smoke_trials.jsonl"
    summary_path = RESULTS / "smoke_summary.json"
    trials_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in trials), encoding="utf-8")
    metrics = ("candidate_coverage", "explicit_hint_match", "plan_match", "plan_graph_valid", "mermaid_rendered")
    summary = {
        "evaluation": "planner_smoke", "dataset_id": dataset.get("dataset_id"),
        "trial_count": len(trials), "success_count": sum(row["success"] for row in trials),
        "success_rate": sum(row["success"] for row in trials) / len(trials),
        "metrics": {metric: sum(bool(row[metric]) for row in trials) / len(trials) for metric in metrics},
        "invalid_plan_fallback_count": sum(row["invalid_plan_fallback"] for row in trials),
        "explicit_hint_repair_count": sum(row["explicit_hint_repair"] for row in trials),
        "mean_latency_ms": round(sum(row["latency_ms"] for row in trials) / len(trials), 3),
        "cases": {
            case_id: {"trials": len(rows), "success_rate": sum(row["success"] for row in rows) / len(rows)}
            for case_id in sorted({row["case_id"] for row in trials})
            for rows in [[row for row in trials if row["case_id"] == case_id]]
        },
        "manifest": {
            "config": str(args.config.resolve().relative_to(ROOT)),
            "dataset": str(args.dataset.resolve().relative_to(ROOT)),
            "candidate_retrieval": "fixture candidates from dataset; Chroma not invoked",
            "llm": "disabled; plan fields are dataset fixtures",
            "production_functions": ["build_planner_context", "get_explicit_agent_hints",
                                     "validate_steps", "chain_steps", "to_mermaid"],
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {len(trials)} trials to {trials_path}")
    print(f"Success rate: {summary['success_rate']:.1%}; summary: {summary_path}")
    print(f"Plan match: {summary['metrics']['plan_match']:.1%}; "
          f"candidate coverage: {summary['metrics']['candidate_coverage']:.1%}; "
          f"hint match: {summary['metrics']['explicit_hint_match']:.1%}")


if __name__ == "__main__":
    main()
