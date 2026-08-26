from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from repository.task_repo import DB_add_task_message, DB_get_task_messages


class Context:
    def __init__(self):
        self.messages: list[BaseMessage] = []
        self.system_message: BaseMessage = SystemMessage(
            content="""You are the Main Agent of AgentOS.

            Understand the user's intent, use the provided context, reason about tasks, and use available tools when necessary.

            Rules:
            - Use context to maintain conversation continuity.
            - Use tools when required; never fabricate tool results.
            - If you cannot perform an action, state the limitation.
            - For complex tasks, break them into logical steps.
            - Give concise, accurate responses.
            - Never claim an action was completed unless it actually was.
            """
        )

    async def add_user_message(self, task_id: str, message: str):
        self.messages.append(HumanMessage(content=message))
        await DB_add_task_message(task_id, "human", message)

    async def add_system_message(self, task_id: str, message: str):
        self.messages.append(AIMessage(content=message))
        await DB_add_task_message(task_id, "ai", message)

    async def get_context(self, req_id: str) -> list[BaseMessage]:
        messages : list[dict[str, str]] | None = await DB_get_task_messages(req_id)

        context = [self.system_message]

        if messages:
            for message in messages:
                if message["role"] == "human":
                    context.append(HumanMessage(content=message["content"]))
    
                elif message["role"] == "ai":
                    context.append(AIMessage(content=message["content"]))

        return context[-20:]
        # return context
        
