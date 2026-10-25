"""Deterministic local smoke evaluation for AgentScheduler."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server" / "kernel"))

# Keep this harness runnable without Redis or MongoDB packages/services. The
# scheduler methods that would call these adapters are stubbed per instance.
class _UnusedRedis:
    def __init__(self, **kwargs: Any):
        pass

    async def hset(self, *args: Any, **kwargs: Any) -> None: pass
    async def hget(self, *args: Any, **kwargs: Any) -> None: return None
    async def zadd(self, *args: Any, **kwargs: Any) -> None: pass
    async def zrem(self, *args: Any, **kwargs: Any) -> None: pass
    async def scan_iter(self, **kwargs: Any):
        if False:
            yield None

class _UnusedCollection:
    async def update_one(self, *args: Any, **kwargs: Any) -> None:
        return None

redis_module = types.ModuleType("redis")
redis_async_module = types.ModuleType("redis.asyncio")
redis_async_module.Redis = _UnusedRedis
redis_module.asyncio = redis_async_module
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_async_module)
db_module = types.ModuleType("DB.mongodb")
db_module.tasks_collection = _UnusedCollection()
sys.modules.setdefault("DB.mongodb", db_module)

try:
    from services import agent_scheduler as scheduler_module
except ImportError as exc:
    raise SystemExit(f"Scheduler dependencies are unavailable: {exc}") from exc
RESULTS = ROOT / "evaluations" / "agent_scheduler" / "results"
DEFAULT_DATASET = ROOT / "evaluations" / "agent_scheduler" / "datasets" / "smoke_scenarios.json"
DEFAULT_CONFIG = ROOT / "evaluations" / "agent_scheduler" / "configs" / "smoke.json"


def make_scheduler(global_slots: int = 3, task_slots: int = 2, token_budget: int = 100):
    scheduler = scheduler_module.AgentScheduler()
    scheduler.resources = scheduler_module.ResourceManager(global_slots, task_slots, token_budget)
    events: list[dict[str, Any]] = []
    # The evaluation measures scheduler behavior, not external persistence.
    async def persist(*args: Any, **kwargs: Any) -> None:
        return None
    async def emit(event: str, job: Any, **data: Any) -> None:
        events.append({"event": event, "task_id": job.task_id, "step_id": job.step_id, **data})
    async def recover() -> None:
        return None
    scheduler._persist = persist
    scheduler._emit = emit
    scheduler._recover_records = recover
    return scheduler, events


def job(task_id: str, step: str, runner, priority: float = 5, tokens: int = 10):
    return scheduler_module.SchedulerJob(
        task_id=task_id, req_id=f"req-{task_id}", step_id=step,
        agent_name="synthetic", runner=runner, base_priority=priority,
        estimated_tokens=tokens,
    )


async def wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise TimeoutError("scheduler scenario did not reach expected state")
        await asyncio.sleep(0.005)


async def execute_scenario(name: str, settings: dict[str, Any]) -> dict[str, Any]:
    scheduler, events = make_scheduler(
        int(settings["global_slots"]), int(settings["task_slots"]), int(settings["token_budget"])
    )
    started_at = time.perf_counter()
    details: dict[str, Any] = {}
    try:
        if name == "concurrency_and_task_limits":
            active = peak = 0
            by_task: dict[str, int] = {}
            task_peaks: dict[str, int] = {}
            lock = asyncio.Lock()
            async def runner(task_id: str):
                nonlocal active, peak
                async with lock:
                    active += 1
                    peak = max(peak, active)
                    by_task[task_id] = by_task.get(task_id, 0) + 1
                    task_peaks[task_id] = max(task_peaks.get(task_id, 0), by_task[task_id])
                await asyncio.sleep(float(settings["runner_delay_ms"]) / 1000)
                async with lock:
                    active -= 1
                    by_task[task_id] -= 1
                return "ok"
            results = await asyncio.gather(*[
                scheduler.submit(job(f"task-{i // 3}", f"step-{i}", lambda tid=f"task-{i // 3}": runner(tid)))
                for i in range(9)
            ])
            details.update(job_count=len(results), peak_global_active=peak, peak_active_by_task=task_peaks)
            details["expected_success"] = peak <= scheduler.resources.global_slots and all(
                value <= scheduler.resources.task_slots for value in task_peaks.values()
            ) and len(results) == 9

        elif name == "priority_queue_order":
            scheduler.resources = scheduler_module.ResourceManager(
                1, 1, int(settings["token_budget"])
            )
            release = asyncio.Event()
            order: list[str] = []
            async def blocker():
                await release.wait()
                order.append("blocker")
                return "ok"
            async def named(label: str):
                order.append(label)
                return label
            blocker_task = asyncio.create_task(scheduler.submit(job("block", "hold", blocker)))
            await wait_until(lambda: scheduler.resources.snapshot()["active_slots"] == 1)
            low = asyncio.create_task(scheduler.submit(job("low", "low", lambda: named("low"), priority=1)))
            await wait_until(lambda: len(scheduler._pending) == 1)
            high = asyncio.create_task(scheduler.submit(job("high", "high", lambda: named("high"), priority=9)))
            await wait_until(lambda: len(scheduler._pending) == 2)
            release.set()
            await asyncio.gather(blocker_task, low, high)
            queued_order = [item for item in order if item != "blocker"]
            details.update(start_order=order, queued_start_order=queued_order,
                           expected_success=queued_order == ["high", "low"])

        elif name == "oversized_token_job":
            async def never():
                return "should not run"
            scheduler.resources.token_budget = 20
            try:
                await scheduler.submit(job("too-large", "large", never, tokens=21))
                error = None
            except RuntimeError as exc:
                error = str(exc)
            snapshot = scheduler.snapshot()
            details.update(
                error=error,
                expected_success=(
                    error == "Estimated execution exceeds the task token budget"
                    and snapshot["metrics"]["failed"] == 1
                    and snapshot["resources"]["active_slots"] == 0
                ),
            )

        elif name == "cumulative_task_token_budget":
            scheduler.resources = scheduler_module.ResourceManager(2, 1, 25)
            first_runs = 0
            blocked_runs = 0
            async def first_step():
                nonlocal first_runs
                first_runs += 1
                return "completed"
            async def blocked_step():
                nonlocal blocked_runs
                blocked_runs += 1
                return "should not run"
            first_result = await scheduler.submit(
                job("budgeted", "step-1", first_step, tokens=15)
            )
            try:
                await scheduler.submit(
                    job("budgeted", "step-2", blocked_step, tokens=15)
                )
                second_error = None
            except RuntimeError as exc:
                second_error = str(exc)
            snapshot = scheduler.snapshot()
            details.update(
                first_result=first_result,
                second_error=second_error,
                first_runner_invocations=first_runs,
                blocked_runner_invocations=blocked_runs,
                expected_success=(
                    first_result == "completed"
                    and second_error == "Task token budget reached; no more agent steps can be admitted"
                    and first_runs == 1
                    and blocked_runs == 0
                    and snapshot["metrics"]["failed"] == 1
                ),
            )

        elif name == "runner_failure":
            async def fails():
                raise ValueError("synthetic failure")
            try:
                await scheduler.submit(job("failure", "fail", fails))
                error = None
            except ValueError as exc:
                error = str(exc)
            details.update(error=error, expected_success=error == "synthetic failure" and scheduler.snapshot()["metrics"]["failed"] == 1)

        elif name == "cooperative_preemption":
            attempts = 0
            async def checkpoint():
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    return {"__scheduler_status": "PREEMPTED"}
                return "resumed"
            returned = await scheduler.submit(job("resume", "checkpoint", checkpoint))
            await wait_until(lambda: scheduler.snapshot()["metrics"]["completed"] == 1)
            details.update(first_result=returned, runner_attempts=attempts,
                           requeued=scheduler.snapshot()["metrics"]["requeued"],
                           expected_success=attempts == 2 and scheduler.snapshot()["metrics"]["requeued"] == 1)

        elif name == "quota_retry":
            attempts = 0
            async def flaky():
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise RuntimeError("synthetic rate limit")
                return "recovered"
            returned = await scheduler.submit(job("quota", "retry", flaky))
            snapshot = scheduler.snapshot()
            details.update(
                result=returned,
                runner_attempts=attempts,
                requeued=snapshot["metrics"]["requeued"],
                expected_success=(
                    returned == "recovered"
                    and attempts == 2
                    and snapshot["metrics"]["requeued"] == 1
                    and snapshot["metrics"]["failed"] == 0
                    and snapshot["metrics"]["completed"] == 1
                ),
            )
        else:
            raise ValueError(f"Unknown scenario: {name}")

        details.setdefault("expected_success", False)
        details.update(scheduler_snapshot=scheduler.snapshot(), event_counts={
            event: sum(1 for item in events if item["event"] == event)
            for event in sorted({item["event"] for item in events})
        })
        return {
            "scenario": name, "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 3),
            "success": bool(details["expected_success"]), "details": details,
        }
    finally:
        await scheduler.stop()


async def run(repetitions: int, cases: list[dict[str, Any]], settings: dict[str, Any]) -> list[dict[str, Any]]:
    trials = []
    for repetition in range(1, repetitions + 1):
        for case in cases:
            scenario = case["scenario"]
            trial = await execute_scenario(scenario, settings)
            trial["repetition"] = repetition
            trial["trial_id"] = f"scheduler-{scenario}-{repetition}"
            trial["case_metadata"] = {
                key: case[key]
                for key in ("category", "description", "workload")
                if key in case
            }
            trial["expected"] = case["expected"]
            trials.append(trial)
    return trials


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--repetitions", type=int)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    settings = json.loads(args.config.read_text(encoding="utf-8"))
    cases = dataset["cases"]
    repetitions = args.repetitions if args.repetitions is not None else int(settings["repetitions"])
    if repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if not cases:
        parser.error("dataset must contain at least one case")
    trials = asyncio.run(run(repetitions, cases, settings))
    RESULTS.mkdir(parents=True, exist_ok=True)
    trials_path = RESULTS / "smoke_trials.jsonl"
    summary_path = RESULTS / "smoke_summary.json"
    trials_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in trials), encoding="utf-8")
    summary = {
        "evaluation": "agent_scheduler_smoke", "dataset_id": dataset.get("dataset_id"),
        "trial_count": len(trials),
        "success_count": sum(row["success"] for row in trials),
        "success_rate": sum(row["success"] for row in trials) / len(trials),
        "scenarios": {
            name: {"trials": len(rows), "success_rate": sum(row["success"] for row in rows) / len(rows),
                   "mean_elapsed_ms": round(sum(row["elapsed_ms"] for row in rows) / len(rows), 3)}
            for name in sorted({row["scenario"] for row in trials})
            for rows in [[row for row in trials if row["scenario"] == name]]
        },
        "manifest": {"config": str(args.config.resolve().relative_to(ROOT)),
                     "dataset": str(args.dataset.resolve().relative_to(ROOT)),
                     "global_slots": settings["global_slots"], "task_slots": settings["task_slots"],
                     "token_budget": settings["token_budget"],
                     "external_persistence": "stubbed", "jobs": "synthetic deterministic async runners"},
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {len(trials)} trials to {trials_path}")
    print(f"Success rate: {summary['success_rate']:.1%}; summary: {summary_path}")
    for scenario, stats in summary["scenarios"].items():
        print(f"{scenario}: success={stats['success_rate']:.1%}, mean_ms={stats['mean_elapsed_ms']:.2f}")


if __name__ == "__main__":
    main()
