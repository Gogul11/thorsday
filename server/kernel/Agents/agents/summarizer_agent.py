"""One-call concise summarization agent."""

from langchain.agents import create_agent

SUMMARIZER_AGENT_DESCRIPTION = """
Summarize supplied text, conversations, documents, or agent results. Preserve
important facts, decisions, dates, risks, and action items. Do not add facts
that are absent from the supplied material.
"""


async def run_summarizer_agent(model, task: str, context: str = "", callbacks: list | None = None, **kwargs) -> str:
    agent = create_agent(model=model, tools=[])
    prompt = f"""You are the lightweight Summarizer Agent.
{SUMMARIZER_AGENT_DESCRIPTION}

User request: {task}
Material to summarize: {context}

Return a concise summary using bullets only when they improve readability.
"""
    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}, config={"callbacks": callbacks} if callbacks else None)
    return result["messages"][-1].content
