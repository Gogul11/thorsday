from Agents.main_agent import Main_Agent
from models.model import Models
from logger import logger

import asyncio
import sys


def configure_terminal_encoding():
    """Keep Unicode responses usable in Windows terminals and Bash."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

async def main():
    configure_terminal_encoding()
    logger.info("Application started successfully!")
    models = Models()
    main_agent = Main_Agent(models)


    while True:
        message = input("Enter a message : ")

        if message == "exit":
            logger.info("Program exited!")
            break

        response = await main_agent.chat(message)
    
        print("Agent : ", response)
            

if __name__ == "__main__":
    asyncio.run(main())
