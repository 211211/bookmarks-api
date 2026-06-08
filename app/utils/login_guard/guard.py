"""In-memory login guard.

A process-local sliding-window failure counter with lockout. Good enough as a
baseline / single-worker defense; for multi-replica deployments back it with a
shared store (the interface lets you swap the implementation). Keyed by a
normalized identifier (the login email), so lockout applies per account
regardless of source IP.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.core.errors import TooManyAttemptsError
from app.utils.login_guard.interface import ILoginGuard


@dataclass
class _Entry:
    count: int = 0
    window_resets_at: float = 0.0
    locked_until: float = 0.0


class InMemoryLoginGuard(ILoginGuard):
    def __init__(
        self,
        *,
        max_failures: int,
        lockout_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max(1, max_failures)
        self._lockout = lockout_seconds
        self._clock = clock
        self._state: dict[str, _Entry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(identifier: str) -> str:
        return identifier.strip().lower()

    def assert_not_locked(self, identifier: str) -> None:
        now = self._clock()
        with self._lock:
            entry = self._state.get(self._key(identifier))
            if entry and entry.locked_until > now:
                retry_after = max(1, math.ceil(entry.locked_until - now))
                raise TooManyAttemptsError(
                    "Too many failed login attempts. Try again later.",
                    details={"retry_after_seconds": retry_after},
                    headers={"Retry-After": str(retry_after)},
                )

    def record_failure(self, identifier: str) -> None:
        now = self._clock()
        with self._lock:
            entry = self._state.setdefault(self._key(identifier), _Entry())
            # Start a fresh counting window if the previous one elapsed.
            if now > entry.window_resets_at:
                entry.count = 0
                entry.window_resets_at = now + self._lockout
            entry.count += 1
            if entry.count >= self._max:
                entry.locked_until = now + self._lockout

    def record_success(self, identifier: str) -> None:
        with self._lock:
            self._state.pop(self._key(identifier), None)

    def clear(self) -> None:
        """Drop all tracked state (used by tests / ops)."""
        with self._lock:
            self._state.clear()
