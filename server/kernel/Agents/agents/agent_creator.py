"""Create and run agents for substantial tasks needing an unsupported capability."""
from __future__ import annotations

from pydantic import BaseModel, Field

from tools.agent_creator_tools import (
    create_and_register_agent,
    rollback_generated_tool,
    run_generated_agent,
    save_tool_file,
)

AGENT_CREATOR_DESCRIPTION = """
agent_creator builds, validates, registers, and runs agents for meaningful new tasks routed by the planner.

Use agent_creator whenever:
- The planner routes a substantial, actionable request here.
- New agent code and tools must be written, saved, registered, and executed to fulfill the request.

Create an agent for the task's core capability.
"""

_MAX_GENERATION_ATTEMPTS = 3


class GeneratedAgentSpec(BaseModel):
    agent_stem: str = Field(description="Reusable snake_case domain name ending in _agent")
    display_name: str
    description: str = Field(description="Precise reusable capability description for future retrieval")
    agent_prompt: str = Field(description="Precise system prompt that instructs this agent how to perform its domain task")
    tool_file_stem: str = Field(description="snake_case tool module name ending in _tools")
    tools_var_name: str = Field(description="Uppercase tool list name ending in _TOOLS")
    tool_function_names: list[str] = Field(description="Names of all @tool functions in the generated module")
    tool_code: str = Field(description="Complete Python source for the tool module")


async def run_agent_creator(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    **kwargs,
) -> str:
    """Create, register, and execute an agent for a task routed here by the planner."""
    logger.info("agent_creator starting creation for task: %s", task[:100])
    agent = create_agent(model=model, tools=AGENT_CREATOR_TOOLS)

    prompt = f"""You are {_NAME} of AgentOS.

The planner routed this meaningful new task here. Determine its core function, then build and run an agent that performs it.

User Task:
{task}

Previous Context:
{context}

CREATION RULES:
1. Identify the core function needed to complete this meaningful task. Name the agent after that capability, not after the user's exact input values. Keep the implementation useful for related tasks with the same core function.
2. Write Python tools that perform the needed work. Each tool must have clear inputs, validation, useful error handling, and a LangChain @tool docstring.
3. Call save_tool_file(filename='<capability>_tools.py', code=...) to validate and save the tools.
4. Call create_and_register_agent with a matching '<capability>_agent' stem, display name, capability description, tool file stem, tools variable name, and short planner summary. This validates, saves, and registers the new agent.
5. Call run_generated_agent with the new agent's file stem, run function name, the user's task, and the previous context. Return the generated agent's result.
"""

    logger.info("agent_creator creating agent for task: %s", task[:80])

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"callbacks": callbacks} if callbacks else None,
    )
