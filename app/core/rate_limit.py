"""
app/core/rate_limit.py

Batch G: a small in-memory sliding-window rate limiter for the three
places this app is most exposed to brute-force/abuse — login, OTP
send, and OTP verify. Deliberately NOT a new infrastructure dependency
(no Redis, no external service): correct for the single-process
deployment this app runs as today, same "start simple, note the real
limitation" approach as core/donut_chart.py (CSS instead of a charting
library) and the registration OTP tokens (signed cookie instead of a
DB table).

Explicitly NOT correct once this app runs behind more than one worker
process or more than one instance (each process keeps its own
in-memory counters, so the effective limit multiplies by process
count) — see PROJECT_STATUS.md. Swapping the storage for Redis at that
point is a change confined to this one file; nothing that calls
`check()` needs to change.

Existing account-level lockout (services/auth_service.py,
LOCKOUT_THRESHOLD/LOCKOUT_DURATION) already stops repeated guesses
against ONE account. This limiter adds the complementary layer that
was missing: a cap on requests from one IP/email regardless of which
account(s) they target — the case account lockout does nothing for
(spraying one password across many different emails from one IP, or
hammering the OTP-send endpoint for a single email to run up the
platform's email bill / spam a real inbox).
"""
import threading
import time

from app.core.exceptions import RateLimitExceededException

_lock = threading.Lock()
# {bucket_key: [timestamp, timestamp, ...]} — timestamps of attempts still
# inside the current window for that key. Pruned lazily on each check().
_attempts: dict[str, list[float]] = {}


def check(bucket: str, identity: str, *, max_attempts: int, window_seconds: int) -> None:
    """
    Records one attempt for (bucket, identity) and raises
    RateLimitExceededException if that combination has exceeded
    `max_attempts` within the last `window_seconds`. Call this ONCE per
    incoming request, before doing the expensive/sensitive work (password
    check, OTP send, OTP compare) — an attempt that gets rate-limited
    still counts as an attempt, which is what makes this a real limiter
    rather than a bypassable counter.

    `bucket` separates independent limiters (e.g. "login" vs "otp_send")
    sharing the same identity space; `identity` is whatever the caller
    wants throttled by — an IP address, an email address, a token hash.
    """
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
    """Clears a key's recorded attempts — used after a SUCCESSFUL login,
    so a legitimate user who mistyped their password a couple of times
    isn't left sitting close to the IP-wide limit for the rest of the
    window. Safe to call even if the key was never recorded."""
    key = f"{bucket}:{identity}"
    with _lock:
        _attempts.pop(key, None)
