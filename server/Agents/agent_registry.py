from .agents.system_agent import SystemAgent
from .agents.time_agent import TimeAgent
from .agents.research_agent import ResearchAgent


class AgentRegistry:

    def __init__(self, model):
        self.model = model

        # Primary registered agents with descriptive, human-readable keys
        self.agents = {
            "system_agent": SystemAgent,
            "time_agent": TimeAgent,
            "research_agent": ResearchAgent,
        }

        # Aliases for flexible routing and backward compatibility
        self._aliases = {
            "system": "system_agent",
            "time": "time_agent",
            "research": "research_agent",
            "a1": "system_agent",
            "a2": "time_agent",
            "a3": "research_agent",
        }

    def _resolve_agent_id(self, agent_id: str) -> str:
        return self._aliases.get(agent_id, agent_id)

    def create(self, agent_id: str):
        resolved_id = self._resolve_agent_id(agent_id)
        agent = self.agents.get(resolved_id)
        if agent is None:
            return None
        return agent(self.model)

    def get(self, agent_id: str):
        resolved_id = self._resolve_agent_id(agent_id)
        return self.agents.get(resolved_id)

    def get_descriptions(self):
        return {
            name: agent.description
            for name, agent in self.agents.items()
        }
