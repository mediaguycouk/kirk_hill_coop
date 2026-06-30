# Verifies the new generation, savings, and diagnostic sensor values map cleanly from coordinator snapshots.
# Human checked: No

from datetime import UTC, datetime
from unittest.mock import Mock

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

    assert _sensor("savings_yesterday_pence", coordinator, entry).native_value == 291.795
    assert _sensor("savings_this_month_pence", coordinator, entry).native_value == 4500.0
    assert _sensor("savings_last_month_pence", coordinator, entry).native_value == 6750.0


# Builds one concrete sensor using the production entity descriptions so tests stay aligned with setup wiring.
# Human checked: No
def _sensor(key: str, coordinator: Mock, entry: Mock) -> KirkHillSensor:
    description = next(description for description in SENSORS if description.key == key)
    return KirkHillSensor(coordinator, entry, description)


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
    next_past_data_check: datetime | None = None,
) -> KirkHillSnapshot:
    stamp = datetime(2026, 6, 30, 10, tzinfo=UTC)
    return KirkHillSnapshot(
        summary={"total_generation_kwh": 1},
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
