from langchain.agents import create_agent
from tools.tool_registry import RESEARCH_TOOLS


class ResearchAgent:
    name = "Research Agent"
    description = """
    Research Agent is responsible for gathering factual, academic, scientific,
    and verified information.

    Use Research Agent when the task requires:
    - Academic, scientific, or technical literature research
    - Finding verified facts, historical records, and encyclopedic data
    - Searching Wikipedia for concepts, biographies, definitions, and overviews
    - Searching trusted academic repositories and peer-reviewed journals
      (e.g., arXiv, Nature, ScienceDirect, IEEE, Springer, NIH, ACM)
    - Fact-checking claims and summarizing verified sources with citations

    Research Agent strictly gathers and reports factual information using its provided
    research tools (Wikipedia Search and Trusted Web Search). It must never
    fabricate information, citations, or URLs.
    """

    def __init__(self, model):
        self.agent = create_agent(
            model=model,
            tools=RESEARCH_TOOLS,
        )

    async def run(self, task: str, context: str = ""):
        prompt = f"""
    You are {self.name}.

    Your responsibility:
    {self.description}

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

        result = await self.agent.ainvoke({
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        })

        return result["messages"][-1].content
