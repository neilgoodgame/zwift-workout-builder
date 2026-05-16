"""Tests for Garmin FIT workout export."""

import pytest
from fit_tool.fit_file import FitFile
from fit_tool.profile.profile_type import (
    Intensity,
    Sport,
    WorkoutStepDuration,
    WorkoutStepTarget,
)

from zwift_workout.garmin_exporter import (
    _watts,
    count_fit_steps,
    segment_to_fit_steps,
    workout_to_fit,
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
)

FIT_MAGIC = b".FIT"


# ---------------------------------------------------------------------------
# Helper: read back workout step messages from raw FIT bytes
# ---------------------------------------------------------------------------

def _step_messages(data: bytes) -> list:
    from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
    fit = FitFile.from_bytes(data)
    return [r.message for r in fit.records if isinstance(r.message, WorkoutStepMessage)]


def _workout_message(data: bytes):
    from fit_tool.profile.messages.workout_message import WorkoutMessage
    fit = FitFile.from_bytes(data)
    for r in fit.records:
        if isinstance(r.message, WorkoutMessage):
            return r.message
    return None


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestWatts:
    def test_basic_conversion(self):
        assert _watts(0.75, 200) == 150
        assert _watts(1.0, 200) == 200
        assert _watts(1.2, 200) == 240

    def test_rounds_down(self):
        assert _watts(0.333, 200) == 66   # 66.6 → 66

    def test_zero_fraction(self):
        assert _watts(0.0, 200) == 0

    def test_clamps_negative(self):
        # Shouldn't happen in practice but must not return negative watts
        assert _watts(-0.1, 200) == 0


class TestCountFitSteps:
    def test_simple_segments(self):
        segs = [
            Warmup(duration=300, power_low=0.25, power_high=0.75),
            SteadyState(duration=600, power=0.88),
            Cooldown(duration=300, power_low=0.75, power_high=0.25),
        ]
        assert count_fit_steps(segs) == 3

    def test_intervals_expand_to_three(self):
        segs = [IntervalsT(repeat=5, on_duration=60, off_duration=120, on_power=1.2, off_power=0.5)]
        assert count_fit_steps(segs) == 3  # on + off + repeat

    def test_mixed_with_intervals(self):
        segs = [
            Warmup(duration=300, power_low=0.25, power_high=0.75),
            IntervalsT(repeat=4, on_duration=60, off_duration=120, on_power=1.2, off_power=0.5),
            Cooldown(duration=300, power_low=0.75, power_high=0.25),
        ]
        assert count_fit_steps(segs) == 5  # 1 + 3 + 1

    def test_multiple_interval_blocks(self):
        segs = [
            IntervalsT(repeat=5, on_duration=60, off_duration=120, on_power=1.2, off_power=0.5),
            IntervalsT(repeat=3, on_duration=30, off_duration=60, on_power=1.5, off_power=0.4),
        ]
        assert count_fit_steps(segs) == 6  # 3 + 3

    def test_empty(self):
        assert count_fit_steps([]) == 0


# ---------------------------------------------------------------------------
# Unit tests for segment_to_fit_steps
# ---------------------------------------------------------------------------

class TestSegmentToFitSteps:
    # fit-tool returns raw ints from field accessors; compare with .value for enum equivalence.

    def test_warmup_produces_one_step(self):
        steps = segment_to_fit_steps(Warmup(duration=300, power_low=0.25, power_high=0.75), 0, 200)
        assert len(steps) == 1
        s = steps[0]
        assert s.step_index == 0
        assert s.duration_type == WorkoutStepDuration.TIME.value
        assert s.duration_value == 300_000
        assert s.intensity == Intensity.WARMUP.value
        assert s.target_type == WorkoutStepTarget.POWER.value
        assert s.custom_target_power_low == 50    # 0.25 * 200
        assert s.custom_target_power_high == 150  # 0.75 * 200

    def test_cooldown_produces_one_step(self):
        steps = segment_to_fit_steps(Cooldown(duration=300, power_low=0.50, power_high=0.75), 2, 200)
        assert len(steps) == 1
        s = steps[0]
        assert s.step_index == 2
        assert s.intensity == Intensity.COOLDOWN.value
        assert s.custom_target_power_low == 100
        assert s.custom_target_power_high == 150

    def test_steady_state_low_equals_high(self):
        steps = segment_to_fit_steps(SteadyState(duration=600, power=0.88), 0, 200)
        assert len(steps) == 1
        s = steps[0]
        assert s.intensity == Intensity.ACTIVE.value
        assert s.custom_target_power_low == s.custom_target_power_high == 176  # 0.88 * 200

    def test_intervals_produce_three_steps(self):
        steps = segment_to_fit_steps(
            IntervalsT(repeat=5, on_duration=60, off_duration=120, on_power=1.2, off_power=0.5),
            step_index=0, ftp=200,
        )
        assert len(steps) == 3
        on, off, repeat = steps

        assert on.step_index == 0
        assert on.duration_value == 60_000
        assert on.intensity == Intensity.INTERVAL.value
        assert on.custom_target_power_low == 240

        assert off.step_index == 1
        assert off.duration_value == 120_000
        assert off.intensity == Intensity.RECOVERY.value
        assert off.custom_target_power_low == 100

        assert repeat.step_index == 2
        assert repeat.duration_type == WorkoutStepDuration.REPEAT_UNTIL_STEPS_CMPLT.value
        assert repeat.duration_value == 5
        assert repeat.target_repeat_steps == 0  # go back to step 0

    def test_intervals_step_index_offset(self):
        # When intervals start at step_index=3, repeat must point back to 3
        steps = segment_to_fit_steps(
            IntervalsT(repeat=4, on_duration=60, off_duration=120, on_power=1.2, off_power=0.5),
            step_index=3, ftp=200,
        )
        on, off, repeat = steps
        assert on.step_index == 3
        assert off.step_index == 4
        assert repeat.step_index == 5
        assert repeat.target_repeat_steps == 3

    def test_freeride_open_target(self):
        steps = segment_to_fit_steps(FreeRide(duration=600), 0, 200)
        assert len(steps) == 1
        assert steps[0].target_type == WorkoutStepTarget.OPEN.value
        assert steps[0].custom_target_power_low is None

    def test_ramp_uses_power_target(self):
        steps = segment_to_fit_steps(Ramp(duration=300, power_low=0.5, power_high=1.0), 0, 200)
        assert len(steps) == 1
        assert steps[0].custom_target_power_low == 100
        assert steps[0].custom_target_power_high == 200

    def test_max_effort_open_target(self):
        steps = segment_to_fit_steps(MaxEffort(duration=30), 0, 200)
        assert len(steps) == 1
        assert steps[0].target_type == WorkoutStepTarget.OPEN.value

    def test_unknown_segment_raises(self):
        from zwift_workout.models import WorkoutSegment

        class UnknownSeg(WorkoutSegment):
            pass

        with pytest.raises(ValueError, match="Unknown segment type"):
            segment_to_fit_steps(UnknownSeg(), 0, 200)


# ---------------------------------------------------------------------------
# Integration tests for workout_to_fit
# ---------------------------------------------------------------------------

