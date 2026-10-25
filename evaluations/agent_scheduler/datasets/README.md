# Scheduler evaluation dataset

`smoke_scenarios.json` is a small, hand-authored deterministic workload used
to exercise the scheduler's queue and resource-management functions. It
contains scenario descriptions and expected outcomes, not production user
data. The runner records each case as JSONL so scenarios can be expanded
without changing the meaning of old result files.
