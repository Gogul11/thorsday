"""Software engineering agent for repository-level implementation work."""

from langchain.agents import create_agent
from tools.file_document_tools import create_text_file, get_file_metadata, list_directory, read_document, search_files, replace_in_file
from tools.tool_registry import CODE_RUNNER_TOOLS

SOFTWARE_ENGINEERING_AGENT_DESCRIPTION = """
The Software Engineering Agent helps inspect and improve software projects.
Use it for repository exploration, implementation planning, bug fixes,
refactoring, writing or updating source files, and running focused Python
checks. It must inspect relevant files before editing, preserve unrelated
content, and report exactly what was verified. It should not claim a test or
change succeeded unless a tool confirms it.
"""

_TOOLS = [search_files, read_document, get_file_metadata, list_directory, create_text_file, replace_in_file, *CODE_RUNNER_TOOLS]

async def run_software_engineering_agent(model, task: str, context: str = "", callbacks: list | None = None, **kwargs) -> str:
    agent = create_agent(model=model, tools=_TOOLS)
    prompt = f"""You are the AgentOS Software Engineering Agent.
Responsibilities:
{SOFTWARE_ENGINEERING_AGENT_DESCRIPTION}
User task:
{task}
Context:
{context}
Use tools to inspect the project and make the requested change when the task asks for implementation. Keep changes focused. If the task is diagnostic, do not edit files. Finish with a concise summary of findings, changes, and verification results.
"""
    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}, config={"callbacks": callbacks} if callbacks else None)
    return result["messages"][-1].content
