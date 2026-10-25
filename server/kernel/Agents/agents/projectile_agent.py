'Generated Projectile Calculator Agent.'

from langchain.agents import create_agent
from tools.tool_registry import PROJECTILE_TOOLS

AGENT_DESCRIPTION = 'Agent that computes projectile motion metrics (range, peak height, total flight time) and can save a summary to a file.'
AGENT_PROMPT = 'You are a projectile calculation assistant. Use the provided tools to compute the maximum flight distance, peak height, and total flight time for a projectile given initial velocity, launch angle, and gravity. If a file path is supplied, write the results to that file using the save tool.'


async def run_projectile_agent(model, task: str, context: str = "", callbacks=None, **kwargs) -> str:
    """Run the generated specialist and return its answer."""
    agent = create_agent(model=model, tools=PROJECTILE_TOOLS)
    prompt = f"{AGENT_PROMPT}\n\nUser task:\n{task}\n\nRelevant context:\n{context}"
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"callbacks": callbacks} if callbacks else None,
    )
    return result["messages"][-1].content
