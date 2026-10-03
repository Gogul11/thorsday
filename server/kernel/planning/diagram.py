"""Diagram and validation helpers for execution plans."""

from __future__ import annotations

from typing import Iterable

from Agents.agent_registry import get_agent_descriptions


_AGENT_PURPOSES = {
    "a1": "System and hardware inspection.",
    "a2": "Date, time, timezone, and calendar information.",
    "a3": "Factual and technical research.",
    "a4": "File and document operations.",
    "content_creator": "Writing and report generation.",
    "email_agent": "Email delivery.",
    "weather_agent": "Weather and forecast retrieval.",
    "agent_creator": "Creating new specialized agents.",
    "code_runner": "Generating, testing, and repairing Python code.",
    "loan_emi_agent": "EMI and amortization calculations.",
    "crypto_pnl_agent": "Cryptocurrency profit/loss analysis.",
}


def _agent_purpose(agent: str) -> str:
    """Return a concise capability-based purpose for a plan node."""
    if agent in _AGENT_PURPOSES:
        return _AGENT_PURPOSES[agent]
    description = get_agent_descriptions().get(agent, "")
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    if lines:
        return lines[0].rstrip(" .,;:") + "."
    return f"Run the {agent} capability for this task."


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
        # Keep graph labels deterministic and compact. The LLM may provide a
        # long explanation, but the visual graph always uses the canonical
        # responsibility label for that agent.
        purpose = _agent_purpose(agent)
        normalized.append(
            {
                "id": step_id,
                "agent": agent,
                "depends_on": list(dict.fromkeys(raw.get("depends_on") or [])),
                "purpose": purpose,
            }
        )

    known_ids = {step["id"] for step in normalized}
    agent_to_step = {
        step["agent"]: step["id"]
        for step in normalized
    }
    for step in normalized:
        dependencies = []
        for dependency in step["depends_on"]:
            dependency_id = agent_to_step.get(dependency, dependency)
            if dependency_id in known_ids and dependency_id != step["id"]:
                dependencies.append(dependency_id)
        step["depends_on"] = list(dict.fromkeys(dependencies))

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
        steps.append({"id": step_id, "agent": agent, "depends_on": [previous] if previous else [], "purpose": _agent_purpose(agent)})
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
