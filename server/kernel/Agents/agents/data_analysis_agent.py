"""Lightweight structured-data analysis agent."""

from langchain.agents import create_agent

from tools.code_runner_tools import build_run_python_code_tool
from tools.file_document_tools import list_directory, read_document, search_files

DATA_ANALYSIS_AGENT_DESCRIPTION = """
Analyze CSV, JSON, TSV, and tabular text data. Inspect the source first,
calculate only what the user requests, state assumptions, and never invent
missing values. Keep the result concise and evidence-based.
"""


async def run_data_analysis_agent(model, task: str, context: str = "", callbacks: list | None = None, **kwargs) -> str:
    code_tool = build_run_python_code_tool(kwargs.get("req_id", ""), kwargs.get("task_id", ""))
    agent = create_agent(model=model, tools=[search_files, read_document, list_directory, code_tool])
    prompt = f"""You are the lightweight Data Analysis Agent.
{DATA_ANALYSIS_AGENT_DESCRIPTION}

Task: {task}
Context: {context}

Use tools only when the task references data that must be inspected. Do not
modify source data. Return key findings, calculations, and assumptions only.
"""
    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}, config={"callbacks": callbacks} if callbacks else None)
    return result["messages"][-1].content
