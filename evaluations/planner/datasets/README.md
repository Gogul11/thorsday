# Planner evaluation dataset

`smoke_tasks.json` contains hand-authored task/candidate/plan fixtures. The
candidate fixtures stand in for Chroma semantic retrieval, while the runner
executes the repository's planner-context, explicit-intent, step validation,
legacy-chain, and Mermaid-rendering functions. No external dataset, LLM, Redis,
or MongoDB is used. This evaluates planner mechanics and routing guards, not
semantic retrieval quality or LLM plan quality.
