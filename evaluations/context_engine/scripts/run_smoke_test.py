"""Run the deterministic five-question context-engine smoke test.

This is a retrieval/visibility smoke test with optional LLM scoring. It checks
that context configurations can be executed and that raw telemetry is written
before a public benchmark is introduced.

Run from the repository root:
    python evaluations/context_engine/scripts/run_smoke_test.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = ROOT / "evaluations/context_engine/datasets/smoke_questions.json"
RESULTS_DIR = ROOT / "evaluations/context_engine/results"
TRIALS_PATH = RESULTS_DIR / "smoke_trials.jsonl"
SUMMARY_PATH = RESULTS_DIR / "smoke_summary.json"
ISOLATED_SWAP_DIR = RESULTS_DIR / "smoke_swap_space"

# Must be set before importing ContextPager: its module-level singleton opens
# the Chroma client during import.
os.environ.setdefault("AOS_CONTEXT_SWAP_DIR", str(ISOLATED_SWAP_DIR))
sys.path.insert(0, str(ROOT / "server" / "kernel"))

try:
    from services.context_pager import (  # type: ignore[import-not-found]
        MAX_PAGE_IN_RESULTS,
        PAGE_IN_SIMILARITY_THRESHOLD,
        context_pager,
    )
except ImportError as exc:
    raise SystemExit(
        "ContextPager dependencies are unavailable. Install server dependencies "
        "and retry. Original error: " + str(exc)
    ) from exc


BASE_CONFIGURATIONS = ("full_context", "recent_truncation", "vector_rag")
THRESHOLDS = (0.40, 0.45, 0.50, 0.55, 0.60)
VECTOR_RAG_TOP_K = 5
LLM_SCORING_ENABLED = os.getenv("AOS_SMOKE_LLM_SCORING", "0") == "1"
LLM_MODEL = os.getenv("AOS_SMOKE_LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = os.getenv("AOS_SMOKE_LLM_BASE_URL", "https://api.openai.com/v1/chat/completions")
# The production window is 20 messages. The five-message fixture is kept
# intentionally small, so the smoke test uses a four-message window to force
# page-out/page-in behaviour. The production value is tested in the full run.
ACTIVE_WINDOW = 4


def token_estimate(text: str) -> int:
    """Stable rough token estimate for smoke-test comparisons."""
    return max(1, (len(text) + 3) // 4) if text else 0


def score_with_llm(question: dict[str, Any], active_text: str) -> tuple[bool | None, str | None]:
    """Optionally judge the answer using an OpenAI-compatible chat endpoint."""
    api_key = os.getenv("AOS_SMOKE_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not LLM_SCORING_ENABLED or not api_key:
        return None, None
    expected = question["expected_answer"] or "The correct response is to abstain because the fact is unavailable."
    prompt = (
        "Answer the question using only the supplied context. If the answer is "
        "not present, say that it is unavailable. Return only the answer.\n\n"
        f"Context:\n{active_text}\n\nQuestion: {question['question']}"
    )
    payload = json.dumps({
        "model": LLM_MODEL,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    request = urllib.request.Request(
        LLM_BASE_URL,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
        answer = body["choices"][0]["message"]["content"].strip()
        if question["expected_answer"] is None:
            correct = "unavailable" in answer.lower() or "not specified" in answer.lower()
        else:
            correct = question["expected_answer"].lower() in answer.lower()
        return correct, answer
    except Exception as exc:  # The smoke run remains useful if the judge fails.
        return None, f"LLM scoring error: {type(exc).__name__}: {exc}"


def load_questions() -> list[dict[str, Any]]:
    with DATASET_PATH.open(encoding="utf-8") as handle:
        questions = json.load(handle)
    if len(questions) != 5:
        raise ValueError(f"Expected exactly 5 seed questions, found {len(questions)}")
    variants = [
        "Please recall: {}", "From our earlier discussion, {}",
        "What did we previously decide about this: {}",
        "Can you retrieve the historical answer to: {}",
        "Using the conversation history, answer: {}",
        "Look back through the context and tell me: {}",
        "What was the earlier AgentOS decision here: {}",
        "Find the relevant prior message and answer: {}",
        "Do you remember this detail: {}",
        "Check the older conversation for the answer: {}",
    ]
    expanded = []
    for seed in questions:
        for index, template in enumerate(variants, start=1):
            item = json.loads(json.dumps(seed))
            item["question_id"] = f"{seed['question_id']}-v{index:02d}"
            item["question"] = template.format(seed["question"])
            item["conversation_id"] = f"{seed['conversation_id']}-v{index:02d}"
            item["messages"] += [
                {"id": f"distractor-{index}-a", "role": "human", "content": "The dashboard layout uses a dark theme."},
                {"id": f"distractor-{index}-b", "role": "ai", "content": "The unrelated demo task completed successfully."},
            ]
            expanded.append(item)
    return expanded


def visible_messages(question: dict[str, Any], configuration: str) -> list[dict[str, Any]]:
    messages = question["messages"]
    if configuration == "full_context":
        return messages
    return messages[-ACTIVE_WINDOW:]


def evaluate_visibility(
    question: dict[str, Any], configuration: str, retrieved_indices: set[int]
) -> tuple[bool, bool]:
    """Return (answer_visible, abstention_correct) without invoking an LLM."""
    ids = {message["id"] for message in visible_messages(question, configuration)}
    retrieved_ids = {
        question["messages"][index]["id"]
        for index in retrieved_indices
        if 0 <= index < len(question["messages"])
    }
    available_ids = ids | retrieved_ids
    relevant_ids = set(question["relevant_message_ids"])
    if relevant_ids:
        return relevant_ids.issubset(available_ids), False
    # For an absent fact, the correct smoke-test behaviour is abstention.
    return False, True


def run_trial(
    question: dict[str, Any], configuration: str, repetition: int, threshold: float | None = None
) -> dict[str, Any]:
    messages = question["messages"]
    task_id = f"smoke-{configuration}-{repetition}-{question['question_id']}"
    full_text = "\n".join(message["content"] for message in messages)
    visible = visible_messages(question, configuration)
    retrieved: list[dict[str, Any]] = []
    page_out_count = 0
    page_out_latency_ms = 0.0
    page_in_latency_ms = 0.0
    error = None

    started = time.perf_counter()
    try:
        is_agentos_paging = configuration.startswith("agentos_paging")
        if configuration == "vector_rag" or is_agentos_paging:
            overflow = messages[:-ACTIVE_WINDOW]
            page_out_started = time.perf_counter()
            page_out_count = context_pager.page_out_messages(
                task_id=task_id, overflow_messages=overflow, base_index=0
            )
            page_out_latency_ms = (time.perf_counter() - page_out_started) * 1000
            page_in_started = time.perf_counter()
            if configuration == "vector_rag":
                retrieved = context_pager.page_in_relevant_context(
                    task_id=task_id, query=question["question"], top_k=VECTOR_RAG_TOP_K, threshold=0.0
                )
            else:
                retrieved = context_pager.page_in_relevant_context(
                    task_id=task_id,
                    query=question["question"],
                    top_k=VECTOR_RAG_TOP_K,
                    threshold=threshold if threshold is not None else PAGE_IN_SIMILARITY_THRESHOLD,
                )
            page_in_latency_ms = (time.perf_counter() - page_in_started) * 1000
        retrieved_indices = {int(page["message_index"]) for page in retrieved}
        answer_visible, abstention_correct = evaluate_visibility(
            question, configuration, retrieved_indices
        )
        active_text = "\n".join(message["content"] for message in visible)
        active_text += "\n" + "\n".join(page["text"] for page in retrieved)
        retrieval_latency_ms = (time.perf_counter() - started) * 1000
    except Exception as exc:  # smoke test records failures instead of stopping
        retrieved_indices = set()
        answer_visible = False
        abstention_correct = False
        retrieval_latency_ms = (time.perf_counter() - started) * 1000
        error = f"{type(exc).__name__}: {exc}"
        active_text = "\n".join(message["content"] for message in visible)

    full_tokens = token_estimate(full_text)
    active_tokens = token_estimate(active_text)
    llm_answer_correct, llm_answer = score_with_llm(question, active_text)
    relevant = set(question["relevant_message_ids"])
    retrieved_ids = {
        messages[index]["id"] for index in retrieved_indices if index < len(messages)
    }
    relevant_retrieved = relevant & retrieved_ids
    precision = len(relevant_retrieved) / len(retrieved_ids) if retrieved_ids else 0.0
    is_retrieval_configuration = configuration == "vector_rag" or configuration.startswith("agentos_paging")
    recall = len(relevant_retrieved) / len(relevant) if relevant and is_retrieval_configuration else None

    return {
        "trial_id": f"{task_id}",
        "configuration": configuration,
        "page_in_threshold": threshold,
        "repetition": repetition,
        "question_id": question["question_id"],
        "conversation_id": question["conversation_id"],
        "question": question["question"],
        "expected_answer": question["expected_answer"],
        "relevant_page_ids": sorted(relevant),
        "retrieved_page_ids": sorted(retrieved_ids),
        "retrieval_distances": [page.get("similarity") for page in retrieved],
        "page_out_count": page_out_count,
        "page_in_count": len(retrieved),
        "retrieval_recall_at_5": recall,
        "retrieval_precision_at_5": precision if retrieved and is_retrieval_configuration else None,
        "full_context_tokens_estimate": full_tokens,
        "active_context_tokens_estimate": active_tokens,
        "context_token_reduction": 1 - active_tokens / full_tokens if full_tokens else None,
        "page_out_latency_ms": round(page_out_latency_ms, 3),
        "page_in_latency_ms": round(page_in_latency_ms, 3),
        "total_context_operation_latency_ms": round(retrieval_latency_ms, 3),
        "answer_visible_without_llm": answer_visible,
        "abstention_correct_without_llm": abstention_correct,
        "error": error,
        "llm_scoring_enabled": LLM_SCORING_ENABLED,
        "llm_answer_correct": llm_answer_correct,
        "llm_answer": llm_answer,
        "smoke_test_note": "Visibility/retrieval check; LLM score is optional.",
        "smoke_active_window_messages": ACTIVE_WINDOW,
    }


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile_value))
    return ordered[index]


def aggregate(trials: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trial in trials:
        grouped[trial["configuration"]].append(trial)
    summary: dict[str, Any] = {"trial_count": len(trials), "configurations": {}}
    for configuration, rows in grouped.items():
        latencies = [row["page_in_latency_ms"] for row in rows if row["page_in_latency_ms"] > 0]
        page_out_latencies = [row["page_out_latency_ms"] for row in rows if row["page_out_latency_ms"] > 0]
        reductions = [row["context_token_reduction"] for row in rows if row["context_token_reduction"] is not None]
        summary["configurations"][configuration] = {
            "trial_count": len(rows),
            "errors": sum(row["error"] is not None for row in rows),
            "visible_or_abstention_success_rate": sum(
                row["answer_visible_without_llm"] or row["abstention_correct_without_llm"]
                for row in rows
            ) / len(rows),
            "mean_recall_at_5": mean(
                [row["retrieval_recall_at_5"] for row in rows if row["retrieval_recall_at_5"] is not None]
            ) if any(row["retrieval_recall_at_5"] is not None for row in rows) else None,
            "mean_token_reduction": mean(reductions) if reductions else None,
            "page_in_latency_ms": latency_stats(latencies),
            "page_out_latency_ms": latency_stats(page_out_latencies),
            "llm_answer_accuracy": (
                mean([row["llm_answer_correct"] for row in rows if row["llm_answer_correct"] is not None])
                if any(row["llm_answer_correct"] is not None for row in rows) else None
            ),
        }
    return summary


def latency_stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "stddev": None, "p95": None}
    return {
        "mean": mean(values),
        "median": median(values),
        "stddev": pstdev(values) if len(values) > 1 else 0.0,
        "p95": percentile(values, 0.95),
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    questions = load_questions()
    # Initialize the embedding model and Chroma path before recording timing.
    warmup_id = "smoke-warmup"
    context_pager.page_out_messages(
        warmup_id, [{"role": "human", "content": "warmup context"}]
    )
    context_pager.page_in_relevant_context(warmup_id, "warmup context", top_k=1, threshold=0.0)

    trials: list[dict[str, Any]] = []
    for repetition in range(1, 2):
        for question in questions:
            for configuration in BASE_CONFIGURATIONS:
                trials.append(run_trial(question, configuration, repetition))
            for threshold in THRESHOLDS:
                trials.append(
                    run_trial(
                        question,
                        f"agentos_paging_t{int(threshold * 100):02d}",
                        repetition,
                        threshold=threshold,
                    )
                )
    with TRIALS_PATH.open("w", encoding="utf-8") as handle:
        for trial in trials:
            handle.write(json.dumps(trial, ensure_ascii=False) + "\n")
    summary = aggregate(trials)
    with SUMMARY_PATH.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(f"Wrote {len(trials)} trials from {len(questions)} questions to {TRIALS_PATH}")
    print(f"Wrote summary to {SUMMARY_PATH}")
    for configuration, result in summary["configurations"].items():
        print(
            f"{configuration}: success={result['visible_or_abstention_success_rate']:.1%}, "
            f"errors={result['errors']}, "
            f"mean_page_in_ms={result['page_in_latency_ms']['mean'] or 0:.2f}, "
            f"mean_page_out_ms={result['page_out_latency_ms']['mean'] or 0:.2f}"
        )


if __name__ == "__main__":
    main()
