"""Tools for the Agent Creator Agent.

Equips the agent_creator with tools to:
1. Save tool files into server/kernel/tools/, validate syntax, and immediately register them
   at the top (line 1) and bottom of server/kernel/tools/tool_registry.py with full rollback protection.
2. Create standard AgentOS agent files into server/kernel/Agents/agents/ importing the tools from
   tools.tool_registry, and register them at line 2 of agent_registry.py and constant.py with full rollback protection.
3. Dynamically load and execute the new agent on the user's task.
"""

import ast
import importlib
import sys
from pathlib import Path
from langchain_core.tools import tool
from logger import logger

KERNEL_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = KERNEL_DIR / "tools"
AGENTS_DIR = KERNEL_DIR / "Agents" / "agents"
AGENT_REGISTRY_FILE = KERNEL_DIR / "Agents" / "agent_registry.py"
TOOL_REGISTRY_FILE = KERNEL_DIR / "tools" / "tool_registry.py"
CONSTANT_FILE = KERNEL_DIR / "graphs" / "constant.py"


def _extract_tool_functions(tool_file_path: Path) -> list[str]:
    """Parse tool file with AST and return names of all tool functions defined."""
    if not tool_file_path.exists():
        return []
    try:
        with open(tool_file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        tools = []
        # 1. Functions decorated with @tool
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    name = getattr(dec, "id", getattr(dec, "attr", None))
                    if isinstance(dec, ast.Call):
                        name = getattr(dec.func, "id", getattr(dec.func, "attr", None))
                    if name == "tool":
                        tools.append(node.name)
                        break
        if tools:
            return tools

        # 2. Check if a tools list was assigned at module level (e.g. <NAME>_TOOLS = [...])
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Name):
                        tools.append(elt.id)
                if tools:
                    return tools

        # 3. Fallback: all top-level functions not starting with underscore
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                tools.append(node.name)
        return tools
    except Exception as exc:
        logger.warning("AST parse failed for %s: %s", tool_file_path, exc)
        return []


