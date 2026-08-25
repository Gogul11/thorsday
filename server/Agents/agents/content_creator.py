from langchain.agents import create_agent
from services.user_session import get_current_user_email, get_current_user_name


class ContentCreatorAgent:
    name = "Content Creator Agent"
    description = """
    Content Creator is responsible for authoring, drafting, formatting, refining, and generating written text content.

    Use Content Creator whenever a task requires:
    - Writing or drafting email content, subjects, and bodies
    - Crafting announcements, messages, memos, summaries, or reports
    - Adapting tone (professional, formal, friendly, persuasive, technical)
    - Structuring text, bullet points, or markdown documents
    - Generating ready-to-send content for downstream agents (such as Email Agent)

    GUIDELINES:
    - GREETING AT THE TOP: Always address the recipient by name or their username extracted from their email/prompt (e.g., if recipient is 'oviyashreechris@gmail.com', greet with 'Hi Oviyashree,' or 'Hi oviyashreechris,').
    - SIGN-OFF AT THE BOTTOM: Sign off with the sender's name/username provided in sender context.
    - NO BRACKETED PLACEHOLDERS: Never produce unfilled template brackets like [Your Name], [Recipient Name], [Company], [Link], [Date], [Location].
    - All generated content MUST be complete, natural, and ready to send immediately.
    """

    def __init__(self, model):
        self.agent = create_agent(
            model=model,
            tools=[]
        )

    async def run(self, task: str, context: str = "") -> str:
        sender_email = get_current_user_email()
        sender_name = get_current_user_name()
        prompt = f"""
    You are {self.name}.

    Your responsibility:
    {self.description}

    Task:
    {task}

    Sender Context:
    - Sender Email: {sender_email}
    - Sender Name / Username: {sender_name}

    Results from previous agents:
    {context}

    STRICT GUIDELINES:
    1. Greeting at the top: Extract the recipient's name or username from the task/email (e.g. "Hi Oviyashree," or "Hi oviyashreechris,") and place it at the very top of the body.
    2. Body: Write a clear, polite, and complete message based on the task.
    3. Sign-off at the bottom: Sign off with "Best regards," followed by "{sender_name}".
    4. NO bracketed placeholders: Do NOT use [Your Name], [Recipient Name], [Insert Link], etc.
    5. Output format:
       Subject: <Clear, engaging subject line>
       Body:
       <Complete email body ready to be sent immediately>
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



