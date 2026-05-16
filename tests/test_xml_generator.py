"""Tests for .zwo XML generation."""

import xml.etree.ElementTree as ET

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
from zwift_workout.xml_generator import segment_to_element, workout_to_xml


def parse_xml(xml_str: str) -> ET.Element:
    return ET.fromstring(xml_str)


class TestSegmentToElement:
    def test_warmup(self):
        el = segment_to_element(Warmup(duration=300, power_low=0.25, power_high=0.75))
        assert el.tag == "Warmup"
        assert el.get("Duration") == "300"
        assert el.get("PowerLow") == "0.25"
        assert el.get("PowerHigh") == "0.75"

    def test_cooldown(self):
        el = segment_to_element(Cooldown(duration=180, power_low=0.50, power_high=0.75))
        assert el.tag == "Cooldown"
        assert el.get("Duration") == "180"
        assert el.get("PowerLow") == "0.50"
        assert el.get("PowerHigh") == "0.75"

    def test_steady_state_no_cadence(self):
        el = segment_to_element(SteadyState(duration=600, power=0.88))
        assert el.tag == "SteadyState"
        assert el.get("Duration") == "600"
        assert el.get("Power") == "0.88"
        assert el.get("Cadence") is None

    def test_steady_state_with_cadence(self):
        el = segment_to_element(SteadyState(duration=600, power=0.88, cadence=90))
        assert el.get("Cadence") == "90"

    def test_intervals_basic(self):
        el = segment_to_element(IntervalsT(
            repeat=5, on_duration=60, off_duration=120,
            on_power=1.20, off_power=0.50,
        ))
        assert el.tag == "IntervalsT"
        assert el.get("Repeat") == "5"
        assert el.get("OnDuration") == "60"
        assert el.get("OffDuration") == "120"
        assert el.get("OnPower") == "1.20"
        assert el.get("OffPower") == "0.50"
        assert el.get("Cadence") is None
        assert el.get("CadenceResting") is None

    def test_intervals_with_cadence(self):
        el = segment_to_element(IntervalsT(
            repeat=5, on_duration=60, off_duration=120,
            on_power=1.20, off_power=0.50,
            cadence=100, cadence_resting=80,
        ))
        assert el.get("Cadence") == "100"
        assert el.get("CadenceResting") == "80"

    def test_freeride_default(self):
        el = segment_to_element(FreeRide(duration=600))
        assert el.tag == "FreeRide"
        assert el.get("Duration") == "600"
        assert el.get("FlatRoad") == "0"

    def test_freeride_flat(self):
        el = segment_to_element(FreeRide(duration=600, flat_road=True))
        assert el.get("FlatRoad") == "1"

    def test_ramp(self):
        el = segment_to_element(Ramp(duration=300, power_low=0.50, power_high=1.00))
        assert el.tag == "Ramp"
        assert el.get("PowerLow") == "0.50"
        assert el.get("PowerHigh") == "1.00"

    def test_max_effort(self):
        el = segment_to_element(MaxEffort(duration=30))
        assert el.tag == "MaxEffort"
        assert el.get("Duration") == "30"

    def test_unknown_segment_raises(self):
        from zwift_workout.models import WorkoutSegment

        class UnknownSegment(WorkoutSegment):
            pass

        with pytest.raises(ValueError, match="Unknown segment type"):
            segment_to_element(UnknownSegment())


class TestWorkoutToXml:
    def _make_workout(self) -> Workout:
        w = Workout(
            name="Sweet Spot Base",
            author="Neil",
            description="A solid sweet-spot session",
            sport_type=SportType.BIKE,
            tags=["training", "base"],
        )
        w.add_segment(Warmup(duration=600, power_low=0.25, power_high=0.75))
        w.add_segment(SteadyState(duration=1200, power=0.88))
        w.add_segment(Cooldown(duration=300, power_low=0.75, power_high=0.25))
        return w

    def test_produces_valid_xml(self):
        xml_str = workout_to_xml(self._make_workout())
        root = parse_xml(xml_str)
        assert root.tag == "workout_file"

    def test_metadata_fields(self):
        root = parse_xml(workout_to_xml(self._make_workout()))
        assert root.findtext("name") == "Sweet Spot Base"
        assert root.findtext("author") == "Neil"
        assert root.findtext("description") == "A solid sweet-spot session"
        assert root.findtext("sportType") == "bike"

    def test_tags(self):
        root = parse_xml(workout_to_xml(self._make_workout()))
        tags_el = root.find("tags")
        assert tags_el is not None
        tag_names = {t.get("name") for t in tags_el.findall("tag")}
        assert tag_names == {"training", "base"}

    def test_segment_count(self):
        root = parse_xml(workout_to_xml(self._make_workout()))
        workout_el = root.find("workout")
        assert workout_el is not None
        assert len(list(workout_el)) == 3

    def test_segment_order(self):
        root = parse_xml(workout_to_xml(self._make_workout()))
        children = list(root.find("workout"))
        assert children[0].tag == "Warmup"
        assert children[1].tag == "SteadyState"
        assert children[2].tag == "Cooldown"

    def test_no_tags_omits_tags_element(self):
        w = Workout(name="No Tags")
        w.add_segment(SteadyState(duration=300, power=0.75))
        root = parse_xml(workout_to_xml(w))
        assert root.find("tags") is None

    def test_run_sport_type(self):
        w = Workout(name="Run", sport_type=SportType.RUN)
        w.add_segment(SteadyState(duration=300, power=0.75))
        root = parse_xml(workout_to_xml(w))
        assert root.findtext("sportType") == "run"

    def test_output_is_pretty_printed(self):
        w = Workout(name="Test")
        w.add_segment(SteadyState(duration=300, power=0.75))
        xml_str = workout_to_xml(w)
        assert "\n" in xml_str
        assert "    " in xml_str  # indented
