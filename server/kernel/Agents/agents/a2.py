"""Agent A2 — date and time agent."""

from langchain.agents import create_agent

from tools.tool_registry import A2_TOOLS

AGENT_A2_DESCRIPTION = """
A2 is responsible for handling date and time related queries.

Use A2 when the task requires:
- Getting the current date
- Getting the current time
- Getting the current date and time
- Determining the day of the week
- Answering questions about dates or times
- Providing date and time information for a specified location or timezone

A2 should use its available date and time tools whenever
accurate or current date/time information is required.
"""

_NAME = "Agent A2"


async def run_agent_a2(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
) -> str:
    """Run the A2 date/time agent and return its text result."""
    agent = create_agent(model=model, tools=A2_TOOLS)

    prompt = f"""
You are {_NAME}.

Your responsibility:
{AGENT_A2_DESCRIPTION}

Task:
{task}

Results from previous agents:
{context}

Perform the task using your available tools when necessary.
Return the final result clearly.
"""

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"callbacks": callbacks} if callbacks else None,
    )

    return result["messages"][-1].content
