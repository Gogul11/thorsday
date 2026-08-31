from langchain.agents import create_agent

from tools.tool_registry import EMAIL_TOOLS

_NAME = "Email Agent"
E_AGENT_DESCRIPTION = """
    Email Agent is responsible for sending emails to target recipient email addresses.

    Use Email Agent whenever a task requires:
    - Sending an email to a specified email address or recipient
    - Dispatching drafted messages, announcements, or notifications via email
    - Forwarding generated content (e.g., from Content Creator) to an email destination

    Email Agent should:
    - Extract the recipient email address(es) from the user's prompt or context
    - Extract or determine the subject line and email body from prior agent results (such as Content Creator)
    - Ensure the email body is completely free of any bracketed placeholder tokens (e.g. [Your Name]) before sending
    - Use the send_email tool to send the email
    - Return a clear summary of the email delivery status, recipient, and subject
    """

async def run_email_agent(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
) -> str:
    agent = create_agent(model=model, tools=EMAIL_TOOLS)
    prompt = f"""You are {_NAME}.

        Your responsibility:
        {E_AGENT_DESCRIPTION}

        Task:
        {task}

        Results from previous agents:
        {context}

        Instructions:
        1. Extract the recipient email address (to_email).
        2. Extract the subject and email body from previous agent results (Content Creator).
        3. Ensure there are NO unresolved bracketed placeholders like [Your Name] or [Link] in the email body.
        4. Call the send_email tool with the recipient, subject, and cleaned email body.
        5. Return the delivery status clearly.
        """

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        },
        config={"callbacks": callbacks} if callbacks else None,
    )

    return result["messages"][-1].content