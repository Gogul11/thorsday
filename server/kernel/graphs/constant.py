"""Planner prompt construction using semantic agent retrieval."""

import re

from Agents.agent_registry import get_agent_descriptions, list_agent_types
from planning.agent_retriever import retrieve_agent_candidates


_EXPLICIT_INTENT_RULES = (
    ("weather_agent", ("weather", "forecast", "temperature", "humidity", "wind speed", "will it rain", "precipitation")),
    ("a2", ("current time", "current date", "date and time", "time and date", "timezone", "time zone")),
    ("a1", ("system information", "system info", "machine information", "machine info", "hardware", "running processes", "operating system")),
    ("a3", ("wikipedia", "search for", "research", "black hole", "blackhole", "information about")),
    ("a4", ("file", "files", "document", "documents", "folder", "folders", "directory", "directories")),
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
                "description": f"Agent: {agent_name}\nCapabilities:\n{descriptions.get(agent_name, '')}",
                "similarity": None,
                "selection": "explicit user intent",
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

Break the user's request into its meaningful requested tasks, then create the
smallest correct ordered execution plan for the parts covered by the candidates.
Use only the candidate agents below. Do not invent agent names.
List any meaningful actionable parts that no candidate can perform in
uncovered_tasks. Do not list greetings, ordinary questions, or simple requests
that a normal LLM can answer directly. Group related uncovered parts that need
the same core capability into one item.
Order agents according to dependencies. Select multiple agents only when the
output of one is needed by another. When the task explicitly requests multiple
capabilities, include every matching candidate. Do not drop a requested
research, email, or code-execution step just because another step is sufficient
for part of the task.
Return a JSON object with these fields: agents (array of strings), steps (array
of objects with id, agent, depends_on, purpose), uncovered_tasks (array of
strings), confidence (number from 0 to 1), and rationale (string). Each purpose must explain the concrete responsibility
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
