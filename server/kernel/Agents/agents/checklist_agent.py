"""One-call action checklist agent."""

from langchain.agents import create_agent

CHECKLIST_AGENT_DESCRIPTION = """
Turn a goal, requirements, or plan into a short ordered checklist. Include
clear action verbs, dependencies, acceptance criteria, and likely risks when
they are present. Do not create unnecessary steps or invent requirements.
"""


async def run_checklist_agent(model, task: str, context: str = "", callbacks: list | None = None, **kwargs) -> str:
    agent = create_agent(model=model, tools=[])
    prompt = f"""You are the lightweight Checklist Agent.
{CHECKLIST_AGENT_DESCRIPTION}

Task: {task}
Context: {context}

Return a concise numbered checklist. Add a brief acceptance check at the end
when useful.
"""
    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}, config={"callbacks": callbacks} if callbacks else None)
    return result["messages"][-1].content
