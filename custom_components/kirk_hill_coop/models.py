# Defines typed API data passed between the client, archive, and entity layers.
# Human checked: No

from dataclasses import dataclass
from datetime import datetime
from typing import Any


# Carries one generation reading so parsing and storage share a stable shape.
# Human checked: No
@dataclass(frozen=True, slots=True)
class GenerationPoint:
    """A timestamped generation value returned by the cooperative API."""

    timestamp: datetime
    generation_kwh: float


# Carries one wind-speed reading so parsing and storage share a stable shape.
# Human checked: No
@dataclass(frozen=True, slots=True)
class WindSpeedPoint:
    """A timestamped mean wind-speed value returned by the cooperative API."""

    timestamp: datetime
    wind_speed_mps: float


# Groups one refresh atomically so every sensor sees a consistent API result.
# Human checked: No
@dataclass(frozen=True, slots=True)
class KirkHillSnapshot:
    """The immutable result of one coordinated API refresh."""

    summary: dict[str, Any]
    generation: tuple[GenerationPoint, ...]
    wind_speed: tuple[WindSpeedPoint, ...]
    turbines: tuple[dict[str, Any], ...]
    bucket: str | None = None
    last_hour_generation_kwh: float | None = None
    last_hour_window_end: datetime | None = None
    next_hourly_check: datetime | None = None
    last_successful_poll: datetime | None = None
