'Generated Radio Signal Latency Calculator.'

from langchain.agents import create_agent
from tools.tool_registry import RADIO_LATENCY_TOOLS

AGENT_DESCRIPTION = 'Calculates round‑trip radio signal travel time between two celestial bodies given their separation distance in kilometers.'
AGENT_PROMPT = 'You are a specialized agent for determining radio‑signal latency between Earth and Mars (or any two points). First, obtain the closest approach distance in kilometers (you may use external search tools not defined here). Then, invoke the `calculate_round_trip_time` tool with that distance. Return the result formatted as "Round‑trip latency: X minutes Y seconds". If the distance cannot be obtained, respond with an appropriate error message.'


async def run_radio_latency_agent(model, task: str, context: str = "", callbacks=None, **kwargs) -> str:
    """Run the generated specialist and return its answer."""
    agent = create_agent(model=model, tools=RADIO_LATENCY_TOOLS)
    prompt = f"{AGENT_PROMPT}\n\nUser task:\n{task}\n\nRelevant context:\n{context}"
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"callbacks": callbacks} if callbacks else None,
    )
    return result["messages"][-1].content
