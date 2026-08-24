from tools.sys_info_tools import *
from tools.time_tool import get_time
from tools.research_tools import wikipedia_search, trusted_web_search

A1_TOOLS = [
    get_system_info
]

A2_TOOLS = [
    get_time
]

A3_TOOLS = [
    wikipedia_search,
    trusted_web_search,
]

RESEARCH_TOOLS = A3_TOOLS

# TOOL_MAP = {tool.name : tool for tool in TOOLS}