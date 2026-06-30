# Coordinates today-range and delayed last-hour refreshes for all entities.
# Human checked: No

import logging
from datetime import datetime

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KirkHillApiClient, KirkHillApiError
from .const import DOMAIN, RUNTIME_RANGE
from .history import (
    UK_TZ,
    build_last_month_window,
    build_latest_eligible_hour_window,
    build_this_month_window,
    delayed_check_for_local_date,
    expected_yesterday_date,
    expected_yesterday_end_utc,
    next_hourly_check,
    next_past_data_check,
)
from .models import KirkHillSnapshot
from .time import TimeProvider

_LOGGER = logging.getLogger(__name__)


# Shares one current snapshot and, when ready, one last-hour snapshot for Home Assistant sensors.
# Human checked: No
class KirkHillCoordinator(DataUpdateCoordinator[KirkHillSnapshot]):
    """Coordinate Kirk Hill data updates."""

    # Receives explicit dependencies so API and time-sensitive logic stay testable.
    # Human checked: No
    def __init__(
        self,
        hass: HomeAssistant,
        api: KirkHillApiClient,
        scope: str,
        time_provider: TimeProvider,
        hourly_minute: int,
        hourly_second: int,
        presumed_net_saving_rate_pence: float | None,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self._api = api
        self._time_provider = time_provider
        self.scope = scope
        self._hourly_minute = hourly_minute
        self._hourly_second = hourly_second
        self._presumed_net_saving_rate_pence = presumed_net_saving_rate_pence
        self._last_hour_window_key: str | None = None

    # Schedules the next refresh for the exact advertised delayed-check timestamp instead of one hour from startup.
    # Human checked: No
    @callback
    def _schedule_refresh(self) -> None:
        if self.config_entry and self.config_entry.pref_disable_polling:
            return

        self._async_unsub_refresh()
        scheduled_check = next_hourly_check(
            self._time_provider.now(),
            self._hourly_minute,
            self._hourly_second,
        )
        self._unsub_refresh = async_track_point_in_utc_time(
            self.hass,
            self._handle_refresh_interval,
            scheduled_check,
        )

    # Refreshes today and, once the delayed trigger has passed, also refreshes the previous whole hour.
    # Human checked: No
    async def _async_update_data(self) -> KirkHillSnapshot:
        try:
            now = self._time_provider.now()
            today = await self._api.fetch_snapshot(RUNTIME_RANGE, self.scope)
            with_last_hour = await self._with_last_hour_data(now, today)
            return await self._with_past_data(now, with_last_hour)
        except KirkHillApiError as err:
            raise UpdateFailed(f"Unable to update Kirk Hill data for scope={self.scope}: {err}") from err

    # Adds the latest eligible complete hour and catches up gracefully after restarts or reloads.
    # Human checked: No
    async def _with_last_hour_data(self, now, today: KirkHillSnapshot) -> KirkHillSnapshot:
        last_hour_generation = self.data.last_hour_generation_kwh if self.data else None
        last_hour_window_end = self.data.last_hour_window_end if self.data else None
        scheduled_check = next_hourly_check(now, self._hourly_minute, self._hourly_second)
        window = build_latest_eligible_hour_window(now, self._hourly_minute, self._hourly_second)
        if self._last_hour_window_key != window.key:
            hourly = await self._api.fetch_custom_snapshot(window.from_utc, window.to_utc, self.scope)
            last_hour_generation = hourly.summary.get("total_generation_kwh")
            last_hour_window_end = window.to_utc
            self._last_hour_window_key = window.key
            _LOGGER.info("Fetched Kirk Hill last-hour window: scope=%s, window=%s", self.scope, window.key)
        return KirkHillSnapshot(
            summary=today.summary,
            generation=today.generation,
            wind_speed=today.wind_speed,
            turbines=today.turbines,
            bucket=today.bucket,
            last_hour_generation_kwh=last_hour_generation,
            last_hour_window_end=last_hour_window_end,
            next_hourly_check=scheduled_check,
            last_successful_poll=now,
        )

    # Adds yesterday and monthly values only when the separate post-midnight schedule or retry schedule is due.
    # Human checked: No
    async def _with_past_data(self, now: datetime, current: KirkHillSnapshot) -> KirkHillSnapshot:
        current_due_check = self._current_past_data_due_check(now)
        next_check = self.data.next_past_data_check if self.data else None
        if next_check is None:
            next_check = current_due_check
        if now < next_check:
            return self._merge_past_data(current, next_check)

        yesterday = await self._api.fetch_snapshot("yesterday", self.scope)
        generation_yesterday_kwh = yesterday.summary.get("total_generation_kwh")
        yesterday_date = expected_yesterday_date(now)
        is_complete = self._is_complete_yesterday_snapshot(yesterday, now)
        next_past_check = next_hourly_check(now, self._hourly_minute, self._hourly_second)
        generation_this_month_kwh = self.data.generation_this_month_kwh if self.data else None
        generation_last_month_kwh = self.data.generation_last_month_kwh if self.data else None
        completed_yesterday = self.data.completed_yesterday_date if self.data else None

        if is_complete:
            next_past_check = next_past_data_check(now, self._hourly_minute, self._hourly_second)
            completed_yesterday = yesterday_date
            this_month_total, last_month_total = await self._fetch_month_totals(now)
            generation_this_month_kwh = this_month_total
            generation_last_month_kwh = last_month_total
            _LOGGER.info("Fetched Kirk Hill past-data totals: scope=%s, date=%s", self.scope, yesterday_date)

        return self._merge_past_data(
            current,
            next_past_check,
            generation_yesterday_kwh=generation_yesterday_kwh,
            generation_this_month_kwh=generation_this_month_kwh,
            generation_last_month_kwh=generation_last_month_kwh,
            completed_yesterday_date=completed_yesterday,
        )

    # Returns the post-midnight delayed check for the current local day so restarts can catch up immediately.
    # Human checked: No
    def _current_past_data_due_check(self, now: datetime) -> datetime:
        local_today = now.astimezone(UK_TZ).date()
        return delayed_check_for_local_date(local_today, self._hourly_minute, self._hourly_second)

    # Rebuilds the immutable snapshot while carrying forward cached past-data values when no refresh is due.
    # Human checked: No
    def _merge_past_data(
        self,
        current: KirkHillSnapshot,
        next_past_data_check_value: datetime,
        *,
        generation_yesterday_kwh: float | None | object = ...,
        generation_this_month_kwh: float | None | object = ...,
        generation_last_month_kwh: float | None | object = ...,
        completed_yesterday_date: object = ...,
    ) -> KirkHillSnapshot:
        previous = self.data
        yesterday_value = previous.generation_yesterday_kwh if previous else None
        this_month_value = previous.generation_this_month_kwh if previous else None
        last_month_value = previous.generation_last_month_kwh if previous else None
        completed_value = previous.completed_yesterday_date if previous else None
        if generation_yesterday_kwh is not ...:
            yesterday_value = generation_yesterday_kwh
        if generation_this_month_kwh is not ...:
            this_month_value = generation_this_month_kwh
        if generation_last_month_kwh is not ...:
            last_month_value = generation_last_month_kwh
        if completed_yesterday_date is not ...:
            completed_value = completed_yesterday_date
        savings_yesterday_pence = self._calculate_savings(yesterday_value)
        savings_this_month_pence = self._calculate_savings(this_month_value)
        savings_last_month_pence = self._calculate_savings(last_month_value)
        return KirkHillSnapshot(
            summary=current.summary,
            generation=current.generation,
            wind_speed=current.wind_speed,
            turbines=current.turbines,
            bucket=current.bucket,
            last_hour_generation_kwh=current.last_hour_generation_kwh,
            last_hour_window_end=current.last_hour_window_end,
            generation_yesterday_kwh=yesterday_value,
            generation_this_month_kwh=this_month_value,
            generation_last_month_kwh=last_month_value,
            savings_yesterday_pence=savings_yesterday_pence,
            savings_this_month_pence=savings_this_month_pence,
            savings_last_month_pence=savings_last_month_pence,
            next_hourly_check=current.next_hourly_check,
            next_past_data_check=next_past_data_check_value,
            completed_yesterday_date=completed_value,
            last_successful_poll=current.last_successful_poll,
        )

    # Fetches the month-to-date and previous-month totals using explicit UK-local calendar boundaries.
    # Human checked: No
    async def _fetch_month_totals(self, now: datetime) -> tuple[float, float]:
        this_month_window = build_this_month_window(now)
        if this_month_window.from_utc == this_month_window.to_utc:
            this_month_total = 0.0
        else:
            this_month_snapshot = await self._api.fetch_custom_snapshot(
                this_month_window.from_utc,
                this_month_window.to_utc,
                self.scope,
            )
            this_month_total = float(this_month_snapshot.summary.get("total_generation_kwh") or 0.0)
        last_month_window = build_last_month_window(now)
        last_month_snapshot = await self._api.fetch_custom_snapshot(
            last_month_window.from_utc,
            last_month_window.to_utc,
            self.scope,
        )
        last_month_total = float(last_month_snapshot.summary.get("total_generation_kwh") or 0.0)
        return this_month_total, last_month_total

    # Checks whether yesterday's latest completed interval reaches the expected UK-local end of yesterday.
    # Human checked: No
    def _is_complete_yesterday_snapshot(self, snapshot: KirkHillSnapshot, now: datetime) -> bool:
        latest_end = snapshot.summary.get("latest_generation_interval_end")
        if not isinstance(latest_end, str):
            return False
        parsed_end = self._parse_summary_datetime(latest_end)
        return parsed_end is not None and parsed_end >= expected_yesterday_end_utc(now)

    # Parses summary timestamps without changing the broader summary dictionary shape used elsewhere.
    # Human checked: No
    def _parse_summary_datetime(self, value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed

    # Converts generation totals into pence using the optional configured presumed net saving rate.
    # Human checked: No
    def _calculate_savings(self, generation_kwh: float | None) -> float | None:
        if self._presumed_net_saving_rate_pence is None or generation_kwh is None:
            return None
        return generation_kwh * self._presumed_net_saving_rate_pence
