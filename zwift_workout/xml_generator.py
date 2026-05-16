"""Convert Workout objects to Zwift .zwo XML format."""

import xml.dom.minidom
import xml.etree.ElementTree as ET

from zwift_workout.models import (
    Cooldown,
    FreeRide,
    IntervalsT,
    MaxEffort,
    Ramp,
    SteadyState,
    Warmup,
    Workout,
    WorkoutSegment,
)


def _fmt(power: float) -> str:
    return f"{power:.2f}"


def segment_to_element(segment: WorkoutSegment) -> ET.Element:
    """Convert a single segment to its XML element."""
    if isinstance(segment, Warmup):
        el = ET.Element("Warmup")
        el.set("Duration", str(segment.duration))
        el.set("PowerLow", _fmt(segment.power_low))
        el.set("PowerHigh", _fmt(segment.power_high))

    elif isinstance(segment, Cooldown):
        el = ET.Element("Cooldown")
        el.set("Duration", str(segment.duration))
        el.set("PowerLow", _fmt(segment.power_low))
        el.set("PowerHigh", _fmt(segment.power_high))

    elif isinstance(segment, SteadyState):
        el = ET.Element("SteadyState")
        el.set("Duration", str(segment.duration))
        el.set("Power", _fmt(segment.power))
        if segment.cadence is not None:
            el.set("Cadence", str(segment.cadence))

    elif isinstance(segment, IntervalsT):
        el = ET.Element("IntervalsT")
        el.set("Repeat", str(segment.repeat))
        el.set("OnDuration", str(segment.on_duration))
        el.set("OffDuration", str(segment.off_duration))
        el.set("OnPower", _fmt(segment.on_power))
        el.set("OffPower", _fmt(segment.off_power))
        if segment.cadence is not None:
            el.set("Cadence", str(segment.cadence))
        if segment.cadence_resting is not None:
            el.set("CadenceResting", str(segment.cadence_resting))

    elif isinstance(segment, FreeRide):
        el = ET.Element("FreeRide")
        el.set("Duration", str(segment.duration))
        el.set("FlatRoad", "1" if segment.flat_road else "0")

    elif isinstance(segment, Ramp):
        el = ET.Element("Ramp")
        el.set("Duration", str(segment.duration))
        el.set("PowerLow", _fmt(segment.power_low))
        el.set("PowerHigh", _fmt(segment.power_high))

    elif isinstance(segment, MaxEffort):
        el = ET.Element("MaxEffort")
        el.set("Duration", str(segment.duration))

    else:
        raise ValueError(f"Unknown segment type: {type(segment).__name__}")

    return el


def workout_to_xml(workout: Workout) -> str:
    """Serialize a Workout to a pretty-printed .zwo XML string."""
    root = ET.Element("workout_file")

    ET.SubElement(root, "author").text = workout.author
    ET.SubElement(root, "name").text = workout.name
    ET.SubElement(root, "description").text = workout.description
    ET.SubElement(root, "sportType").text = workout.sport_type.value

    if workout.tags:
        tags_el = ET.SubElement(root, "tags")
        for tag in workout.tags:
            tag_el = ET.SubElement(tags_el, "tag")
            tag_el.set("name", tag)

    workout_el = ET.SubElement(root, "workout")
    for segment in workout.segments:
        workout_el.append(segment_to_element(segment))

    raw = ET.tostring(root, encoding="unicode", xml_declaration=False)
    dom = xml.dom.minidom.parseString(raw)
    return dom.toprettyxml(indent="    ", encoding=None)
