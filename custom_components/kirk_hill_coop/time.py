# Provides a simple injectable time source so tests can control current UK/UTC boundary logic.
# Human checked: No

from datetime import UTC, datetime
from typing import Protocol


# Describes the only clock capability needed by coordinator scheduling logic.
# Human checked: No
class TimeProvider(Protocol):
    """Return the current timezone-aware UTC timestamp."""

    def now(self) -> datetime:
        """Return the current UTC time."""


# Uses the real system clock in production while keeping tests free to substitute their own time.
# Human checked: No
class UtcTimeProvider:
    """Production time source for bootstrap and hourly archive scheduling."""

    # Returns the current UTC time with explicit timezone information.
    # Human checked: No
    def now(self) -> datetime:
        return datetime.now(UTC)
