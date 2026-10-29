"""One-call translation and tone-preserving rewriting agent."""

from langchain.agents import create_agent

TRANSLATOR_AGENT_DESCRIPTION = """
Translate text between languages or rewrite it for the requested audience and
tone. Preserve meaning, names, numbers, formatting, and placeholders. Ask for
clarification only when the target language or requested transformation is
ambiguous; otherwise return the transformed text directly.
"""


async def run_translator_agent(model, task: str, context: str = "", callbacks: list | None = None, **kwargs) -> str:
    agent = create_agent(model=model, tools=[])
    prompt = f"""You are the lightweight Translator Agent.
{TRANSLATOR_AGENT_DESCRIPTION}

Task: {task}
Text and context: {context}

Return only the requested translation or rewrite, with no commentary unless
the user explicitly asks for explanation.
"""
    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}, config={"callbacks": callbacks} if callbacks else None)
    return result["messages"][-1].content
