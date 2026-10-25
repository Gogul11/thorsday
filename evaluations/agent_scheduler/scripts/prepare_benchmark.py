"""Convert LoCoMo, LongMemEval, or context-engine JSON into scheduler workloads."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any


def _locomo(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for sample_index, sample in enumerate(raw):
        sample_id = str(sample.get("sample_id", sample.get("id", sample_index)))
        conversation = sample.get("conversation", {})
        turns = []
        for key, value in conversation.items():
            if key.startswith("session_") and isinstance(value, list):
                turns.extend(turn for turn in value if isinstance(turn, dict) and turn.get("text"))
        for q_index, qa in enumerate(sample.get("qa", [])):
            if not isinstance(qa, dict) or not qa.get("question"):
                continue
            records.append({
                "question_id": f"locomo-{sample_id}-q{q_index + 1:03d}",
                "conversation_id": f"locomo-{sample_id}",
                "category": str(qa.get("category", "unknown")),
                "message_count": len(turns),
                "context_chars": sum(len(str(turn.get("text", ""))) for turn in turns),
                "question_chars": len(str(qa["question"])),
            })
    return records


def _longmemeval(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for index, item in enumerate(raw):
        question = item.get("question", item.get("query", ""))
        sessions = item.get("haystack_sessions", item.get("haystack", item.get("conversation", [])))
        session_count = len(sessions) if isinstance(sessions, list) else 0
        turns = [turn for session in sessions if isinstance(session, list) for turn in session if isinstance(turn, dict)] if isinstance(sessions, list) else []
        context_chars = sum(len(str(turn.get("content", turn.get("text", "")))) for turn in turns)
        records.append({
            "question_id": str(item.get("question_id", item.get("id", f"longmemeval-{index:05d}"))),
            "conversation_id": str(item.get("conversation_id", item.get("sample_id", f"longmemeval-{index:05d}"))),
            "category": str(item.get("question_type", item.get("category", "unknown"))),
            "message_count": len(turns),
            "session_count": session_count,
            "context_chars": context_chars,
            "question_chars": len(str(question)),
        })
    return records


def _context_engine(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for index, item in enumerate(raw):
        messages = item.get("messages", [])
        records.append({
            "question_id": str(item.get("question_id", f"question-{index:05d}")),
            "conversation_id": str(item.get("conversation_id", f"conversation-{index:05d}")),
            "category": str(item.get("category", "unknown")),
            "message_count": len(messages),
            "context_chars": sum(len(str(message.get("content", ""))) for message in messages if isinstance(message, dict)),
            "question_chars": len(str(item.get("question", ""))),
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--format", choices=("locomo", "longmemeval", "context_engine"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        parser.error("input must contain a JSON array")
    records = {"locomo": _locomo, "longmemeval": _longmemeval,
               "context_engine": _context_engine}[args.format](raw)
    if not records:
        parser.error("no benchmark questions were found in the input")
    output = {"dataset_id": f"{args.format}_scheduler_workload_v1", "source_format": args.format,
              "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "dataset_id": output["dataset_id"], "source_format": args.format,
        "source_file": args.input.name,
        "source_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "converted_on": date.today().isoformat(), "question_count": len(records),
        "conversation_count": len({record["conversation_id"] for record in records}),
        "stored_fields": "IDs, category, message/session counts, and character counts only; no question or conversation text",
        "note": "Scheduler workload adapter; these benchmark QA sets are not native scheduler traces.",
    }
    args.output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Prepared {len(records)} question workloads from {manifest['conversation_count']} conversations")
    print(f"Wrote workload records to {args.output}")


if __name__ == "__main__":
    main()
