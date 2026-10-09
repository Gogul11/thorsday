# AgentOS Context Engine Evaluation

This directory contains the isolated evaluation plan and artifacts for the
AgentOS context-paging engine. It is deliberately separate from
`server/kernel/services/` so evaluation code, datasets, and results do not
change production behaviour.

## Research question

Can AgentOS preserve the answer quality of a full-context system while using
less active context and keeping retrieval latency acceptable?

## Initial experiment

Run the same tasks through these configurations:

1. `full_context`: provide the complete conversation to the model.
2. `recent_truncation`: keep only the most recent messages.
3. `vector_rag`: retrieve top-k historical messages with a simple vector search.
4. `agentos_paging`: use `ContextPager` and the normal AgentOS context path.

Use the same model, embedding model, prompt, temperature, dataset split, and
number of repetitions for every configuration. Begin with 100 questions from
LongMemEval or LoCoMo plus 25--50 AgentOS-specific questions. Repeat each
configuration three times.

## Metrics

### Retrieval

- Recall@1, Recall@5, and Recall@10
- Precision@k
- Mean reciprocal rank
- Retrieval failure rate

### End-to-end

- Answer accuracy
- Task success rate
- Abstention accuracy for questions whose answer is absent
- Hallucination or unsupported-answer rate

### Efficiency

- Active context tokens
- Context token reduction against full context
- Page-in latency
- End-to-end latency
- Estimated and provider-reported token cost

The full-context configuration is the quality baseline. The intended result is
similar task accuracy with lower active-context tokens and acceptable latency.

## Required per-trial record

Each trial should retain:

```text
trial_id
configuration
dataset
question_id
conversation_id
question
expected_answer
relevant_page_ids
retrieved_page_ids
retrieval_distances
active_context_tokens
full_context_tokens
page_out_count
page_in_count
page_in_latency_ms
end_to_end_latency_ms
answer
answer_correct
abstention_correct
error
```

Do not store only aggregate scores. Raw records make it possible to recompute
metrics and inspect retrieval failures.

## Dataset layout

Place downloaded or converted datasets under `datasets/`. Do not commit
private or licensed data. The expected local format is JSONL with one question
per line:

```json
{
  "question_id": "example-001",
  "conversation_id": "conversation-001",
  "messages": [{"role": "user", "content": "..."}],
  "question": "What database was selected?",
  "expected_answer": "MongoDB",
  "relevant_page_ids": ["conversation-001-msg-004"]
}
```

Use `datasets/README.md` for source and licensing notes.

## Comparison policy

Published numbers from MemGPT/Letta, Mem0, or other systems are useful
background but are not directly comparable unless the model, prompt,
embedding model, k, judge, and dataset split are identical. Add those systems
as external comparisons only after the four local configurations are stable.

## Current AgentOS implementation notes

- Active context window: `ACTIVE_RAM_WINDOW = 20` messages.
- Page-in default: top 3 results.
- Page-in threshold: similarity `0.55`.
- Local embedding: ChromaDB `DefaultEmbeddingFunction`.
- Implementation: `server/kernel/services/context_pager.py` and
  `server/kernel/services/context.py`.

These values should be recorded in every experiment manifest and kept fixed
within a comparison.
