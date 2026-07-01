# Verifies separate hourly and past-data scheduling, including retries and month totals.
# Human checked: No

from datetime import UTC, date, datetime
from unittest.mock import Mock

import pytest

from custom_components.kirk_hill_coop import coordinator as coordinator_module
from custom_components.kirk_hill_coop.coordinator import KirkHillCoordinator
from custom_components.kirk_hill_coop.history import (
    build_last_month_window,
    build_this_month_window,
    next_live_check,
    next_hourly_check,
    next_past_data_check,
)
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


# Records named and custom range requests while returning stable snapshots for each requested window.
# Human checked: No
class FakeApi:
    """Minimal API test double."""

    # Starts with explicit named and custom responses so tests can assert exact sequencing.
    # Human checked: No
    def __init__(
        self,
        *,
        current_snapshot: KirkHillSnapshot | None = None,
        named_snapshots: dict[str, KirkHillSnapshot] | None = None,
        custom_snapshots: list[KirkHillSnapshot] | None = None,
    ) -> None:
        self.current_calls = 0
        self.named_ranges: list[str] = []
        self.custom_windows: list[tuple[datetime, datetime]] = []
        self._current_snapshot = current_snapshot or _current_snapshot()
        self._named_snapshots = named_snapshots or {"today": _today_snapshot(datetime(2026, 6, 30, 10, tzinfo=UTC))}
        self._custom_snapshots = list(custom_snapshots or [])

    # Returns one stable current snapshot while recording the refresh count.
    # Human checked: No
    async def fetch_current_snapshot(self, scope: str) -> KirkHillSnapshot:
        self.current_calls += 1
        return self._current_snapshot

    # Returns one stable named-range snapshot.
    # Human checked: No
    async def fetch_snapshot(self, requested_range: str, scope: str) -> KirkHillSnapshot:
        self.named_ranges.append(requested_range)
        return self._named_snapshots[requested_range]

    # Returns queued custom-window snapshots while recording their UTC boundaries.
    # Human checked: No
    async def fetch_custom_snapshot(self, from_utc: datetime, to_utc: datetime, scope: str) -> KirkHillSnapshot:
        self.custom_windows.append((from_utc, to_utc))
        if self._custom_snapshots:
            return self._custom_snapshots.pop(0)
        return _generation_total_snapshot(from_utc, 1.0)


# Confirms refreshes before the delayed threshold still catch up the latest eligible completed hour.
# Human checked: No
@pytest.mark.asyncio
async def test_first_update_fetches_latest_eligible_hour_before_threshold() -> None:
    api = FakeApi()
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        time_provider=FakeTimeProvider(datetime(2026, 6, 30, 15, 20, tzinfo=UTC)),
        hourly_minute=42,
        hourly_second=30,
        live_refresh_minutes=15,
        presumed_net_saving_rate_pence=None,
    )
    coordinator.data = _seed_snapshot(next_past_data_check_value=datetime(2026, 7, 1, 0, 42, 30, tzinfo=UTC))

    snapshot = await coordinator._async_update_data()

    assert api.current_calls == 1
    assert api.named_ranges == ["today"]
    assert api.custom_windows == [
        (
            datetime(2026, 6, 30, 13, 0, tzinfo=UTC),
            datetime(2026, 6, 30, 14, 0, tzinfo=UTC),
        )
    ]
    assert snapshot.last_hour_generation_kwh == 1
    assert snapshot.last_hour_window_end == datetime(2026, 6, 30, 14, 0, tzinfo=UTC)
    assert snapshot.next_latest_check == datetime(2026, 6, 30, 15, 27, 30, tzinfo=UTC)
    assert snapshot.next_hourly_check == datetime(2026, 6, 30, 15, 42, 30, tzinfo=UTC)
    assert snapshot.next_past_data_check == datetime(2026, 7, 1, 0, 42, 30, tzinfo=UTC)
    assert snapshot.last_poll == datetime(2026, 6, 30, 15, 20, tzinfo=UTC)
    assert snapshot.summary["total_generation_kwh"] == 1


