"""Compatibility entrypoint for the API application."""

from Redis.redis_connection import RedisPubSub
from models.model import Models
from Agents.main_agent import Main_Agent

redis_client = RedisPubSub()
models = Models()
main_agent = Main_Agent(models, redis_client)
print("Otha")
while True:
    pass

# __all__ = ["models", "redis_client", "main_agent"]
