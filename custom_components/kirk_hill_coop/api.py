# Defines the cooperative API boundary and domain-specific failures.
# Human checked: No

import asyncio
from datetime import datetime
from typing import Any, Protocol

from aiohttp import ClientError, ClientSession

from .const import API_BASE_URL, DEFAULT_SCOPE
from .models import GenerationPoint, KirkHillSnapshot, WindSpeedPoint


# Identifies cooperative API failures without leaking transport details outward.
# Human checked: No
class KirkHillApiError(Exception):
    """Base failure raised for a cooperative API request."""


# Separates rejected credentials so Home Assistant can start reauthentication.
# Human checked: No
class KirkHillAuthenticationError(KirkHillApiError):
    """Indicates that the supplied bearer key was rejected."""


# Reports malformed or unexpectedly shaped API responses separately from HTTP failures.
# Human checked: No
class KirkHillResponseError(KirkHillApiError):
    """Indicates that the API returned data that could not be interpreted."""


# Defines the API seam so coordinator and setup logic remain independently testable.
# Human checked: No
class KirkHillApiClient(Protocol):
    """Describes API operations required by setup and periodic refreshes."""

    async def fetch_snapshot(self, requested_range: str, scope: str) -> KirkHillSnapshot:
        """Fetch all endpoint data for one range and scope."""

    async def fetch_custom_snapshot(self, from_utc: datetime, to_utc: datetime, scope: str) -> KirkHillSnapshot:
        """Fetch all endpoint data for one explicit custom window."""


# Implements authenticated requests against the cooperative's read-only HTTP API.
# Human checked: No
class KirkHillHttpClient:
    """Fetch and parse Kirk Hill API snapshots."""

    # Stores shared request dependencies so Home Assistant can manage the HTTP session.
    # Human checked: No
    def __init__(
        self,
        session: ClientSession,
        api_key: str,
        base_url: str = API_BASE_URL,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    # Builds stable request headers so the integration looks like a normal JSON API client.
    # Human checked: No
    def _request_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "Kirk Hill Coop Home Assistant/0.2.0",
        }

    # Omits the default owner scope because the live API already applies it implicitly.
    # Human checked: No
    def _request_params(
        self,
        requested_range: str,
        scope: str,
        from_utc: datetime | None = None,
        to_utc: datetime | None = None,
    ) -> dict[str, str]:
        params = {"range": requested_range}
        if scope != DEFAULT_SCOPE:
            params["scope"] = scope
        if requested_range == "custom":
            if from_utc is None or to_utc is None:
                raise ValueError("Custom range requests require from_utc and to_utc")
            params["from"] = from_utc.isoformat().replace("+00:00", "Z")
            params["to"] = to_utc.isoformat().replace("+00:00", "Z")
        return params

    # Fetches the four endpoints concurrently because they describe one logical snapshot.
    # Human checked: No
    async def fetch_snapshot(self, requested_range: str, scope: str) -> KirkHillSnapshot:
        return await self._fetch_snapshot(requested_range, scope)

    # Fetches one explicit custom window for archive backfill and delayed hourly history.
    # Human checked: No
    async def fetch_custom_snapshot(self, from_utc: datetime, to_utc: datetime, scope: str) -> KirkHillSnapshot:
        return await self._fetch_snapshot("custom", scope, from_utc, to_utc)

    # Fetches the four endpoint families for either a named range or a custom time span.
    # Human checked: No
    async def _fetch_snapshot(
        self,
        requested_range: str,
        scope: str,
        from_utc: datetime | None = None,
        to_utc: datetime | None = None,
    ) -> KirkHillSnapshot:
        try:
            summary, generation, wind_speed, turbines = await asyncio.gather(
                self._get("summary", requested_range, scope, from_utc, to_utc),
                self._get("generation", requested_range, scope, from_utc, to_utc),
                self._get("wind-speed", requested_range, scope, from_utc, to_utc),
                self._get("turbines", requested_range, scope, from_utc, to_utc),
            )
            return self._parse_snapshot(summary, generation, wind_speed, turbines)
        except KirkHillApiError:
            raise
        except (KeyError, TypeError, ValueError) as err:
            raise KirkHillResponseError(
                f"Invalid Kirk Hill response for range={requested_range}, scope={scope}: {err}"
            ) from err

    # Performs one JSON request and translates transport/status failures into domain errors.
    # Human checked: No
    async def _get(
        self,
        endpoint: str,
        requested_range: str,
        scope: str,
        from_utc: datetime | None = None,
        to_utc: datetime | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/api/v1/{endpoint}"
        try:
            response = await self._session.get(
                url,
                headers=self._request_headers(),
                params=self._request_params(requested_range, scope, from_utc, to_utc),
            )
            if response.status == 401:
                raise KirkHillAuthenticationError("The Kirk Hill API key was rejected")
            if response.status >= 400:
                body = await response.text()
                raise KirkHillApiError(
                    f"Kirk Hill request failed: endpoint={endpoint}, status={response.status}, body={body[:200]}"
                )
            payload = await response.json()
        except KirkHillApiError:
            raise
        except (ClientError, asyncio.TimeoutError) as err:
            raise KirkHillApiError(
                f"Kirk Hill request failed: endpoint={endpoint}, range={requested_range}, scope={scope}"
            ) from err
        if not isinstance(payload, dict):
            raise KirkHillResponseError(f"Kirk Hill endpoint {endpoint} returned non-object JSON")
        return payload

    # Converts API dictionaries into stable typed values consumed by storage and sensors.
    # Human checked: No
    @staticmethod
    def _parse_snapshot(
        summary_payload: dict[str, Any],
        generation_payload: dict[str, Any],
        wind_payload: dict[str, Any],
        turbines_payload: dict[str, Any],
    ) -> KirkHillSnapshot:
        summary_data = summary_payload["data"]
        generation_data = generation_payload["data"]
        wind_data = wind_payload["data"]
        turbines_data = turbines_payload["data"]
        generation = tuple(
            GenerationPoint(
                timestamp=_parse_datetime(point["timestamp"]),
                generation_kwh=float(point["generation_kwh"]),
            )
            for point in generation_data["series"]
        )
        wind_speed = tuple(
            WindSpeedPoint(
                timestamp=_parse_datetime(point["timestamp"]),
                wind_speed_mps=float(point["wind_speed_mps"]),
            )
            for point in wind_data["series"]
        )
        return KirkHillSnapshot(
            summary=dict(summary_data["summary"]),
            generation=generation,
            wind_speed=wind_speed,
            turbines=tuple(dict(turbine) for turbine in turbines_data["turbines"]),
            bucket=generation_data.get("window", {}).get("bucket"),
        )


# Parses API timestamps and requires timezone information to avoid GMT/BST ambiguity.
# Human checked: No
def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"API timestamp has no timezone: {value}")
    return parsed
