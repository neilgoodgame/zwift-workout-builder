"""Tests for workout data models."""

import pytest

from zwift_workout.models import (
    Cooldown,
    FreeRide,
    IntervalsT,
    MaxEffort,
    Ramp,
    SportType,
    SteadyState,
    Warmup,
    Workout,
)


class TestWarmup:
    def test_valid(self):
        seg = Warmup(duration=300, power_low=0.25, power_high=0.75)
        assert seg.duration == 300
        assert seg.power_low == 0.25
        assert seg.power_high == 0.75

    def test_zero_duration_raises(self):
        with pytest.raises(ValueError, match="Duration must be positive"):
            Warmup(duration=0, power_low=0.25, power_high=0.75)

    def test_negative_duration_raises(self):
        with pytest.raises(ValueError, match="Duration must be positive"):
            Warmup(duration=-60, power_low=0.25, power_high=0.75)

    def test_negative_power_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            Warmup(duration=300, power_low=-0.1, power_high=0.75)


class TestCooldown:
    def test_valid(self):
        seg = Cooldown(duration=300, power_low=0.25, power_high=0.75)
        assert seg.duration == 300

    def test_zero_duration_raises(self):
        with pytest.raises(ValueError):
            Cooldown(duration=0, power_low=0.25, power_high=0.75)

    def test_negative_power_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            Cooldown(duration=300, power_low=0.25, power_high=-0.1)


class TestSteadyState:
    def test_valid_no_cadence(self):
        seg = SteadyState(duration=600, power=0.75)
        assert seg.duration == 600
        assert seg.power == 0.75
        assert seg.cadence is None

    def test_valid_with_cadence(self):
        seg = SteadyState(duration=600, power=0.88, cadence=90)
        assert seg.cadence == 90

    def test_zero_duration_raises(self):
        with pytest.raises(ValueError):
            SteadyState(duration=0, power=0.75)

    def test_negative_power_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            SteadyState(duration=600, power=-0.1)

    def test_zero_cadence_raises(self):
        with pytest.raises(ValueError, match="Cadence must be positive"):
            SteadyState(duration=600, power=0.75, cadence=0)


class TestIntervalsT:
    def test_valid(self):
        seg = IntervalsT(
            repeat=5, on_duration=60, off_duration=120,
            on_power=1.2, off_power=0.5,
        )
        assert seg.repeat == 5
        assert seg.cadence is None
        assert seg.cadence_resting is None

    def test_total_duration(self):
        seg = IntervalsT(
            repeat=4, on_duration=60, off_duration=120,
            on_power=1.2, off_power=0.5,
        )
        assert seg.total_duration == 4 * (60 + 120)

    def test_with_cadence(self):
        seg = IntervalsT(
            repeat=5, on_duration=60, off_duration=120,
            on_power=1.2, off_power=0.5,
            cadence=100, cadence_resting=80,
        )
        assert seg.cadence == 100
        assert seg.cadence_resting == 80

    def test_zero_repeat_raises(self):
        with pytest.raises(ValueError, match="Repeat must be positive"):
            IntervalsT(repeat=0, on_duration=60, off_duration=120, on_power=1.2, off_power=0.5)

    def test_zero_on_duration_raises(self):
        with pytest.raises(ValueError, match="on_duration must be positive"):
            IntervalsT(repeat=5, on_duration=0, off_duration=120, on_power=1.2, off_power=0.5)

    def test_negative_power_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            IntervalsT(repeat=5, on_duration=60, off_duration=120, on_power=-1.0, off_power=0.5)


class TestFreeRide:
    def test_valid_defaults(self):
        seg = FreeRide(duration=600)
        assert seg.duration == 600
        assert seg.flat_road is False

    def test_flat_road(self):
        seg = FreeRide(duration=300, flat_road=True)
        assert seg.flat_road is True

    def test_zero_duration_raises(self):
        with pytest.raises(ValueError):
            FreeRide(duration=0)


class TestRamp:
    def test_valid(self):
        seg = Ramp(duration=300, power_low=0.5, power_high=1.0)
        assert seg.power_low == 0.5
        assert seg.power_high == 1.0

    def test_zero_duration_raises(self):
        with pytest.raises(ValueError):
            Ramp(duration=0, power_low=0.5, power_high=1.0)


class TestMaxEffort:
    def test_valid(self):
        seg = MaxEffort(duration=30)
        assert seg.duration == 30

    def test_zero_duration_raises(self):
        with pytest.raises(ValueError):
            MaxEffort(duration=0)


class TestWorkout:
    def test_defaults(self):
        w = Workout(name="Test")
        assert w.author == ""
        assert w.description == ""
        assert w.sport_type == SportType.BIKE
        assert w.tags == []
        assert w.segments == []

    def test_add_segment(self):
        w = Workout(name="Test")
        seg = SteadyState(duration=300, power=0.75)
        result = w.add_segment(seg)
        assert result is w
        assert len(w.segments) == 1

    def test_total_duration_mixed_segments(self):
        w = Workout(name="Test")
        w.add_segment(Warmup(duration=300, power_low=0.25, power_high=0.75))
        w.add_segment(SteadyState(duration=600, power=0.88))
        w.add_segment(IntervalsT(
            repeat=4, on_duration=60, off_duration=120,
            on_power=1.2, off_power=0.5,
        ))
        w.add_segment(Cooldown(duration=300, power_low=0.75, power_high=0.25))
        # 300 + 600 + 4*(60+120) + 300 = 300 + 600 + 720 + 300 = 1920
        assert w.total_duration == 1920

    def test_total_duration_empty(self):
        assert Workout(name="Empty").total_duration == 0

    def test_sport_type_run(self):
        w = Workout(name="Run workout", sport_type=SportType.RUN)
        assert w.sport_type == SportType.RUN
