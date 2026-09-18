"""Agent registry — function-based registry for all agent types."""
from Agents.agents.crypto_pnl_agent import run_crypto_pnl_agent, CRYPTO_PNL_AGENT_DESCRIPTION
from Agents.agents.loan_emi_agent import run_loan_emi_agent, LOAN_EMI_AGENT_DESCRIPTION
from Agents.agents.a1 import run_agent_a1, AGENT_A1_DESCRIPTION
from Agents.agents.a2 import run_agent_a2, AGENT_A2_DESCRIPTION
from Agents.agents.a3 import run_agent_a3, AGENT_A3_DESCRIPTION
from Agents.agents.a4 import run_agent_a4, AGENT_A4_DESCRIPTION
from Agents.agents.content_creator_agent import run_content_creator_agent, CONTENT_AGENT_DESCRIPTION
from Agents.agents.email_agent import run_email_agent, E_AGENT_DESCRIPTION
from Agents.agents.weather_agent import run_weather_agent, WEATHER_AGENT_DESCRIPTION
from Agents.agents.agent_creator import run_agent_creator, AGENT_CREATOR_DESCRIPTION

# Registry maps agent_type → (run_fn, description)
_REGISTRY: dict[str, dict] = {
    "crypto_pnl_agent": {"run": run_crypto_pnl_agent, "description": CRYPTO_PNL_AGENT_DESCRIPTION},

    "loan_emi_agent": {"run": run_loan_emi_agent, "description": LOAN_EMI_AGENT_DESCRIPTION},

    "a1": {"run": run_agent_a1, "description": AGENT_A1_DESCRIPTION},
    "a2": {"run": run_agent_a2, "description": AGENT_A2_DESCRIPTION},
    "a3": {"run": run_agent_a3, "description": AGENT_A3_DESCRIPTION},
    "a4": {"run": run_agent_a4, "description": AGENT_A4_DESCRIPTION},
    "content_creator": {"run": run_content_creator_agent, "description": CONTENT_AGENT_DESCRIPTION},
    "email_agent": {"run": run_email_agent, "description": E_AGENT_DESCRIPTION},
    "weather_agent": {"run": run_weather_agent, "description": WEATHER_AGENT_DESCRIPTION},
    "agent_creator": {"run": run_agent_creator, "description": AGENT_CREATOR_DESCRIPTION},
}



def register_agent(agent_type: str, run_fn, description: str) -> None:
    """Register or update an agent dynamically in memory."""
    _REGISTRY[agent_type] = {"run": run_fn, "description": description}



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
