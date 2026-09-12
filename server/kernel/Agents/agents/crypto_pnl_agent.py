"""Agent Crypto PnL Agent."""

from langchain.agents import create_agent
from tools.tool_registry import CRYPTO_PNL_TOOLS

_NAME = "Crypto PnL Agent"

CRYPTO_PNL_AGENT_DESCRIPTION = """
An agent that calculates net profit and ROI for cryptocurrency trades, formats an investment report, and saves it to a specified file path.
"""


async def run_crypto_pnl_agent(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    **kwargs,
) -> str:
    """Run Crypto PnL Agent and return its formatted result."""
    agent = create_agent(model=model, tools=CRYPTO_PNL_TOOLS)

    prompt = f"""You are {_NAME}.

Your responsibility:
{CRYPTO_PNL_AGENT_DESCRIPTION}

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
