from __future__ import annotations

import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int]:
        now = time.time()
        queue = self._requests[key]

        while queue and (now - queue[0]) > self.window_seconds:
            queue.popleft()

        if len(queue) >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - (now - queue[0])))
            return False, retry_after

        queue.append(now)
        return True, 0
