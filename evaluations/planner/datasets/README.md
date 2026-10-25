# Planner evaluation dataset

`smoke_tasks.json` contains hand-authored task/candidate/plan fixtures. The
candidate fixtures stand in for Chroma semantic retrieval, while the runner
executes the repository's planner-context, explicit-intent, step validation,
legacy-chain, and Mermaid-rendering functions. No external dataset, LLM, Redis,
or MongoDB is used. This evaluates planner mechanics and routing guards, not
semantic retrieval quality or LLM plan quality.

The fixture includes baseline, multi-agent, ambiguous, missing-candidate,
conflicting-capability, invalid-dependency, fallback, and implicit-intent-gap
categories. The implicit-intent-gap cases are expected to expose weaknesses in
the current keyword-based intent detector; a non-perfect result is intentional
and more informative than a perfect fixture score.

For an external tool-selection benchmark, use the official BFCL data and
evaluator rather than treating these fixtures as a replacement:
https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard
