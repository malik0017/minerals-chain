"""
app/core/rate_limit.py
"""
import threading
import time

from app.core.exceptions import RateLimitExceededException

_lock = threading.Lock()
_attempts: dict[str, list[float]] = {}


def check(bucket: str, identity: str, *, max_attempts: int, window_seconds: int) -> None:

    key = f"{bucket}:{identity}"
    now = time.monotonic()
    cutoff = now - window_seconds

    with _lock:
        timestamps = [t for t in _attempts.get(key, []) if t > cutoff]

        if len(timestamps) >= max_attempts:
            retry_after = int(window_seconds - (now - timestamps[0])) + 1
            _attempts[key] = timestamps  # keep pruned list even on rejection
            raise RateLimitExceededException(retry_after_seconds=max(retry_after, 1))

        timestamps.append(now)
        _attempts[key] = timestamps


def reset(bucket: str, identity: str) -> None:
    key = f"{bucket}:{identity}"
    with _lock:
        _attempts.pop(key, None)
