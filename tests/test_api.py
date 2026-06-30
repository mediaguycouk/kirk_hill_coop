# Verifies API parsing and timezone-safe timestamp handling.
# Human checked: No

from datetime import datetime, timedelta

import pytest

from custom_components.kirk_hill_coop.api import KirkHillHttpClient, KirkHillResponseError


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


# Preserves explicit scope selection so site-wide requests still reach the correct API mode.
# Human checked: No
def test_request_params_includes_non_default_scope() -> None:
    client = KirkHillHttpClient(session=None, api_key="token")  # type: ignore[arg-type]
    assert client._request_params("today", "site") == {"range": "today", "scope": "site"}


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
