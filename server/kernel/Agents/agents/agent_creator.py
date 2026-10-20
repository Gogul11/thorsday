"""Create and immediately run specialized agents for unsupported tasks."""

from pydantic import BaseModel, Field

from tools.agent_creator_tools import (
    create_and_register_agent,
    rollback_generated_tool,
    run_generated_agent,
    save_tool_file,
)

AGENT_CREATOR_DESCRIPTION = """
Creates a reusable specialized agent and the Python tools it needs when a task
cannot be performed by the existing agents. Validates generated Python syntax,
registers the new tool and agent in their registries, indexes the new capability
for future retrieval, and immediately runs the newly created agent for the task.
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
    """Generate, register, and directly execute an agent for an unsupported task."""
    feedback = "No previous generation attempt."
    generated = None

    for attempt in range(1, _MAX_GENERATION_ATTEMPTS + 1):
        spec_prompt = f"""You are AgentOS Agent Creator. Existing agents cannot perform this task.
Create a reusable domain agent and an efficient, functional tool that performs
the requested computation or operation. Do not create a one-off name based on
specific numbers or entities in this request.

Requirements:
- Return complete Python source for a module in server/kernel/tools/.
- Define each listed tool function with @tool from langchain_core.tools and useful argument docstrings.
- Define the listed tools variable as a list containing every generated tool function.
- Use only imports required by the task; avoid placeholder or unimplemented functions.
- Set agent_stem to a lowercase snake_case reusable name ending in _agent and tool_file_stem to the corresponding name ending in _tools.
- Write a concise but precise description and agent_prompt that make the generated agent handle this domain task correctly.
- The agent will be assembled using the existing AgentOS create_agent structure and the generated tools variable.
- Do not attempt to perform the user's task in this generation step.

The json object must contain every schema field with these exact names:
agent_stem, display_name, description, agent_prompt, tool_file_stem,
tools_var_name, tool_function_names, and tool_code. Do not replace
tool_function_names with `tools`. `tool_code` must contain the complete source
code for the tool module, not a summary or an empty value.

User task:\n{task}

Context:\n{context}

Previous attempt feedback:\n{feedback}

Generation attempt: {attempt} of {_MAX_GENERATION_ATTEMPTS}

Return only a valid json object matching the GeneratedAgentSpec schema. The
response must be json, with no surrounding prose or markdown fences.
"""
        try:
            generated: GeneratedAgentSpec = await model.with_structured_output(
                GeneratedAgentSpec, method="json_mode"
            ).ainvoke(spec_prompt)
        except Exception as exc:
            feedback = (
                "The previous response did not match GeneratedAgentSpec. "
                "Return every required field using its exact name, especially "
                "display_name, tools_var_name, tool_function_names, and complete "
                f"tool_code. Validation error: {exc}"
            )
            continue
        tool_message = str(await save_tool_file.ainvoke(
            {
                "filename": f"{generated.tool_file_stem}.py",
                "code": generated.tool_code,
                "tools_var_name": generated.tools_var_name,
                "function_names": generated.tool_function_names,
            },
            config={"callbacks": callbacks} if callbacks else None,
        ))
        if "SUCCESS:" in tool_message:
            agent_message = str(await create_and_register_agent.ainvoke(
                {
                    "agent_stem": generated.agent_stem,
                    "display_name": generated.display_name,
                    "description": generated.description,
                    "agent_prompt": generated.agent_prompt,
                    "tool_file_stem": generated.tool_file_stem,
                    "tools_var_name": generated.tools_var_name,
                },
                config={"callbacks": callbacks} if callbacks else None,
            ))
            if "SUCCESS:" in agent_message:
                break
            rollback_generated_tool(
                generated.tool_file_stem,
                generated.tools_var_name,
                generated.tool_function_names,
            )
            feedback = agent_message
            continue
        feedback = tool_message
    else:
        return (
            f"Could not create and register an agent after {_MAX_GENERATION_ATTEMPTS} attempts. "
            f"Last error: {feedback}"
        )

    return await run_generated_agent(
        model=model,
        agent_file_stem=generated.agent_stem,
        run_fn_name=f"run_{generated.agent_stem}",
        task=task,
        context=context,
        callbacks=callbacks,
    )
