"""Global cooperative scheduler for DAG agent executions.

The graph remains responsible for dependency correctness.  This module owns
cross-task fairness, resource admission, durable queue metadata, and the
observable scheduler lifecycle.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from Redis.redis_connection import publish, redis_client
from logger import logger
from repository.task_repo import DB_add_task_event, DB_update_task


@dataclass
class ResourceLease:
    task_id: str
    estimated_tokens: int


class ResourceManager:
    """In-process admission control with Redis-visible accounting."""

    def __init__(self, global_slots: int = 3, task_slots: int = 2, token_budget: int = 50_000):
        self.global_slots = global_slots
        self.task_slots = task_slots
        self.token_budget = token_budget
        self._active = 0
        self._active_by_task: dict[str, int] = {}
        self._tokens_by_task: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, task_id: str, estimated_tokens: int) -> ResourceLease | None:
        async with self._lock:
            used_tokens = self._tokens_by_task.get(task_id, 0)
            task_active = self._active_by_task.get(task_id, 0)
            if self._active >= self.global_slots or task_active >= self.task_slots:
                return None
            if used_tokens + estimated_tokens > self.token_budget:
                return None
            self._active += 1
            self._active_by_task[task_id] = task_active + 1
            self._tokens_by_task[task_id] = used_tokens + estimated_tokens
            return ResourceLease(task_id, estimated_tokens)

    async def release(self, lease: ResourceLease, consumed_tokens: int | None = None) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)
            current = self._active_by_task.get(lease.task_id, 1)
            if current <= 1:
                self._active_by_task.pop(lease.task_id, None)
            else:
                self._active_by_task[lease.task_id] = current - 1
            if consumed_tokens is not None:
                self._tokens_by_task[lease.task_id] = max(
                    0, self._tokens_by_task.get(lease.task_id, 0) - lease.estimated_tokens + consumed_tokens
                )

    def snapshot(self) -> dict[str, Any]:
        return {
            "global_slots": self.global_slots,
            "active_slots": self._active,
            "task_slots": self.task_slots,
            "active_by_task": dict(self._active_by_task),
            "tokens_by_task": dict(self._tokens_by_task),
            "token_budget": self.token_budget,
        }

    def can_admit(self, task_id: str, estimated_tokens: int) -> bool:
        return (
            estimated_tokens <= self.token_budget
            and self._active < self.global_slots
            and self._active_by_task.get(task_id, 0) < self.task_slots
            and self._tokens_by_task.get(task_id, 0) + estimated_tokens <= self.token_budget
        )


@dataclass
class SchedulerJob:
    task_id: str
    req_id: str
    step_id: str
    agent_name: str
    runner: Callable[[], Awaitable[Any]]
    base_priority: float = 5.0
    estimated_tokens: int = 4_000
    ready_at: float = field(default_factory=time.time)
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    attempt: int = 1
    token_usage: dict[str, int] = field(default_factory=dict)
    future: asyncio.Future[Any] | None = None


class AgentScheduler:
    """One scheduler worker shared by every task in the kernel process."""

    def __init__(self):
        self.aging_factor = float(os.getenv("SCHEDULER_AGING_FACTOR", "0.002"))
        self.max_priority = float(os.getenv("SCHEDULER_MAX_PRIORITY", "10"))
        self.time_quantum = float(os.getenv("SCHEDULER_TIME_QUANTUM", "30"))
        self.retry_limit = int(os.getenv("SCHEDULER_RETRY_LIMIT", "3"))
        self.resources = ResourceManager(
            global_slots=int(os.getenv("SCHEDULER_GLOBAL_SLOTS", "3")),
            task_slots=int(os.getenv("SCHEDULER_TASK_SLOTS", "2")),
            token_budget=int(os.getenv("SCHEDULER_TOKEN_BUDGET", "50000")),
        )
        self._pending: list[SchedulerJob] = []
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._worker: asyncio.Task[None] | None = None
        self._running: set[asyncio.Task[None]] = set()
        self._started = False
        self._metrics = {"submitted": 0, "completed": 0, "failed": 0, "requeued": 0, "wait_ms": 0}
        self._usage_by_task: dict[str, dict[str, int]] = {}

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._worker = asyncio.create_task(self._run(), name="agent_scheduler")
        await self._recover_records()
        logger.info("Agent scheduler started | global_slots=%d | task_slots=%d", self.resources.global_slots, self.resources.task_slots)

    async def stop(self) -> None:
        for task in list(self._running):
            task.cancel()
        if self._running:
            await asyncio.gather(*self._running, return_exceptions=True)
        self._running.clear()
        if self._worker:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
        self._worker = None
        self._started = False

    async def submit(self, job: SchedulerJob) -> Any:
        await self.start()
        job.future = asyncio.get_running_loop().create_future()
        async with self._lock:
            self._pending.append(job)
            self._metrics["submitted"] += 1
            await self._persist(job, "READY")
        await self._emit("AGENT_READY", job, status="READY")
        self._wake.set()
        return await job.future

    async def _run(self) -> None:
        while True:
            launched = False
            while True:
                job = await self._next_job(only_admissible=True)
                if job is None:
                    # A permanently oversized job must not remain invisible in
                    # the durable queue; process it into BLOCKED below.
                    oversized = next(
                        (candidate for candidate in self._pending if candidate.estimated_tokens > self.resources.token_budget),
                        None,
                    )
                    if oversized is not None:
                        async with self._lock:
                            self._pending.remove(oversized)
                        await self._persist(oversized, "FAILED", error="Estimated execution exceeds the task token budget")
                        await self._emit("RESOURCE_DENIED", oversized, status="FAILED", reason="token_budget")
                        await self._emit("AGENT_BLOCKED", oversized, status="BLOCKED", reason="token_budget")
                        if oversized.future and not oversized.future.done():
                            oversized.future.set_exception(RuntimeError("Estimated execution exceeds the task token budget"))
                    break

                lease = await self.resources.acquire(job.task_id, job.estimated_tokens)
                if lease is None:
                    async with self._lock:
                        self._pending.append(job)
                    break

                launched = True
                task = asyncio.create_task(self._execute(job, lease), name=f"agent:{job.execution_id}")
                self._running.add(task)
                task.add_done_callback(self._running.discard)

            if not self._pending and not self._running:
                self._wake.clear()
                await self._wake.wait()
                continue

            if not launched:
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=0.15)
                except asyncio.TimeoutError:
                    pass

    async def _execute(self, job: SchedulerJob, lease: ResourceLease) -> None:
        await self._persist(job, "RUNNING")
        await self._emit("RESOURCE_APPROVED", job, status="RUNNING")
        await self._emit("AGENT_RUNNING", job, status="RUNNING", time_quantum=self.time_quantum)
        started = time.monotonic()
        try:
            # Cooperative quantum: the runner may return a PREEMPTED result
            # at a safe checkpoint. We never cancel an active LLM request.
            result = await job.runner()
            if isinstance(result, dict) and result.get("__scheduler_status") == "PREEMPTED":
                await self._requeue(job, "cooperative_checkpoint")
                if job.future and not job.future.done():
                    job.future.set_result(result)
            else:
                self._metrics["completed"] += 1
                usage = job.token_usage or {}
                task_usage = self._usage_by_task.setdefault(job.task_id, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    task_usage[key] += int(usage.get(key, 0))
                try:
                    await DB_update_task(job.task_id, token_usage=task_usage)
                except Exception as exc:
                    logger.warning("Scheduler token usage persistence failed: %s", exc)
                await self._persist(job, "COMPLETED", token_usage=usage)
                await self._emit(
                    "AGENT_COMPLETED",
                    job,
                    status="COMPLETED",
                    duration_ms=int((time.monotonic() - started) * 1000),
                    token_usage=usage,
                )
                if job.future and not job.future.done():
                    job.future.set_result(result)
        except Exception as exc:
            if self._is_quota_error(exc) and job.attempt < self.retry_limit:
                job.attempt += 1
                await self._requeue(job, "provider_quota_or_rate_limit", delay=2 ** (job.attempt - 1))
            else:
                self._metrics["failed"] += 1
                await self._persist(job, "FAILED", error=str(exc))
                await self._emit("AGENT_FAILED", job, status="FAILED", error=str(exc))
                if job.future and not job.future.done():
                    job.future.set_exception(exc)
        finally:
            await self.resources.release(lease)
            self._wake.set()

    async def _next_job(self, only_admissible: bool = False) -> SchedulerJob | None:
        async with self._lock:
            if not self._pending:
                return None
            now = time.time()
            scored = [
                (min(self.max_priority, job.base_priority + self.aging_factor * (now - job.ready_at)), -job.ready_at, index, job)
                for index, job in enumerate(self._pending)
                if not only_admissible or self.resources.can_admit(job.task_id, job.estimated_tokens)
            ]
            if not scored:
                return None
            _, _, index, job = max(scored)
            self._pending.pop(index)
            self._metrics["wait_ms"] += int((now - job.ready_at) * 1000)
            return job

    async def _requeue(self, job: SchedulerJob, reason: str, delay: float = 0) -> None:
        self._metrics["requeued"] += 1
        if delay:
            await asyncio.sleep(delay)
        job.ready_at = time.time()
        async with self._lock:
            self._pending.append(job)
        await self._persist(job, "READY", reason=reason)
        await self._emit("AGENT_PREEMPTED", job, status="READY", reason=reason)
        self._wake.set()

    async def _persist(self, job: SchedulerJob, status: str, **extra: Any) -> None:
        key = f"agentos:scheduler:job:{job.execution_id}"
        payload = {
            "task_id": job.task_id, "req_id": job.req_id, "step_id": job.step_id,
            "agent_name": job.agent_name, "status": status, "base_priority": job.base_priority,
            "ready_at": job.ready_at, "attempt": job.attempt, "updated_at": time.time(), **extra,
        }
        try:
            await redis_client.hset(key, mapping={k: str(v) for k, v in payload.items()})
            if status in {"READY", "WAITING"}:
                await redis_client.zadd("agentos:scheduler:ready", {job.execution_id: -job.base_priority})
            else:
                await redis_client.zrem("agentos:scheduler:ready", job.execution_id)
        except Exception as exc:
            logger.warning("Scheduler Redis persistence failed: %s", exc)

    async def _recover_records(self) -> None:
        """Mark stale RUNNING records interrupted for audit/recovery visibility."""
        try:
            async for key in redis_client.scan_iter(match="agentos:scheduler:job:*"):
                status = await redis_client.hget(key, "status")
                if status == "RUNNING":
                    await redis_client.hset(key, mapping={"status": "INTERRUPTED", "recovered_at": str(time.time())})
        except Exception as exc:
            logger.warning("Scheduler recovery scan failed: %s", exc)

    async def _emit(self, event: str, job: SchedulerJob, **data: Any) -> None:
        now = time.time()
        wait_ms = max(0, int((now - job.ready_at) * 1000))
        effective = min(self.max_priority, job.base_priority + self.aging_factor * (now - job.ready_at))
        payload = {
            "event": event, "req_id": job.req_id, "task_id": job.task_id,
            "step_id": job.step_id, "agent_id": f"{job.task_id}-{job.step_id}-{job.agent_name}",
            "agent_name": job.agent_name, "execution_id": job.execution_id,
            "status": data.pop("status", None), "priority": job.base_priority,
            "effective_priority": round(effective, 4), "queue_wait_ms": wait_ms,
            "queue_position": max(0, len(self._pending) + 1),
            "attempt": job.attempt, "timestamp": now,
            "estimated_tokens": job.estimated_tokens,
            "scheduler_metrics": self.snapshot(), **data,
        }
        try:
            await publish("kernel_events", payload)
            await DB_add_task_event(job.task_id, payload)
        except Exception as exc:
            logger.warning("Scheduler event persistence failed: %s", exc)

    @staticmethod
    def _is_quota_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(token in text for token in ("rate limit", "quota", "429", "tokens per day"))

    def snapshot(self) -> dict[str, Any]:
        return {
            "pending": len(self._pending),
            "metrics": dict(self._metrics),
            "resources": self.resources.snapshot(),
            "usage_by_task": dict(self._usage_by_task),
        }


_scheduler: AgentScheduler | None = None


def get_scheduler() -> AgentScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AgentScheduler()
    return _scheduler
