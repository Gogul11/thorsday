"""Shared MongoDB connection for the backend service."""

import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

_client = AsyncIOMotorClient(_MONGO_URI)
_db = _client["agentos"]

tasks_collection = _db["tasks"]
