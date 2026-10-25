"""Agent A3 — bounded research agent."""

import asyncio

from pydantic import BaseModel, Field

from tools.research_tools import trusted_web_search, wikipedia_search

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

A3 handles research, source discovery, fact-checking, academic or scientific
evidence, and sourced factual findings. It does not perform calculations,
conversions, code generation, file operations, writing, or other tasks that do
not require research.

Judge the request by its meaning, not by individual keywords. If the requested
work is outside A3's research responsibility, do not attempt to answer it or
call a research tool. State briefly that A3 handles sourced research only.
"""

_NAME = "Agent A3 (Research Agent)"

class ResearchSearchPlan(BaseModel):
    """At most one query for each research source."""

    is_research_task: bool = Field(description="Whether the requested work is research that A3 is responsible for")
    use_wikipedia: bool = Field(description="Whether Wikipedia is useful for this task")
    wikipedia_query: str = Field(default="", description="One focused Wikipedia search query")
    use_trusted_web: bool = Field(description="Whether trusted academic or authoritative web search is useful")
    trusted_web_query: str = Field(default="", description="One focused trusted-web search query")


async def run_agent_a3(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    **kwargs
) -> str:
    """Search each source at most once, then synthesize without a tool loop."""
    call_config = {"callbacks": callbacks} if callbacks else None
    planning_prompt = f"""You are {_NAME}. First decide whether the task, by its
meaning, requires research or sourced factual findings. Do not rely on isolated
keywords. If it is outside A3's responsibility, do not run searches and state
that A3 does not handle it by setting is_research_task=false and both search
flags=false.

Choose whether to run one search against each
available source. Do not create multiple queries or ask to search again.

Wikipedia is useful for established encyclopedic facts and overviews.
Trusted web search is useful for current, academic, scientific, or technical facts.
Set a source's use flag false when it is not useful. Each selected query must be
focused on facts needed for the user's task.

Task:\n{task}

Results from previous agents:\n{context}

Return a valid json object matching the ResearchSearchPlan schema.
"""

    try:
        search_plan: ResearchSearchPlan = await model.with_structured_output(
            ResearchSearchPlan, method="json_mode"
        ).ainvoke(planning_prompt, config=call_config)
    except Exception:
        return "A3 could not prepare a research search for this request."

    if not search_plan.is_research_task:
        # If the planner misroutes an unsupported task to A3, hand it to the
        # creator instead of answering it as a research agent.
        from Agents.agents.agent_creator import run_agent_creator

        return await run_agent_creator(
            model=model,
            task=task,
            context=context,
            callbacks=callbacks,
            **kwargs,
        )

    searches = []
    if search_plan.use_wikipedia and search_plan.wikipedia_query.strip():
        searches.append((
            "Wikipedia",
            wikipedia_search.ainvoke(
                {"query": search_plan.wikipedia_query.strip(), "max_results": 3},
                config=call_config,
            ),
        ))
    if search_plan.use_trusted_web and search_plan.trusted_web_query.strip():
        searches.append((
            "Trusted web",
            trusted_web_search.ainvoke(
                {"query": search_plan.trusted_web_query.strip(), "max_results": 5},
                config=call_config,
            ),
        ))

    search_results = await asyncio.gather(
        *(search for _, search in searches),
        return_exceptions=True,
    )
    sources = []
    for (source_name, _), result in zip(searches, search_results):
        if isinstance(result, Exception):
            sources.append(f"{source_name} search error: {result}")
        else:
            sources.append(f"{source_name} results:\n{result}")

    answer_prompt = f"""You are {_NAME}.

Responsibility:
{AGENT_A3_DESCRIPTION}

User task:
{task}

Results from previous agents:
{context}

Retrieved sources:
{chr(10).join(sources) if sources else 'No search was needed or selected.'}

Answer with only the key facts needed for the task. Keep it concise. Use source
URLs only when they appear in the retrieved results. Do not invent facts,
citations, or URLs. If the searches did not provide enough evidence, say so.
"""
    result = await model.ainvoke(answer_prompt, config=call_config)
    return result.content
