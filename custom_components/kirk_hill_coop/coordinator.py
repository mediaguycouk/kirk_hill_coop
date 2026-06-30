# Coordinates today-range and delayed last-hour refreshes for all entities.
# Human checked: No

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KirkHillApiClient, KirkHillApiError
from .const import DOMAIN, RUNTIME_RANGE
from .history import (
    build_latest_eligible_hour_window,
    next_hourly_check,
    should_archive_previous_hour,
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
        update_interval,
        time_provider: TimeProvider,
        hourly_minute: int,
        hourly_second: int,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)
        self._api = api
        self._time_provider = time_provider
        self.scope = scope
        self._hourly_minute = hourly_minute
        self._hourly_second = hourly_second
        self._last_hour_window_key: str | None = None

    # Refreshes today and, once the delayed trigger has passed, also refreshes the previous whole hour.
    # Human checked: No
    async def _async_update_data(self) -> KirkHillSnapshot:
        try:
            now = self._time_provider.now()
            today = await self._api.fetch_snapshot(RUNTIME_RANGE, self.scope)
            return await self._with_last_hour_data(now, today)
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
