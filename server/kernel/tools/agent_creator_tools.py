"""Transactional file and registry operations for Agent Creator."""

from __future__ import annotations

import ast
import importlib
import re
import sys
from pathlib import Path

from langchain_core.tools import tool

KERNEL_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = KERNEL_DIR / "tools"
AGENTS_DIR = KERNEL_DIR / "Agents" / "agents"
TOOL_REGISTRY_FILE = KERNEL_DIR / "tools" / "tool_registry.py"
AGENT_REGISTRY_FILE = KERNEL_DIR / "Agents" / "agent_registry.py"


def _parse_source(source: str, label: str) -> str | None:
    try:
        ast.parse(source, filename=label)
    except SyntaxError as exc:
        return f"Syntax error in {label}, line {exc.lineno}: {exc.msg}"
    return None


def _extract_tool_names(source: str) -> list[str]:
    tree = ast.parse(source)
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            (isinstance(dec, ast.Name) and dec.id == "tool")
            or (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "tool")
            for dec in node.decorator_list
        )
    ]


def _snapshot(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _restore(path: Path, content: str | None) -> None:
    if content is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(content, encoding="utf-8")


def _register_tool_module(stem: str, tools_var: str, function_names: list[str]) -> tuple[bool, str]:
    target = TOOLS_DIR / f"{stem}.py"
    source = target.read_text(encoding="utf-8")
    code_error = _parse_source(source, target.name)
    if code_error:
        return False, code_error
    if not function_names or not set(function_names).issubset(_extract_tool_names(source)):
        return False, "Generated tool module must define the named functions with @tool decorators."
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*_TOOLS", tools_var):
        return False, "Tool list name must be an uppercase identifier ending in _TOOLS."
    tree = ast.parse(source)
    has_tools_list = any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == tools_var for target in node.targets)
        and isinstance(node.value, ast.List)
        and {elt.id for elt in node.value.elts if isinstance(elt, ast.Name)} >= set(function_names)
        for node in tree.body
    )
    if not has_tools_list:
        return False, f"Generated tool module must define {tools_var} as a list containing all generated tools."

    tool_registry_before = _snapshot(TOOL_REGISTRY_FILE)
    tool_file_before = _snapshot(target)
    if tool_registry_before is None:
        return False, "Tool registry file is missing."
    import_line = f"from tools.{stem} import {', '.join(function_names)}\n"
    tools_line = f"\n\n{tools_var} = [{', '.join(function_names)}]\n"
    new_registry = tool_registry_before
    if import_line.strip() not in new_registry:
        new_registry = import_line + new_registry
    if f"{tools_var} =" not in new_registry:
        new_registry = new_registry.rstrip() + tools_line
    error = _parse_source(new_registry, TOOL_REGISTRY_FILE.name)
    if error:
        return False, error

    try:
        TOOL_REGISTRY_FILE.write_text(new_registry, encoding="utf-8")
        importlib.invalidate_caches()
        module = importlib.import_module(f"tools.{stem}")
        importlib.reload(module)
        registry = importlib.import_module("tools.tool_registry")
        importlib.reload(registry)
        if not hasattr(registry, tools_var):
            raise ImportError(f"{tools_var} was not exported by tools.tool_registry")
        return True, "Tool module passed syntax validation and was registered."
    except Exception as exc:
        _restore(TOOL_REGISTRY_FILE, tool_registry_before)
        _restore(target, tool_file_before)
        sys.modules.pop(f"tools.{stem}", None)
        if "tools.tool_registry" in sys.modules:
            importlib.reload(sys.modules["tools.tool_registry"])
        importlib.invalidate_caches()
        return False, f"Tool registration failed and was rolled back: {exc}"


@tool
def save_tool_file(filename: str, code: str, tools_var_name: str, function_names: list[str]) -> str:
    """Validate, save, and add a generated tool module to tool_registry.py."""
    stem = filename[:-3] if filename.endswith(".py") else filename
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,60}_tools", stem):
        return "ERROR: Tool filename must be a snake_case name ending in _tools.py."
    target = TOOLS_DIR / f"{stem}.py"
    if target.exists():
        return f"ERROR: {target.name} already exists; refusing to overwrite it."
    error = _parse_source(code, target.name)
    if error:
        return f"ERROR: {error}"
    target.write_text(code, encoding="utf-8")
    ok, message = _register_tool_module(stem, tools_var_name, function_names)
    if not ok:
        target.unlink(missing_ok=True)
        return f"ERROR: {message}"
    return f"SUCCESS: {message}"


def rollback_generated_tool(stem: str, tools_var: str, function_names: list[str]) -> None:
    """Remove a just-created tool module and its registry wiring after a later failure."""
    target = TOOLS_DIR / f"{stem}.py"
    if not target.exists():
        return
    registry = _snapshot(TOOL_REGISTRY_FILE)
    if registry is not None:
        import_line = f"from tools.{stem} import {', '.join(function_names)}\n"
        updated = registry.replace(import_line, "")
        updated = re.sub(
            rf"(?m)^[ \t]*{re.escape(tools_var)}\s*=\s*\[[^\]]*\][ \t]*\n?",
            "",
            updated,
        )
        TOOL_REGISTRY_FILE.write_text(updated, encoding="utf-8")
    target.unlink(missing_ok=True)
    sys.modules.pop(f"tools.{stem}", None)
    if "tools.tool_registry" in sys.modules:
        importlib.reload(sys.modules["tools.tool_registry"])
    importlib.invalidate_caches()


