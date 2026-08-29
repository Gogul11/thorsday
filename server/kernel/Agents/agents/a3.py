"""Agent A3 — research agent."""

from langchain.agents import create_agent

from tools.tool_registry import A3_TOOLS

AGENT_A3_DESCRIPTION = """
A3 is a specialized Research Agent responsible for gathering factual,
academic, scientific, and verified information.

Use A3 when the task requires:
- Academic, scientific, or technical literature research
- Finding verified facts, historical records, and encyclopedic data
- Searching Wikipedia for concepts, biographies, definitions, and overviews
- Searching trusted academic repositories and peer-reviewed journals
  (e.g., arXiv, Nature, ScienceDirect, IEEE, Springer, NIH, ACM)
- Fact-checking claims and summarizing verified sources with citations

A3 should strictly gather and report factual information using its provided
research tools (Wikipedia Search and Trusted Web Search). It must never
fabricate information, citations, or URLs.
"""

_NAME = "Agent A3 (Research Agent)"


async def run_agent_a3(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
) -> str:
    """Run the A3 research agent and return its text result."""
    agent = create_agent(model=model, tools=A3_TOOLS)

    prompt = f"""
You are {_NAME}.

Your responsibility:
{AGENT_A3_DESCRIPTION}

Task:
{task}

Results from previous agents:
{context}

Instructions:
1. Perform in-depth research using your available research tools (Wikipedia Search and Trusted Web Search).
2. Synthesize factual, high-quality, and objective findings based on retrieved data.
3. Include source references, paper titles, and URLs where available.
4. Return the final research result clearly and concisely.
"""

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"callbacks": callbacks} if callbacks else None,
    )

    return result["messages"][-1].content
