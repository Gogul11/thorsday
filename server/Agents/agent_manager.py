from Agents.agent_registry import AgentRegistry


class AgentManager:

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.agents = {}

    def create_agent(
        self,
        agent_id: str,
        agent_type: str,
        task_id: str
    ):
        if agent_id in self.agents:
            raise ValueError(
                f"Agent {agent_id} already exists"
            )

        agent = self.registry.create(agent_type)

        if agent is None:
            raise ValueError(
                f"Unknown agent type: {agent_type}"
            )

        runtime = {
            "id": agent_id,
            "type": agent_type,
            "task_id": task_id,
            "agent": agent,
            "status": "CREATED"
        }

        self.agents[agent_id] = runtime

        return runtime

    def set_status(
        self,
        agent_id: str,
        status: str
    ):
        if agent_id not in self.agents:
            raise ValueError(
                f"Unknown agent: {agent_id}"
            )

        self.agents[agent_id]["status"] = status

    def get_agent(self, agent_id: str):

        if agent_id not in self.agents:
            raise ValueError(
                f"Unknown agent: {agent_id}"
            )

        return self.agents[agent_id]["agent"]

    def destroy_agent(self, agent_id: str):

        if agent_id not in self.agents:
            return

        self.set_status(
            agent_id,
            "DESTROYED"
        )

        del self.agents[agent_id]

    def get_agent_descriptions(self):
        return self.registry.get_descriptions()