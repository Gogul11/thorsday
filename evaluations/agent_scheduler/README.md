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

## LoCoMo and LongMemEval workload benchmark

The external benchmark runner treats each QA item as one synthetic scheduler
job, using conversation length to vary a short, deterministic runner duration.
It compares serial (1 slot), default (3 slots), and expanded (8 slots)
admission profiles and reports throughput, queue wait, end-to-end latency,
peak concurrency, and failures. This measures scheduler behavior under
benchmark-sized arrival volume. It does not evaluate QA accuracy or live
provider latency because the scheduler is not itself a memory-answering model.

Get the official LoCoMo `locomo10.json` and LongMemEval `longmemeval_oracle.json`
files and place them in `datasets/local/`. LoCoMo is available from the
[official LoCoMo repository](https://github.com/snap-research/LoCoMo); the
[official LongMemEval README](https://github.com/xiaowu0162/LongMemEval) links
to its Hugging Face release. The original benchmark files and prepared
workloads stay local and are git-ignored.

Prepare each workload (the adapter keeps IDs and length metadata, not message
or question text):

```powershell
python evaluations/agent_scheduler/scripts/prepare_benchmark.py `
  --input evaluations/agent_scheduler/datasets/local/locomo10.json `
  --format locomo `
  --output evaluations/agent_scheduler/datasets/local/locomo_workload.json

python evaluations/agent_scheduler/scripts/prepare_benchmark.py `
  --input evaluations/agent_scheduler/datasets/local/longmemeval_oracle.json `
  --format longmemeval `
  --output evaluations/agent_scheduler/datasets/local/longmemeval_workload.json
```

Run the benchmark on either prepared workload:

```powershell
python evaluations/agent_scheduler/scripts/run_benchmark.py `
  --dataset evaluations/agent_scheduler/datasets/local/locomo_workload.json

python evaluations/agent_scheduler/scripts/run_benchmark.py `
  --dataset evaluations/agent_scheduler/datasets/local/longmemeval_workload.json
```

Summary and per-job result files are written under `results/` with the workload
dataset ID in their filenames. Prepared workload manifests preserve the
original file checksum and question count.

### Run results (26 October 2026)

All jobs completed with zero failures in all three profiles. These are
synthetic-runner measurements; use them to compare scheduler admission
profiles on identical benchmark workloads, not as live provider latency.

| Workload | Jobs | Global slots | Throughput (jobs/s) | P95 queue wait |
| --- | ---: | ---: | ---: | ---: |
| LoCoMo | 1,986 | 1 | 63.9 | 29,508 ms |
| LoCoMo | 1,986 | 3 (default) | 164.1 | 11,561 ms |
| LoCoMo | 1,986 | 8 | 292.8 | 6,545 ms |
| LongMemEval Oracle | 500 | 1 | 64.3 | 7,367 ms |
| LongMemEval Oracle | 500 | 3 (default) | 191.5 | 2,466 ms |
| LongMemEval Oracle | 500 | 8 | 501.7 | 929 ms |

The runs used one job per QA record, 4,000 estimated tokens per job, and a
2–12 ms deterministic runner delay derived from history size. Since each QA
record is modeled as an independent task, these benchmark runs exercise global
admission and queueing; the per-task cap is covered by the scheduler smoke
scenario above. Full measurements and dataset checksums are in the summary and
prepared-workload manifests.
