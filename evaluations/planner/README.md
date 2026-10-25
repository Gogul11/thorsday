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

The deterministic cases cover baseline routing plus ambiguous multi-intent
requests, multi-agent ordering, missing candidate recovery, conflicting
capabilities, invalid dependencies, duplicate-step filtering, unsupported
capability fallback, direct responses with no agent, and cycle fallback.
Metrics include candidate coverage, explicit-hint detection, final plan match,
dependency normalization, graph validity, Mermaid rendering, fallback/repair
counts, category-level outcomes, and helper latency.

This is a mechanics smoke test, not an end-to-end LLM or semantic-retrieval
benchmark. Candidate lists and structured plan proposals are fixed dataset
fixtures because this evaluation environment does not have ChromaDB or the
provider dependencies installed. The result manifest states those limits.
The headline result should therefore be described as planner-mechanics
conformance, not semantic planner accuracy. A meaningful end-to-end benchmark
must replace fixture candidates with production Chroma retrieval and evaluate
real structured LLM outputs on a held-out task set.

## External benchmark route

For an accepted external comparison, use the Berkeley Function Calling
Leaderboard (BFCL) for tool-selection and function-call correctness. BFCL
contains executable single-call, parallel, multi-turn, multi-step, and
stateful categories. Its official evaluator and data are available in the
[Gorilla BFCL repository](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard).

BFCL should not be copied directly into the local fixture file. An adapter
must first map each BFCL function schema to an AgentOS registered tool, send
the same tool schema to the planner, execute the returned calls in a controlled
environment, and score the calls with the official BFCL checker. Report BFCL
tool-call accuracy separately from AgentOS DAG metrics.

Generate the current AgentOS function catalog with:

```powershell
server\.venv\Scripts\python.exe evaluations/planner/scripts/prepare_bfcl_adapter.py
```

This writes `results/agentos_bfcl_tool_manifest.json`. The manifest is the
reproducible mapping boundary: it contains one OpenAI-compatible function
schema per registered agent and a SHA-256 catalog hash. It is ready for a
model-backed runner, but it is not itself an official BFCL score.

For a small model-backed AgentOS tool-selection run using the configured Groq
endpoint:

```powershell
server\.venv\Scripts\python.exe evaluations/planner/scripts/run_agentos_tool_smoke.py
```

The output is stored in `results/tool_selection_summary.json` and records the
model name, exact tool-set accuracy, required-tool recall, provider errors, and
raw tool calls. This is an AgentOS adapter smoke test; official BFCL results
still require running the official BFCL generator and evaluator.

The local v3 dataset deliberately includes two implicit-intent cases whose
wording is outside the current keyword rules. Their failures are useful: they
prevent the fixture score from becoming a claim of perfect semantic routing.