class TestWorkoutToFit:
    def _simple_workout(self) -> Workout:
        w = Workout(name="FIT Test", author="Neil")
        w.add_segment(Warmup(duration=300, power_low=0.25, power_high=0.75))
        w.add_segment(SteadyState(duration=600, power=0.75))
        w.add_segment(Cooldown(duration=300, power_low=0.75, power_high=0.25))
        return w

    def test_returns_bytes(self):
        data = workout_to_fit(self._simple_workout())
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_fit_magic_header(self):
        data = workout_to_fit(self._simple_workout())
        assert data[8:12] == FIT_MAGIC

    def test_readable_by_fit_tool(self):
        data = workout_to_fit(self._simple_workout())
        fit = FitFile.from_bytes(data)
        assert fit is not None

    def test_workout_name_in_file(self):
        w = Workout(name="My Threshold Session")
        w.add_segment(SteadyState(duration=300, power=1.0))
        wkt_msg = _workout_message(workout_to_fit(w))
        assert wkt_msg is not None
        assert wkt_msg.workout_name == "My Threshold Session"

    def test_num_valid_steps_matches(self):
        w = self._simple_workout()
        wkt_msg = _workout_message(workout_to_fit(w))
        assert wkt_msg.num_valid_steps == 3

    def test_sport_bike(self):
        w = Workout(name="Bike", sport_type=SportType.BIKE)
        w.add_segment(SteadyState(duration=300, power=0.75))
        wkt_msg = _workout_message(workout_to_fit(w))
        assert wkt_msg.sport == Sport.CYCLING.value

    def test_sport_run(self):
        w = Workout(name="Run", sport_type=SportType.RUN)
        w.add_segment(SteadyState(duration=300, power=0.75))
        wkt_msg = _workout_message(workout_to_fit(w))
        assert wkt_msg.sport == Sport.RUNNING.value

    def test_step_count_with_intervals(self):
        w = Workout(name="Intervals")
        w.add_segment(Warmup(duration=300, power_low=0.25, power_high=0.75))
        w.add_segment(IntervalsT(repeat=5, on_duration=60, off_duration=120, on_power=1.2, off_power=0.5))
        w.add_segment(Cooldown(duration=300, power_low=0.75, power_high=0.25))
        data = workout_to_fit(w)
        steps = _step_messages(data)
        assert len(steps) == 5  # warmup + on + off + repeat + cooldown

    def test_ftp_scales_power(self):
        w = Workout(name="FTP Scale Test")
        w.add_segment(SteadyState(duration=300, power=1.0))
        steps_200 = _step_messages(workout_to_fit(w, ftp=200))
        steps_300 = _step_messages(workout_to_fit(w, ftp=300))
        assert steps_200[0].custom_target_power_low == 200
        assert steps_300[0].custom_target_power_low == 300

    def test_default_ftp_is_200(self):
        w = Workout(name="Default FTP")
        w.add_segment(SteadyState(duration=300, power=1.0))
        steps = _step_messages(workout_to_fit(w))
        assert steps[0].custom_target_power_low == 200

    def test_interval_repeat_step_roundtrip(self):
        w = Workout(name="Repeat Test")
        w.add_segment(IntervalsT(repeat=4, on_duration=60, off_duration=120, on_power=1.2, off_power=0.5))
        steps = _step_messages(workout_to_fit(w, ftp=200))
        assert len(steps) == 3
        on, off, repeat = steps
        assert repeat.duration_type == WorkoutStepDuration.REPEAT_UNTIL_STEPS_CMPLT.value
        assert repeat.duration_value == 4
        assert repeat.target_repeat_steps == 0

    def test_all_segment_types_produce_valid_fit(self):
        w = Workout(name="All Types")
        w.add_segment(Warmup(duration=300, power_low=0.25, power_high=0.75))
        w.add_segment(SteadyState(duration=600, power=0.88))
        w.add_segment(IntervalsT(repeat=3, on_duration=60, off_duration=120, on_power=1.2, off_power=0.5))
        w.add_segment(FreeRide(duration=300))
        w.add_segment(Ramp(duration=300, power_low=0.5, power_high=1.0))
        w.add_segment(MaxEffort(duration=30))
        w.add_segment(Cooldown(duration=300, power_low=0.75, power_high=0.25))
        data = workout_to_fit(w, ftp=250)
        assert data[8:12] == FIT_MAGIC
        fit = FitFile.from_bytes(data)
        assert fit is not None


# ---------------------------------------------------------------------------
# CLI tests for --garmin flag
# ---------------------------------------------------------------------------

