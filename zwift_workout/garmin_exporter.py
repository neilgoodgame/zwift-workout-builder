"""Convert Workout objects to Garmin FIT workout files (.fit)."""

from datetime import datetime, timezone

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.workout_message import WorkoutMessage
from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
from fit_tool.profile.profile_type import (
    FileType,
    Intensity,
    Manufacturer,
    Sport,
    WorkoutStepDuration,
    WorkoutStepTarget,
)

from zwift_workout.models import (
    Cooldown,
    FreeRide,
    IntervalsT,
    MaxEffort,
    Ramp,
    SteadyState,
    SportType,
    Warmup,
    Workout,
    WorkoutSegment,
)

def _unix_now_ms() -> int:
    """Current time as Unix milliseconds, which is what fit-tool's time_created field expects."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _ms(seconds: int) -> int:
    return seconds * 1000


def _watts(fraction: float, ftp: int) -> int:
    """Convert a fraction of FTP to whole watts, clamped to zero."""
    return max(0, int(fraction * ftp))


def count_fit_steps(segments: list[WorkoutSegment]) -> int:
    """Return the total number of FIT steps (each IntervalsT expands to 3: on, off, repeat)."""
    total = 0
    for seg in segments:
        total += 3 if isinstance(seg, IntervalsT) else 1
    return total


def _power_step(
    step_index: int,
    duration_secs: int,
    intensity: Intensity,
    low_w: int,
    high_w: int,
) -> WorkoutStepMessage:
    step = WorkoutStepMessage()
    step.step_index = step_index
    step.duration_type = WorkoutStepDuration.TIME
    step.duration_value = _ms(duration_secs)
    step.intensity = intensity
    step.target_type = WorkoutStepTarget.POWER
    step.custom_target_power_low = low_w
    step.custom_target_power_high = high_w
    return step


def _open_step(
    step_index: int,
    duration_secs: int,
    intensity: Intensity,
) -> WorkoutStepMessage:
    step = WorkoutStepMessage()
    step.step_index = step_index
    step.duration_type = WorkoutStepDuration.TIME
    step.duration_value = _ms(duration_secs)
    step.intensity = intensity
    step.target_type = WorkoutStepTarget.OPEN
    return step


def _repeat_step(
    step_index: int,
    repeat_count: int,
    back_to_step: int,
) -> WorkoutStepMessage:
    step = WorkoutStepMessage()
    step.step_index = step_index
    step.duration_type = WorkoutStepDuration.REPEAT_UNTIL_STEPS_CMPLT
    step.duration_value = repeat_count
    step.target_repeat_steps = back_to_step
    return step


def segment_to_fit_steps(
    segment: WorkoutSegment,
    step_index: int,
    ftp: int,
) -> list[WorkoutStepMessage]:
    """Convert a single workout segment to one or more FIT WorkoutStepMessages."""
    if isinstance(segment, Warmup):
        return [_power_step(
            step_index, segment.duration, Intensity.WARMUP,
            _watts(segment.power_low, ftp), _watts(segment.power_high, ftp),
        )]

    if isinstance(segment, Cooldown):
        return [_power_step(
            step_index, segment.duration, Intensity.COOLDOWN,
            _watts(segment.power_low, ftp), _watts(segment.power_high, ftp),
        )]

    if isinstance(segment, SteadyState):
        w = _watts(segment.power, ftp)
        return [_power_step(step_index, segment.duration, Intensity.ACTIVE, w, w)]

    if isinstance(segment, IntervalsT):
        on_w = _watts(segment.on_power, ftp)
        off_w = _watts(segment.off_power, ftp)
        return [
            _power_step(step_index, segment.on_duration, Intensity.INTERVAL, on_w, on_w),
            _power_step(step_index + 1, segment.off_duration, Intensity.RECOVERY, off_w, off_w),
            _repeat_step(step_index + 2, segment.repeat, step_index),
        ]

    if isinstance(segment, FreeRide):
        return [_open_step(step_index, segment.duration, Intensity.ACTIVE)]

    if isinstance(segment, Ramp):
        return [_power_step(
            step_index, segment.duration, Intensity.ACTIVE,
            _watts(segment.power_low, ftp), _watts(segment.power_high, ftp),
        )]

    if isinstance(segment, MaxEffort):
        return [_open_step(step_index, segment.duration, Intensity.ACTIVE)]

    raise ValueError(f"Unknown segment type: {type(segment).__name__}")


def workout_to_fit(workout: Workout, ftp: int = 200) -> bytes:
    """Convert a Workout to a Garmin FIT workout file.

    Args:
        workout: The workout to convert.
        ftp: Functional Threshold Power in watts. Used to convert the fractional
             power targets stored in the workout (e.g. 0.75) to absolute watts.

    Returns:
        Raw bytes of a valid .fit file ready for import into Garmin Connect.
    """
    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    file_id = FileIdMessage()
    file_id.type = FileType.WORKOUT
    file_id.manufacturer = Manufacturer.DEVELOPMENT.value
    file_id.product = 0
    file_id.time_created = _unix_now_ms()
    file_id.serial_number = 0x12345678
    builder.add(file_id)

    workout_msg = WorkoutMessage()
    workout_msg.workout_name = workout.name
    workout_msg.sport = Sport.CYCLING if workout.sport_type == SportType.BIKE else Sport.RUNNING
    workout_msg.num_valid_steps = count_fit_steps(workout.segments)
    builder.add(workout_msg)

    step_index = 0
    for segment in workout.segments:
        steps = segment_to_fit_steps(segment, step_index, ftp)
        for step in steps:
            builder.add(step)
        step_index += len(steps)

    return builder.build().to_bytes()