# Confirms the first daytime load immediately backfills yesterday and month totals instead of waiting for midnight.
# Human checked: No
@pytest.mark.asyncio
async def test_first_daytime_load_backfills_past_data_immediately() -> None:
    now = datetime(2026, 7, 15, 14, 20, tzinfo=UTC)
    api = FakeApi(
        named_snapshots={
            "today": _today_snapshot(now),
            "yesterday": _yesterday_snapshot(19.453, "2026-07-14T23:00:00Z", "processing"),
        },
        custom_snapshots=[
            _generation_total_snapshot(datetime(2026, 7, 15, 12, tzinfo=UTC), 1.0),
            _generation_total_snapshot(datetime(2026, 6, 30, 23, tzinfo=UTC), 300.0),
            _generation_total_snapshot(datetime(2026, 5, 31, 23, tzinfo=UTC), 450.0),
        ],
    )
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        time_provider=FakeTimeProvider(now),
        hourly_minute=42,
        hourly_second=30,
        live_refresh_minutes=15,
        presumed_net_saving_rate_pence=15.0,
    )

    snapshot = await coordinator._async_update_data()

    assert api.named_ranges == ["today", "yesterday"]
    assert len(api.custom_windows) == 3
    assert snapshot.generation_yesterday_kwh == 19.453
    assert snapshot.generation_this_month_kwh == 300.0
    assert snapshot.generation_last_month_kwh == 450.0
    assert snapshot.next_past_data_check == datetime(2026, 7, 15, 23, 42, 30, tzinfo=UTC)


# Confirms the delayed hourly fetch exposes the previous whole BST hour after the chosen trigger time.
# Human checked: No
@pytest.mark.asyncio
async def test_hourly_archive_uses_previous_whole_bst_hour() -> None:
    api = FakeApi()
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        time_provider=FakeTimeProvider(datetime(2026, 6, 30, 15, 42, 30, tzinfo=UTC)),
        hourly_minute=42,
        hourly_second=30,
        live_refresh_minutes=15,
        presumed_net_saving_rate_pence=None,
    )
    coordinator.data = _seed_snapshot(next_past_data_check_value=datetime(2026, 7, 1, 0, 42, 30, tzinfo=UTC))

    snapshot = await coordinator._async_update_data()

    assert api.custom_windows[-1] == (
        datetime(2026, 6, 30, 14, 0, tzinfo=UTC),
        datetime(2026, 6, 30, 15, 0, tzinfo=UTC),
    )
    assert snapshot.last_hour_generation_kwh == 1
    assert snapshot.last_hour_window_end == datetime(2026, 6, 30, 15, 0, tzinfo=UTC)
    assert snapshot.next_hourly_check == datetime(2026, 6, 30, 16, 42, 30, tzinfo=UTC)


# Confirms the delayed hourly fetch exposes the previous whole GMT hour in winter.
# Human checked: No
@pytest.mark.asyncio
async def test_hourly_archive_uses_previous_whole_gmt_hour() -> None:
    api = FakeApi()
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        time_provider=FakeTimeProvider(datetime(2026, 1, 30, 12, 42, 30, tzinfo=UTC)),
        hourly_minute=42,
        hourly_second=30,
        live_refresh_minutes=15,
        presumed_net_saving_rate_pence=None,
    )
    coordinator.data = _seed_snapshot(next_past_data_check_value=datetime(2026, 1, 31, 0, 42, 30, tzinfo=UTC))

    await coordinator._async_update_data()

    assert api.custom_windows[-1] == (
        datetime(2026, 1, 30, 11, 0, tzinfo=UTC),
        datetime(2026, 1, 30, 12, 0, tzinfo=UTC),
    )


# Confirms the next delayed hourly check advances to the next GMT hour after the threshold passes.
# Human checked: No
def test_next_hourly_check_rolls_to_next_gmt_hour() -> None:
    assert next_hourly_check(datetime(2026, 1, 30, 12, 42, 30, tzinfo=UTC), 42, 30) == datetime(
        2026, 1, 30, 13, 42, 30, tzinfo=UTC
    )


