"""Planner prompt construction using semantic agent retrieval."""

import re

from Agents.agent_registry import get_agent_descriptions, list_agent_types
from planning.agent_retriever import (
    retrieve_agent_candidates,
    refresh_agent_index,
    register_agent_in_vector_db,
)


_EXPLICIT_INTENT_RULES = (
    ("a2", ("current time", "current date", "date and time", "time and date", "timezone", "time zone")),
    ("a1", ("system information", "system info", "machine information", "machine info", "hardware", "running processes", "operating system")),
    ("a3", ("wikipedia", "search for", "research", "black hole", "blackhole", "information about")),
    ("email_agent", ("email", "e-mail", "send it to", "send this to", "mail it to")),
    ("code_runner", ("python", "write code", "python code", "program", "test them", "test it", "add two numbers", "execute code")),
)

def get_explicit_agent_hints(user_task: str) -> list[str]:
    """Return registered capabilities explicitly requested by the user."""
    task = re.sub(r"\s+", " ", user_task.casefold())
    return [agent for agent, phrases in _EXPLICIT_INTENT_RULES if any(phrase in task for phrase in phrases)]


def _candidate_label(candidate: dict) -> str:
    if candidate.get("selection"):
        return str(candidate["selection"])
    return f"similarity={candidate['similarity']}"


def build_planner_context(user_task: str) -> tuple[str, list[str]]:
    """Build a compact planner prompt from semantically retrieved agents."""
    candidates = list(retrieve_agent_candidates(user_task))
    valid_types = set(list_agent_types())
    explicit_hints = get_explicit_agent_hints(user_task)
    candidate_map = {candidate["name"]: candidate for candidate in candidates}
    descriptions = get_agent_descriptions()
    for agent_name in explicit_hints:
        if agent_name in valid_types and agent_name not in candidate_map:
            candidates.append({
                "name": agent_name,
                "description": f"Agent: {agent_name}\nCapabilities:\n{descriptions[agent_name]}",
                "similarity": None,
                "selection": "explicit user intent",
            })
    # Planner-only fallback: it is not a semantic retrieval result.
    if "agent_creator" in valid_types and "agent_creator" not in candidate_map:
        candidates.append({
            "name": "agent_creator",
            "description": f"Agent: agent_creator\nCapabilities:\n{descriptions['agent_creator']}",
            "similarity": None,
            "selection": "fallback for unsupported subtasks (not a retrieval match)",
        })
    candidate_names = [
        candidate["name"]
        for candidate in candidates
        if candidate["name"] in valid_types
    ]
    candidate_block = "\n\n".join(
        f"- {candidate['name']} ({_candidate_label(candidate)}):\n{candidate['description']}"
        for candidate in candidates
        if candidate["name"] in candidate_names
    )

    prompt = f"""
You are the AgentOS planning engine.

Create the smallest correct ordered execution plan for the user's task.
First identify every distinct requested sub-task, then map each sub-task to
the candidate agent that can perform it. Include all required agents for
multi-task prompts. Put each concrete sub-task not covered by any candidate in
unhandled_tasks; do not omit it merely because no candidate can perform it.
Preserve the order in which the user requests sub-tasks, especially words such
as before, after, then, first, and once. For a mixed task, include an
agent_creator step where the unsupported sub-task belongs in that sequence,
and set that step's task field to only the unsupported sub-task(s). Add
dependencies to enforce the requested order. Agent Creator is a fallback for
unsupported work, not a general-purpose semantic match. If no existing agent
can handle any part, leave agents and steps empty; Prompt_type will decide
whether this is conversation or a wholly new task.
Return an empty plan only when all parts are conversational or need no agent.
Select A3 only when the requested work itself is research, source gathering,
fact-checking, or sourced academic/scientific findings. Do not select A3 merely
for a factual question or an unsupported calculation/task; put unsupported work
in unhandled_tasks so Agent Creator can handle it.
Use only the candidate agents below. Do not invent agent names.
Return an empty plan for a general question that needs no specialized agent.
Order agents according to dependencies. Select multiple agents only when the
output of one is needed by another. When the task explicitly requests multiple
capabilities, include every matching candidate. Do not drop a requested
research, email, or code-execution step just because another step is sufficient
for part of the task.
Return a JSON object with these fields: agents (array of strings), steps (array
of objects with id, agent, depends_on, purpose, and optional task), unhandled_tasks (array of
concrete unsupported subtasks), confidence (number from 0 to 1), and rationale
(string). Each purpose must explain the concrete responsibility
of that node; do not use generic text such as "Execute the selected agent.".
Do not call tools.

Candidate agents retrieved by semantic capability search:
{candidate_block}

User task:
{user_task}

Valid candidate identifiers:
{', '.join(candidate_names)}

Explicit capability requirements detected:
{', '.join(explicit_hints) or 'none'}
"""
    return prompt, candidate_names


def get_planner_system_prompt(user_task: str) -> str:
    """Compatibility wrapper for callers that only need the prompt."""
    prompt, _ = build_planner_context(user_task)
    return prompt
