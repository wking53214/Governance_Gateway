"""Accept and reject counts for the Governance Gateway.

The dashboard records outcomes only. It reads each finished decision and
counts it. It never changes what the gateway accepts or rejects.

What it counts:

  - how many artifacts were evaluated, accepted, and rejected
  - why each rejection happened, by reason code
"""

from __future__ import annotations

import threading
from collections import Counter
from typing import Any

from .models import GateResult

#: Label used when a rejection carries no reason code.
NO_REASON = "NO_REASON"


class GateDashboard:
    """Counts gateway decisions. Safe to share across threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total = 0
        self._accepted = 0
        self._rejections: Counter[str] = Counter()

    def record(self, result: GateResult) -> None:
        """Count one finished decision."""
        with self._lock:
            self._total += 1
            if result.accepted:
                self._accepted += 1
            else:
                key = result.reason.value if result.reason is not None else NO_REASON
                self._rejections[key] += 1

    def snapshot(self) -> dict[str, Any]:
        """Return the current figures as a plain dictionary."""
        with self._lock:
            total = self._total
            accepted = self._accepted
            rejections = dict(self._rejections)

        return {
            "total_evaluations": total,
            "accepted": accepted,
            "rejected": total - accepted,
            "accept_rate": round(accepted / total, 4) if total else 0.0,
            "rejections_by_reason": rejections,
        }


__all__ = ["GateDashboard", "NO_REASON"]
