"""User session and authentication context helper.

This module provides functions to retrieve the current user's profile/context.
Currently, as a login system is not yet active, it reads from environment variables
or defaults to a configured custom email. When user authentication (e.g., JWT/session)
is implemented, this function can be updated to retrieve the logged-in user from request context.
"""

import os
import re
from dotenv import load_dotenv

load_dotenv()


def get_current_user_email() -> str:
    """Return the email address of the current user.

    Returns:
        The sender email address from DEFAULT_SENDER_EMAIL, SENDER_EMAIL, or a fallback.
    """
    return (
        os.getenv("DEFAULT_SENDER_EMAIL")
        or os.getenv("SENDER_EMAIL")
        or "vitaladmin6@gmail.com"
    )


def _clean_name(raw_name: str) -> str:

    """Format a name string so it contains only letters and spaces with Title Case.

    Removes all digits, numbers, and symbols/punctuation.
    Example: 'vitaladmin6' -> 'Vitaladmin', 'john_doe123' -> 'John Doe'
    """
    # Replace non-alphabetic characters with spaces
    letters_only = re.sub(r"[^a-zA-Z\s]", " ", raw_name)
    # Collapse multiple spaces and strip
    cleaned = " ".join(letters_only.split())
    # Return Title Case (first letter capital)
    return cleaned.title() if cleaned else "User"


def get_current_user_name() -> str:
    """Return the display name or username of the current user.

    Ensures the name contains no numbers, digits, or symbols, and starts
    with a capital letter.

    Returns:
        The cleaned name from DEFAULT_SENDER_NAME, or derived from the sender email.
    """
    custom_name = os.getenv("DEFAULT_SENDER_NAME") or os.getenv("USER_NAME")
    if custom_name:
        return _clean_name(custom_name)

    email = get_current_user_email()
    prefix = email.split("@")[0] if "@" in email else email
    return _clean_name(prefix)



