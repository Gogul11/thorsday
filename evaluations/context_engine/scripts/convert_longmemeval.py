"""Normalize LongMemEval records for the AgentOS context-engine runner.

LongMemEval has had multiple public releases with slightly different field
names. This adapter accepts the common ``haystack``/``conversation`` and
``question``/``answer`` layouts, and fails loudly when evidence annotations
are unavailable instead of silently claiming retrieval ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any


SOURCE_URL = "https://github.com/xiaowu0162/LongMemEval-V2"


def _messages(record: dict[str, Any]) -> list[dict[str, Any]]:
    raw = record.get("haystack", record.get("conversation", record.get("messages")))
    if not isinstance(raw, list):
        raise ValueError("record has no list-valued haystack, conversation, or messages")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if isinstance(item, str):
            result.append({"id": f"msg-{index:05d}", "role": "human", "content": item})
            continue
        if not isinstance(item, dict):
            continue
        content = item.get("content", item.get("text", item.get("message")))
        if content is None:
            continue
        message_id = str(item.get("id", item.get("message_id", item.get("dia_id", f"msg-{index:05d}"))))
        role = str(item.get("role", item.get("speaker", "human"))).lower()
        result.append({
            "id": message_id,
            "role": "ai" if role in {"assistant", "ai", "bot"} else "human",
            "content": str(content),
        })
    return result


def _evidence(record: dict[str, Any], messages: list[dict[str, Any]]) -> list[str]:
    raw = record.get("evidence", record.get("evidence_ids", record.get("relevant_message_ids")))
    if raw is None:
        raise ValueError("record has no evidence annotation; retrieval scoring would be invalid")
    values = raw if isinstance(raw, list) else [raw]
    ids = {message["id"] for message in messages}
    result: list[str] = []
    for value in values:
        if isinstance(value, dict):
            value = value.get("id", value.get("message_id", value.get("turn_id")))
        if isinstance(value, int):
            if 0 <= value < len(messages):
                value = messages[value]["id"]
        if value is not None and str(value) in ids:
            result.append(str(value))
    return sorted(set(result))


def convert(source: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with source.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise ValueError("LongMemEval input must be a JSON array")
    records: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        question = item.get("question", item.get("query"))
        if not question:
            raise ValueError(f"record {index} has no question/query field")
        messages = _messages(item)
        evidence = _evidence(item, messages)
        records.append({
            "question_id": str(item.get("question_id", item.get("id", f"longmemeval-{index:05d}"))),
            "conversation_id": str(item.get("conversation_id", item.get("sample_id", f"conversation-{index:05d}"))),
            "messages": messages,
            "question": str(question),
            "expected_answer": item.get("answer", item.get("expected_answer")),
            "relevant_message_ids": evidence,
            "category": item.get("question_type", item.get("category")),
        })
    return records, {
        "source": SOURCE_URL,
        "source_file": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "converted_on": date.today().isoformat(),
        "question_count": len(records),
        "format": "AgentOS context-engine evaluation JSON",
        "notes": "Conversion requires explicit evidence annotations for retrieval metrics.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records, manifest = convert(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output.with_name(f"{args.output.stem}.manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"Converted {len(records)} LongMemEval questions")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