@tool
def create_and_register_agent(
    agent_stem: str,
    display_name: str,
    description: str,
    agent_prompt: str,
    tool_file_stem: str,
    tools_var_name: str,
) -> str:
    """Create an agent module, register it, and add its capability to retrieval."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,60}_agent", agent_stem):
        return "ERROR: Agent name must be a snake_case name ending in _agent."
    target = AGENTS_DIR / f"{agent_stem}.py"
    tool_path = TOOLS_DIR / f"{tool_file_stem}.py"
    if not tool_path.exists() or target.exists():
        return "ERROR: Registered tool file must exist and agent filename must be new."
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*_TOOLS", tools_var_name):
        return "ERROR: Invalid tools list name."

    description_literal = repr(description.strip())
    prompt_literal = repr(agent_prompt.strip())
    module_doc = repr(f"Generated {display_name}.")
    code = f'''{module_doc}

from langchain.agents import create_agent
from tools.tool_registry import {tools_var_name}

AGENT_DESCRIPTION = {description_literal}
AGENT_PROMPT = {prompt_literal}


async def run_{agent_stem}(model, task: str, context: str = "", callbacks=None, **kwargs) -> str:
    """Run the generated specialist and return its answer."""
    agent = create_agent(model=model, tools={tools_var_name})
    prompt = f"{{AGENT_PROMPT}}\\n\\nUser task:\\n{{task}}\\n\\nRelevant context:\\n{{context}}"
    result = await agent.ainvoke(
        {{"messages": [{{"role": "user", "content": prompt}}]}},
        config={{"callbacks": callbacks}} if callbacks else None,
    )
    return result["messages"][-1].content
'''
    error = _parse_source(code, target.name)
    if error:
        return f"ERROR: {error}"

    registry_before = _snapshot(AGENT_REGISTRY_FILE)
    if registry_before is None:
        return "ERROR: Agent registry file is missing."
    import_line = f"from Agents.agents.{agent_stem} import run_{agent_stem}, AGENT_DESCRIPTION as {agent_stem.upper()}_DESCRIPTION\n"
    key = agent_stem
    entry = f'    "{key}": {{"run": run_{agent_stem}, "description": {agent_stem.upper()}_DESCRIPTION}},\n'
    new_registry = registry_before
    if import_line.strip() not in new_registry:
        new_registry = import_line + new_registry
    marker = "_REGISTRY: dict[str, dict] = {"
    if marker not in new_registry:
        return "ERROR: Agent registry structure was not recognized."
    if f'"{key}"' in new_registry:
        return f"ERROR: Agent registry key '{key}' already exists."
    new_registry = new_registry.replace(marker, marker + "\n" + entry, 1)
    error = _parse_source(new_registry, AGENT_REGISTRY_FILE.name)
    if error:
        return f"ERROR: {error}"

    try:
        target.write_text(code, encoding="utf-8")
        AGENT_REGISTRY_FILE.write_text(new_registry, encoding="utf-8")
        importlib.invalidate_caches()
        agent_module = importlib.import_module(f"Agents.agents.{agent_stem}")
        importlib.reload(agent_module)
        registry = importlib.import_module("Agents.agent_registry")
        importlib.reload(registry)
        from planning.agent_retriever import register_agent_in_vector_db
        register_agent_in_vector_db(agent_name=key, description=description)
        return f"SUCCESS: Agent '{key}' was syntax-validated, registered, and indexed."
    except Exception as exc:
        _restore(AGENT_REGISTRY_FILE, registry_before)
        target.unlink(missing_ok=True)
        try:
            from planning.agent_retriever import remove_agent_from_vector_db
            remove_agent_from_vector_db(key)
        except Exception:
            pass
        sys.modules.pop(f"Agents.agents.{agent_stem}", None)
        if "Agents.agent_registry" in sys.modules:
            importlib.reload(sys.modules["Agents.agent_registry"])
        importlib.invalidate_caches()
        return f"ERROR: Agent registration failed and was rolled back: {exc}"


async def run_generated_agent(
    model,
    agent_file_stem: str,
    run_fn_name: str,
    task: str,
    context: str = "",
    callbacks: list | None = None,
) -> str:
    """Load and execute the newly registered agent for the current task."""
    try:
        importlib.invalidate_caches()
        module = importlib.import_module(f"Agents.agents.{agent_file_stem}")
        module = importlib.reload(module)
        run_fn = getattr(module, run_fn_name)
        return str(await run_fn(model=model, task=task, context=context, callbacks=callbacks))
    except Exception as exc:
        return f"ERROR: Could not execute generated agent: {exc}"


AGENT_CREATOR_TOOLS = [save_tool_file, create_and_register_agent]
