"""Tests for the CLI commands."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from click.testing import CliRunner

from zwift_workout.cli import main, parse_segment
from zwift_workout.models import (
    Cooldown,
    FreeRide,
    IntervalsT,
    MaxEffort,
    Ramp,
    SteadyState,
    Warmup,
)


@pytest.fixture
def runner():
    return CliRunner()


class TestParseSegment:
    def test_warmup(self):
        seg = parse_segment("warmup:duration=300,power_low=0.25,power_high=0.75")
        assert isinstance(seg, Warmup)
        assert seg.duration == 300
        assert seg.power_low == 0.25
        assert seg.power_high == 0.75

    def test_cooldown(self):
        seg = parse_segment("cooldown:duration=300,power_low=0.25,power_high=0.75")
        assert isinstance(seg, Cooldown)

    def test_steady(self):
        seg = parse_segment("steady:duration=600,power=0.88")
        assert isinstance(seg, SteadyState)
        assert seg.power == 0.88
        assert seg.cadence is None

    def test_steady_with_cadence(self):
        seg = parse_segment("steady:duration=600,power=0.88,cadence=90")
        assert isinstance(seg, SteadyState)
        assert seg.cadence == 90

    def test_steadystate_alias(self):
        seg = parse_segment("steadystate:duration=600,power=0.75")
        assert isinstance(seg, SteadyState)

    def test_intervals(self):
        seg = parse_segment("intervals:repeat=5,on_duration=60,off_duration=120,on_power=1.2,off_power=0.5")
        assert isinstance(seg, IntervalsT)
        assert seg.repeat == 5
        assert seg.on_duration == 60
        assert seg.off_duration == 120
        assert seg.on_power == 1.2
        assert seg.off_power == 0.5

    def test_intervals_with_cadence(self):
        seg = parse_segment(
            "intervals:repeat=5,on_duration=60,off_duration=120,"
            "on_power=1.2,off_power=0.5,cadence=100,cadence_resting=80"
        )
        assert isinstance(seg, IntervalsT)
        assert seg.cadence == 100
        assert seg.cadence_resting == 80

    def test_intervalst_alias(self):
        seg = parse_segment("intervalst:repeat=3,on_duration=30,off_duration=60,on_power=1.5,off_power=0.4")
        assert isinstance(seg, IntervalsT)

    def test_freeride(self):
        seg = parse_segment("freeride:duration=600")
        assert isinstance(seg, FreeRide)
        assert seg.flat_road is False

    def test_freeride_flat(self):
        seg = parse_segment("freeride:duration=600,flat_road=true")
        assert isinstance(seg, FreeRide)
        assert seg.flat_road is True

    def test_ramp(self):
        seg = parse_segment("ramp:duration=300,power_low=0.5,power_high=1.0")
        assert isinstance(seg, Ramp)
        assert seg.power_low == 0.5
        assert seg.power_high == 1.0

    def test_maxeffort(self):
        seg = parse_segment("maxeffort:duration=30")
        assert isinstance(seg, MaxEffort)
        assert seg.duration == 30

    def test_missing_colon_raises(self):
        from click import BadParameter
        with pytest.raises(BadParameter, match="format"):
            parse_segment("warmup_duration=300")

    def test_unknown_type_raises(self):
        from click import BadParameter
        with pytest.raises(BadParameter, match="Unknown segment type"):
            parse_segment("sprint:duration=30")

    def test_missing_required_param_raises(self):
        from click import BadParameter
        with pytest.raises(BadParameter, match="requires"):
            parse_segment("warmup:duration=300,power_low=0.25")

    def test_bad_int_param_raises(self):
        from click import BadParameter
        with pytest.raises(BadParameter, match="integer"):
            parse_segment("warmup:duration=abc,power_low=0.25,power_high=0.75")

    def test_bad_float_param_raises(self):
        from click import BadParameter
        with pytest.raises(BadParameter, match="number"):
            parse_segment("warmup:duration=300,power_low=high,power_high=0.75")


class TestCreateCommand:
    def test_basic_create(self, runner, tmp_path):
        output = tmp_path / "test.zwo"
        result = runner.invoke(main, [
            "create",
            "--name", "Test Workout",
            "--output", str(output),
            "--segment", "warmup:duration=300,power_low=0.25,power_high=0.75",
            "--segment", "steady:duration=600,power=0.88",
            "--segment", "cooldown:duration=300,power_low=0.75,power_high=0.25",
        ])
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_output_is_valid_xml(self, runner, tmp_path):
        output = tmp_path / "workout.zwo"
        runner.invoke(main, [
            "create",
            "--name", "XML Test",
            "--output", str(output),
            "--segment", "steady:duration=300,power=0.75",
        ])
        root = ET.parse(str(output)).getroot()
        assert root.tag == "workout_file"
        assert root.findtext("name") == "XML Test"

    def test_metadata_written_to_file(self, runner, tmp_path):
        output = tmp_path / "meta.zwo"
        runner.invoke(main, [
            "create",
            "--name", "Meta Test",
            "--author", "Neil",
            "--description", "A test",
            "--sport-type", "run",
            "--tag", "speed",
            "--tag", "track",
            "--output", str(output),
            "--segment", "steady:duration=300,power=0.75",
        ])
        root = ET.parse(str(output)).getroot()
        assert root.findtext("author") == "Neil"
        assert root.findtext("description") == "A test"
        assert root.findtext("sportType") == "run"
        tag_names = {t.get("name") for t in root.find("tags").findall("tag")}
        assert tag_names == {"speed", "track"}

    def test_default_output_filename(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, [
                "create",
                "--name", "My Workout",
                "--segment", "steady:duration=300,power=0.75",
            ])
            assert result.exit_code == 0, result.output
            assert Path("My Workout.zwo").exists()

    def test_no_segments_fails(self, runner):
        result = runner.invoke(main, ["create", "--name", "Empty"])
        assert result.exit_code != 0
        assert "segment" in result.output.lower()

    def test_no_name_fails(self, runner):
        result = runner.invoke(main, [
            "create",
            "--segment", "steady:duration=300,power=0.75",
        ])
        assert result.exit_code != 0

    def test_invalid_segment_fails(self, runner):
        result = runner.invoke(main, [
            "create",
            "--name", "Bad",
            "--segment", "notasegment",
        ])
        assert result.exit_code != 0

    def test_summary_output(self, runner, tmp_path):
        output = tmp_path / "s.zwo"
        result = runner.invoke(main, [
            "create",
            "--name", "Summary Test",
            "--output", str(output),
            "--segment", "warmup:duration=600,power_low=0.25,power_high=0.75",
            "--segment", "steady:duration=1200,power=0.88",
            "--segment", "cooldown:duration=300,power_low=0.75,power_high=0.25",
        ])
        assert "35m" in result.output  # 600+1200+300 = 2100s = 35m


class TestInfoCommand:
    def test_info_on_created_file(self, runner, tmp_path):
        output = tmp_path / "info_test.zwo"
        runner.invoke(main, [
            "create",
            "--name", "Info Workout",
            "--author", "Neil",
            "--output", str(output),
            "--segment", "steady:duration=300,power=0.75",
        ])
        result = runner.invoke(main, ["info", str(output)])
        assert result.exit_code == 0, result.output
        assert "Info Workout" in result.output
        assert "Neil" in result.output
        assert "SteadyState" in result.output

    def test_info_missing_file_fails(self, runner):
        result = runner.invoke(main, ["info", "nonexistent.zwo"])
        assert result.exit_code != 0
