from langchain.agents import create_agent
from services.user_session import get_current_user_email, get_current_user_name

_NAME = "Content Creator Agent"
CONTENT_AGENT_DESCRIPTION = """
    Content Creator is a text drafting, writing, and formatting agent ONLY.

    Its responsibility is to create, draft, rewrite, refine, summarize, format,
    and structure written content based on the user's instruction.

    It drafts content such as:
    - Email drafts and subjects
    - Messages and chat replies
    - Announcements
    - Reports and memos
    - Documentation and summaries
    - Articles and blog posts
    - Social media posts
    - LinkedIn posts
    - Meeting notes
    - Proposals
    - Statements
    - Presentations or slide content
    - Marketing copy
    - Technical explanations
    - Instructions and guides
    - Bullet-point content
    - Markdown documents
    - Other text-based content

    IMPORTANT:
    - Content Creator ONLY writes and formats text.
    - Content Creator CANNOT send emails or communicate with mail servers.
    - If an email needs to be physically sent, Content Creator should draft the content first, and Email Agent must be used to send it.
    - Do not use unfilled bracketed placeholders such as [Your Name], [Recipient], [Company], [Date], [Link].
    """


async def run_content_creator_agent(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    **kwargs
) -> str:
    sender_email = get_current_user_email()
    sender_name = get_current_user_name()

    agent = create_agent(model=model, tools=[])
    prompt = f"""
    You are {_NAME}.

    Your responsibility:
    {CONTENT_AGENT_DESCRIPTION}

    USER TASK:
    {task}

    SENDER CONTEXT:
    - Sender Email: {sender_email}
    - Sender Name / Username: {sender_name}

    RESULTS FROM PREVIOUS AGENTS:
    {context}

    IMPORTANT INSTRUCTIONS:

    1. FIRST understand what type of content the user is requesting.

    2. DO NOT assume the task is an email.

    3. Choose the output format based on the task.

    Examples:

    If the task is an email:
    - Include an appropriate subject if needed.
    - Include a greeting when appropriate.
    - Write the email body.
    - Include a professional sign-off when appropriate.

    If the task is a report:
    - Use an appropriate title.
    - Use headings, sections, bullet points, tables, etc. when useful.
    - Do NOT add an email greeting or sign-off.

    If the task is a social media post:
    - Generate the actual post.
    - Use an appropriate tone and formatting.
    - Add hashtags only when appropriate.

    If the task is a message/chat reply:
    - Generate a natural conversational response.
    - Do NOT add an email-style subject or sign-off.

    If the task is a summary:
    - Provide the summary directly.
    - Do NOT add unnecessary greetings, subjects, or sign-offs.

    If the task is documentation:
    - Structure it clearly using headings, lists, examples, or code
        where appropriate.

    4. If the user explicitly requests a particular format, follow that format
    even if another format might seem more natural.

    5. Do not add:
    - "[Your Name]"
    - "[Recipient Name]"
    - "[Company]"
    - "[Date]"
    - "[Link]"
    - "[Location]"
    - or any other unfilled placeholder.

    6. Use the sender name "{sender_name}" only when the requested content
    naturally requires a sender identity, such as an email or formal message.

    7. Return ONLY the completed content requested by the user.
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
