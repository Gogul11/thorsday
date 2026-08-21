from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, AnyMessage

class Context:
    def __init__(self):
        self.messages : list[AnyMessage] = []
        self.system_message : AnyMessage = SystemMessage(content=   
            """You are the Main Agent of AgentOS.
            
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

    def add_user_message(self, message : str):
        self.messages.append(HumanMessage(content=message))

    def add_system_message(self, message : str):
        self.messages.append(AIMessage(content=message))

    def get_context(self) -> list[AnyMessage]:
        return [
            self.system_message,
            *self.messages
        ]