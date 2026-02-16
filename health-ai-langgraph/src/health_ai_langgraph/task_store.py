"""Redis-backed task store for the A2A protocol.

Replaces ``InMemoryTaskStore`` so that task state survives restarts and
is shared across multiple server instances behind a load balancer.

Tasks are stored as JSON in Redis with a configurable TTL (default 1 hour).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis
from a2a.server.context import ServerCallContext
from a2a.server.tasks import TaskStore
from a2a.types import Task

logger = logging.getLogger("health_ai_langgraph.task_store")

# Default TTL for tasks in Redis (seconds)
DEFAULT_TASK_TTL = 3600  # 1 hour
REDIS_KEY_PREFIX = "health_ai:task:"


class RedisTaskStore(TaskStore):
    """Persist A2A tasks in Redis with automatic expiry.

    Each task is stored as a JSON string under
    ``health_ai:task:{task_id}``.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        ttl: int = DEFAULT_TASK_TTL,
    ) -> None:
        self._redis = redis_client
        self._ttl = ttl
        # lock + tasks kept for backwards compatibility with the
        # custom list_tasks endpoint in server.py
        self.lock = asyncio.Lock()

    async def save(
        self, task: Task, context: ServerCallContext | None = None
    ) -> None:
        """Save or update a task in Redis."""
        key = f"{REDIS_KEY_PREFIX}{task.id}"
        data = task.model_dump(mode="json", exclude_none=True)
        await self._redis.set(key, json.dumps(data), ex=self._ttl)

    async def get(
        self, task_id: str, context: ServerCallContext | None = None
    ) -> Task | None:
        """Retrieve a task by ID from Redis."""
        key = f"{REDIS_KEY_PREFIX}{task_id}"
        raw = await self._redis.get(key)
        if raw is None:
            return None
        data = json.loads(raw)
        return Task(**data)

    async def delete(
        self, task_id: str, context: ServerCallContext | None = None
    ) -> None:
        """Delete a task from Redis."""
        key = f"{REDIS_KEY_PREFIX}{task_id}"
        await self._redis.delete(key)

    async def list_tasks(self) -> list[Task]:
        """List all active tasks (scan the key prefix)."""
        tasks: list[Task] = []
        async for key in self._redis.scan_iter(f"{REDIS_KEY_PREFIX}*", count=100):
            raw = await self._redis.get(key)
            if raw:
                data = json.loads(raw)
                tasks.append(Task(**data))
        return tasks

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._redis.aclose()

    @classmethod
    async def create(
        cls,
        redis_url: str = "redis://localhost:6379/0",
        ttl: int = DEFAULT_TASK_TTL,
    ) -> RedisTaskStore:
        """Factory: create a RedisTaskStore with a connected client."""
        client = aioredis.from_url(redis_url, decode_responses=True)
        await client.ping()
        logger.info("Redis task store connected to %s", redis_url)
        return cls(redis_client=client, ttl=ttl)
