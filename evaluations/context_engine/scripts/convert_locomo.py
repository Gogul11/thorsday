"""Convert the official LoCoMo JSON into the AgentOS evaluation format.

Download the official ``data/locomo10.json`` first, then run:

    python evaluations/context_engine/scripts/convert_locomo.py \
        --input path/to/locomo10.json \
        --output evaluations/context_engine/datasets/locomo.json

The converter keeps one record per LoCoMo QA item. Evidence dialog IDs are
mapped to stable message IDs, so retrieval metrics can be calculated without
guessing which turn contains the answer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any


SOURCE_URL = "https://github.com/snap-research/locomo"


def _session_number(key: str) -> int:
    digits = "".join(character for character in key if character.isdigit())
    return int(digits) if digits else 10**9


def _conversation_turns(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for session_key in sorted(conversation, key=_session_number):
        value = conversation[session_key]
        if not isinstance(value, list):
            continue
        for turn in value:
            if not isinstance(turn, dict) or not turn.get("text"):
                continue
            dialog_id = str(turn.get("dia_id", turn.get("id", len(turns))))
            speaker = str(turn.get("speaker", "unknown"))
            turns.append({
                "id": dialog_id,
                "role": "human" if speaker.lower() in {"user", "human"} else "ai",
                "content": str(turn["text"]),
                "speaker": speaker,
            })
    return turns


def _evidence_ids(evidence: Any) -> list[str]:
    if not isinstance(evidence, list):
        return []
    result: list[str] = []
    for item in evidence:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, list):
            result.extend(str(value) for value in item)
        elif isinstance(item, dict):
            value = item.get("dia_id", item.get("id"))
            if value is not None:
                result.append(str(value))
    return sorted(set(result))


def convert(source: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with source.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise ValueError("LoCoMo input must be a JSON array")

    records: list[dict[str, Any]] = []
    for sample in raw:
        if not isinstance(sample, dict):
            continue
        sample_id = str(sample.get("sample_id", sample.get("id", len(records))))
        conversation = sample.get("conversation")
        if not isinstance(conversation, dict):
            raise ValueError(f"Sample {sample_id} has no conversation object")
        messages = _conversation_turns(conversation)
        message_ids = {message["id"] for message in messages}
        qa_items = sample.get("qa", [])
        if not isinstance(qa_items, list):
            continue
        for qa_index, qa in enumerate(qa_items):
            if not isinstance(qa, dict) or not qa.get("question"):
                continue
            evidence = [item for item in _evidence_ids(qa.get("evidence")) if item in message_ids]
            records.append({
                "question_id": f"locomo-{sample_id}-q{qa_index + 1:03d}",
                "conversation_id": f"locomo-{sample_id}",
                "messages": messages,
                "question": str(qa["question"]),
                "expected_answer": qa.get("answer"),
                "relevant_message_ids": evidence,
                "category": qa.get("category"),
                "source_evidence_ids": _evidence_ids(qa.get("evidence")),
            })

    return records, {
        "source": SOURCE_URL,
        "source_file": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "converted_on": date.today().isoformat(),
        "conversation_count": len(raw),
        "question_count": len(records),
        "format": "AgentOS context-engine evaluation JSON",
        "notes": "Evidence IDs are retained from LoCoMo; no synthetic questions were added.",
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
    print(f"Converted {manifest['conversation_count']} conversations and {len(records)} questions")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
