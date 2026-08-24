from langchain.agents import create_agent
from tools.tool_registry import TIME_TOOLS


class TimeAgent:
    name = "Time Agent"
    description = """
    Time Agent is responsible for handling date, time, and calendar-related queries.

    Use Time Agent when the task requires:
    - Getting the current date and time
    - Checking the current day of the week
    - Answering questions about timestamps, dates, or time differences
    - Providing date and time information for scheduling or context

    Time Agent uses its available time tools whenever accurate or
    current date/time information is required.
    """

    def __init__(self, model):
        self.agent = create_agent(
            model=model,
            tools=TIME_TOOLS,
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
