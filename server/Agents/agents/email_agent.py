from langchain.agents import create_agent

from tools.tool_registry import EMAIL_TOOLS


class EmailAgent:
    name = "Email Agent"
    description = """
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

    def __init__(self, model):
        self.agent = create_agent(
            model=model,
            tools=EMAIL_TOOLS
        )

    async def run(self, task: str, context: str = "") -> str:
        prompt = f"""
    You are {self.name}.

    Your responsibility:
    {self.description}

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

        result = await self.agent.ainvoke({
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        })

        return result["messages"][-1].content


