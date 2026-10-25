# AgentOS Agent Scheduler Evaluation

An isolated, deterministic harness for measuring the global agent scheduler in
`server/kernel/services/agent_scheduler.py`. It uses the scheduler's public
`submit` lifecycle and real resource admission logic, with Redis and database
I/O stubbed so results do not depend on external services.

## Questions and scenarios

The smoke benchmark covers concurrent load, per-task concurrency limits,
priority ordering under queue contention, oversized token estimates, runner
failures, and cooperative preemption/requeue. Synthetic jobs use controlled
delays; they do not call an LLM or modify production scheduler behavior.

The checked-in smoke result currently passes four of five scenarios. The
oversized-token scenario is a real failure: the scheduler emits `RESOURCE_DENIED`
and `AGENT_BLOCKED` and rejects the submitted job, but does not increment its
`failed` metric in that code path. The evaluation leaves this production
behavior untouched so the result records what the current scheduler does.

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

Raw records are written to
`evaluations/agent_scheduler/results/smoke_trials.jsonl` and aggregate metrics
to `evaluations/agent_scheduler/results/smoke_summary.json`.

## Metrics

- Job completion, failure, and expected outcome rates
- Queue wait and end-to-end latency
- Peak global and per-task active jobs
- Observed task token usage and resource denials
- Retry/requeue counts and lifecycle event counts

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
