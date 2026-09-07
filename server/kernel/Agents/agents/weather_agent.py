"""Agent Weather — Weather and Meteorological Information Agent."""

from langchain.agents import create_agent
from tools.tool_registry import WEATHER_TOOLS

_NAME = "Weather Agent"

WEATHER_AGENT_DESCRIPTION = """
Weather Agent is responsible for fetching, analyzing, and reporting live weather conditions,
forecasts, temperatures, and meteorological data for any city, region, or location worldwide.

Use Weather Agent whenever a task requires:
- Checking the current weather or temperature in a city (e.g., "what's the weather in London?", "how hot is it in Tokyo?")
- Getting multi-day weather forecasts (e.g., "3-day forecast for Paris", "will it rain this weekend in Seattle?")
- Checking humidity, wind speeds, precipitation, or apparent ("feels like") temperatures
- Answering questions about weather conditions, storms, rain, snow, or sunshine

Weather Agent should:
- Extract the target city or location name from the user's prompt or context
- Call `get_current_weather` when current conditions, temperature, or humidity are requested
- Call `get_weather_forecast` when future days or upcoming weather forecasts are requested
- Present the meteorological data clearly and concisely, including temperature in both Celsius and Fahrenheit
"""


async def run_weather_agent(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    **kwargs
) -> str:
    """Run the Weather Agent and return its formatted weather report."""
    agent = create_agent(model=model, tools=WEATHER_TOOLS)

    prompt = f"""You are {_NAME}.

Your responsibility:
{WEATHER_AGENT_DESCRIPTION}

User Task:
{task}

Previous Agent Results:
{context}

Instructions:
1. Identify the city or location mentioned in the task. If no city is mentioned, infer or ask for the location.
2. If the user wants current conditions or temperature, call `get_current_weather(city=...)`.
3. If the user wants a forecast for upcoming days, call `get_weather_forecast(city=..., days=...)`.
4. Return a clear, friendly, and well-structured response summarizing the weather data.
"""

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        },
        config={"callbacks": callbacks} if callbacks else None,
    )

    return result["messages"][-1].content

