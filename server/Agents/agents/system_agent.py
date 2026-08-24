from langchain.agents import create_agent
from tools.tool_registry import SYSTEM_TOOLS


class SystemAgent:
    name = "System Agent"
    description = """
    System Agent is responsible for inspecting the system environment,
    machine configuration, and operating system state.

    Use System Agent when the task requires:
    - Gathering information about the host operating system
    - Checking machine hardware, processor, and architecture
    - Inspecting system configuration and environment details
    - Analyzing system-level status and reporting specs clearly

    System Agent uses its available system information tools whenever
    host/system details are required.
    """

    def __init__(self, model):
        self.agent = create_agent(
            model=model,
            tools=SYSTEM_TOOLS,
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
                    "content": prompt,
                }
            ]
        })

        return result["messages"][-1].content
