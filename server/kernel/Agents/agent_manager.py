"""Agent manager — stateless functions over a plain dict runtime store."""

from Agents.agent_registry import get_agent_run_fn

# In-process store: agent_id → runtime dict
_agents: dict[str, dict] = {}


def create_agent(agent_id: str, agent_type: str, task_id: str) -> dict:
    """Register a new agent runtime. Raises if agent_id already exists."""
    if agent_id in _agents:
        raise ValueError(f"Agent {agent_id} already exists")

    run_fn = get_agent_run_fn(agent_type)  # raises if unknown type

    runtime = {
        "id": agent_id,
        "type": agent_type,
        "task_id": task_id,
        "run": run_fn,
        "status": "CREATED",
    }
    _agents[agent_id] = runtime
    return runtime


def get_agent(agent_id: str) -> dict:
    """Return the runtime dict for an existing agent."""
    if agent_id not in _agents:
        raise ValueError(f"Unknown agent: {agent_id}")
    return _agents[agent_id]


def set_agent_status(agent_id: str, status: str) -> None:
    """Update the status of an existing agent."""
    if agent_id not in _agents:
        raise ValueError(f"Unknown agent: {agent_id}")
    _agents[agent_id]["status"] = status


def destroy_agent(agent_id: str) -> None:
    """Remove an agent from the runtime store (no-op if already gone)."""
    if agent_id in _agents:
        _agents.pop(agent_id, None)
