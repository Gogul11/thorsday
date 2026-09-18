"""Agent Creator — Autonomous Meta-Agent for AgentOS.

When the planner determines that a user's task cannot be performed by any existing
agent, agent_creator is dispatched. Its responsibility is to:
1. Synthesize the necessary Python tool code and save it to server/kernel/tools/.
2. Synthesize the new agent Python code and save it to server/kernel/Agents/agents/.
3. Permanently register the new agent and tools in agent_registry.py, tool_registry.py,
   and constant.py.
4. Dynamically execute the newly created agent to fulfill the user's prompt immediately.
"""

from langchain.agents import create_agent
from tools.tool_registry import AGENT_CREATOR_TOOLS
from logger import logger

_NAME = "Agent Creator"

AGENT_CREATOR_DESCRIPTION = """
agent_creator is responsible for creating a brand-new specialized agent and its tools
when the user's task CANNOT be performed by any of the other existing agents (a1, a2, a3, a4,
content_creator, email_agent, weather_agent, etc).

Use agent_creator whenever:
- The user requests a specialized domain computation, financial calculation, crypto price lookup,
  custom conversion, or API operation that no other existing agent supports.
- A new dedicated tool and agent must be written, saved to the filesystem, registered in the
  agent registry, and executed to fulfill the request.

agent_creator will:
1. Code the new tool in server/kernel/tools/<name>_tools.py.
2. Code the new agent in server/kernel/Agents/agents/<name>_agent.py.
3. Update agent_registry.py, tool_registry.py, and constant.py so the new agent is permanently saved.
4. Execute the newly created agent on the user's prompt and return the result.
"""


async def run_agent_creator(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    **kwargs,
) -> str:
    """Run the Agent Creator agent to design, save, register, and run a new agent."""
    agent = create_agent(model=model, tools=AGENT_CREATOR_TOOLS)

    prompt = f"""You are {_NAME} of AgentOS.

Your responsibility:
A user's task CANNOT be performed by any of the existing agents. You must autonomously create
a brand-new agent and its tools, register them permanently in the codebase, and execute the new
agent to solve the user's request.

User Task:
{task}

Previous Context:
{context}

CRITICAL STEP-BY-STEP EXECUTION PROCESS:

Step 1: Choose a concise snake_case stem for the new agent (e.g. 'loan_emi', 'crypto_tracker', 'unit_converter').
        Tool file will be `<stem>_tools.py`
        Agent file will be `<stem>_agent.py`
        Tools list variable will be `<STEM_UPPER>_TOOLS`

Step 2: TOOL CREATION & REGISTRATION (Tool must always be created FIRST):
- Write clear, robust, functional Python code for the tool file.
- ONLY generate tools for the NEW/UNHANDLED capability (math formulas, financial calculations, custom APIs).
- DO NOT recreate tools for capabilities that already exist in other agents! Specifically:
  * DO NOT create email sending tools (email_agent handles sending emails via SMTP).
  * DO NOT create local file/folder tools (a4 handles files and documents).
  * DO NOT create Wikipedia/web search tools (a3 handles search).
  * DO NOT create weather tools (weather_agent handles weather).
  The other agents in the execution plan will run next and handle those tasks using your output!
- Write clear, robust, functional Python code.
- First the tool file must be generated and saved to server/kernel/tools/<stem>_tools.py.
- It contains the functions that the new agent will use to perform its task.
- Must import `from langchain_core.tools import tool`.
- Can use standard libraries (`math`, `datetime`, `urllib.request`, `json`, `re`, etc.).
- Decorate tool functions with `@tool` and detailed docstrings explaining arguments..
- Call `save_tool_file(filename="<stem>_tools.py", code=...)`.
  This automatically saves `<stem>_tools.py` AND permanently registers it at Line 1 and the bottom of `tool_registry.py` with full transactional rollback protection!

Step 3: AGENT CREATION & REGISTRATION (Agent created SECOND, using the registered tools):
- Once Step 2 succeeds, call `create_and_register_agent`:
  * agent_stem: "<stem>_agent"
  * display_name: "Readable Name Agent"
  * description: "Comprehensive description of what this agent does"
  * tool_file_stem: "<stem>_tools"
  * tools_var_name: "<STEM_UPPER>_TOOLS"
  * short_summary: "1-line summary for the planner"
- This tool automatically creates `<stem>_agent.py` importing `<STEM_UPPER>_TOOLS` from `tools.tool_registry`, and registers it at Line 2 of `agent_registry.py` and `constant.py`.

Step 4: EXECUTION (Execute the newly created agent):
- Call `run_generated_agent(agent_file_stem="<stem>_agent", run_fn_name="run_<stem>_agent", task="{task}", context="{context}")`.
- Return the exact result produced by the new agent to the user!

---
ANTI-DUPLICATION & ERROR RECOVERY RULES:
- NEVER invent new, alternative file names (e.g. NEVER try <stem>_calc, <stem>_custom, or <stem>_v2 if a tool fails).
- Stick strictly to your chosen stem: `<stem>_tools.py` and `<stem>_agent.py`.
- If any tool returns an error, address the specific issue directly rather than generating new redundant files.
"""

    logger.info("agent_creator starting generation for task: %s", task[:100])

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"callbacks": callbacks} if callbacks else None,
    )

    return result["messages"][-1].content

