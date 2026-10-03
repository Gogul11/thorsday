"""Planner prompt construction using semantic agent retrieval."""

from Agents.agent_registry import list_agent_types
from planning.agent_retriever import retrieve_agent_candidates


def build_planner_context(user_task: str) -> tuple[str, list[str]]:
    """Build a compact planner prompt from semantically retrieved agents."""
    candidates = list(retrieve_agent_candidates(user_task))
    valid_types = set(list_agent_types())
    candidate_names = [
        candidate["name"]
        for candidate in candidates
        if candidate["name"] in valid_types
    ]
    candidate_block = "\n\n".join(
        f"- {candidate['name']} (similarity={candidate['similarity']}):\n{candidate['description']}"
        for candidate in candidates
        if candidate["name"] in candidate_names
    )

    prompt = f"""
You are the AgentOS planning engine.

Create the smallest correct ordered execution plan for the user's task.
Use only the candidate agents below. Do not invent agent names.
Return an empty plan for a general question that needs no specialized agent.
Order agents according to dependencies. Select multiple agents only when the
output of one is needed by another.
Return a JSON object with these fields: agents (array of strings), steps (array
of objects with id, agent, depends_on, purpose), confidence (number from 0 to 1),
and rationale (string). Do not call tools.

Candidate agents retrieved by semantic capability search:
{candidate_block}

User task:
{user_task}

Valid candidate identifiers:
{', '.join(candidate_names)}
"""
    return prompt, candidate_names


def get_planner_system_prompt(user_task: str) -> str:
    """Compatibility wrapper for callers that only need the prompt."""
    prompt, _ = build_planner_context(user_task)
    return prompt
