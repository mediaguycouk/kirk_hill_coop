# Calculates delayed hourly custom windows in UK local time.
# Human checked: No

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

UK_TZ = ZoneInfo("Europe/London")


# Carries one custom API window in both UTC and a stable key for duplicate prevention.
# Human checked: No
@dataclass(frozen=True, slots=True)
class HistoryWindow:
    """One custom API window that can be identified uniquely."""

    key: str
    from_utc: datetime
    to_utc: datetime


# Returns the most recent completed whole UK-local hour whose delayed fetch point has passed.
# Human checked: No
def build_latest_eligible_hour_window(now: datetime, minute: int, second: int) -> HistoryWindow:
    local_now = now.astimezone(UK_TZ)
    current_hour_start = local_now.replace(minute=0, second=0, microsecond=0)
    if should_archive_previous_hour(now, minute, second):
        previous_hour_start = current_hour_start - timedelta(hours=1)
    else:
        previous_hour_start = current_hour_start - timedelta(hours=2)
    return _window_from_local_datetimes(
        previous_hour_start,
        previous_hour_start + timedelta(hours=1),
        f"hour:{previous_hour_start.strftime('%Y-%m-%dT%H')}",
    )


# Picks one stable delayed trigger per config entry so installs spread load without drifting.
# Human checked: No
def calculate_hourly_offset(entry_id: str) -> tuple[int, int]:
    checksum = sum(ord(char) for char in entry_id)
    return 30 + (checksum % 30), 30 + ((checksum // 30) % 30)


# Decides whether this refresh should fetch the previous full hour for the configured offset.
# Human checked: No
def should_archive_previous_hour(now: datetime, minute: int, second: int) -> bool:
    local_now = now.astimezone(UK_TZ)
    return (local_now.minute, local_now.second) >= (minute, second)


# Calculates the next delayed hourly check in UK local time and returns it as a UTC timestamp.
# Human checked: No
def next_hourly_check(now: datetime, minute: int, second: int) -> datetime:
    local_now = now.astimezone(UK_TZ)
    scheduled = local_now.replace(minute=minute, second=second, microsecond=0)
    if scheduled <= local_now:
        scheduled += timedelta(hours=1)
    return scheduled.astimezone(UTC)


# Normalises one local datetime span into explicit UTC boundaries for API requests.
# Human checked: No
def _window_from_local_datetimes(start: datetime, end: datetime, key: str) -> HistoryWindow:
    return HistoryWindow(key=key, from_utc=start.astimezone(UTC), to_utc=end.astimezone(UTC))