class TestGarminCli:
    def test_garmin_flag_creates_fit_file(self, tmp_path):
        from click.testing import CliRunner
        from zwift_workout.cli import main
        runner = CliRunner()
        zwo = tmp_path / "workout.zwo"
        fit = tmp_path / "workout.fit"
        result = runner.invoke(main, [
            "create",
            "--name", "Garmin Export",
            "--output", str(zwo),
            "--garmin",
            "--segment", "steady:duration=300,power=0.75",
        ])
        assert result.exit_code == 0, result.output
        assert fit.exists()
        assert fit.read_bytes()[8:12] == FIT_MAGIC

    def test_garmin_with_ftp(self, tmp_path):
        from click.testing import CliRunner
        from zwift_workout.cli import main
        runner = CliRunner()
        zwo = tmp_path / "workout.zwo"
        fit = tmp_path / "workout.fit"
        result = runner.invoke(main, [
            "create",
            "--name", "FTP Test",
            "--output", str(zwo),
            "--garmin",
            "--ftp", "280",
            "--segment", "steady:duration=300,power=1.0",
        ])
        assert result.exit_code == 0, result.output
        assert fit.exists()
        # 1.0 * 280W should be stored in the FIT file
        steps = _step_messages(fit.read_bytes())
        assert steps[0].custom_target_power_low == 280

    def test_garmin_output_mentions_fit_file(self, tmp_path):
        from click.testing import CliRunner
        from zwift_workout.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "create",
            "--name", "Output Test",
            "--output", str(tmp_path / "out.zwo"),
            "--garmin",
            "--ftp", "200",
            "--segment", "steady:duration=300,power=0.75",
        ])
        assert "Garmin FIT" in result.output
        assert "FTP=200W" in result.output

    def test_without_garmin_flag_no_fit_file(self, tmp_path):
        from click.testing import CliRunner
        from zwift_workout.cli import main
        runner = CliRunner()
        zwo = tmp_path / "workout.zwo"
        fit = tmp_path / "workout.fit"
        runner.invoke(main, [
            "create",
            "--name", "No Garmin",
            "--output", str(zwo),
            "--segment", "steady:duration=300,power=0.75",
        ])
        assert not fit.exists()

    def test_garmin_flag_also_creates_zwo(self, tmp_path):
        from click.testing import CliRunner
        from zwift_workout.cli import main
        runner = CliRunner()
        zwo = tmp_path / "out.zwo"
        result = runner.invoke(main, [
            "create",
            "--name", "Both Files",
            "--output", str(zwo),
            "--garmin",
            "--segment", "steady:duration=300,power=0.75",
        ])
        assert result.exit_code == 0, result.output
        assert zwo.exists()
        assert (tmp_path / "out.fit").exists()

    def test_ftp_must_be_positive(self, tmp_path):
        from click.testing import CliRunner
        from zwift_workout.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "create",
            "--name", "Bad FTP",
            "--output", str(tmp_path / "out.zwo"),
            "--garmin",
            "--ftp", "0",
            "--segment", "steady:duration=300,power=0.75",
        ])
        assert result.exit_code != 0

    def test_garmin_intervals_roundtrip(self, tmp_path):
        from click.testing import CliRunner
        from zwift_workout.cli import main
        runner = CliRunner()
        fit = tmp_path / "intervals.fit"
        runner.invoke(main, [
            "create",
            "--name", "Intervals",
            "--output", str(tmp_path / "intervals.zwo"),
            "--garmin",
            "--ftp", "200",
            "--segment", "warmup:duration=300,power_low=0.25,power_high=0.75",
            "--segment", "intervals:repeat=5,on_duration=60,off_duration=120,on_power=1.2,off_power=0.5",
            "--segment", "cooldown:duration=300,power_low=0.75,power_high=0.25",
        ])
        steps = _step_messages(fit.read_bytes())
        # warmup + on + off + repeat + cooldown = 5
        assert len(steps) == 5
        repeat_step = steps[3]
        assert repeat_step.duration_type == WorkoutStepDuration.REPEAT_UNTIL_STEPS_CMPLT.value
        assert repeat_step.duration_value == 5
        assert repeat_step.target_repeat_steps == 1  # back to the 'on' step (index 1)
