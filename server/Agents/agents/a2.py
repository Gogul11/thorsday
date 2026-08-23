from langchain.agents import create_agent
from tools.tool_registry import A2_TOOLS


class AgentA2:

    def __init__(self, model):

        self.name = "Agent A2"

        self.description = """
        A2 is responsible for handling date and time related queries.

        Use A2 when the task requires:

        - Getting the current date
        - Getting the current time
        - Getting the current date and time
        - Determining the day of the week
        - Answering questions about dates or times
        - Providing date and time information for a specified location
          or timezone

        A2 should use its available date and time tools whenever
        accurate or current date/time information is required.
        """

        self.agent = create_agent(
            model=model,
            tools=A2_TOOLS
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