# Confirms live polling uses the hourly offset as its anchor so every cadence hits the hourly archive slot.
# Human checked: No
def test_next_live_check_uses_hourly_anchor() -> None:
    assert next_live_check(datetime(2026, 1, 30, 12, 42, 30, tzinfo=UTC), 42, 30, 15) == datetime(
        2026, 1, 30, 12, 57, 30, tzinfo=UTC
    )
    assert next_live_check(datetime(2026, 1, 30, 12, 41, 0, tzinfo=UTC), 42, 30, 15) == datetime(
        2026, 1, 30, 12, 42, 30, tzinfo=UTC
    )


# Confirms past-data checks point to the next delayed post-midnight slot in BST.
# Human checked: No
def test_next_past_data_check_targets_next_bst_midnight_slot() -> None:
    assert next_past_data_check(datetime(2026, 6, 30, 12, 0, tzinfo=UTC), 35, 0) == datetime(
        2026, 6, 30, 23, 35, 0, tzinfo=UTC
    )


# Confirms past-data checks point to the next delayed post-midnight slot in GMT.
# Human checked: No
def test_next_past_data_check_targets_next_gmt_midnight_slot() -> None:
    assert next_past_data_check(datetime(2026, 1, 30, 13, 0, tzinfo=UTC), 35, 0) == datetime(
        2026, 1, 31, 0, 35, 0, tzinfo=UTC
    )


# Confirms successful yesterday data refreshes month totals and moves the next past-data check to the next day.
# Human checked: No
@pytest.mark.asyncio
async def test_past_data_refresh_fetches_yesterday_and_months_once_complete() -> None:
    now = datetime(2026, 7, 15, 23, 42, 30, tzinfo=UTC)
    api = FakeApi(
        named_snapshots={
            "today": _today_snapshot(now),
            "yesterday": _yesterday_snapshot(19.453, "2026-07-15T23:00:00Z", "processing"),
        },
        custom_snapshots=[
            _generation_total_snapshot(datetime(2026, 7, 15, 22, tzinfo=UTC), 1.0),
            _generation_total_snapshot(datetime(2026, 6, 30, 23, tzinfo=UTC), 300.0),
            _generation_total_snapshot(datetime(2026, 5, 31, 23, tzinfo=UTC), 450.0),
        ],
    )
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        time_provider=FakeTimeProvider(now),
        hourly_minute=42,
        hourly_second=30,
        live_refresh_minutes=15,
        presumed_net_saving_rate_pence=15.0,
    )

    snapshot = await coordinator._async_update_data()

    assert api.named_ranges == ["today", "yesterday"]
    assert len(api.custom_windows) == 3
    this_month_window = build_this_month_window(now)
    last_month_window = build_last_month_window(now)
    assert api.custom_windows[1] == (this_month_window.from_utc, this_month_window.to_utc)
    assert api.custom_windows[2] == (last_month_window.from_utc, last_month_window.to_utc)
    assert snapshot.generation_yesterday_kwh == 19.453
    assert snapshot.generation_this_month_kwh == 300.0
    assert snapshot.generation_last_month_kwh == 450.0
    assert snapshot.savings_yesterday_pence == pytest.approx(291.795)
    assert snapshot.savings_this_month_pence == 4500.0
    assert snapshot.savings_last_month_pence == 6750.0
    assert snapshot.completed_yesterday_date == date(2026, 7, 15)
    assert snapshot.next_past_data_check == datetime(2026, 7, 16, 23, 42, 30, tzinfo=UTC)


# Confirms incomplete yesterday data publishes partial totals and retries one hour later.
# Human checked: No
@pytest.mark.asyncio
async def test_past_data_refresh_retries_hourly_when_yesterday_is_incomplete() -> None:
    now = datetime(2026, 6, 30, 23, 42, 30, tzinfo=UTC)
    api = FakeApi(
        named_snapshots={
            "today": _today_snapshot(now),
            "yesterday": _yesterday_snapshot(10.0, "2026-06-29T22:00:00Z", "processing"),
        },
        custom_snapshots=[_generation_total_snapshot(datetime(2026, 6, 30, 22, tzinfo=UTC), 1.0)],
    )
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        time_provider=FakeTimeProvider(now),
        hourly_minute=42,
        hourly_second=30,
        live_refresh_minutes=15,
        presumed_net_saving_rate_pence=12.0,
    )

    snapshot = await coordinator._async_update_data()

    assert api.named_ranges == ["today", "yesterday"]
    assert len(api.custom_windows) == 1
    assert snapshot.generation_yesterday_kwh == 10.0
    assert snapshot.generation_this_month_kwh is None
    assert snapshot.generation_last_month_kwh is None
    assert snapshot.savings_yesterday_pence == 120.0
    assert snapshot.next_past_data_check == datetime(2026, 7, 1, 0, 42, 30, tzinfo=UTC)
    assert snapshot.completed_yesterday_date is None


