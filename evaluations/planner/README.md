# AgentOS Planner Evaluation

An offline smoke evaluation for planner routing and plan-graph mechanics. The
runner uses the production functions for planner prompt construction, explicit
intent detection, step validation, fallback chaining, and Mermaid rendering.
It records raw per-case outcomes and aggregate scores.

## Run

From the repository root:

```powershell
python evaluations/planner/scripts/run_smoke_test.py
```

The input cases are in `datasets/smoke_tasks.json`; run settings are in
`configs/smoke.json`. Override the repetition count or input paths with
`--repetitions`, `--dataset`, and `--config`.

Results are written to `results/smoke_trials.jsonl` and
`results/smoke_summary.json`.

## Scope and metrics

The deterministic cases cover explicit time, hardware, research/email, and
code intent; filtering unknown agents; cycle fallback; and a general document
task. Metrics include candidate coverage, explicit-hint detection, final plan
match, graph validity, Mermaid rendering, fallback/repair counts, and helper
latency.

This is a mechanics smoke test, not an end-to-end LLM or semantic-retrieval
benchmark. Candidate lists and structured plan proposals are fixed dataset
fixtures because this evaluation environment does not have ChromaDB or the
provider dependencies installed. The result manifest states those limits.
