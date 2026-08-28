"""Agent A1 — system information agent."""

from langchain.agents import create_agent

from tools.tool_registry import A1_TOOLS

AGENT_A1_DESCRIPTION = """
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

_NAME = "Agent A1"


async def run_agent_a1(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
) -> str:
    """Run the A1 system-info agent and return its text result."""
    agent = create_agent(model=model, tools=A1_TOOLS)

    prompt = f"""
You are {_NAME}.

Your responsibility:
{AGENT_A1_DESCRIPTION}

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
