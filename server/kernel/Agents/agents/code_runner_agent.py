"""Coder and Tester Agent with a bounded self-healing loop."""

import json

from pydantic import BaseModel, Field

from tools.code_runner_tools import build_run_python_code_tool

CODE_RUNNER_AGENT_DESCRIPTION = """
The Coder & Tester Agent writes and tests standalone Python programs in a
constrained sandbox. It reads stdout and stderr and repairs failures up to
three attempts. It must never claim success unless exit_code is zero.
"""

MAX_ATTEMPTS = 3


class CodeProposal(BaseModel):
    code: str = Field(description="Complete standalone Python code to execute")
    intent: str = Field(description="Short description of what the code tests")


async def run_code_runner_agent(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    req_id: str = "",
    task_id: str = "",
    **kwargs,
) -> str:
    """Generate, execute, and repair Python code up to three times."""
    tool = build_run_python_code_tool(req_id=req_id, task_id=task_id)
    proposal_model = model.with_structured_output(CodeProposal)
    feedback = "No previous attempt."

    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = f"""
You are the AgentOS Coder & Tester Agent.

Responsibilities:
{CODE_RUNNER_AGENT_DESCRIPTION}

User task:
{task}

Relevant context:
{context}

Previous execution feedback:
{feedback}

Return a complete standalone Python script. Use only the standard library,
print useful results, do not access secrets or parent directories, and repair
the previous traceback when this is a retry.
"""
        proposal = await proposal_model.ainvoke(prompt)
        result = json.loads(
            await tool.ainvoke({"code": proposal.code, "attempt": attempt})
        )

        if result.get("exit_code") == 0:
            return (
                f"Code execution succeeded on attempt {attempt}.\n\n"
                f"Intent: {proposal.intent}\n"
                f"Duration: {result.get('duration_ms', 0)} ms\n\n"
                f"stdout:\n{result.get('stdout') or '(empty)'}"
            )

        feedback = (
            f"Attempt {attempt} failed with exit code {result.get('exit_code')}.\n"
            f"stdout:\n{result.get('stdout', '')[-8000:]}\n"
            f"stderr:\n{result.get('stderr', '')[-8000:]}"
        )

    return (
        f"Code execution failed after {MAX_ATTEMPTS} attempts.\n\n"
        f"{feedback}"
    )
