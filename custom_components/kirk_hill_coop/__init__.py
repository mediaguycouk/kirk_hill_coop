# Wires the Kirk Hill Coop config entry into Home Assistant platforms.
# Human checked: No

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KirkHillHttpClient
from .const import (
    CONF_API_KEY,
    CONF_LIVE_REFRESH_MINUTES,
    CONF_PRESUMED_NET_SAVING_RATE_PENCE,
    CONF_SCOPE,
    DEFAULT_LIVE_REFRESH_MINUTES,
    DEFAULT_SCOPE,
)
from .coordinator import KirkHillCoordinator
from .history import calculate_hourly_offset
from .time import UtcTimeProvider

PLATFORMS = (Platform.SENSOR,)
type KirkHillConfigEntry = ConfigEntry[KirkHillCoordinator]


# Creates runtime services, completes the first refresh, and forwards entity setup.
# Human checked: No
async def async_setup_entry(hass: HomeAssistant, entry: KirkHillConfigEntry) -> bool:
    options = {**entry.data, **entry.options}
    api = KirkHillHttpClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    hourly_minute, hourly_second = calculate_hourly_offset(entry.entry_id)
    coordinator = KirkHillCoordinator(
        hass,
        api,
        options.get(CONF_SCOPE, DEFAULT_SCOPE),
        UtcTimeProvider(),
        hourly_minute,
        hourly_second,
        options.get(CONF_LIVE_REFRESH_MINUTES, DEFAULT_LIVE_REFRESH_MINUTES),
        options.get(CONF_PRESUMED_NET_SAVING_RATE_PENCE),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


# Unloads entity platforms before Home Assistant discards integration runtime state.
# Human checked: No
async def async_unload_entry(hass: HomeAssistant, entry: KirkHillConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


# Reloads the entry so changed scope takes effect immediately.
# Human checked: No
async def _async_reload_entry(hass: HomeAssistant, entry: KirkHillConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
