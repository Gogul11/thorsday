from langchain.agents import create_agent

from tools.tool_registry import A1_TOOLS


class AgentA1:

    def __init__(self, model):

        self.name = "Agent A1"

        self.description = """
        A1 is responsible for gathering information about the system
        and analyzing the current system state.

        A1 should:
        - Gather information about the system
        - Inspect system resources and configuration
        - Check running processes and services
        - Check system status and environment
        - Retrieve hardware and software information
        - Analyze system-level information
        - Report relevant system information clearly

        A1 should use its available system tools whenever
        additional information about the system is required.
        """

        self.agent = create_agent(
            model=model,
            tools=A1_TOOLS
        )

    async def run(self, task: str, context: str = ""):
    
        prompt = f"""
    You are {self.name}.
    
    Your responsibility:
    {self.description}
    
    Task:
    {task}
    
    Results from previous agents:
    {context}
    
    Perform the task using your available tools when necessary.
    Return the final result clearly.
    """
    
        result = await self.agent.ainvoke({
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        })
    
        return result["messages"][-1].content