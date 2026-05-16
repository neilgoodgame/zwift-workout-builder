"""Data models for Zwift .zwo workout segments."""

from dataclasses import dataclass, field
from enum import StrEnum


class SportType(StrEnum):
    BIKE = "bike"
    RUN = "run"


@dataclass
class WorkoutSegment:
    """Base class for all workout segments."""
    pass


@dataclass
class Warmup(WorkoutSegment):
    """Ramp from power_low up to power_high over duration seconds."""
    duration: int       # seconds
    power_low: float    # fraction of FTP (e.g. 0.25 = 25% FTP)
    power_high: float   # fraction of FTP

    def __post_init__(self):
        if self.duration <= 0:
            raise ValueError(f"Duration must be positive, got {self.duration}")
        if self.power_low < 0 or self.power_high < 0:
            raise ValueError("Power values must be non-negative")


@dataclass
class Cooldown(WorkoutSegment):
    """Ramp from power_high down to power_low over duration seconds."""
    duration: int
    power_low: float
    power_high: float

    def __post_init__(self):
        if self.duration <= 0:
            raise ValueError(f"Duration must be positive, got {self.duration}")
        if self.power_low < 0 or self.power_high < 0:
            raise ValueError("Power values must be non-negative")


@dataclass
class SteadyState(WorkoutSegment):
    """Hold a constant power target for duration seconds."""
    duration: int
    power: float                  # fraction of FTP
    cadence: int | None = None    # optional target cadence in RPM

    def __post_init__(self):
        if self.duration <= 0:
            raise ValueError(f"Duration must be positive, got {self.duration}")
        if self.power < 0:
            raise ValueError("Power must be non-negative")
        if self.cadence is not None and self.cadence <= 0:
            raise ValueError("Cadence must be positive")


@dataclass
class IntervalsT(WorkoutSegment):
    """Repeated on/off intervals."""
    repeat: int
    on_duration: int              # seconds per on interval
    off_duration: int             # seconds per off interval
    on_power: float               # fraction of FTP during on interval
    off_power: float              # fraction of FTP during off interval
    cadence: int | None = None           # target cadence during on intervals
    cadence_resting: int | None = None   # target cadence during off intervals

    def __post_init__(self):
        if self.repeat <= 0:
            raise ValueError(f"Repeat must be positive, got {self.repeat}")
        if self.on_duration <= 0:
            raise ValueError(f"on_duration must be positive, got {self.on_duration}")
        if self.off_duration <= 0:
            raise ValueError(f"off_duration must be positive, got {self.off_duration}")
        if self.on_power < 0 or self.off_power < 0:
            raise ValueError("Power values must be non-negative")

    @property
    def total_duration(self) -> int:
        return self.repeat * (self.on_duration + self.off_duration)


@dataclass
class FreeRide(WorkoutSegment):
    """Unstructured riding — no power target."""
    duration: int
    flat_road: bool = False  # simulate flat road (no virtual elevation)

    def __post_init__(self):
        if self.duration <= 0:
            raise ValueError(f"Duration must be positive, got {self.duration}")


@dataclass
class Ramp(WorkoutSegment):
    """Linear ramp between two power targets over duration seconds."""
    duration: int
    power_low: float
    power_high: float

    def __post_init__(self):
        if self.duration <= 0:
            raise ValueError(f"Duration must be positive, got {self.duration}")
        if self.power_low < 0 or self.power_high < 0:
            raise ValueError("Power values must be non-negative")


@dataclass
class MaxEffort(WorkoutSegment):
    """All-out sprint segment with no prescribed power target."""
    duration: int

    def __post_init__(self):
        if self.duration <= 0:
            raise ValueError(f"Duration must be positive, got {self.duration}")


@dataclass
class Workout:
    name: str
    author: str = ""
    description: str = ""
    sport_type: SportType = SportType.BIKE
    tags: list[str] = field(default_factory=list)
    segments: list[WorkoutSegment] = field(default_factory=list)

    def add_segment(self, segment: WorkoutSegment) -> "Workout":
        self.segments.append(segment)
        return self

    @property
    def total_duration(self) -> int:
        """Total workout duration in seconds."""
        total = 0
        for seg in self.segments:
            if isinstance(seg, IntervalsT):
                total += seg.total_duration
            elif hasattr(seg, "duration"):
                total += seg.duration  # type: ignore[attr-defined]
        return total