# Confirms ordinary daytime refreshes skip yesterday and month fetches once the next past-data check is tomorrow.
# Human checked: No
@pytest.mark.asyncio
async def test_daytime_refreshes_do_not_refetch_past_data_when_not_due() -> None:
    now = datetime(2026, 6, 30, 15, 42, 30, tzinfo=UTC)
    api = FakeApi(custom_snapshots=[_generation_total_snapshot(datetime(2026, 6, 30, 14, tzinfo=UTC), 1.0)])
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        time_provider=FakeTimeProvider(now),
        hourly_minute=42,
        hourly_second=30,
        live_refresh_minutes=15,
        presumed_net_saving_rate_pence=15.0,
    )
    coordinator.data = _seed_snapshot(
        next_past_data_check_value=datetime(2026, 6, 30, 23, 42, 30, tzinfo=UTC),
        generation_yesterday_kwh=19.453,
        generation_this_month_kwh=300.0,
        generation_last_month_kwh=450.0,
        completed_yesterday_date=date(2026, 6, 29),
    )

    snapshot = await coordinator._async_update_data()

    assert api.named_ranges == ["today"]
    assert len(api.custom_windows) == 1
    assert snapshot.generation_yesterday_kwh == 19.453
    assert snapshot.generation_this_month_kwh == 300.0
    assert snapshot.generation_last_month_kwh == 450.0
    assert snapshot.next_past_data_check == datetime(2026, 6, 30, 23, 42, 30, tzinfo=UTC)


# Confirms live-only refreshes do not touch the archive endpoints before the hourly slot is due.
# Human checked: No
@pytest.mark.asyncio
async def test_live_only_refresh_preserves_archive_data() -> None:
    now = datetime(2026, 6, 30, 15, 27, 30, tzinfo=UTC)
    api = FakeApi()
    coordinator = KirkHillCoordinator(
        hass=None,
        api=api,
        scope="owner",
        time_provider=FakeTimeProvider(now),
        hourly_minute=42,
        hourly_second=30,
        live_refresh_minutes=15,
        presumed_net_saving_rate_pence=None,
    )
    coordinator.data = _seed_snapshot(
        next_past_data_check_value=datetime(2026, 7, 1, 0, 42, 30, tzinfo=UTC),
        next_latest_check_value=now,
        next_hourly_check_value=datetime(2026, 6, 30, 15, 42, 30, tzinfo=UTC),
    )

    snapshot = await coordinator._async_update_data()

    assert api.current_calls == 1
    assert api.named_ranges == []
    assert api.custom_windows == []
    assert snapshot.summary["total_generation_kwh"] == 1
    assert snapshot.last_poll == now
    assert snapshot.next_latest_check == datetime(2026, 6, 30, 15, 42, 30, tzinfo=UTC)
    assert snapshot.next_hourly_check == datetime(2026, 6, 30, 15, 42, 30, tzinfo=UTC)


