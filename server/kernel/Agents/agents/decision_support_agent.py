"""Lightweight evidence-synthesis and recommendation agent."""

from langchain.agents import create_agent

DECISION_SUPPORT_AGENT_DESCRIPTION = """
Compare options, summarize prior findings, weigh trade-offs, prioritize work,
and produce practical recommendations from the supplied evidence. Separate
facts from assumptions and clearly state uncertainty. Do not invent evidence.
"""


async def run_decision_support_agent(model, task: str, context: str = "", callbacks: list | None = None, **kwargs) -> str:
    agent = create_agent(model=model, tools=[])
    prompt = f"""You are the lightweight Decision Support Agent.
{DECISION_SUPPORT_AGENT_DESCRIPTION}

Task: {task}
Evidence and prior results: {context}

Make the recommendation first, then give only the most important reasons,
trade-offs, assumptions, and next action.
"""
    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}, config={"callbacks": callbacks} if callbacks else None)
    return result["messages"][-1].content
