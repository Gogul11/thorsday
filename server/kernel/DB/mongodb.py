from motor.motor_asyncio import AsyncIOMotorClient
import os


MONGO_URI = os.getenv("MONGO_URI")

client = AsyncIOMotorClient(MONGO_URI)

db = client["agentos"]

tasks_collection = db["tasks"]