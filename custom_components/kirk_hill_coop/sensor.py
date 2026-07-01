# Exposes statistics-capable sensors backed by coordinated API snapshots.
# Human checked: No

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INTEGRATION_NAME
from .coordinator import KirkHillCoordinator

SENSORS = (
    SensorEntityDescription(
        key="total_power_kw",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="total_generation_kwh",
        translation_key="generation_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="last_hour_generation_kwh",
        translation_key="generation_last_hour",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="generation_yesterday_kwh",
        translation_key="generation_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="generation_this_month_kwh",
        translation_key="generation_this_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="generation_last_month_kwh",
        translation_key="generation_last_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="savings_yesterday_pence",
        translation_key="savings_yesterday",
        native_unit_of_measurement="GBP",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="savings_this_month_pence",
        translation_key="savings_this_month",
        native_unit_of_measurement="GBP",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="savings_last_month_pence",
        translation_key="savings_last_month",
        native_unit_of_measurement="GBP",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="wind_speed_mps",
        translation_key="wind_speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="capacity_factor_percent",
        translation_key="capacity_factor",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(key="active_turbines", translation_key="active_turbines"),
    SensorEntityDescription(
        key="site_capacity_watts",
        translation_key="site_capacity",
        native_unit_of_measurement=UnitOfPower.MEGA_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="last_poll",
        translation_key="last_poll",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="next_latest_check",
        translation_key="next_latest_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="next_hourly_check",
        translation_key="next_hourly_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="next_past_data_check",
        translation_key="next_past_data_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


# Adds all snapshot-backed sensors after the coordinator has valid first-refresh data.
# Human checked: No
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[KirkHillCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(KirkHillSensor(entry.runtime_data, entry, description) for description in SENSORS)


# Maps coordinator fields to stable Home Assistant sensor entities.
# Human checked: No
class KirkHillSensor(CoordinatorEntity[KirkHillCoordinator], SensorEntity):
    """Represent one Kirk Hill reading."""

    _attr_has_entity_name = True

    # Binds identity and device metadata while sharing the coordinator's availability state.
    # Human checked: No
    def __init__(
        self,
        coordinator: KirkHillCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=INTEGRATION_NAME,
            manufacturer="Kirk Hill Wind Farm Coop",
            configuration_url="https://dashboard.kirkhillcoop.org",
        )

    # Returns the appropriate summary or latest-series value for this entity description.
    # Human checked: No
    @property
    def native_value(self) -> Any:
        key = self.entity_description.key
        if key == "wind_speed_mps":
            return (self.coordinator.data.current_summary or {}).get("wind_speed_mps")
        if key == "total_power_kw":
            return (self.coordinator.data.current_summary or {}).get("total_power_kw")
        if key == "last_hour_generation_kwh":
            return self.coordinator.data.last_hour_generation_kwh
        if key == "next_latest_check":
            return self.coordinator.data.next_latest_check
        if key == "next_hourly_check":
            return self.coordinator.data.next_hourly_check
        if key == "next_past_data_check":
            return self.coordinator.data.next_past_data_check
        if key == "last_poll":
            return self.coordinator.data.last_poll
        if key == "generation_yesterday_kwh":
            return self.coordinator.data.generation_yesterday_kwh
        if key == "generation_this_month_kwh":
            return self.coordinator.data.generation_this_month_kwh
        if key == "generation_last_month_kwh":
            return self.coordinator.data.generation_last_month_kwh
        if key == "savings_yesterday_pence":
            return _pence_to_pounds(self.coordinator.data.savings_yesterday_pence)
        if key == "savings_this_month_pence":
            return _pence_to_pounds(self.coordinator.data.savings_this_month_pence)
        if key == "savings_last_month_pence":
            return _pence_to_pounds(self.coordinator.data.savings_last_month_pence)
        if key == "site_capacity_watts":
            current_value = (self.coordinator.data.current_summary or {}).get(key)
            if current_value is None:
                current_value = self.coordinator.data.summary.get(key)
            return _watts_to_megawatts(current_value)
        current_summary = self.coordinator.data.current_summary or {}
        if key in {"capacity_factor_percent", "active_turbines"}:
            return current_summary.get(key)
        value = self.coordinator.data.summary.get(key)
        return value

    # Surfaces useful import context and turbine detail without creating excessive entities.
    # Human checked: No
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "last_hour_generation_kwh":
            return {
                "scope": self.coordinator.scope,
                "window_end": self.coordinator.data.last_hour_window_end,
            }
        if self.entity_description.key == "total_power_kw":
            current_reading = self.coordinator.data.current_reading or {}
            return {
                "scope": self.coordinator.scope,
                "generated_at": current_reading.get("generated_at"),
                "source_interval": current_reading.get("source_interval"),
                "complete": current_reading.get("complete"),
                "turbines": list(self.coordinator.data.current_turbines),
            }
        if self.entity_description.key != "total_generation_kwh":
            return None
        return {
            "scope": self.coordinator.scope,
            "bucket": self.coordinator.data.bucket,
            "latest_import_status": self.coordinator.data.summary.get("latest_import_status"),
            "turbines": list(self.coordinator.data.turbines),
        }


# Converts stored pence totals into pounds for the user-facing savings sensors.
# Human checked: No
def _pence_to_pounds(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100


# Converts the API's raw watt value into megawatts for a more readable default display.
# Human checked: No
def _watts_to_megawatts(value: Any) -> float | None:
    if value is None:
        return None
    return float(value) / 1_000_000
