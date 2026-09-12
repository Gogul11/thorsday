from langchain.agents import create_agent

from services.user_session import get_current_user_email
from tools.tool_registry import EMAIL_TOOLS

_NAME = "Email Agent"
E_AGENT_DESCRIPTION = """
    Email Agent is responsible for SENDING, DISPATCHING, and DELIVERING emails to recipients.

    Use Email Agent whenever a task requires:
    - Sending an email to an email address (e.g. "send an email to...", "email test@example.com", "mail someone...")
    - Dispatching drafted messages, invitations, announcements, or notifications via email
    - Forwarding generated text (such as drafts prepared by Content Creator) to a recipient inbox

    Email Agent should:
    - Extract the recipient email address(es) from the user's prompt or context
    - Extract or determine the subject line and email body from prior agent results (such as Content Creator)
    - Ensure the email body is completely free of any bracketed placeholder tokens (e.g. [Your Name]) before sending
    - Email Agent ALWAYS executes its `send_email` tool to deliver the email.
    """


async def run_email_agent(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    **kwargs
) -> str:
    sender_email = get_current_user_email()
    agent = create_agent(model=model, tools=EMAIL_TOOLS)

    prompt = f"""You are {_NAME}.

Your responsibility:
{E_AGENT_DESCRIPTION}

User Task:
{task}

Previous Agent Results (Content Drafts):
{context}

        Instructions:
        1. Extract the recipient email address (to_email) from the task or context.
        2. Determine the subject line and email body (use the text prepared by prior agents like Content Creator or calculation agents). Keep the email body clean, professional, and well-structured. If previous results contain lengthy tables or schedules, include the key figures (principal, interest, monthly payment, tenure) and a concise summary breakdown rather than dumping dozens of repeated lines, keeping the email readable and within tool payload limits.
        3. Ensure there are NO unresolved bracketed placeholders like [Your Name] or [Link] or [Date] in the email body.
        4. Call the send_email tool with the recipient, subject, and cleaned email body. YOU MUST CALL THE `send_email` TOOL with:
           - to_email: <recipient email address>
           - subject: <email subject>
           - body: <cleaned email body content>
        5. Return the exact delivery confirmation output provided by the `send_email` tool.
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

