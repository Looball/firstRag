"""Redis backed runtime state for vector index workers.

PostgreSQL remains the durable queue for ``vector_index_jobs``. This module
only stores short-lived worker heartbeats, best-effort file leases and small
runtime counters so health checks can distinguish "queued but no worker online"
from "queued and worker is alive".
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, RLock, Thread
from time import monotonic
from typing import Any

from app.core import config
from app.services.cache_service import build_cache_key, build_cache_prefix
from app.services.redis_service import (
    RedisServiceError,
    get_redis_client,
    sanitize_redis_error_message,
)


logger = logging.getLogger(__name__)

_RUNTIME_CIRCUIT_TTL_SECONDS = 5.0
_METRICS_TTL_SECONDS = 7 * 24 * 60 * 60
_CIRCUIT_LOCK = RLock()
_UNAVAILABLE_UNTIL = 0.0
_UNAVAILABLE_REASON: str | None = None

_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


@dataclass(frozen=True)
class VectorWorkerFileLock:
    """A short Redis lease for one file indexing job."""

    key: str
    value: str
    acquired: bool
    available: bool
    owner_job_id: str | None = None
    fallback_reason: str | None = None

    @property
    def is_busy(self) -> bool:
        """Return True when Redis is available and another holder owns it."""
        return self.available and not self.acquired


def reset_vector_worker_runtime_state() -> None:
    """Reset the short Redis runtime circuit; used by tests."""
    global _UNAVAILABLE_UNTIL, _UNAVAILABLE_REASON
    with _CIRCUIT_LOCK:
        _UNAVAILABLE_UNTIL = 0.0
        _UNAVAILABLE_REASON = None


def _heartbeat_ttl_seconds() -> int:
    """Return a safe heartbeat TTL."""
    return max(5, int(config.VECTOR_WORKER_HEARTBEAT_TTL_SECONDS))


def _file_lock_ttl_seconds() -> int:
    """Return a safe file lock TTL."""
    return max(5, int(config.VECTOR_WORKER_FILE_LOCK_TTL_SECONDS))


def _now_utc() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    """Serialize datetimes as timezone-aware ISO strings."""
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    """Parse a Redis ISO datetime value defensively."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _worker_key(worker_id: str) -> str:
    """Hash worker id before using or exposing it as Redis metadata."""
    return hashlib.sha256(worker_id.encode("utf-8")).hexdigest()[:24]


def _workers_set_key() -> str:
    """Return Redis set key for online worker keys."""
    return build_cache_key("vector_worker", "workers")


def _worker_heartbeat_key(worker_key: str) -> str:
    """Return Redis heartbeat key for a hashed worker key."""
    return build_cache_key("vector_worker", "heartbeat", worker_key)


def _file_lock_key(user_id: int, file_id: object) -> str:
    """Return Redis lock key for a user's file."""
    return build_cache_key("vector_worker", "file_lock", user_id, file_id)


def _file_lock_prefix() -> str:
    """Return Redis scan prefix for active file locks."""
    return build_cache_prefix("vector_worker", "file_lock")


def _metrics_key() -> str:
    """Return Redis hash key for worker runtime counters."""
    return build_cache_key("vector_worker", "metrics")


def _read_open_circuit() -> str | None:
    """Return cached Redis failure reason while runtime circuit is open."""
    with _CIRCUIT_LOCK:
        if _UNAVAILABLE_UNTIL > monotonic():
            return _UNAVAILABLE_REASON or "Redis worker runtime 暂不可用。"
    return None


def _mark_redis_unavailable(exc: Exception) -> str:
    """Open a short circuit after Redis runtime failure."""
    reason = sanitize_redis_error_message(str(exc))
    global _UNAVAILABLE_UNTIL, _UNAVAILABLE_REASON
    with _CIRCUIT_LOCK:
        _UNAVAILABLE_UNTIL = monotonic() + _RUNTIME_CIRCUIT_TTL_SECONDS
        _UNAVAILABLE_REASON = reason
    logger.debug("Redis worker runtime 暂不可用，降级到 PostgreSQL 队列：%s", reason)
    return reason


def _runtime_fallback_reason(exc: Exception) -> str:
    """Return fallback reason without extending an already-open circuit."""
    if isinstance(exc, RedisServiceError):
        return sanitize_redis_error_message(str(exc))
    return _mark_redis_unavailable(exc)


def _get_runtime_client() -> Any:
    """Return Redis client unless the worker runtime circuit is open."""
    reason = _read_open_circuit()
    if reason is not None:
        raise RedisServiceError(reason)
    return get_redis_client()


