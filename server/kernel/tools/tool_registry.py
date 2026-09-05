from tools.sys_info_tools import *
from tools.time_tool import get_time
from tools.research_tools import wikipedia_search, trusted_web_search
from tools.email_tools import send_email

"""
Tool registry for AgentOS.
"""

from tools.file_document_tools import (
    append_to_file,
    classify_document,
    compare_documents,
    create_docx_file,
    create_folder,
    create_text_file,
    get_file_metadata,
    list_directory,
    move_file,
    read_document,
    rename_file,
    replace_in_file,
    request_delete_confirmation,
    search_files,
)

A1_TOOLS = [
    get_system_info
]

A2_TOOLS = [
    get_time
]

A3_TOOLS = [
    wikipedia_search,
    trusted_web_search
]

A4_TOOLS = [
    search_files,
    read_document,

    create_text_file,
    create_docx_file,

    append_to_file,
    replace_in_file,

    create_folder,
    rename_file,
    move_file,

    # IMPORTANT:
    # There is intentionally NO delete_file tool.
    #
    # A4 can only request deletion.
    # The backend performs deletion after the user confirms.
    request_delete_confirmation,

    get_file_metadata,
    list_directory,

    compare_documents,
    classify_document,
]

EMAIL_TOOLS = [
    send_email
]

# TOOL_MAP = {tool.name : tool for tool in TOOLS}