"""Bounded Python subprocess execution with live terminal events."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool

from logger import logger
from Redis.redis_connection import publish

_SANDBOX_ROOT = Path(__file__).resolve().parent.parent / "data" / "code_runner_sandbox"
_MAX_CODE_CHARS = 20_000
_MAX_OUTPUT_CHARS = 64_000
_MAX_RUNTIME_SECONDS = 10
_RUN_SEMAPHORE = asyncio.Semaphore(2)


async def _emit(event: str, req_id: str, task_id: str, attempt: int, **data: Any) -> None:
    try:
        await publish(
            "kernel_events",
            {"event": event, "req_id": req_id, "task_id": task_id, "attempt": attempt, **data},
        )
    except Exception as exc:  # Telemetry must never break code execution.
        logger.warning("Code runner event failed | event=%s | error=%s", event, exc)


async def _read_stream(
    stream: asyncio.StreamReader,
    name: str,
    queue: asyncio.Queue[tuple[str, bytes | None]],
) -> None:
    while True:
        line = await stream.readline()
        if not line:
            await queue.put((name, None))
            return
        await queue.put((name, line))


async def _execute(
    code: str,
    *,
    req_id: str,
    task_id: str,
    attempt: int,
) -> dict[str, Any]:
    if not code.strip():
        return {"exit_code": 2, "stdout": "", "stderr": "No code was provided."}
    if len(code) > _MAX_CODE_CHARS:
        return {
            "exit_code": 2,
            "stdout": "",
            "stderr": f"Code exceeds the {_MAX_CODE_CHARS}-character limit.",
        }

    _SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="run_", dir=_SANDBOX_ROOT))
    script = run_dir / "main.py"
    script.write_text(code, encoding="utf-8")
    process: asyncio.subprocess.Process | None = None
    stdout: list[str] = []
    stderr: list[str] = []
    output_size = 0
    timed_out = False
    truncated = False
    started = time.perf_counter()

    # Do not pass application environment variables, API keys, or PYTHONPATH.
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SystemRoot": os.environ.get("SystemRoot", ""),
        "TEMP": str(run_dir),
        "TMP": str(run_dir),
        "PYTHONNOUSERSITE": "1",
    }

    async with _RUN_SEMAPHORE:
        await _emit(
            "terminal.STARTED",
            req_id,
            task_id,
            attempt,
            timeout_seconds=_MAX_RUNTIME_SECONDS,
        )
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                str(script),
                cwd=str(run_dir),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            queue: asyncio.Queue[tuple[str, bytes | None]] = asyncio.Queue()
            readers = [
                asyncio.create_task(_read_stream(process.stdout, "stdout", queue)),
                asyncio.create_task(_read_stream(process.stderr, "stderr", queue)),
            ]

            async def consume() -> None:
                nonlocal output_size, truncated
                closed = 0
                while closed < 2:
                    stream_name, raw = await queue.get()
                    if raw is None:
                        closed += 1
                        continue
                    remaining = _MAX_OUTPUT_CHARS - output_size
                    if remaining <= 0:
                        truncated = True
                        if process.returncode is None:
                            process.kill()
                        continue
                    line = raw.decode("utf-8", errors="replace")[:remaining]
                    output_size += len(line)
                    (stdout if stream_name == "stdout" else stderr).append(line)
                    await _emit(
                        "terminal.OUTPUT",
                        req_id,
                        task_id,
                        attempt,
                        stream=stream_name,
                        line=line.rstrip("\r\n"),
                    )

            try:
                await asyncio.wait_for(consume(), timeout=_MAX_RUNTIME_SECONDS)
            except asyncio.TimeoutError:
                timed_out = True
                if process.returncode is None:
                    process.kill()
            finally:
                await process.wait()
                for reader in readers:
                    if not reader.done():
                        reader.cancel()
                await asyncio.gather(*readers, return_exceptions=True)
        except Exception as exc:
            logger.exception("Code runner failed | req=%s | task=%s", req_id, task_id)
            stderr.append(str(exc))

    duration_ms = round((time.perf_counter() - started) * 1000)
    exit_code = 124 if timed_out else (process.returncode if process else 1)
    result = {
        "exit_code": exit_code,
        "stdout": "".join(stdout),
        "stderr": "".join(stderr),
        "timed_out": timed_out,
        "truncated": truncated,
        "duration_ms": duration_ms,
    }
    await _emit(
        "terminal.FAILED" if exit_code else "terminal.COMPLETED",
        req_id,
        task_id,
        attempt,
        exit_code=exit_code,
        duration_ms=duration_ms,
        timed_out=timed_out,
        truncated=truncated,
    )
    logger.info(
        "Code runner finished | req=%s | task=%s | attempt=%d | exit=%s | duration_ms=%d",
        req_id,
        task_id,
        attempt,
        exit_code,
        duration_ms,
    )
    shutil.rmtree(run_dir, ignore_errors=True)
    return result


def build_run_python_code_tool(req_id: str, task_id: str) -> StructuredTool:
    """Return run_python_code bound to the current task for event routing."""

    async def run_python_code(code: str, attempt: int = 1) -> str:
        result = await _execute(
            code,
            req_id=req_id,
            task_id=task_id,
            attempt=attempt,
        )
        return json.dumps(result)

    return StructuredTool.from_function(
        coroutine=run_python_code,
        name="run_python_code",
        description=(
            "Run standalone Python code in the constrained AgentOS sandbox. "
            "Returns JSON containing exit_code, stdout, stderr, timeout, and duration."
        ),
    )


async def _manual_run(code: str, attempt: int = 1) -> str:
    return json.dumps(await _execute(code, req_id="manual", task_id="manual", attempt=attempt))


run_python_code = StructuredTool.from_function(
    coroutine=_manual_run,
    name="run_python_code",
    description="Run Python code in the constrained AgentOS sandbox.",
)
