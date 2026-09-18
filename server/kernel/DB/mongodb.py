import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os

# Load .env from server/ directory or current directory
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["agentos"]

tasks_collection = db["tasks"]