def _extract_tools_var_name(tool_file_path: Path, stem: str) -> str:
    """Find existing <NAME>_TOOLS variable in tool file, or generate standard one."""
    try:
        with open(tool_file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.endswith("_TOOLS"):
                        return target.id
    except Exception:
        pass
    clean_stem = stem[:-6] if stem.endswith("_tools") else stem
    return f"{clean_stem.upper()}_TOOLS"


def _register_tool_in_registry(tool_file_stem: str, tools_var_name: str = "") -> tuple[bool, str]:
    """Register tool import at top (line 1) and tools array at bottom of tool_registry.py
    with automatic transactional rollback on failure.
    """
    if tool_file_stem.endswith(".py"):
        tool_file_stem = tool_file_stem[:-3]

    # Normalize tool_file_stem to match the actual file on disk
    if (TOOLS_DIR / f"{tool_file_stem}.py").exists():
        stem = tool_file_stem
    elif (TOOLS_DIR / f"{tool_file_stem}_tools.py").exists():
        stem = f"{tool_file_stem}_tools"
    elif tool_file_stem.endswith("_tools") and (TOOLS_DIR / f"{tool_file_stem[:-6]}.py").exists():
        stem = tool_file_stem[:-6]
    else:
        return False, f"Tool file '{tool_file_stem}.py' does not exist in {TOOLS_DIR}"

    tool_path = TOOLS_DIR / f"{stem}.py"
    extracted_tools = _extract_tool_functions(tool_path)
    if not extracted_tools:
        return False, f"No tool functions found in {stem}.py"

    if not tools_var_name:
        tools_var_name = _extract_tools_var_name(tool_path, stem)

    # In-memory snapshot for rollback
    try:
        with open(TOOL_REGISTRY_FILE, "r", encoding="utf-8") as f:
            original_content = f.read()
    except Exception as e:
        return False, f"Cannot read tool_registry.py: {e}"

    import_names = ", ".join(extracted_tools)
    import_line = f"from tools.{stem} import {import_names}\n"
    funcs_block = ",\n    ".join(extracted_tools)
    def_block = f"\n\n{tools_var_name} = [\n    {funcs_block},\n]\n"

    new_content = original_content

    # Line 1: Tool import at the top of tool_registry.py
    if import_line.strip() not in new_content:
        new_content = import_line + new_content

    # Bottom: Tools array definition at the bottom of tool_registry.py
    if f"{tools_var_name} =" not in new_content:
        new_content = new_content.rstrip() + def_block

    # AST validation before writing to disk
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        return False, f"Syntax error generating tool_registry.py: {e}"

    # Write to disk
    try:
        with open(TOOL_REGISTRY_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        return False, f"Failed to write tool_registry.py: {e}"

    # Verify reload in memory with rollback protection
    try:
        if f"tools.{stem}" in sys.modules:
            importlib.reload(sys.modules[f"tools.{stem}"])
        else:
            importlib.import_module(f"tools.{stem}")

        if "tools.tool_registry" in sys.modules:
            importlib.reload(sys.modules["tools.tool_registry"])
        else:
            importlib.import_module("tools.tool_registry")

        tr = sys.modules["tools.tool_registry"]
        if not hasattr(tr, tools_var_name):
            raise AttributeError(f"tools.tool_registry does not export '{tools_var_name}'")

        logger.info("Permanently imported and defined %s in tool_registry.py", tools_var_name)
        return True, f"Successfully registered {tools_var_name} in tool_registry.py"
    except Exception as exc:
        logger.error("Failed to reload tool_registry.py after adding %s: %s. Rolling back!", tools_var_name, exc)
        # ROLLBACK
        try:
            with open(TOOL_REGISTRY_FILE, "w", encoding="utf-8") as f:
                f.write(original_content)
            if "tools.tool_registry" in sys.modules:
                importlib.reload(sys.modules["tools.tool_registry"])
        except Exception:
            pass
        return False, f"Failed to import/reload tool_registry.py: {exc}. All changes to tool_registry.py have been rolled back."


def _save_tool_file_core(filename: str, code: str, tools_var_name: str = "") -> str:
    """Core logic to save tool file and register it in tool_registry.py."""
    if not filename.endswith(".py"):
        filename += ".py"

    # Syntax validation with AST
    try:
        ast.parse(code)
    except SyntaxError as e:
        logger.error("Syntax error in generated tool code %s: %s", filename, e)
        return f"ERROR: Syntax error on line {e.lineno}: {e.msg}. Please fix the tool code."

    target_path = TOOLS_DIR / filename
    stem = filename[:-3]

    # Snapshot existing tool file if it already existed (for deduplication / safe update)
    existing_tool_backup = None
    if target_path.exists():
        try:
            existing_tool_backup = target_path.read_text(encoding="utf-8")
        except Exception:
            pass

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(code)
        logger.info("Saved tool file to %s", target_path)
    except Exception as e:
        logger.error("Failed to write tool file %s: %s", target_path, e)
        return f"ERROR: Could not save tool file: {e}"

    # Step 1b: Register the new tool in tool_registry.py immediately
    success, msg = _register_tool_in_registry(stem, tools_var_name)
    if not success:
        # Rollback the tool file
        if existing_tool_backup is not None:
            target_path.write_text(existing_tool_backup, encoding="utf-8")
        else:
            target_path.unlink(missing_ok=True)
        return f"ERROR: Saved tool file but failed to register in tool_registry.py: {msg}"

    derived_var = tools_var_name or _extract_tools_var_name(target_path, stem)
    return (
        f"SUCCESS: Tool file '{filename}' created and '{derived_var}' successfully imported at line 1 "
        f"and defined at the bottom of tool_registry.py!\n"
        f"Next, call create_and_register_agent with tool_file_stem='{stem}' and tools_var_name='{derived_var}'."
    )


@tool
def save_tool_file(filename: str, code: str, tools_var_name: str = "") -> str:
    """Validate syntax and write a new Python tool file into server/kernel/tools/,
    then immediately import it at the top (line 1) and define its tools array at the bottom
    of server/kernel/tools/tool_registry.py with full rollback protection.
    
    Parameters:
    - filename: File name, e.g. "loan_calculator_tools.py".
    - code: Full Python source code for the tool file. Must contain @tool definitions.
    - tools_var_name: Optional uppercase variable name for the tools array (e.g. "LOAN_CALCULATOR_TOOLS").
    """
    return _save_tool_file_core(filename, code, tools_var_name)


def _create_and_register_agent_core(
    agent_stem: str,
    display_name: str,
    description: str,
    tool_file_stem: str,
    tools_var_name: str,
    short_summary: str,
) -> str:
    """Core logic to generate agent file and register it in agent_registry.py and constant.py."""
    if agent_stem.endswith(".py"):
        agent_stem = agent_stem[:-3]
    if tool_file_stem.endswith(".py"):
        tool_file_stem = tool_file_stem[:-3]

    # Normalize tool_file_stem
    if (TOOLS_DIR / f"{tool_file_stem}.py").exists():
        tool_stem = tool_file_stem
    elif (TOOLS_DIR / f"{tool_file_stem}_tools.py").exists():
        tool_stem = f"{tool_file_stem}_tools"
    elif tool_file_stem.endswith("_tools") and (TOOLS_DIR / f"{tool_file_stem[:-6]}.py").exists():
        tool_stem = tool_file_stem[:-6]
    else:
        return (
            f"ERROR: Tool file for stem '{tool_file_stem}' does not exist on disk. "
            f"First call save_tool_file to create the tool file and register it in tool_registry.py."
        )

    # Ensure the tool is registered and available in tool_registry.py
    try:
        import tools.tool_registry as tr
        importlib.reload(tr)
        if not hasattr(tr, tools_var_name):
            ok, rmsg = _register_tool_in_registry(tool_stem, tools_var_name)
            if not ok:
                return f"ERROR: Tool '{tools_var_name}' is not available in tool_registry: {rmsg}"
    except Exception as e:
        return f"ERROR: Could not verify tool in tool_registry: {e}"

    run_fn_name = f"run_{agent_stem}"
    desc_var_name = f"{agent_stem.upper()}_DESCRIPTION"

    # Build standard agent code importing tools from tools.tool_registry
    agent_code = f'''"""Agent {display_name}."""

from langchain.agents import create_agent
from tools.tool_registry import {tools_var_name}

_NAME = "{display_name}"

{desc_var_name} = """
{description.strip()}
"""


async def {run_fn_name}(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    **kwargs,
) -> str:
    """Run {display_name} and return its formatted result."""
    agent = create_agent(model=model, tools={tools_var_name})

    prompt = f"""You are {{_NAME}}.

Your responsibility:
{{{desc_var_name}}}

Task:
{{task}}

Previous Context:
{{context}}

Perform the task using your available tools and return the final result clearly with clean Markdown formatting.
"""

    result = await agent.ainvoke(
        {{"messages": [{{"role": "user", "content": prompt}}]}},
        config={{"callbacks": callbacks}} if callbacks else None,
    )

    return result["messages"][-1].content
'''

    # Validate AST of generated agent code
    try:
        ast.parse(agent_code)
    except SyntaxError as e:
        logger.error("Syntax error in generated agent template: %s", e)
        return f"ERROR: Syntax error in agent template: {e}"

    # Snapshots for agent registration rollback
    try:
        with open(AGENT_REGISTRY_FILE, "r", encoding="utf-8") as f:
            original_agent_reg = f.read()
    except Exception as e:
        return f"ERROR: Cannot read agent_registry.py: {e}"

    try:
        with open(CONSTANT_FILE, "r", encoding="utf-8") as f:
            original_constant = f.read()
    except Exception as e:
        return f"ERROR: Cannot read constant.py: {e}"

    target_agent_path = AGENTS_DIR / f"{agent_stem}.py"
    existing_agent_backup = None
    if target_agent_path.exists():
        try:
            existing_agent_backup = target_agent_path.read_text(encoding="utf-8")
        except Exception:
            pass

    # Save agent file to disk
    try:
        with open(target_agent_path, "w", encoding="utf-8") as f:
            f.write(agent_code)
        logger.info("Saved agent file to %s", target_agent_path)
    except Exception as e:
        logger.error("Failed to write agent file %s: %s", target_agent_path, e)
        return f"ERROR: Could not save agent file: {e}"

    # Update agent_registry.py and constant.py with transactional rollback
    try:
        agent_import = f"from Agents.agents.{agent_stem} import {run_fn_name}, {desc_var_name}\n"
        new_agent_reg = original_agent_reg

        if agent_import.strip() not in new_agent_reg:
            # Add new agent import at the 2nd line of agent_registry.py
            lines = new_agent_reg.splitlines(keepends=True)
            if len(lines) >= 1:
                lines.insert(1, agent_import)
            else:
                lines.append(agent_import)
            new_agent_reg = "".join(lines)

        registry_entry = f'    "{agent_stem}": {{"run": {run_fn_name}, "description": {desc_var_name}}},\n'
        if f'"{agent_stem}"' not in new_agent_reg:
            marker = "_REGISTRY: dict[str, dict] = {"
            if marker in new_agent_reg:
                parts = new_agent_reg.split(marker, 1)
                new_agent_reg = parts[0] + marker + "\n" + registry_entry + parts[1]

        ast.parse(new_agent_reg)

        with open(AGENT_REGISTRY_FILE, "w", encoding="utf-8") as f:
            f.write(new_agent_reg)
        logger.info("Permanently registered %s at line 2 in agent_registry.py", agent_stem)

        # Update constant.py (planner prompt rules)
        new_constant = original_constant
        rule_entry = f"    - {agent_stem} = {short_summary}\n"
        if agent_stem not in new_constant:
            marker = "Agent selection rules:"
            if marker in new_constant:
                parts = new_constant.split(marker, 1)
                new_constant = parts[0] + marker + "\n" + rule_entry + parts[1]
                ast.parse(new_constant)
                with open(CONSTANT_FILE, "w", encoding="utf-8") as f:
                    f.write(new_constant)
                logger.info("Added %s to planner prompt rules in constant.py", agent_stem)

        # Live in-memory registration
        mod = importlib.import_module(f"Agents.agents.{agent_stem}")
        mod = importlib.reload(mod)
        fn = getattr(mod, run_fn_name)
        d = getattr(mod, desc_var_name)
        from Agents.agent_registry import register_agent
        register_agent(agent_stem, fn, d)
        logger.info("In-memory dynamic registration successful for %s", agent_stem)

    except Exception as exc:
        logger.error("Failed to register agent %s: %s. Rolling back all changes!", agent_stem, exc)
        # ROLLBACK
        try:
            with open(AGENT_REGISTRY_FILE, "w", encoding="utf-8") as f:
                f.write(original_agent_reg)
        except Exception:
            pass
        try:
            with open(CONSTANT_FILE, "w", encoding="utf-8") as f:
                f.write(original_constant)
        except Exception:
            pass
        if existing_agent_backup is not None:
            target_agent_path.write_text(existing_agent_backup, encoding="utf-8")
        else:
            target_agent_path.unlink(missing_ok=True)
        return f"ERROR: Failed during agent registration: {exc}. All agent files and registries were rolled back."

    return (
        f"SUCCESS: Agent '{agent_stem}' created, configured with '{tools_var_name}', and registered at line 2 of agent_registry.py!\n"
        f"Next, call run_generated_agent(agent_file_stem='{agent_stem}', run_fn_name='{run_fn_name}', task=...)"
    )


@tool
def create_and_register_agent(
    agent_stem: str,
    display_name: str,
    description: str,
    tool_file_stem: str,
    tools_var_name: str,
    short_summary: str,
) -> str:
    """Generate, save, and permanently register the new agent in the codebase.
    
    The agent file will be created in server/kernel/Agents/agents/<agent_stem>.py importing
    its tools from tools.tool_registry, and permanently registered at line 2 of agent_registry.py
    and in constant.py with full rollback protection.
    
    Parameters:
    - agent_stem: e.g. "loan_emi_agent" or "unit_converter_agent".
    - display_name: e.g. "Loan EMI Agent".
    - description: Comprehensive description of the agent's responsibilities.
    - tool_file_stem: Name of the tool file without .py, e.g. "loan_emi_tools".
    - tools_var_name: Name of the exported tools list, e.g. "LOAN_EMI_TOOLS".
    - short_summary: 1-line description of capabilities for the planner rules.
    """
    return _create_and_register_agent_core(
        agent_stem=agent_stem,
        display_name=display_name,
        description=description,
        tool_file_stem=tool_file_stem,
        tools_var_name=tools_var_name,
        short_summary=short_summary,
    )


@tool
async def run_generated_agent(agent_file_stem: str, run_fn_name: str, task: str, context: str = "") -> str:
    """Execute the newly created agent to solve the user's task immediately.
    
    Parameters:
    - agent_file_stem: Filename without .py, e.g. "loan_calculator_agent".
    - run_fn_name: e.g. "run_loan_calculator_agent".
    - task: The user's task prompt.
    - context: Any previous context or background info.
    """
    try:
        if "tools.tool_registry" in sys.modules:
            importlib.reload(sys.modules["tools.tool_registry"])
        mod = importlib.import_module(f"Agents.agents.{agent_file_stem}")
        mod = importlib.reload(mod)
        run_fn = getattr(mod, run_fn_name)
        from models.model import get_model
        model = get_model()
        result = await run_fn(model=model, task=task, context=context)
        return str(result)
    except Exception as e:
        logger.exception("Failed to run newly created agent %s: %s", agent_file_stem, e)
        return f"ERROR running generated agent: {e}"


# Backwards compatibility wrappers
def _register_new_agent_core(
    agent_type: str,
    agent_file_stem: str,
    tool_file_stem: str,
    run_fn_name: str,
    desc_var_name: str,
    tools_var_name: str,
    short_summary: str,
) -> str:
    ok, msg = _register_tool_in_registry(tool_file_stem, tools_var_name)
    if not ok:
        return f"ERROR: {msg}"
    return create_and_register_agent(
        agent_stem=agent_file_stem,
        display_name=agent_type.replace("_", " ").title(),
        description="Autonomous Agent",
        tool_file_stem=tool_file_stem,
        tools_var_name=tools_var_name,
        short_summary=short_summary,
    )


@tool
def register_new_agent(
    agent_type: str,
    agent_file_stem: str,
    tool_file_stem: str,
    run_fn_name: str,
    desc_var_name: str,
    tools_var_name: str,
    short_summary: str,
) -> str:
    """Register the new agent in the registries."""
    return _register_new_agent_core(
        agent_type=agent_type,
        agent_file_stem=agent_file_stem,
        tool_file_stem=tool_file_stem,
        run_fn_name=run_fn_name,
        desc_var_name=desc_var_name,
        tools_var_name=tools_var_name,
        short_summary=short_summary,
    )


@tool
def save_agent_file(filename: str, code: str) -> str:
    """Save raw agent code directly to Agents/agents/."""
    if not filename.endswith(".py"):
        filename += ".py"
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"ERROR: Syntax error: {e}"
    target = AGENTS_DIR / filename
    target.write_text(code, encoding="utf-8")
    return f"SUCCESS: Saved {filename}"
