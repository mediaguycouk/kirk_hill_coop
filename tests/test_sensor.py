# Verifies the new generation, savings, and diagnostic sensor values map cleanly from coordinator snapshots.
# Human checked: No

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from custom_components.kirk_hill_coop.models import GenerationPoint, KirkHillSnapshot, WindSpeedPoint
from custom_components.kirk_hill_coop.sensor import KirkHillSensor, SENSORS


# Confirms yesterday, monthly, and next past-data sensors expose the coordinator's stored values directly.
# Human checked: No
def test_sensor_native_values_include_new_past_data_fields() -> None:
    coordinator = Mock()
    coordinator.scope = "owner"
    coordinator.data = _snapshot(
        generation_yesterday_kwh=19.453,
        generation_this_month_kwh=300.0,
        generation_last_month_kwh=450.0,
        next_past_data_check=datetime(2026, 7, 1, 23, 42, 30, tzinfo=UTC),
    )
    entry = Mock(entry_id="entry-1")

    assert _sensor("generation_yesterday_kwh", coordinator, entry).native_value == 19.453
    assert _sensor("generation_this_month_kwh", coordinator, entry).native_value == 300.0
    assert _sensor("generation_last_month_kwh", coordinator, entry).native_value == 450.0
    assert _sensor("next_past_data_check", coordinator, entry).native_value == datetime(
        2026, 7, 1, 23, 42, 30, tzinfo=UTC
    )


# Confirms savings sensors stay unavailable when no presumed net saving rate has been configured.
# Human checked: No
def test_savings_sensors_are_unavailable_without_values() -> None:
    coordinator = Mock()
    coordinator.scope = "owner"
    coordinator.data = _snapshot()
    entry = Mock(entry_id="entry-1")

    assert _sensor("savings_yesterday_pence", coordinator, entry).native_value is None
    assert _sensor("savings_this_month_pence", coordinator, entry).native_value is None
    assert _sensor("savings_last_month_pence", coordinator, entry).native_value is None


# Confirms savings sensors expose pence totals once the coordinator has calculated them.
# Human checked: No
def test_savings_sensors_expose_calculated_pence_values() -> None:
    coordinator = Mock()
    coordinator.scope = "owner"
    coordinator.data = _snapshot(
        savings_yesterday_pence=291.795,
        savings_this_month_pence=4500.0,
        savings_last_month_pence=6750.0,
    )
    entry = Mock(entry_id="entry-1")

    assert _sensor("savings_yesterday_pence", coordinator, entry).native_value == pytest.approx(2.91795)
    assert _sensor("savings_this_month_pence", coordinator, entry).native_value == 45.0
    assert _sensor("savings_last_month_pence", coordinator, entry).native_value == 67.5


# Confirms site capacity is surfaced in megawatts rather than raw watts.
# Human checked: No
def test_site_capacity_sensor_uses_megawatts() -> None:
    coordinator = Mock()
    coordinator.scope = "owner"
    coordinator.data = _snapshot(site_capacity_watts=18_800_000)
    entry = Mock(entry_id="entry-1")

    assert _sensor("site_capacity_watts", coordinator, entry).native_value == 18.8


# Confirms the non-live energy totals use Home Assistant's allowed energy state classes.
# Human checked: No
def test_energy_total_sensors_use_total_state_class() -> None:
    assert _description("last_hour_generation_kwh").state_class == "total"
    assert _description("generation_yesterday_kwh").state_class == "total"
    assert _description("generation_this_month_kwh").state_class == "total"
    assert _description("generation_last_month_kwh").state_class == "total"
    assert _description("savings_yesterday_pence").native_unit_of_measurement == "GBP"
    assert _description("savings_yesterday_pence").suggested_display_precision == 2
    assert _description("site_capacity_watts").native_unit_of_measurement == "MW"


# Builds one concrete sensor using the production entity descriptions so tests stay aligned with setup wiring.
# Human checked: No
def _sensor(key: str, coordinator: Mock, entry: Mock) -> KirkHillSensor:
    description = _description(key)
    return KirkHillSensor(coordinator, entry, description)


# Returns the production entity description for one key so tests can assert metadata as well as values.
# Human checked: No
def _description(key: str):
    return next(description for description in SENSORS if description.key == key)


# Builds a representative snapshot with optional past-data values for direct sensor mapping tests.
# Human checked: No
def _snapshot(
    *,
    generation_yesterday_kwh: float | None = None,
    generation_this_month_kwh: float | None = None,
    generation_last_month_kwh: float | None = None,
    savings_yesterday_pence: float | None = None,
    savings_this_month_pence: float | None = None,
    savings_last_month_pence: float | None = None,
    site_capacity_watts: int | None = None,
    next_past_data_check: datetime | None = None,
) -> KirkHillSnapshot:
    stamp = datetime(2026, 6, 30, 10, tzinfo=UTC)
    return KirkHillSnapshot(
        summary={"total_generation_kwh": 1, "site_capacity_watts": site_capacity_watts},
        generation=(GenerationPoint(stamp, 1),),
        wind_speed=(WindSpeedPoint(stamp, 8),),
        turbines=(),
        generation_yesterday_kwh=generation_yesterday_kwh,
        generation_this_month_kwh=generation_this_month_kwh,
        generation_last_month_kwh=generation_last_month_kwh,
        savings_yesterday_pence=savings_yesterday_pence,
        savings_this_month_pence=savings_this_month_pence,
        savings_last_month_pence=savings_last_month_pence,
        next_past_data_check=next_past_data_check,
    )
