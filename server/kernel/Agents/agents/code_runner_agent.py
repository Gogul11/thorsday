"""Coder and Tester Agent with a bounded self-healing loop."""

import json

from tools.code_runner_tools import build_run_python_code_tool

CODE_RUNNER_AGENT_DESCRIPTION = """
The Coder & Tester Agent writes and tests standalone Python programs in a
constrained sandbox. It reads stdout and stderr and repairs failures up to
three attempts. It must never claim success unless exit_code is zero.
"""

MAX_ATTEMPTS = 3


def _extract_code(content: object) -> str:
    """Extract Python from a plain model response without tool calling."""
    if isinstance(content, list):
        content = "\n".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        )
    text = str(content).strip()
    if "```" in text:
        blocks = text.split("```")
        if len(blocks) >= 3:
            code = blocks[1]
            if code.lstrip().startswith("python"):
                code = code.lstrip()[6:]
            return code.strip()
    return text


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

Return only a complete standalone Python script, preferably inside a ```python
code fence. Use only the standard library,
print useful results, do not access secrets or parent directories, and repair
the previous traceback when this is a retry.
"""
        # Deliberately use a plain model call here. Some Groq models can emit
        # an unrelated tool call while a structured-output schema is selected.
        response = await model.ainvoke(prompt)
        code = _extract_code(response.content)
        result = json.loads(
            await tool.ainvoke({"code": code, "attempt": attempt})
        )

        if result.get("exit_code") == 0:
            return (
                f"Code execution succeeded on attempt {attempt}.\n\n"
                f"Generated and tested Python code.\n"
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
