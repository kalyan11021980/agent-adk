"""Tests for the Redis-backed task store.

Requires a local Redis instance on localhost:6379.
These tests use a dedicated DB index (15) to avoid polluting other data.
"""

from __future__ import annotations

import pytest
import redis.asyncio as aioredis
from a2a.types import Task, TaskState, TaskStatus

from health_ai_langgraph.task_store import RedisTaskStore

REDIS_TEST_URL = "redis://localhost:6379/15"


@pytest.fixture
async def store():
    """Create a RedisTaskStore on test DB 15, clean up after."""
    client = aioredis.from_url(REDIS_TEST_URL, decode_responses=True)
    try:
        await client.ping()
    except Exception:
        pytest.skip("Redis not available at localhost:6379")

    task_store = RedisTaskStore(redis_client=client, ttl=60)
    yield task_store

    # Cleanup: flush test DB
    await client.flushdb()
    await client.aclose()


def _make_task(task_id: str, state: TaskState = TaskState.working) -> Task:
    return Task(
        id=task_id,
        contextId=f"ctx-{task_id}",
        status=TaskStatus(state=state),
    )


class TestRedisTaskStore:

    @pytest.mark.asyncio
    async def test_save_and_get(self, store: RedisTaskStore):
        task = _make_task("t-001")
        await store.save(task)
        retrieved = await store.get("t-001")
        assert retrieved is not None
        assert retrieved.id == "t-001"
        assert retrieved.status.state == TaskState.working

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, store: RedisTaskStore):
        result = await store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, store: RedisTaskStore):
        task = _make_task("t-002")
        await store.save(task)
        await store.delete("t-002")
        assert await store.get("t-002") is None

    @pytest.mark.asyncio
    async def test_save_overwrites(self, store: RedisTaskStore):
        task1 = _make_task("t-003", TaskState.working)
        await store.save(task1)
        task2 = _make_task("t-003", TaskState.completed)
        await store.save(task2)
        retrieved = await store.get("t-003")
        assert retrieved is not None
        assert retrieved.status.state == TaskState.completed

    @pytest.mark.asyncio
    async def test_list_tasks(self, store: RedisTaskStore):
        await store.save(_make_task("t-010"))
        await store.save(_make_task("t-011"))
        await store.save(_make_task("t-012"))
        tasks = await store.list_tasks()
        ids = {t.id for t in tasks}
        assert ids == {"t-010", "t-011", "t-012"}
