from tools.sys_info_tools import get_system_info
from tools.time_tool import get_time
from tools.research_tools import wikipedia_search, trusted_web_search

# System & OS Inspection Tools
SYSTEM_TOOLS = [
    get_system_info,
]
SYS_INFO_TOOLS = SYSTEM_TOOLS

# Time & Date Tools
TIME_TOOLS = [
    get_time,
]

# Academic & Web Research Tools
RESEARCH_TOOLS = [
    wikipedia_search,
    trusted_web_search,
]

# Backward compatibility aliases
A1_TOOLS = SYSTEM_TOOLS
A2_TOOLS = TIME_TOOLS
A3_TOOLS = RESEARCH_TOOLS

# TOOL_MAP = {tool.name : tool for tool in TOOLS}