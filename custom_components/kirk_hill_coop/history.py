# Calculates delayed hourly custom windows in UK local time.
# Human checked: No

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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


# Calculates the next post-midnight delayed check for yesterday and monthly totals.
# Human checked: No
def next_past_data_check(now: datetime, minute: int, second: int) -> datetime:
    local_now = now.astimezone(UK_TZ)
    next_day = local_now.date() + timedelta(days=1)
    return delayed_check_for_local_date(next_day, minute, second)


# Returns the delayed post-midnight check for one explicit UK-local date.
# Human checked: No
def delayed_check_for_local_date(local_date: date, minute: int, second: int) -> datetime:
    scheduled_local = datetime(
        local_date.year,
        local_date.month,
        local_date.day,
        0,
        minute,
        second,
        tzinfo=UK_TZ,
    )
    return scheduled_local.astimezone(UTC)


# Returns the UK-local date whose yesterday data should be complete at the given refresh time.
# Human checked: No
def expected_yesterday_date(now: datetime) -> date:
    return now.astimezone(UK_TZ).date() - timedelta(days=1)


# Returns the UTC timestamp that marks the end of the requested UK-local yesterday.
# Human checked: No
def expected_yesterday_end_utc(now: datetime) -> datetime:
    return start_of_local_day_utc(now.astimezone(UK_TZ).date())


# Builds the current month-to-date window through the start of today in UK local time.
# Human checked: No
def build_this_month_window(now: datetime) -> HistoryWindow:
    local_today = now.astimezone(UK_TZ).date()
    month_start = local_today.replace(day=1)
    return _window_from_local_dates(month_start, local_today, f"month:{month_start.isoformat()}:{local_today.isoformat()}")


# Builds the previous full UK-local calendar month window.
# Human checked: No
def build_last_month_window(now: datetime) -> HistoryWindow:
    local_today = now.astimezone(UK_TZ).date()
    current_month_start = local_today.replace(day=1)
    previous_month_end = current_month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    return _window_from_local_dates(
        previous_month_start,
        current_month_start,
        f"month:{previous_month_start.isoformat()}:{current_month_start.isoformat()}",
    )


# Converts one UK-local date boundary into a UTC midnight marker for API comparisons.
# Human checked: No
def start_of_local_day_utc(local_date: date) -> datetime:
    return datetime(local_date.year, local_date.month, local_date.day, tzinfo=UK_TZ).astimezone(UTC)


# Normalises one local datetime span into explicit UTC boundaries for API requests.
# Human checked: No
def _window_from_local_datetimes(start: datetime, end: datetime, key: str) -> HistoryWindow:
    return HistoryWindow(key=key, from_utc=start.astimezone(UTC), to_utc=end.astimezone(UTC))


# Normalises one UK-local date span into explicit UTC boundaries for API requests.
# Human checked: No
def _window_from_local_dates(start: date, end: date, key: str) -> HistoryWindow:
    return _window_from_local_datetimes(
        datetime(start.year, start.month, start.day, tzinfo=UK_TZ),
        datetime(end.year, end.month, end.day, tzinfo=UK_TZ),
        key,
    )
