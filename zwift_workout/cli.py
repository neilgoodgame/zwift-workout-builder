"""Command-line interface for Zwift Workout Builder."""

import xml.etree.ElementTree as ET
from pathlib import Path

import click

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
from zwift_workout.garmin_exporter import workout_to_fit
from zwift_workout.xml_generator import workout_to_xml

_SEGMENT_FORMATS = """\b
Segment format: TYPE:param=value,param=value,...

Segment types and required parameters:

  warmup:duration=SECS,power_low=FTP,power_high=FTP
  cooldown:duration=SECS,power_low=FTP,power_high=FTP
  steady:duration=SECS,power=FTP[,cadence=RPM]
  intervals:repeat=N,on_duration=SECS,off_duration=SECS,on_power=FTP,off_power=FTP
            [,cadence=RPM][,cadence_resting=RPM]
  freeride:duration=SECS[,flat_road=true|false]
  ramp:duration=SECS,power_low=FTP,power_high=FTP
  maxeffort:duration=SECS

Power values are fractions of FTP (e.g., 0.75 = 75% FTP, 1.05 = 105% FTP).
"""


def _parse_params(params_str: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for token in params_str.split(","):
        token = token.strip()
        if not token:
            continue
        if "=" not in token:
            raise click.BadParameter(f"Expected key=value, got '{token}'")
        k, v = token.split("=", 1)
        params[k.strip().lower()] = v.strip()
    return params


def parse_segment(segment_str: str) -> WorkoutSegment:
    """Parse a segment string into a WorkoutSegment object."""
    if ":" not in segment_str:
        raise click.BadParameter(
            f"'{segment_str}' must be in format 'type:param=value,...'\n"
            f"Run with --help to see supported segment types."
        )

    seg_type, params_str = segment_str.split(":", 1)
    seg_type = seg_type.strip().lower()
    params = _parse_params(params_str)

    def req_int(key: str) -> int:
        if key not in params:
            raise click.BadParameter(f"'{seg_type}' segment requires '{key}'")
        try:
            return int(params[key])
        except ValueError:
            raise click.BadParameter(f"'{key}' must be an integer, got '{params[key]}'")

    def req_float(key: str) -> float:
        if key not in params:
            raise click.BadParameter(f"'{seg_type}' segment requires '{key}'")
        try:
            return float(params[key])
        except ValueError:
            raise click.BadParameter(f"'{key}' must be a number, got '{params[key]}'")

    def opt_int(key: str) -> int | None:
        if key not in params:
            return None
        try:
            return int(params[key])
        except ValueError:
            raise click.BadParameter(f"'{key}' must be an integer, got '{params[key]}'")

    def opt_bool(key: str, default: bool = False) -> bool:
        return params.get(key, "").lower() in ("true", "1", "yes") if key in params else default

    try:
        if seg_type == "warmup":
            return Warmup(
                duration=req_int("duration"),
                power_low=req_float("power_low"),
                power_high=req_float("power_high"),
            )
        elif seg_type == "cooldown":
            return Cooldown(
                duration=req_int("duration"),
                power_low=req_float("power_low"),
                power_high=req_float("power_high"),
            )
        elif seg_type in ("steady", "steadystate"):
            return SteadyState(
                duration=req_int("duration"),
                power=req_float("power"),
                cadence=opt_int("cadence"),
            )
        elif seg_type in ("intervals", "intervalst"):
            return IntervalsT(
                repeat=req_int("repeat"),
                on_duration=req_int("on_duration"),
                off_duration=req_int("off_duration"),
                on_power=req_float("on_power"),
                off_power=req_float("off_power"),
                cadence=opt_int("cadence"),
                cadence_resting=opt_int("cadence_resting"),
            )
        elif seg_type == "freeride":
            return FreeRide(
                duration=req_int("duration"),
                flat_road=opt_bool("flat_road"),
            )
        elif seg_type == "ramp":
            return Ramp(
                duration=req_int("duration"),
                power_low=req_float("power_low"),
                power_high=req_float("power_high"),
            )
        elif seg_type == "maxeffort":
            return MaxEffort(duration=req_int("duration"))
        else:
            valid = "warmup, cooldown, steady, intervals, freeride, ramp, maxeffort"
            raise click.BadParameter(
                f"Unknown segment type '{seg_type}'. Valid types: {valid}"
            )
    except ValueError as e:
        raise click.BadParameter(str(e))


def _duration_str(seconds: int) -> str:
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()


@click.group()
@click.version_option()
def main():
    """Zwift Workout Builder — generate .zwo workout files for Zwift."""


@main.command()
@click.option("--name", required=True, help="Workout name.")
@click.option("--author", default="", show_default=False, help="Author name.")
@click.option("--description", default="", show_default=False, help="Workout description.")
@click.option(
    "--sport-type",
    type=click.Choice(["bike", "run"], case_sensitive=False),
    default="bike",
    show_default=True,
    help="Sport type.",
)
@click.option("--tag", multiple=True, metavar="TAG", help="Workout tag (repeatable).")
@click.option(
    "--segment",
    multiple=True,
    metavar="SEGMENT",
    help=_SEGMENT_FORMATS,
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Output file path (default: <name>.zwo).",
)
@click.option(
    "--garmin",
    is_flag=True,
    default=False,
    help="Also export a Garmin FIT workout file (.fit) for import into Garmin Connect.",
)
@click.option(
    "--ftp",
    type=click.IntRange(min=1),
    default=200,
    show_default=True,
    help="Functional Threshold Power in watts. Used to convert percentage-based power "
         "targets to absolute watts when generating a Garmin FIT file.",
)
def create(name, author, description, sport_type, tag, segment, output, garmin, ftp):
    """Create a new Zwift workout .zwo file.

    \b
    Example:
      zwift-workout create \\
        --name "Sweet Spot Base" \\
        --author "Neil" \\
        --tag "training" --tag "base" \\
        --segment "warmup:duration=600,power_low=0.25,power_high=0.75" \\
        --segment "steady:duration=1200,power=0.88,cadence=90" \\
        --segment "intervals:repeat=4,on_duration=60,off_duration=120,on_power=1.2,off_power=0.5" \\
        --segment "cooldown:duration=300,power_low=0.75,power_high=0.25" \\
        --garmin --ftp 250
    """
    if not segment:
        raise click.UsageError(
            "At least one --segment is required. Use --help for segment formats."
        )

    segments = []
    for seg_str in segment:
        try:
            segments.append(parse_segment(seg_str))
        except click.BadParameter as exc:
            raise click.UsageError(f"Invalid segment '{seg_str}': {exc}")

    workout = Workout(
        name=name,
        author=author,
        description=description,
        sport_type=SportType(sport_type.lower()),
        tags=list(tag),
        segments=segments,
    )

    if output is None:
        output = f"{_safe_filename(name)}.zwo"

    Path(output).write_text(workout_to_xml(workout), encoding="utf-8")

    click.echo(f"Written: {output}")
    click.echo(f"  Name     : {name}")
    click.echo(f"  Sport    : {sport_type}")
    click.echo(f"  Segments : {len(workout.segments)}")
    click.echo(f"  Duration : {_duration_str(workout.total_duration)}")
    if tag:
        click.echo(f"  Tags     : {', '.join(tag)}")

    if garmin:
        fit_path = Path(output).with_suffix(".fit")
        fit_path.write_bytes(workout_to_fit(workout, ftp=ftp))
        click.echo(f"Written: {fit_path}  (Garmin FIT, FTP={ftp}W)")


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
def info(file):
    """Show a summary of an existing .zwo file."""
    try:
        tree = ET.parse(file)
        root = tree.getroot()
    except ET.ParseError as exc:
        raise click.ClickException(f"Could not parse '{file}': {exc}")

    click.echo(f"Name        : {root.findtext('name', '—')}")
    click.echo(f"Author      : {root.findtext('author', '—')}")
    click.echo(f"Sport       : {root.findtext('sportType', '—')}")
    click.echo(f"Description : {root.findtext('description', '—')}")

    tags_el = root.find("tags")
    if tags_el is not None:
        tag_names = [t.get("name", "") for t in tags_el.findall("tag")]
        click.echo(f"Tags        : {', '.join(tag_names)}")

    workout_el = root.find("workout")
    if workout_el is not None:
        segments = list(workout_el)
        click.echo(f"Segments    : {len(segments)}")
        for seg in segments:
            attrs = ", ".join(f"{k}={v}" for k, v in seg.attrib.items())
            click.echo(f"  {seg.tag:<14} {attrs}")
