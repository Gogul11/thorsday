# AgentOS Agent Scheduler Evaluation

An isolated, deterministic harness for measuring the global agent scheduler in
`server/kernel/services/agent_scheduler.py`. It uses the scheduler's public
`submit` lifecycle and real resource admission logic, with Redis and database
I/O stubbed so results do not depend on external services.

## Questions and scenarios

The smoke benchmark covers concurrent load, per-task concurrency limits,
priority ordering under queue contention, oversized token estimates, cumulative
task token budgets, runner failures, cooperative preemption/requeue, and
transient provider rate-limit retry. Synthetic jobs use controlled delays and
error signals; they do not call an LLM or depend on external services.

The checked-in smoke result passes all seven scenarios across three repetitions.
The oversized-token scenario verifies that the scheduler emits
`RESOURCE_DENIED` and `AGENT_BLOCKED`, rejects the submitted job, increments its
`failed` metric, and releases all active resources.

## Run

From the repository root:

```powershell
python evaluations/agent_scheduler/scripts/run_smoke_test.py
```

The inputs are in `datasets/smoke_scenarios.json`; run settings are in
`configs/smoke.json` (three repetitions by default). Override either input or
the repetition count with:

```powershell
python evaluations/agent_scheduler/scripts/run_smoke_test.py `
  --dataset evaluations/agent_scheduler/datasets/smoke_scenarios.json `
  --config evaluations/agent_scheduler/configs/smoke.json `
  --repetitions 3
```

For performance measurements, run the seeded workload benchmark. It runs the
same workload through the production priority policy and an admission-aware
FIFO baseline, with ten repetitions per policy/profile by default:

```powershell
python evaluations/agent_scheduler/scripts/run_benchmark.py
```

To add another repetition to the existing benchmark results without
overwriting them:

```powershell
python evaluations/agent_scheduler/scripts/run_benchmark.py `
  --append --repetitions 1
```

This writes `results/benchmark_trials.jsonl` and
`results/benchmark_summary.json`. The summary includes per-policy throughput,
queue-wait p95, end-to-end p95, high/low-priority latency, and explicit
priority-versus-FIFO deltas. It is a same-host comparison tool, not a
production capacity claim.

Raw records are written to
`evaluations/agent_scheduler/results/smoke_trials.jsonl` and aggregate metrics
to `evaluations/agent_scheduler/results/smoke_summary.json`.

## Metrics

- Job completion, failure, and expected outcome rates
- Queue wait and end-to-end latency
- Peak global and per-task active jobs
- Observed task token usage and resource denials
- Retry/requeue counts and lifecycle event counts

The performance benchmark additionally reports throughput, queue-wait latency,
end-to-end latency, high/low-priority latency, peak active slots, cross-task
completion spread, and priority-versus-FIFO deltas.

Each JSONL row retains the scenario, job inputs, outcome, timing, and observed
resource/scheduler snapshot. Aggregate results are diagnostic: the scenarios
are synthetic and should not be presented as production workload performance.

## Interpretation

The configured slot and token limits are recorded in each run manifest. The
priority scenario checks that a queued high-priority job is selected before a
queued low-priority job once a slot opens. It does not claim strict fairness
under every possible arrival pattern. The cooperative preemption case submits
a resumed job after the first safe-checkpoint result because the scheduler
returns that result to its caller while separately requeueing the job.
