"""Redis worker runtime service tests."""

from __future__ import annotations

import fnmatch
import unittest
from unittest.mock import patch

from app.core import config
from app.services.vectors.vector_worker_runtime_service import (
    acquire_file_processing_lock,
    get_vector_worker_runtime_summary,
    record_worker_heartbeat,
    release_file_processing_lock,
    reset_vector_worker_runtime_state,
)


class FakeRedis:
    """Small Redis test double for worker runtime behavior."""

    def __init__(self) -> None:
        """Initialize in-memory Redis structures."""
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.hashes: dict[str, dict[str, str]] = {}

    def sadd(self, key: str, value: str) -> int:
        """Add a value to a set."""
        bucket = self.sets.setdefault(key, set())
        before = len(bucket)
        bucket.add(value)
        return len(bucket) - before

    def expire(self, key: str, ttl: int) -> bool:
        """Accept expire calls without simulating time."""
        return ttl > 0 and bool(key)

    def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        """Set a string value, honoring NX semantics."""
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True

    def get(self, key: str) -> str | None:
        """Return a string value."""
        return self.values.get(key)

    def smembers(self, key: str) -> set[str]:
        """Return set members."""
        return set(self.sets.get(key, set()))

    def srem(self, key: str, value: str) -> int:
        """Remove a set member."""
        if key not in self.sets or value not in self.sets[key]:
            return 0
        self.sets[key].remove(value)
        return 1

    def delete(self, *keys: str) -> int:
        """Delete string keys."""
        deleted = 0
        for key in keys:
            deleted += int(self.values.pop(key, None) is not None)
        return deleted

    def eval(self, script: str, numkeys: int, key: str, value: str) -> int:
        """Support compare-and-delete lock release script."""
        if numkeys != 1 or not script:
            return 0
        if self.values.get(key) == value:
            del self.values[key]
            return 1
        return 0

    def hincrby(self, key: str, field: str, amount: int) -> int:
        """Increment a hash integer field."""
        bucket = self.hashes.setdefault(key, {})
        next_value = int(bucket.get(field, "0")) + amount
        bucket[field] = str(next_value)
        return next_value

    def hset(self, key: str, mapping: dict[str, str]) -> int:
        """Set hash fields."""
        bucket = self.hashes.setdefault(key, {})
        before = len(bucket)
        bucket.update(mapping)
        return len(bucket) - before

    def hgetall(self, key: str) -> dict[str, str]:
        """Return a hash copy."""
        return dict(self.hashes.get(key, {}))

    def scan_iter(self, *, match: str, count: int = 200):
        """Yield string keys matching a glob pattern."""
        del count
        for key in sorted(self.values):
            if fnmatch.fnmatch(key, match):
                yield key


class VectorWorkerRuntimeServiceTests(unittest.TestCase):
    """Validate Redis runtime heartbeat, lock and fallback behavior."""

    def setUp(self) -> None:
        """Reset Redis runtime circuit before each test."""
        reset_vector_worker_runtime_state()
        self.redis = FakeRedis()

    def tearDown(self) -> None:
        """Reset Redis runtime circuit after each test."""
        reset_vector_worker_runtime_state()

    def test_records_worker_heartbeat_and_summary(self) -> None:
        """Heartbeat summary should expose online count without raw worker id."""
        with patch.object(config, "REDIS_ENABLED", True), patch(
            "app.services.vectors.vector_worker_runtime_service.get_redis_client",
            return_value=self.redis,
        ):
            result = record_worker_heartbeat(
                "host-a:123",
                status="processing",
                current_job={
                    "job_id": "job-1",
                    "user_id": 7,
                    "file_id": "file-1",
                    "index_version": 2,
                },
            )
            summary = get_vector_worker_runtime_summary()

        self.assertTrue(result["available"])
        self.assertTrue(summary["redis_available"])
        self.assertEqual(summary["online_worker_count"], 1)
        self.assertEqual(summary["workers"][0]["status"], "processing")
        self.assertEqual(summary["workers"][0]["current_job_id"], "job-1")
        self.assertNotIn("worker_id", summary["workers"][0])

    def test_file_processing_lock_blocks_until_release(self) -> None:
        """A second worker should see a busy file lease until it is released."""
        with patch.object(config, "REDIS_ENABLED", True), patch(
            "app.services.vectors.vector_worker_runtime_service.get_redis_client",
            return_value=self.redis,
        ):
            first = acquire_file_processing_lock(
                worker_id="worker-1",
                user_id=1,
                file_id="file-1",
                job_id="job-1",
                index_version=1,
            )
            second = acquire_file_processing_lock(
                worker_id="worker-2",
                user_id=1,
                file_id="file-1",
                job_id="job-2",
                index_version=1,
            )
            release_file_processing_lock(first)
            third = acquire_file_processing_lock(
                worker_id="worker-2",
                user_id=1,
                file_id="file-1",
                job_id="job-2",
                index_version=1,
            )

        self.assertTrue(first.acquired)
        self.assertTrue(second.is_busy)
        self.assertEqual(second.owner_job_id, "job-1")
        self.assertTrue(third.acquired)

    def test_summary_degrades_when_redis_unavailable(self) -> None:
        """Redis errors should produce a safe unavailable summary."""
        with patch.object(config, "REDIS_ENABLED", True), patch(
            "app.services.vectors.vector_worker_runtime_service.get_redis_client",
            side_effect=RuntimeError("redis://:secret@localhost:6379/0 failed"),
        ):
            summary = get_vector_worker_runtime_summary()

        self.assertFalse(summary["redis_available"])
        self.assertEqual(summary["redis_status"], "unavailable")
        self.assertEqual(summary["online_worker_count"], 0)
        self.assertNotIn("secret", summary["redis_error_message"])


if __name__ == "__main__":
    unittest.main()
