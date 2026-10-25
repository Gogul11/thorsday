"""Run scheduler throughput benchmarks over LoCoMo/LongMemEval workload records."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
import types
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server" / "kernel"))

# The benchmark intentionally has no Redis/MongoDB dependency or side effects.
class _RedisStub:
    def __init__(self, **kwargs: Any): pass
    async def hset(self, *args: Any, **kwargs: Any) -> None: pass
    async def hget(self, *args: Any, **kwargs: Any) -> None: return None
    async def zadd(self, *args: Any, **kwargs: Any) -> None: pass
    async def zrem(self, *args: Any, **kwargs: Any) -> None: pass
    async def scan_iter(self, **kwargs: Any):
        if False: yield None

class _MongoStub:
    async def update_one(self, *args: Any, **kwargs: Any) -> None: pass

redis_pkg = types.ModuleType("redis")
redis_async = types.ModuleType("redis.asyncio")
redis_async.Redis = _RedisStub
redis_pkg.asyncio = redis_async
sys.modules.setdefault("redis", redis_pkg)
sys.modules.setdefault("redis.asyncio", redis_async)
db = types.ModuleType("DB.mongodb")
db.tasks_collection = _MongoStub()
sys.modules.setdefault("DB.mongodb", db)

from services import agent_scheduler as scheduler_module  # noqa: E402

PROFILES = (("serial", 1), ("default", 3), ("expanded", 8))
TASK_SLOTS = 2
TOKEN_BUDGET = 50_000
ESTIMATED_TOKENS = 4_000


def _service_time_ms(row: dict[str, Any]) -> float:
    """Deterministic synthetic runner time scaled by input history size."""
    context_units = math.ceil(int(row.get("context_chars", 0)) / 20_000)
    return float(2 + min(10, context_units))


async def run_profile(records: list[dict[str, Any]], dataset_id: str,
                      profile_name: str, global_slots: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scheduler = scheduler_module.AgentScheduler()
    scheduler.resources = scheduler_module.ResourceManager(global_slots, TASK_SLOTS, TOKEN_BUDGET)
    events: list[dict[str, Any]] = []
    active = 0
    peak_active = 0
    start_times: dict[str, float] = {}

    async def persist(*args: Any, **kwargs: Any) -> None: return None
    async def emit(event: str, job: Any, **data: Any) -> None:
        events.append({"event": event, "execution_id": job.execution_id,
                       "task_id": job.task_id, "step_id": job.step_id})
    async def recover() -> None: return None
    scheduler._persist = persist
    scheduler._emit = emit
    scheduler._recover_records = recover

    wall_started = time.perf_counter()
    waiters = []
    rows_by_execution: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(records):
        row = {**source}
        service_ms = _service_time_ms(row)
        execution_id = f"{profile_name}-{index}-{row['question_id']}"
        task_id = f"{dataset_id}-{row['question_id']}"
        scheduled = scheduler_module.SchedulerJob(
            task_id=task_id, req_id=str(row["question_id"]), step_id="agent-1",
            agent_name="benchmark_agent", runner=None, base_priority=5.0,
            estimated_tokens=ESTIMATED_TOKENS, execution_id=execution_id,
        )
        async def runner(job_row=row, eid=execution_id, delay=service_ms):
            nonlocal active, peak_active
            active += 1
            peak_active = max(peak_active, active)
            start_times[eid] = time.perf_counter()
            await asyncio.sleep(delay / 1000)
            active -= 1
            return "completed"
        scheduled.runner = runner
        rows_by_execution[execution_id] = {
            "question_id": row["question_id"], "conversation_id": row["conversation_id"],
            "category": row.get("category", "unknown"), "message_count": row.get("message_count", 0),
            "context_chars": row.get("context_chars", 0), "estimated_tokens": ESTIMATED_TOKENS,
            "simulated_runner_ms": service_ms, "execution_id": execution_id,
        }
        submit_started = time.perf_counter()
        async def submit_and_record(job=scheduled, baseline=submit_started, eid=execution_id):
            value = await scheduler.submit(job)
            end = time.perf_counter()
            started = start_times.get(eid, end)
            return {**rows_by_execution[eid], "result": value,
                    "queue_wait_ms": round(max(0, started - baseline) * 1000, 3),
                    "end_to_end_ms": round((end - baseline) * 1000, 3),
                    "service_ms": round((end - started) * 1000, 3)}
        waiters.append(submit_and_record())

    try:
        records_out = await asyncio.gather(*waiters)
        elapsed = time.perf_counter() - wall_started
        snapshot = scheduler.snapshot()
        for row in records_out:
            row["configuration"] = profile_name
            row["scheduler_global_slots"] = global_slots
            row["queue_wait_ms"] = round(row["queue_wait_ms"], 3)
        metrics = {
            "profile": profile_name, "global_slots": global_slots, "task_slots": TASK_SLOTS,
            "job_count": len(records_out), "completed": snapshot["metrics"]["completed"],
            "failed": snapshot["metrics"]["failed"], "requeued": snapshot["metrics"]["requeued"],
            "elapsed_seconds": round(elapsed, 4),
            "throughput_jobs_per_second": round(len(records_out) / elapsed, 3) if elapsed else 0,
            "mean_queue_wait_ms": round(mean(row["queue_wait_ms"] for row in records_out), 3) if records_out else 0,
            "p95_queue_wait_ms": _percentile([row["queue_wait_ms"] for row in records_out], 0.95),
            "mean_end_to_end_ms": round(mean(row["end_to_end_ms"] for row in records_out), 3) if records_out else 0,
            "p95_end_to_end_ms": _percentile([row["end_to_end_ms"] for row in records_out], 0.95),
            "peak_active_jobs": peak_active, "scheduler_wait_ms_accumulated": snapshot["metrics"]["wait_ms"],
            "event_counts": {name: sum(event["event"] == name for event in events)
                             for name in sorted({event["event"] for event in events})},
        }
        return records_out, metrics
    finally:
        await scheduler.stop()


def _percentile(values: list[float], percentile: float) -> float:
    if not values: return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)], 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True,
                        help="Prepared workload JSON from prepare_benchmark.py")
    parser.add_argument("--output-prefix", default=None,
                        help="Output stem; defaults to the workload dataset id")
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    provenance_path = args.dataset.with_suffix(".manifest.json")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.exists() else None
    records = dataset["records"]
    if not records: parser.error("workload dataset has no records")
    prefix = args.output_prefix or dataset.get("dataset_id", "scheduler_benchmark")
    trials_path = ROOT / "evaluations" / "agent_scheduler" / "results" / f"{prefix}_trials.jsonl"
    summary_path = ROOT / "evaluations" / "agent_scheduler" / "results" / f"{prefix}_summary.json"
    all_trials = []
    profiles = []
    for name, slots in PROFILES:
        trials, metrics = asyncio.run(run_profile(records, dataset.get("dataset_id", prefix), name, slots))
        all_trials.extend(trials)
        profiles.append(metrics)
        print(f"{name}: jobs={metrics['job_count']}, throughput={metrics['throughput_jobs_per_second']:.2f}/s, "
              f"p95_wait={metrics['p95_queue_wait_ms']:.2f}ms, failures={metrics['failed']}")
    trials_path.parent.mkdir(parents=True, exist_ok=True)
    trials_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in all_trials), encoding="utf-8")
    summary = {
        "evaluation": "agent_scheduler_external_benchmark",
        "dataset_id": dataset.get("dataset_id"), "question_count": len(records),
        "conversation_count": len({row["conversation_id"] for row in records}),
        "profiles": profiles,
        "manifest": {
            "workload_dataset": str(args.dataset.resolve().relative_to(ROOT)),
            "dataset_provenance": provenance,
            "runner": "deterministic synthetic async function; no LLM or external API",
            "job_mapping": "one scheduler job per benchmark QA item",
            "service_time": "2 ms plus one ms per 20,000 history characters, capped at 12 ms",
            "estimated_tokens_per_job": ESTIMATED_TOKENS,
            "profiles": [{"name": name, "global_slots": slots} for name, slots in PROFILES],
            "task_slots": TASK_SLOTS, "token_budget": TOKEN_BUDGET,
            "external_persistence": "stubbed",
        },
        "limits": ["Benchmark QA records are workload IDs/metadata, not native scheduler traces.",
                   "Latency and throughput describe this synthetic runner, not live LLM/provider execution."],
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {len(all_trials)} job trials to {trials_path}")
    print(f"Wrote profile summary to {summary_path}")


if __name__ == "__main__":
    main()
