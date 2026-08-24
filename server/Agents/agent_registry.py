from .agents.system_agent import SystemAgent
from .agents.time_agent import TimeAgent
from .agents.research_agent import ResearchAgent


class AgentRegistry:

    def __init__(self, model):
        self.model = model

        self.agents = {
            "system_agent": SystemAgent,
            "time_agent": TimeAgent,
            "research_agent": ResearchAgent,
        }

    def create(self, agent_id: str):
        agent = self.agents.get(agent_id)
        if agent is None:
            return None
        return agent(self.model)

    def get(self, agent_id: str):
        return self.agents.get(agent_id)

    def get_descriptions(self):
        return {
            name: agent.description
            for name, agent in self.agents.items()
        }
