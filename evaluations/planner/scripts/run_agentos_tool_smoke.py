"""Run a model-backed AgentOS tool-selection evaluation.

This uses the generated AgentOS function catalog and an OpenAI-compatible
chat-completions endpoint. It is intentionally reported as an AgentOS adapter
smoke evaluation, not as an official BFCL leaderboard score.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TASKS = ROOT / "evaluations/planner/datasets/tool_selection_tasks.json"
DEFAULT_MANIFEST = ROOT / "evaluations/planner/results/agentos_bfcl_tool_manifest.json"
RESULTS = ROOT / "evaluations/planner/results"


def load_env_key() -> str | None:
    value = os.getenv("GROQ_API_KEY") or os.getenv("AOS_TOOL_EVAL_API_KEY")
    if value:
        return value
    env_path = ROOT / "server/.env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("GROQ_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def call_model(api_key: str, tools: list[dict[str, Any]], task: str) -> dict[str, Any]:
    endpoint = os.getenv("AOS_TOOL_EVAL_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")
    model = os.getenv("AOS_TOOL_EVAL_MODEL", "openai/gpt-oss-120b")
    payload = {
        "model": model,
        "temperature": 0,
        "max_completion_tokens": 256,
        # Every case in this AgentOS routing dataset has at least one expected
        # agent, so require a function call instead of permitting a prose-only
        # response to be counted as a routing decision.
        "tool_choice": "required",
        "tools": tools,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Route the task to the registered AgentOS function or functions that must execute it. "
                    "If a matching capability exists, you MUST call the corresponding function; do not answer "
                    "that task in prose and do not omit the call. Direct prose is allowed only when no registered "
                    "AgentOS function applies. Apply these routing rules: research, factual investigation, or "
                    "source gathering MUST use a3; sending, dispatching, or delivering an email MUST use email_agent "
                    "and never content_creator alone; cryptocurrency profit/loss MUST use crypto_pnl_agent; reading "
                    "a document and producing a summary MUST use a4 and content_creator; coding and testing MUST use "
                    "code_runner. Use multiple function calls when the task requires multiple capabilities. Do not "
                    "call content_creator for an email unless the task explicitly asks only for a draft."
                ),
            },
            {"role": "user", "content": task},
        ],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Groq's Cloudflare edge rejects urllib's default Python-urllib
            # user-agent with HTTP 403/error code 1010.
            "User-Agent": "AgentOS-BFCL-Eval/1.0",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Preserve the provider's diagnostic message while never exposing the
        # Authorization header or the request payload in the recorded error.
        detail = exc.read().decode("utf-8", errors="replace").strip()
        if len(detail) > 500:
            detail = detail[:500] + "..."
        raise RuntimeError(f"Provider HTTP {exc.code}: {detail or exc.reason}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument(
        "--total-trials",
        type=int,
        default=None,
        help="Run exactly this many trials, cycling through the selected cases.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.0,
        help="Pause between provider requests to avoid token-per-minute throttling.",
    )
    args = parser.parse_args()
    api_key = load_env_key()
    if not api_key:
        raise SystemExit("No GROQ_API_KEY or AOS_TOOL_EVAL_API_KEY is configured")
    tasks = json.loads(DEFAULT_TASKS.read_text(encoding="utf-8"))["cases"]
    tools = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))["tools"]
    if args.limit:
        tasks = tasks[:args.limit]
    rows = []
    request_number = 0
    for repetition in range(1, args.repetitions + 1):
        for case in tasks:
            if args.total_trials is not None and len(rows) >= args.total_trials:
                break
            if request_number and args.delay_seconds > 0:
                time.sleep(args.delay_seconds)
            request_number += 1
            started = time.perf_counter()
            error = None
            error_kind = None
            response: dict[str, Any] = {}
            selected: list[str] = []
            try:
                response = call_model(api_key, tools, case["task"])
                message = response["choices"][0]["message"]
                for call in message.get("tool_calls", []):
                    name = call.get("function", {}).get("name")
                    if name and name not in selected:
                        selected.append(name)
            except Exception as exc:  # record provider failures per trial
                error = f"{type(exc).__name__}: {exc}"
                error_kind = "tool_call_failure" if "tool_use_failed" in error else "provider_error"
            expected = case["expected_tools"]
            rows.append({
                "trial_id": f"tool-selection-{case['case_id']}-{repetition}",
                "case_id": case["case_id"],
                "category": case.get("category", "uncategorized"),
                "task": case["task"],
                "expected_tools": expected,
                "selected_tools": selected,
                "exact_tool_set_match": selected == expected,
                "required_tools_recalled": set(expected).issubset(selected),
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "model": os.getenv("AOS_TOOL_EVAL_MODEL", "openai/gpt-oss-120b"),
                "error": error,
                "error_kind": error_kind,
            })
        if args.total_trials is not None and len(rows) >= args.total_trials:
            break
    RESULTS.mkdir(parents=True, exist_ok=True)
    trials_path = RESULTS / "tool_selection_trials.jsonl"
    summary_path = RESULTS / "tool_selection_summary.json"
    trials_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    valid = [row for row in rows if row["error"] is None]
    category_metrics = {}
    grouped = defaultdict(list)
    for row in valid:
        grouped[row["category"]].append(row)
    for category, category_rows in sorted(grouped.items()):
        count = len(category_rows)
        category_metrics[category] = {
            "trial_count": count,
            "exact_tool_set_accuracy": sum(row["exact_tool_set_match"] for row in category_rows) / count,
            "required_tool_recall": sum(row["required_tools_recalled"] for row in category_rows) / count,
            "no_tool_call_rate": sum(not row["selected_tools"] for row in category_rows) / count,
            "mean_latency_ms": round(sum(row["latency_ms"] for row in category_rows) / count, 3),
        }
    summary = {
        "evaluation": "agentos_tool_selection_adapter_smoke",
        "dataset_id": json.loads(DEFAULT_TASKS.read_text(encoding="utf-8"))["dataset_id"],
        "trial_count": len(rows),
        "successful_api_trials": len(valid),
        "exact_tool_set_accuracy": sum(row["exact_tool_set_match"] for row in valid) / len(valid) if valid else None,
        "required_tool_recall": sum(row["required_tools_recalled"] for row in valid) / len(valid) if valid else None,
        "end_to_end_exact_tool_set_accuracy": sum(row["exact_tool_set_match"] for row in rows) / len(rows) if rows else None,
        "end_to_end_required_tool_recall": sum(row["required_tools_recalled"] for row in rows) / len(rows) if rows else None,
        "provider_errors": sum(row["error_kind"] == "provider_error" for row in rows),
        "tool_call_failures": sum(row["error_kind"] == "tool_call_failure" for row in rows),
        "tool_choice": "required",
        "category_metrics": category_metrics,
        "model": os.getenv("AOS_TOOL_EVAL_MODEL", "openai/gpt-oss-120b"),
        "note": "AgentOS tool-catalog adapter smoke test; not an official BFCL leaderboard score.",
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
