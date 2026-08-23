from datetime import datetime
from langchain_core.tools import tool


@tool
def get_time() -> str:
    """Get current date and time"""
    return (
           f"Current date and time : {datetime.now()}"
    )
