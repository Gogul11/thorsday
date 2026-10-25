"""Create an auditable function-calling catalog for the registered AgentOS agents.

This is the adapter boundary for BFCL-style evaluation. It does not claim that
arbitrary BFCL APIs are AgentOS tools. Instead, it exposes the actual AgentOS
registered agents as callable functions with a stable schema. A model-backed
runner can use this catalog to measure tool selection and argument generation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server" / "kernel"))

from Agents.agent_registry import get_agent_descriptions, list_agent_types  # noqa: E402


def build_catalog() -> dict:
    descriptions = get_agent_descriptions()
    functions = []
    for agent_name in list_agent_types():
        description = descriptions.get(agent_name, "")
        functions.append({
            "type": "function",
            "function": {
                "name": agent_name,
                "description": description.strip(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The complete user subtask to execute.",
                        },
                        "context": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "Relevant results or context from earlier steps.",
                        },
                    },
                    "required": ["task"],
                    "additionalProperties": False,
                },
            },
        })
    serialized = json.dumps(functions, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {
        "format": "OpenAI-compatible function tools",
        "source": "server/kernel/Agents/agent_registry.py",
        "created_on": date.today().isoformat(),
        "agent_count": len(functions),
        "agent_names": [item["function"]["name"] for item in functions],
        "catalog_sha256": hashlib.sha256(serialized).hexdigest(),
        "tools": functions,
        "warning": "This is an AgentOS tool catalog for an adapter evaluation, not an official BFCL score.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluations" / "planner" / "results" / "agentos_bfcl_tool_manifest.json",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_catalog(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(build_catalog()['agent_names'])} AgentOS tool schemas to {output}")


if __name__ == "__main__":
    main()
