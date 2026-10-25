"""Seeded performance benchmark for AgentScheduler."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evaluations" / "agent_scheduler" / "scripts"))

from run_smoke_test import job, make_scheduler  # noqa: E402

RESULTS = ROOT / "evaluations" / "agent_scheduler" / "results"
DEFAULT_DATASET = ROOT / "evaluations" / "agent_scheduler" / "datasets" / "benchmark_workloads.json"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def install_policy(scheduler: Any, policy: str) -> None:
    """Install a benchmark-only queue policy without changing production code."""
    if policy == "priority":
        return
    if policy != "fifo":
        raise ValueError(f"Unknown benchmark policy: {policy}")

    async def fifo_next_job(self: Any, only_admissible: bool = False) -> Any:
        async with self._lock:
            if not self._pending:
                return None
            now = time.time()
            candidates = [
                (index, job)
                for index, job in enumerate(self._pending)
                if not only_admissible or self.resources.can_admit(job.task_id, job.estimated_tokens)
            ]
            if not candidates:
                return None
            index, job = candidates[0]
            self._pending.pop(index)
            self._metrics["wait_ms"] += int((now - job.ready_at) * 1000)
            return job

    scheduler._next_job = types.MethodType(fifo_next_job, scheduler)


async def run_profile(profile: dict[str, Any], repetition: int, policy: str) -> dict[str, Any]:
    scheduler, _events = make_scheduler(
        int(profile["global_slots"]), int(profile["task_slots"]), int(profile["token_budget"])
    )
    install_policy(scheduler, policy)
    rng = random.Random(int(profile["seed"]) + repetition)
    submitted_at: dict[int, float] = {}
    runner_started_at: dict[int, float] = {}
    priorities_by_job: dict[int, float] = {}
    active_by_task: dict[str, int] = {}
    task_peak: dict[str, int] = {}
    active = 0
    peak_global_active = 0
    lock = asyncio.Lock()

    async def submit_one(index: int) -> dict[str, Any]:
        nonlocal active, peak_global_active
        task_id = f"workload-task-{index % int(profile['tasks'])}"
        delay_ms = rng.randint(*[int(value) for value in profile["service_time_ms"]])
        priority = float(rng.choice(profile["priorities"]))
        priorities_by_job[index] = priority
        submitted_at[index] = time.perf_counter()

        async def runner() -> str:
            nonlocal active, peak_global_active
            runner_started_at[index] = time.perf_counter()
            async with lock:
                active += 1
                peak_global_active = max(peak_global_active, active)
                active_by_task[task_id] = active_by_task.get(task_id, 0) + 1
                task_peak[task_id] = max(task_peak.get(task_id, 0), active_by_task[task_id])
            await asyncio.sleep(delay_ms / 1000)
            async with lock:
                active -= 1
                active_by_task[task_id] -= 1
            return "ok"

        result = await scheduler.submit(
            job(task_id, f"step-{index}", runner, priority=priority, tokens=10)
        )
        completed_at = time.perf_counter()
        return {
            "index": index,
            "priority": priority,
            "result": result,
            "queue_wait_ms": (runner_started_at[index] - submitted_at[index]) * 1000,
            "end_to_end_ms": (completed_at - submitted_at[index]) * 1000,
        }

    started = time.perf_counter()
    try:
        records = await asyncio.wait_for(
            asyncio.gather(*[submit_one(index) for index in range(int(profile["jobs"]))]),
            timeout=30,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        queue_wait = [record["queue_wait_ms"] for record in records]
        end_to_end = [record["end_to_end_ms"] for record in records]
        high_priority_wait = [record["queue_wait_ms"] for record in records if record["priority"] >= 9]
        low_priority_wait = [record["queue_wait_ms"] for record in records if record["priority"] <= 1]
        per_task_completed = {
            task_id: sum(1 for record in records if record["index"] % int(profile["tasks"]) == int(task_id.rsplit("-", 1)[-1]))
            for task_id in sorted(task_peak)
        }
        return {
            "profile": profile["profile"],
            "policy": policy,
            "repetition": repetition,
            "success": all(record["result"] == "ok" for record in records),
            "jobs": len(records),
            "elapsed_ms": round(elapsed_ms, 3),
            "throughput_jobs_per_sec": round(len(records) / (elapsed_ms / 1000), 3),
            "queue_wait_ms": {
                "p50": round(percentile(queue_wait, 0.50), 3),
                "p95": round(percentile(queue_wait, 0.95), 3),
                "max": round(max(queue_wait), 3),
            },
            "end_to_end_ms": {
                "p50": round(percentile(end_to_end, 0.50), 3),
                "p95": round(percentile(end_to_end, 0.95), 3),
                "max": round(max(end_to_end), 3),
            },
            "priority_queue_wait_p95_ms": {
                "high": round(percentile(high_priority_wait, 0.95), 3),
                "low": round(percentile(low_priority_wait, 0.95), 3),
            },
            "peak_global_active": peak_global_active,
            "peak_active_by_task": task_peak,
            "task_completion_counts": per_task_completed,
            "fairness": {
                "min_task_completions": min(per_task_completed.values()),
                "max_task_completions": max(per_task_completed.values()),
                "completion_spread": max(per_task_completed.values()) - min(per_task_completed.values()),
            },
            "scheduler_snapshot": scheduler.snapshot(),
        }
    finally:
        await scheduler.stop()


async def run(dataset: dict[str, Any], repetitions: int | None, start_repetition: int = 1) -> list[dict[str, Any]]:
    rows = []
    count = repetitions if repetitions is not None else int(dataset["repetitions"])
    for repetition in range(start_repetition, start_repetition + count):
        for profile in dataset["profiles"]:
            for policy in ("priority", "fifo"):
                rows.append(await run_profile(profile, repetition, policy))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--append", action="store_true", help="Append repetitions to existing benchmark results")
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    repetitions = args.repetitions if args.repetitions is not None else int(dataset["repetitions"])
    if repetitions < 1:
        parser.error("--repetitions must be at least 1")
    RESULTS.mkdir(parents=True, exist_ok=True)
    trials_path = RESULTS / "benchmark_trials.jsonl"
    summary_path = RESULTS / "benchmark_summary.json"
    existing_rows: list[dict[str, Any]] = []
    start_repetition = 1
    if args.append and trials_path.exists():
        existing_rows = [json.loads(line) for line in trials_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        start_repetition = max((int(row["repetition"]) for row in existing_rows), default=0) + 1
    rows = existing_rows + asyncio.run(run(dataset, repetitions, start_repetition))
    trials_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    profiles = {}
    for profile in sorted({row["profile"] for row in rows}):
        for policy in ("priority", "fifo"):
            group = [row for row in rows if row["profile"] == profile and row["policy"] == policy]
            profiles[f"{profile}/{policy}"] = {
            "trials": len(group),
            "all_completed": all(row["success"] for row in group),
            "throughput_jobs_per_sec": {
                "mean": round(statistics.mean(row["throughput_jobs_per_sec"] for row in group), 3),
                "min": round(min(row["throughput_jobs_per_sec"] for row in group), 3),
                "max": round(max(row["throughput_jobs_per_sec"] for row in group), 3),
            },
            "queue_wait_p95_ms": round(statistics.mean(row["queue_wait_ms"]["p95"] for row in group), 3),
            "end_to_end_p95_ms": round(statistics.mean(row["end_to_end_ms"]["p95"] for row in group), 3),
                "high_priority_queue_p95_ms": round(statistics.mean(row["priority_queue_wait_p95_ms"]["high"] for row in group), 3),
                "low_priority_queue_p95_ms": round(statistics.mean(row["priority_queue_wait_p95_ms"]["low"] for row in group), 3),
            "peak_global_active": max(row["peak_global_active"] for row in group),
            "max_task_completion_spread": max(row["fairness"]["completion_spread"] for row in group),
        }
    comparisons = {}
    for profile in sorted({row["profile"] for row in rows}):
        priority = profiles[f"{profile}/priority"]
        fifo = profiles[f"{profile}/fifo"]
        comparisons[profile] = {
            "throughput_delta_percent_priority_vs_fifo": round(
                (priority["throughput_jobs_per_sec"]["mean"] / fifo["throughput_jobs_per_sec"]["mean"] - 1) * 100, 3
            ),
            "queue_wait_p95_delta_ms_priority_minus_fifo": round(
                priority["queue_wait_p95_ms"] - fifo["queue_wait_p95_ms"], 3
            ),
            "end_to_end_p95_delta_ms_priority_minus_fifo": round(
                priority["end_to_end_p95_ms"] - fifo["end_to_end_p95_ms"], 3
            ),
            "high_priority_queue_p95_delta_ms_priority_minus_fifo": round(
                priority["high_priority_queue_p95_ms"] - fifo["high_priority_queue_p95_ms"], 3
            ),
            "winner_for_high_priority_latency": "priority" if priority["high_priority_queue_p95_ms"] < fifo["high_priority_queue_p95_ms"] else "fifo",
        }
    summary = {
        "evaluation": "agent_scheduler_performance",
        "dataset_id": dataset["dataset_id"],
        "result_type": "measurement_not_pass_rate",
        "trial_count": len(rows),
        "profiles": profiles,
        "comparisons": comparisons,
        "manifest": {
            "methodology": dataset["methodology"],
            "external_persistence": "stubbed",
            "same_host_comparison_required": True,
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} benchmark trials to {trials_path}")
    for name, metrics in profiles.items():
        print(
            f"{name}: throughput={metrics['throughput_jobs_per_sec']['mean']:.2f} jobs/s, "
            f"queue_p95={metrics['queue_wait_p95_ms']:.2f} ms, "
            f"e2e_p95={metrics['end_to_end_p95_ms']:.2f} ms"
        )
    for name, metrics in comparisons.items():
        print(
            f"{name}: priority-vs-fifo throughput={metrics['throughput_delta_percent_priority_vs_fifo']:+.2f}%, "
            f"queue_p95_delta={metrics['queue_wait_p95_delta_ms_priority_minus_fifo']:+.2f} ms, "
            f"high_priority_winner={metrics['winner_for_high_priority_latency']}"
        )


if __name__ == "__main__":
    main()
