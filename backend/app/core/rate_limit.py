from __future__ import annotations

import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        self._buckets.clear()

    def allow(self, *, key: str, limit: int, window_seconds: int, now: float | None = None) -> tuple[bool, int]:
        if limit <= 0:
            return True, 0

        current_time = now if now is not None else time.time()
        bucket = self._buckets[key]
        cutoff = current_time - window_seconds

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, int(bucket[0] + window_seconds - current_time))
            return False, retry_after

        bucket.append(current_time)
        return True, 0
