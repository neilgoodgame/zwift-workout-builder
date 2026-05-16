# Zwift Workout Builder

[![CI](https://github.com/neilgoodgame/zwift-workout-builder/actions/workflows/ci.yml/badge.svg)](https://github.com/neilgoodgame/zwift-workout-builder/actions/workflows/ci.yml)
[![Lint](https://github.com/neilgoodgame/zwift-workout-builder/actions/workflows/lint.yml/badge.svg)](https://github.com/neilgoodgame/zwift-workout-builder/actions/workflows/lint.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**https://github.com/neilgoodgame/zwift-workout-builder**

A command-line tool for creating structured Zwift workouts in the `.zwo` format, with optional export to Garmin FIT files for import into Garmin Connect.

## Installation

Requires Python 3.11+.

### With Poetry (recommended)

```bash
git clone git@github.com:neilgoodgame/zwift-workout-builder.git
cd zwift-workout-builder
poetry install
poetry run zwift-workout --help
```

### With pip

```bash
git clone git@github.com:neilgoodgame/zwift-workout-builder.git
cd zwift-workout-builder
pip install -r requirements.txt
pip install -e .
zwift-workout --help
```

For development (includes pytest, ruff, pre-commit):

```bash
pip install -r requirements-dev.txt
```

## Commands

### `create` — build a workout file

```
zwift-workout create [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--name TEXT` | Workout name *(required)* |
| `--author TEXT` | Author name |
| `--description TEXT` | Workout description |
| `--sport-type [bike\|run]` | Sport type (default: `bike`) |
| `--tag TAG` | Tag, repeatable |
| `--segment SEGMENT` | Workout segment, repeatable — see format below |
| `--output FILE` | Output `.zwo` path (default: `<name>.zwo`) |
| `--garmin` | Also export a Garmin FIT file (`.fit`) |
| `--ftp INTEGER` | FTP in watts for Garmin power conversion (default: `200`) |

### `info` — inspect an existing `.zwo` file

```
zwift-workout info <file.zwo>
```

## Segment format

Segments are specified as `TYPE:param=value,param=value,...` and can be repeated to build up a workout.

| Type | Required parameters | Optional parameters |
|------|--------------------|--------------------|
| `warmup` | `duration`, `power_low`, `power_high` | |
| `cooldown` | `duration`, `power_low`, `power_high` | |
| `steady` | `duration`, `power` | `cadence` |
| `intervals` | `repeat`, `on_duration`, `off_duration`, `on_power`, `off_power` | `cadence`, `cadence_resting` |
| `freeride` | `duration` | `flat_road` |
| `ramp` | `duration`, `power_low`, `power_high` | |
| `maxeffort` | `duration` | |

- **Duration** values are in seconds.
- **Power** values are fractions of FTP — `0.75` means 75% FTP, `1.05` means 105% FTP.
- **Cadence** values are in RPM.

## Examples

### Sweet spot training

```bash
zwift-workout create \
  --name "Sweet Spot Base" \
  --author "Neil" \
  --description "Solid sweet spot session" \
  --tag "training" --tag "base" \
  --segment "warmup:duration=600,power_low=0.25,power_high=0.75" \
  --segment "steady:duration=1200,power=0.88,cadence=90" \
  --segment "steady:duration=1200,power=0.88,cadence=90" \
  --segment "cooldown:duration=300,power_low=0.75,power_high=0.25"
```

### VO2 max intervals with Garmin export

```bash
zwift-workout create \
  --name "VO2 Max Intervals" \
  --segment "warmup:duration=600,power_low=0.25,power_high=0.75" \
  --segment "intervals:repeat=6,on_duration=180,off_duration=180,on_power=1.05,off_power=0.5,cadence=95,cadence_resting=85" \
  --segment "cooldown:duration=600,power_low=0.75,power_high=0.25" \
  --garmin --ftp 265
```

Produces `VO2 Max Intervals.zwo` (for Zwift) and `VO2 Max Intervals.fit` (for Garmin Connect).

### Inspect an existing file

```bash
zwift-workout info "VO2 Max Intervals.zwo"
```

## Garmin Connect import

When `--garmin` is used, a `.fit` workout file is generated alongside the `.zwo`. To import into Garmin Connect:

1. Go to [Garmin Connect](https://connect.garmin.com) → **Training & Planning** → **Workouts**
2. Click **Import Workout** and select the `.fit` file

The `--ftp` value controls how fractional power targets are converted to watts in the FIT file. Set it to match your current FTP for accurate power zones on your device.

## Project structure

```
zwift_workout/
├── models.py          # Dataclasses for workout segments
├── xml_generator.py   # Zwift .zwo XML serialisation
├── garmin_exporter.py # Garmin FIT file generation
└── cli.py             # Click CLI
tests/
├── test_models.py
├── test_xml_generator.py
├── test_garmin_exporter.py
└── test_cli.py
```

## Running tests

```bash
poetry run pytest
```

## Dependencies

- [click](https://click.palletsprojects.com/) — CLI framework
- [fit-tool](https://pypi.org/project/fit-tool/) — Garmin FIT file generation
