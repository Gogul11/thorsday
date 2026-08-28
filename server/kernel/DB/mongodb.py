from motor.motor_asyncio import AsyncIOMotorClient
import os


MONGO_URI = os.getenv("MONGO_URI")

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["agentos"]

tasks_collection = db["tasks"]