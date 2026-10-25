# Scheduler evaluation dataset

`smoke_scenarios.json` is a deterministic contract dataset used to exercise
the scheduler's queue and resource-management functions. It contains
scenario descriptions and expected outcomes, not production user data.

`benchmark_workloads.json` is a separate seeded performance workload. It uses
mixed priorities, controlled service-time ranges, and resource contention to
measure throughput and p50/p95 queueing latency. Its results are measurements,
not a pass-rate claim, and should only be compared on the same host profile.
