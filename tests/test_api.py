# Verifies API parsing and timezone-safe timestamp handling.
# Human checked: No

from datetime import datetime, timedelta

import pytest

from custom_components.kirk_hill_coop.api import KirkHillHttpClient, KirkHillResponseError


# Builds a representative current-endpoint response and verifies typed snapshot conversion.
# Human checked: No
def test_parse_current_snapshot() -> None:
    current = {
        "data": {
            "reading": {
                "scope": "owner",
                "source_interval": "1m",
                "generated_at": "2026-06-30T10:00:00Z",
                "complete": True,
            },
            "summary": {
                "total_power_kw": 12.5,
                "wind_speed_mps": 8.2,
                "active_turbines": 8,
                "latest_power_at": "2026-06-30T10:00:00Z",
            },
            "turbines": [{"id": "T1", "power_kw": 1.2, "latest_power_at": "2026-06-30T10:00:00Z"}],
        }
    }

    snapshot = KirkHillHttpClient._parse_current_snapshot(current)

    assert snapshot.current_reading == current["data"]["reading"]
    assert snapshot.current_summary["total_power_kw"] == 12.5
    assert snapshot.current_turbines[0]["id"] == "T1"


# Builds a representative four-endpoint response and verifies typed snapshot conversion.
# Human checked: No
def test_parse_snapshot() -> None:
    summary = {"data": {"summary": {"total_generation_kwh": 12.5}}}
    generation = {
        "data": {
            "window": {"bucket": "1h"},
            "series": [{"timestamp": "2026-06-30T10:00:00Z", "generation_kwh": 12.5}],
        }
    }
    wind = {
        "data": {
            "series": [{"timestamp": "2026-06-30T10:00:00Z", "wind_speed_mps": 8.2}]
        }
    }
    turbines = {"data": {"turbines": [{"id": "T1"}]}}

    snapshot = KirkHillHttpClient._parse_snapshot(summary, generation, wind, turbines)

    assert snapshot.bucket == "1h"
    assert snapshot.generation[0].generation_kwh == 12.5
    assert snapshot.wind_speed[0].wind_speed_mps == 8.2
    assert snapshot.generation[0].timestamp.utcoffset() == timedelta(0)


# Rejects timestamps without an offset because local interpretation differs in GMT and BST.
# Human checked: No
def test_parse_snapshot_rejects_timezone_naive_timestamp() -> None:
    summary = {"data": {"summary": {}}}
    generation = {
        "data": {
            "window": {"bucket": "1h"},
            "series": [{"timestamp": "2026-01-30T10:00:00", "generation_kwh": 1}],
        }
    }
    wind = {"data": {"series": []}}
    turbines = {"data": {"turbines": []}}

    with pytest.raises(ValueError, match="no timezone"):
        KirkHillHttpClient._parse_snapshot(summary, generation, wind, turbines)


# Keeps owner requests aligned with the live API by omitting the default scope parameter.
# Human checked: No
def test_request_params_omits_default_scope() -> None:
    client = KirkHillHttpClient(session=None, api_key="token")  # type: ignore[arg-type]
    assert client._request_params("today", "owner") == {"range": "today"}


# Keeps owner current requests aligned with the live API by omitting the default scope parameter there too.
# Human checked: No
def test_current_request_params_omits_default_scope() -> None:
    client = KirkHillHttpClient(session=None, api_key="token")  # type: ignore[arg-type]
    assert client._current_request_params("owner") is None


# Preserves explicit scope selection so site-wide requests still reach the correct API mode.
# Human checked: No
def test_request_params_includes_non_default_scope() -> None:
    client = KirkHillHttpClient(session=None, api_key="token")  # type: ignore[arg-type]
    assert client._request_params("today", "site") == {"range": "today", "scope": "site"}


# Preserves explicit scope selection on the current endpoint so site-wide live reads stay site-wide.
# Human checked: No
def test_current_request_params_include_non_default_scope() -> None:
    client = KirkHillHttpClient(session=None, api_key="token")  # type: ignore[arg-type]
    assert client._current_request_params("site") == {"scope": "site"}


# Includes explicit UTC timestamps for custom windows so hourly archive requests match Postman tests.
# Human checked: No
def test_request_params_include_custom_window() -> None:
    client = KirkHillHttpClient(session=None, api_key="token")  # type: ignore[arg-type]
    assert client._request_params(
        "custom",
        "owner",
        datetime.fromisoformat("2026-06-30T14:00:00+00:00"),
        datetime.fromisoformat("2026-06-30T15:00:00+00:00"),
    ) == {
        "range": "custom",
        "from": "2026-06-30T14:00:00Z",
        "to": "2026-06-30T15:00:00Z",
    }


# Rejects malformed current payloads that omit the expected top-level reading block.
# Human checked: No
def test_parse_current_snapshot_rejects_missing_reading() -> None:
    with pytest.raises(KeyError):
        KirkHillHttpClient._parse_current_snapshot({"data": {"summary": {}, "turbines": []}})


# Rejects current-endpoint timestamps without an offset because live readings must stay GMT/BST safe as well.
# Human checked: No
def test_parse_current_snapshot_rejects_timezone_naive_timestamp() -> None:
    current = {
        "data": {
            "reading": {
                "scope": "owner",
                "source_interval": "1m",
                "generated_at": "2026-06-30T10:00:00",
                "complete": True,
            },
            "summary": {"total_power_kw": 12.5},
            "turbines": [],
        }
    }

    with pytest.raises(ValueError, match="no timezone"):
        KirkHillHttpClient._parse_current_snapshot(current)
