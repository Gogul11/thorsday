# Evaluation scripts

Scripts for dataset conversion, running configurations, scoring trials, and
producing reports belong here.

The first implementation should write one JSON object per trial to
`../results/trials.jsonl`. Aggregation must use pooled numerators and
denominators for rates, and must report mean, median, standard deviation, and
P95 for latency and token measurements.
