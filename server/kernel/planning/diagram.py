"""Diagram and validation helpers for execution plans."""

from __future__ import annotations

from typing import Iterable


def validate_steps(steps: Iterable[dict], valid_agents: set[str], candidates: set[str]) -> list[dict]:
    """Normalize plan steps and reject unknown agents, dependencies, or cycles."""
    normalized: list[dict] = []
    ids: set[str] = set()
    for index, raw in enumerate(steps):
        step_id = str(raw.get("id") or f"step_{index + 1}")
        agent = raw.get("agent")
        if step_id in ids or agent not in valid_agents or agent not in candidates:
            continue
        ids.add(step_id)
        normalized.append(
            {
                "id": step_id,
                "agent": agent,
                "depends_on": list(dict.fromkeys(raw.get("depends_on") or [])),
                "purpose": str(raw.get("purpose") or "Execute the assigned agent."),
            }
        )

    known_ids = {step["id"] for step in normalized}
    for step in normalized:
        step["depends_on"] = [dependency for dependency in step["depends_on"] if dependency in known_ids and dependency != step["id"]]

    # Kahn-style cycle check.
    remaining = {step["id"]: set(step["depends_on"]) for step in normalized}
    resolved: set[str] = set()
    while remaining:
        ready = {step_id for step_id, deps in remaining.items() if deps <= resolved}
        if not ready:
            return []
        resolved.update(ready)
        for step_id in ready:
            remaining.pop(step_id)

    return normalized


def chain_steps(agents: list[str]) -> list[dict]:
    """Convert a legacy ordered agent list into a valid sequential DAG."""
    steps = []
    previous = None
    for index, agent in enumerate(agents, start=1):
        step_id = f"step_{index}"
        steps.append({"id": step_id, "agent": agent, "depends_on": [previous] if previous else [], "purpose": "Execute the selected agent."})
        previous = step_id
    return steps


def to_mermaid(steps: list[dict]) -> str:
    """Render a plan DAG as Mermaid flowchart source."""
    lines = ["flowchart TD"]
    if not steps:
        lines.append('  empty["Direct response — no agents selected"]')
        return "\n".join(lines)
    for step in steps:
        label = f"{step['id']}\\n{step['agent']}"
        lines.append(f'  {step["id"]}["{label}"]')
    for step in steps:
        for dependency in step["depends_on"]:
            lines.append(f"  {dependency} --> {step['id']}")
    return "\n".join(lines)
