# Verifies today refreshes and delayed whole-hour scheduling for the visible last-hour sensor.
# Human checked: No

from datetime import UTC, datetime

import pytest

from custom_components.kirk_hill_coop.coordinator import KirkHillCoordinator
from custom_components.kirk_hill_coop.models import GenerationPoint, KirkHillSnapshot, WindSpeedPoint


# Returns controlled UTC times so coordinator scheduling can be checked across GMT and BST.
# Human checked: No
class FakeTimeProvider:
    """Deterministic test clock."""

    # Captures the exact current time the coordinator should observe.
    # Human checked: No
    def __init__(self, now: datetime) -> None:
        self._now = now

    # Returns the controlled current time.
    # Human checked: No
    def now(self) -> datetime:
        return self._now


# Records named and custom range requests while returning simple timestamped snapshots.
# Human checked: No
class FakeApi:
    """Minimal API test double."""

    # Starts with no requests so tests can assert exact sequencing.
    # Human checked: No
    def __init__(self) -> None:
        self.named_ranges: list[str] = []
        self.custom_windows: list[tuple[datetime, datetime]] = []

    # Returns one stable named-range snapshot.
    # Human checked: No
    async def fetch_snapshot(self, requested_range: str, scope: str) -> KirkHillSnapshot:
        self.named_ranges.append(requested_range)
        return _snapshot(datetime(2026, 6, 30, 10, tzinfo=UTC))

    # Returns one stable custom-window snapshot while recording its UTC boundaries.
    # Human checked: No
    async def fetch_custom_snapshot(self, from_utc: datetime, to_utc: datetime, scope: str) -> KirkHillSnapshot:
        self.custom_windows.append((from_utc, to_utc))
        return _snapshot(from_utc)


# Confirms refreshes before the delayed threshold still catch up the latest eligible completed hour.
# Human checked: No
@pytest.mark.asyncio
async def test_first_update_fetches_latest_eligible_hour_before_threshold() -> None:
    api = FakeApi()
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        update_interval=None,
        time_provider=FakeTimeProvider(datetime(2026, 6, 30, 15, 20, tzinfo=UTC)),
        hourly_minute=42,
        hourly_second=30,
    )

    snapshot = await coordinator._async_update_data()

    assert api.named_ranges == ["today"]
    assert api.custom_windows == [
        (
            datetime(2026, 6, 30, 13, 0, tzinfo=UTC),
            datetime(2026, 6, 30, 14, 0, tzinfo=UTC),
        )
    ]
    assert snapshot.last_hour_generation_kwh == 1
    assert snapshot.last_hour_window_end == datetime(2026, 6, 30, 14, 0, tzinfo=UTC)
    assert snapshot.next_hourly_check == datetime(2026, 6, 30, 15, 42, 30, tzinfo=UTC)
    assert snapshot.last_successful_poll == datetime(2026, 6, 30, 15, 20, tzinfo=UTC)
    assert snapshot.summary["total_generation_kwh"] == 1


# Confirms the delayed hourly fetch exposes the previous whole BST hour after the chosen trigger time.
# Human checked: No
@pytest.mark.asyncio
async def test_hourly_archive_uses_previous_whole_bst_hour() -> None:
    api = FakeApi()
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        update_interval=None,
        time_provider=FakeTimeProvider(datetime(2026, 6, 30, 15, 42, 30, tzinfo=UTC)),
        hourly_minute=42,
        hourly_second=30,
    )

    snapshot = await coordinator._async_update_data()

    assert api.custom_windows[-1] == (
        datetime(2026, 6, 30, 14, 0, tzinfo=UTC),
        datetime(2026, 6, 30, 15, 0, tzinfo=UTC),
    )
    assert snapshot.last_hour_generation_kwh == 1
    assert snapshot.last_hour_window_end == datetime(2026, 6, 30, 15, 0, tzinfo=UTC)
    assert snapshot.next_hourly_check == datetime(2026, 6, 30, 16, 42, 30, tzinfo=UTC)
    assert snapshot.last_successful_poll == datetime(2026, 6, 30, 15, 42, 30, tzinfo=UTC)


# Confirms the delayed hourly fetch exposes the previous whole GMT hour in winter.
# Human checked: No
@pytest.mark.asyncio
async def test_hourly_archive_uses_previous_whole_gmt_hour() -> None:
    api = FakeApi()
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        update_interval=None,
        time_provider=FakeTimeProvider(datetime(2026, 1, 30, 12, 42, 30, tzinfo=UTC)),
        hourly_minute=42,
        hourly_second=30,
    )

    await coordinator._async_update_data()

    assert api.custom_windows[-1] == (
        datetime(2026, 1, 30, 11, 0, tzinfo=UTC),
        datetime(2026, 1, 30, 12, 0, tzinfo=UTC),
    )


# Confirms the next delayed hourly check advances to the next GMT hour after the threshold passes.
# Human checked: No
def test_next_hourly_check_rolls_to_next_gmt_hour() -> None:
    from custom_components.kirk_hill_coop.history import next_hourly_check

    assert next_hourly_check(datetime(2026, 1, 30, 12, 42, 30, tzinfo=UTC), 42, 30) == datetime(
        2026, 1, 30, 13, 42, 30, tzinfo=UTC
    )


# Builds one consistent snapshot for both named and custom API test doubles.
# Human checked: No
def _snapshot(stamp: datetime) -> KirkHillSnapshot:
    return KirkHillSnapshot(
        summary={"total_generation_kwh": 1},
        generation=(GenerationPoint(stamp, 1),),
        wind_speed=(WindSpeedPoint(stamp, 8),),
        turbines=(),
    )
