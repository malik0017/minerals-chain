"""
app/core/rate_limit.py
"""
import threading
import time
import uuid

from app.core.config import settings
from app.core.exceptions import RateLimitExceededException

_lock = threading.Lock()
_attempts: dict[str, list[float]] = {}
_redis = None
_redis_error: str | None = None


def _client():
    global _redis, _redis_error
    if not settings.REDIS_URL:
        return None
    if _redis is None and _redis_error is None:
        try:
            import redis
            client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1, socket_connect_timeout=1)
            client.ping()
            _redis = client
        except Exception as exc:
            _redis_error = str(exc)[:200]
    return _redis


def backend() -> dict:
    client = _client()
    if client is not None:
        return {"name": "redis", "ok": True, "detail": "Redis — shared across all workers."}
    if settings.REDIS_URL:
        return {"name": "memory", "ok": False, "detail": f"REDIS_URL set but unreachable ({_redis_error}). Falling back to memory."}
    return {"name": "memory", "ok": False, "detail": "In-memory, per process."}


def _check_redis(client, key: str, max_attempts: int, window_seconds: int) -> None:
    now = time.time()
    zkey = f"rl:{key}"
    pipe = client.pipeline()
    pipe.zremrangebyscore(zkey, 0, now - window_seconds)
    pipe.zcard(zkey)
    pipe.zrange(zkey, 0, 0, withscores=True)
    _, count, oldest = pipe.execute()
    if count >= max_attempts:
        first = oldest[0][1] if oldest else now
        raise RateLimitExceededException(retry_after_seconds=max(int(window_seconds - (now - first)) + 1, 1))
    pipe = client.pipeline()
    pipe.zadd(zkey, {f"{now}:{uuid.uuid4().hex[:6]}": now})
    pipe.expire(zkey, window_seconds)
    pipe.execute()


def check(bucket: str, identity: str, *, max_attempts: int, window_seconds: int) -> None:
    key = f"{bucket}:{identity}"
    client = _client()
    if client is not None:
        try:
            return _check_redis(client, key, max_attempts, window_seconds)
        except RateLimitExceededException:
            raise
        except Exception:
            pass
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        timestamps = [t for t in _attempts.get(key, []) if t > cutoff]
        if len(timestamps) >= max_attempts:
            retry_after = int(window_seconds - (now - timestamps[0])) + 1
            _attempts[key] = timestamps
            raise RateLimitExceededException(retry_after_seconds=max(retry_after, 1))
        timestamps.append(now)
        _attempts[key] = timestamps


def reset(bucket: str, identity: str) -> None:
    key = f"{bucket}:{identity}"
    client = _client()
    if client is not None:
        try:
            client.delete(f"rl:{key}")
        except Exception:
            pass
    with _lock:
        _attempts.pop(key, None)
