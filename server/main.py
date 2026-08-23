from Agents.main_agent import Main_Agent
from models.model import Models
from logger import logger

import asyncio

async def main():
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
