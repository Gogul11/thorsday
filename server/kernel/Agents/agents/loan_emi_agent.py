"""Agent Loan EMI Calculator Agent."""

from langchain.agents import create_agent
from tools.tool_registry import LOAN_EMI_TOOLS

_NAME = "Loan EMI Calculator Agent"

LOAN_EMI_AGENT_DESCRIPTION = """
Calculates loan EMI and provides amortization schedule as plain text.
"""


async def run_loan_emi_agent(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    **kwargs,
) -> str:
    """Run Loan EMI Calculator Agent and return its formatted result."""
    agent = create_agent(model=model, tools=LOAN_EMI_TOOLS)

    prompt = f"""You are {_NAME}.

Your responsibility:
{LOAN_EMI_AGENT_DESCRIPTION}

Task:
{task}

Previous Context:
{context}

Perform the task using your available tools and return the final result clearly with clean Markdown formatting.
"""

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"callbacks": callbacks} if callbacks else None,
    )

    return result["messages"][-1].content
