from langchain.agents import create_agent

from tools.tool_registry import A3_TOOLS


class AgentA3:

    name = "Agent A3"

    description = """

    A3 is responsible for managing files and documents
    on the user's system.

    A3 should:

    - List files and directories
    - Search for files
    - Read text files
    - Get file and directory information
    - Create files
    - Write and modify text files
    - Append content to files
    - Create directories
    - Rename files and directories
    - Move files and directories
    - Delete files or empty directories
    - Report file operations clearly

    A3 should use its available file tools whenever
    information about files or filesystem operations
    is required.

    A3 should not perform destructive operations unless
    the user's request clearly asks for them.

    """

    def __init__(self, model):

        self.agent = create_agent(
            model=model,
            tools=A3_TOOLS
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

        Perform the task using your available tools
        when necessary.

        Return the final result clearly.

        """

        result = await self.agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
        )

        return result["messages"][-1].content