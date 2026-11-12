"""Per-user sliding-window rate limiter for quantum job submission (Section 9A, 14).

Guards against resource-abusive circuit submission being used as a DoS vector against
the shared simulator. In-process, matching the rest of the prototype's minimal-infra
posture (ADR-002).
"""

import time
import uuid
from collections import defaultdict, deque

from app.config import settings


class QuantumJobRateLimiter:
    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self._timestamps: dict[uuid.UUID, deque] = defaultdict(deque)

    def allow(self, user_id: uuid.UUID) -> bool:
        now = time.monotonic()
        window = self._timestamps[user_id]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.max_per_minute:
            return False
        window.append(now)
        return True


quantum_rate_limiter = QuantumJobRateLimiter(settings.quantum_jobs_per_user_per_minute)
