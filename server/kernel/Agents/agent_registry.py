"""Agent registry — function-based registry for all agent types."""

from Agents.agents.a1 import run_agent_a1, AGENT_A1_DESCRIPTION
from Agents.agents.a2 import run_agent_a2, AGENT_A2_DESCRIPTION
from Agents.agents.a3 import run_agent_a3, AGENT_A3_DESCRIPTION
from Agents.agents.email_agent import run_email_agent, E_AGENT_DESCRIPTION

# Registry maps agent_type → (run_fn, description)
_REGISTRY: dict[str, dict] = {
    "a1": {"run": run_agent_a1, "description": AGENT_A1_DESCRIPTION},
    "a2": {"run": run_agent_a2, "description": AGENT_A2_DESCRIPTION},
    "a3": {"run": run_agent_a3, "description": AGENT_A3_DESCRIPTION},
    "email_agent": {"run": run_email_agent, "description": E_AGENT_DESCRIPTION},
}


def get_agent_run_fn(agent_type: str):
    """Return the run function for the given agent type."""
    entry = _REGISTRY.get(agent_type)
    if entry is None:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return entry["run"]


def get_agent_descriptions() -> dict[str, str]:
    """Return a dict of agent_type → description for the planner prompt."""
    return {name: entry["description"] for name, entry in _REGISTRY.items()}


def list_agent_types() -> list[str]:
    """Return all registered agent type keys."""
    return list(_REGISTRY.keys())