def _json_loads(raw_value: Any) -> dict[str, Any] | None:
    """Decode a Redis JSON dict defensively."""
    if not isinstance(raw_value, str) or not raw_value:
        return None
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _normalize_job_context(job: dict[str, Any] | None) -> dict[str, Any]:
    """Keep only safe, low-cardinality job fields in worker heartbeat."""
    if not job:
        return {}
    return {
        key: value
        for key, value in {
            "current_job_id": job.get("job_id"),
            "current_user_id": job.get("user_id"),
            "current_file_id": job.get("file_id"),
            "current_index_version": job.get("index_version"),
        }.items()
        if value is not None
    }


def record_worker_heartbeat(
    worker_id: str,
    *,
    status: str = "idle",
    current_job: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a short-lived worker heartbeat to Redis.

    Redis failures never stop the PostgreSQL-backed queue; callers get a small
    result dict that can be logged or ignored.
    """
    worker_key = _worker_key(worker_id)
    payload = {
        "worker_key": worker_key,
        "worker_id": worker_id,
        "hostname": socket.gethostname(),
        "status": status,
        "heartbeat_at": _isoformat(_now_utc()),
        **_normalize_job_context(current_job),
    }

    try:
        client = _get_runtime_client()
        heartbeat_ttl = _heartbeat_ttl_seconds()
        client.sadd(_workers_set_key(), worker_key)
        client.expire(_workers_set_key(), heartbeat_ttl * 20)
        client.set(
            _worker_heartbeat_key(worker_key),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            ex=heartbeat_ttl,
        )
    except Exception as exc:  # noqa: BLE001 - 运行态不可影响队列消费
        return {
            "available": False,
            "fallback_reason": _runtime_fallback_reason(exc),
        }

    return {"available": True}


class WorkerHeartbeatLoop:
    """Background heartbeat loop used while a long indexing job runs."""

    def __init__(
        self,
        worker_id: str,
        *,
        status: str,
        current_job: dict[str, Any] | None = None,
        interval_seconds: float | None = None,
    ) -> None:
        """Create a heartbeat loop for one worker/job context."""
        self.worker_id = worker_id
        self.status = status
        self.current_job = current_job
        self.interval_seconds = interval_seconds or max(
            1.0,
            _heartbeat_ttl_seconds() / 3,
        )
        self._stop_event = Event()
        self._thread: Thread | None = None

    def __enter__(self) -> "WorkerHeartbeatLoop":
        """Start the loop and write the first heartbeat immediately."""
        record_worker_heartbeat(
            self.worker_id,
            status=self.status,
            current_job=self.current_job,
        )
        self._thread = Thread(
            target=self._run,
            name=f"vector-worker-heartbeat-{_worker_key(self.worker_id)}",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        """Stop the loop without blocking worker shutdown for long."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        """Periodically refresh the heartbeat until stopped."""
        while not self._stop_event.wait(self.interval_seconds):
            record_worker_heartbeat(
                self.worker_id,
                status=self.status,
                current_job=self.current_job,
            )


def acquire_file_processing_lock(
    *,
    worker_id: str,
    user_id: int,
    file_id: object,
    job_id: object,
    index_version: int,
) -> VectorWorkerFileLock:
    """Acquire a short Redis lease for a single file indexing job."""
    key = _file_lock_key(user_id, file_id)
    token = secrets.token_urlsafe(18)
    value = json.dumps(
        {
            "token": token,
            "worker_key": _worker_key(worker_id),
            "job_id": str(job_id),
            "user_id": user_id,
            "file_id": str(file_id),
            "index_version": index_version,
            "acquired_at": _isoformat(_now_utc()),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    try:
        client = _get_runtime_client()
        acquired = bool(client.set(key, value, nx=True, ex=_file_lock_ttl_seconds()))
        if acquired:
            return VectorWorkerFileLock(
                key=key,
                value=value,
                acquired=True,
                available=True,
            )

        owner = _json_loads(client.get(key)) or {}
        return VectorWorkerFileLock(
            key=key,
            value=value,
            acquired=False,
            available=True,
            owner_job_id=owner.get("job_id"),
        )
    except Exception as exc:  # noqa: BLE001 - Redis 锁不可用时继续依赖 PostgreSQL
        return VectorWorkerFileLock(
            key=key,
            value=value,
            acquired=False,
            available=False,
            fallback_reason=_runtime_fallback_reason(exc),
        )


def release_file_processing_lock(lock: VectorWorkerFileLock | None) -> None:
    """Release a file lease if this worker acquired it."""
    if lock is None or not lock.acquired:
        return
    try:
        _get_runtime_client().eval(
            _RELEASE_LOCK_SCRIPT,
            1,
            lock.key,
            lock.value,
        )
    except Exception as exc:  # noqa: BLE001 - lock release failure is self-healing by TTL
        _runtime_fallback_reason(exc)


def record_worker_job_event(event: str) -> dict[str, Any]:
    """Increment a small Redis metric counter for worker runtime observability."""
    try:
        client = _get_runtime_client()
        now = _isoformat(_now_utc())
        key = _metrics_key()
        client.hincrby(key, event, 1)
        client.hset(
            key,
            mapping={
                "last_event": event,
                "last_event_at": now,
            },
        )
        client.expire(key, _METRICS_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001 - metrics must be best-effort
        return {
            "available": False,
            "fallback_reason": _runtime_fallback_reason(exc),
        }
    return {"available": True}


def _count_active_file_locks(client: Any) -> int:
    """Count live file lock keys for health output."""
    try:
        return sum(
            1
            for _ in client.scan_iter(
                match=f"{_file_lock_prefix()}*",
                count=200,
            )
        )
    except Exception:  # noqa: BLE001 - lock count is secondary runtime telemetry
        return 0


def _read_metrics(client: Any) -> dict[str, Any]:
    """Read worker runtime metrics from Redis."""
    try:
        metrics = client.hgetall(_metrics_key()) or {}
    except Exception:  # noqa: BLE001 - metrics are optional
        return {}

    numeric_metrics: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, str) and value.isdigit():
            numeric_metrics[key] = int(value)
        else:
            numeric_metrics[key] = value
    return numeric_metrics


def get_vector_worker_runtime_summary() -> dict[str, Any]:
    """Return Redis worker runtime summary for health endpoints."""
    if not config.REDIS_ENABLED:
        return {
            "redis_enabled": False,
            "redis_available": False,
            "redis_status": "disabled",
            "online_worker_count": 0,
            "workers": [],
            "last_heartbeat_at": None,
            "last_heartbeat_age_seconds": None,
            "heartbeat_ttl_seconds": _heartbeat_ttl_seconds(),
            "file_lock_ttl_seconds": _file_lock_ttl_seconds(),
            "active_file_lock_count": 0,
            "metrics": {},
        }

    try:
        client = _get_runtime_client()
        worker_keys = sorted(client.smembers(_workers_set_key()) or [])
        now = _now_utc()
        workers: list[dict[str, Any]] = []
        last_heartbeat_at: datetime | None = None

        for worker_key in worker_keys:
            heartbeat_key = _worker_heartbeat_key(str(worker_key))
            raw_value = client.get(heartbeat_key)
            payload = _json_loads(raw_value)
            heartbeat_at = _parse_datetime(
                payload.get("heartbeat_at") if payload else None,
            )
            if payload is None or heartbeat_at is None:
                client.srem(_workers_set_key(), worker_key)
                continue

            heartbeat_age_seconds = max(
                0.0,
                (now - heartbeat_at).total_seconds(),
            )
            if heartbeat_age_seconds > _heartbeat_ttl_seconds():
                client.delete(heartbeat_key)
                client.srem(_workers_set_key(), worker_key)
                continue

            last_heartbeat_at = (
                heartbeat_at
                if last_heartbeat_at is None
                else max(last_heartbeat_at, heartbeat_at)
            )
            workers.append(
                {
                    "worker_key": payload.get("worker_key") or worker_key,
                    "status": payload.get("status") or "unknown",
                    "current_job_id": payload.get("current_job_id"),
                    "current_user_id": payload.get("current_user_id"),
                    "current_file_id": payload.get("current_file_id"),
                    "current_index_version": payload.get(
                        "current_index_version",
                    ),
                    "heartbeat_at": _isoformat(heartbeat_at),
                    "heartbeat_age_seconds": round(heartbeat_age_seconds, 3),
                },
            )

        last_heartbeat_age_seconds = (
            round((now - last_heartbeat_at).total_seconds(), 3)
            if last_heartbeat_at is not None
            else None
        )

        return {
            "redis_enabled": True,
            "redis_available": True,
            "redis_status": "healthy",
            "online_worker_count": len(workers),
            "workers": workers,
            "last_heartbeat_at": (
                _isoformat(last_heartbeat_at)
                if last_heartbeat_at is not None
                else None
            ),
            "last_heartbeat_age_seconds": last_heartbeat_age_seconds,
            "heartbeat_ttl_seconds": _heartbeat_ttl_seconds(),
            "file_lock_ttl_seconds": _file_lock_ttl_seconds(),
            "active_file_lock_count": _count_active_file_locks(client),
            "metrics": _read_metrics(client),
        }
    except Exception as exc:  # noqa: BLE001 - health endpoint must degrade safely
        reason = _runtime_fallback_reason(exc)
        return {
            "redis_enabled": True,
            "redis_available": False,
            "redis_status": "unavailable",
            "redis_error_message": reason,
            "online_worker_count": 0,
            "workers": [],
            "last_heartbeat_at": None,
            "last_heartbeat_age_seconds": None,
            "heartbeat_ttl_seconds": _heartbeat_ttl_seconds(),
            "file_lock_ttl_seconds": _file_lock_ttl_seconds(),
            "active_file_lock_count": 0,
            "metrics": {},
        }
