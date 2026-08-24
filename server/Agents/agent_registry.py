from .agents.a1 import AgentA1
from .agents.a2 import AgentA2
from .agents.a3 import AgentA3


class AgentRegistry:

    def __init__(self, model):
        self.model = model

        self.agents = {
            "a1": AgentA1,
            "a2": AgentA2,
            "a3": AgentA3,
        }

    def create(self, agent_id: str):
        agent = self.agents[agent_id]
        return agent(self.model)

    # def destroy(self, agent_id : str):
    #     agent = self.agents[agent_id]
    #     del agent

    def get(self, agent_id: str):
        return self.agents.get(agent_id)

    def get_descriptions(self):
        return {name: agent.description for name, agent in self.agents.items()}
