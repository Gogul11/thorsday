import os
import platform
from pathlib import Path

from langchain_core.tools import tool

@tool
def get_system_info() -> str:
    """Get basic information about the operating system and machine."""
    return (
            f"Operating System: {platform.system()} {platform.release()}\n"
            f"Architecture: {platform.machine()}\n"
            f"Processor: {platform.processor()}"
    )