# Confirms the scheduler targets the earliest live-or-archive slot rather than drifting from startup time.
# Human checked: No
def test_schedule_refresh_targets_next_delayed_check(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_when: list[datetime] = []

    # Captures whichever UTC time the coordinator schedules next so the test can assert it directly.
    # Human checked: No
    def _capture_schedule(hass, action, point_in_time):
        captured_when.append(point_in_time)
        return lambda: None

    monkeypatch.setattr(coordinator_module, "async_track_point_in_utc_time", _capture_schedule)
    coordinator = KirkHillCoordinator(
        hass=Mock(),
        api=FakeApi(),
        scope="owner",
        time_provider=FakeTimeProvider(datetime(2026, 6, 30, 19, 12, tzinfo=UTC)),
        hourly_minute=53,
        hourly_second=0,
        live_refresh_minutes=15,
        presumed_net_saving_rate_pence=None,
    )

    coordinator._schedule_refresh()

    assert captured_when == [datetime(2026, 6, 30, 19, 23, tzinfo=UTC)]


# Builds a stable today-range snapshot for coordinator tests.
# Human checked: No
def _today_snapshot(stamp: datetime) -> KirkHillSnapshot:
    return KirkHillSnapshot(
        summary={"total_generation_kwh": 1, "latest_import_status": "success"},
        generation=(GenerationPoint(stamp, 1),),
        wind_speed=(WindSpeedPoint(stamp, 8),),
        turbines=(),
    )


# Builds a yesterday snapshot with explicit completion metadata.
# Human checked: No
def _yesterday_snapshot(total_kwh: float, latest_end: str, status: str) -> KirkHillSnapshot:
    stamp = datetime.fromisoformat(latest_end.replace("Z", "+00:00"))
    return KirkHillSnapshot(
        summary={
            "total_generation_kwh": total_kwh,
            "latest_generation_interval_end": latest_end,
            "latest_import_status": status,
        },
        generation=(GenerationPoint(stamp, total_kwh),),
        wind_speed=(WindSpeedPoint(stamp, 8),),
        turbines=(),
    )


# Builds a custom-window snapshot that only needs to expose a stable total generation value.
# Human checked: No
def _generation_total_snapshot(stamp: datetime, total_kwh: float) -> KirkHillSnapshot:
    return KirkHillSnapshot(
        summary={"total_generation_kwh": total_kwh},
        generation=(GenerationPoint(stamp, total_kwh),),
        wind_speed=(WindSpeedPoint(stamp, 8),),
        turbines=(),
    )


# Builds a stable current-endpoint snapshot for coordinator tests.
# Human checked: No
def _current_snapshot() -> KirkHillSnapshot:
    return KirkHillSnapshot(
        summary={},
        generation=(),
        wind_speed=(),
        turbines=(),
        current_reading={"generated_at": "2026-06-30T10:00:00Z", "source_interval": "1m", "complete": True},
        current_summary={
            "total_power_kw": 0.202,
            "wind_speed_mps": 4.96,
            "capacity_factor_percent": 9.47,
            "active_turbines": 8,
            "capacity_watts": 18_800_000,
        },
        current_turbines=({"id": "T1"},),
    )


# Seeds a previous snapshot so tests can exercise refreshes without retriggering past-data fetches.
# Human checked: No
def _seed_snapshot(
    *,
    next_past_data_check_value: datetime,
    next_latest_check_value: datetime | None = None,
    next_hourly_check_value: datetime | None = None,
    generation_yesterday_kwh: float | None = None,
    generation_this_month_kwh: float | None = None,
    generation_last_month_kwh: float | None = None,
    completed_yesterday_date: date | None = None,
) -> KirkHillSnapshot:
    stamp = datetime(2026, 6, 30, 10, tzinfo=UTC)
    return KirkHillSnapshot(
        summary={"total_generation_kwh": 1},
        generation=(GenerationPoint(stamp, 1),),
        wind_speed=(WindSpeedPoint(stamp, 8),),
        turbines=(),
        current_reading={"generated_at": "2026-06-30T10:00:00Z", "source_interval": "1m", "complete": True},
        current_summary={"total_power_kw": 0.202, "wind_speed_mps": 4.96, "active_turbines": 8, "capacity_watts": 18_800_000},
        next_past_data_check=next_past_data_check_value,
        next_latest_check=next_latest_check_value,
        next_hourly_check=next_hourly_check_value,
        generation_yesterday_kwh=generation_yesterday_kwh,
        generation_this_month_kwh=generation_this_month_kwh,
        generation_last_month_kwh=generation_last_month_kwh,
        completed_yesterday_date=completed_yesterday_date,
    )
