#!/usr/bin/env python3
"""CLI launcher for configurable programs in the programs/ directory."""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
PROGRAMS_DIR = ROOT / "programs"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from program_elements.program import Program  # noqa: E402


def discover_programs(programs_dir: Path) -> dict[str, type[Program]]:
    """Load Program subclasses from Python files in programs_dir."""
    from program_elements.program import Program as ProgramBase

    discovered: dict[str, type[Program]] = {}
    if not programs_dir.is_dir():
        return discovered

    for path in sorted(programs_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"programs.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            print(f"Skipping {path.name}: {exc}", file=sys.stderr)
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, ProgramBase)
                and obj is not ProgramBase
                and obj.__module__ == module_name
            ):
                discovered[obj.__name__] = obj

    return discovered


def apply_config(program: Program, path: Path) -> None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc

    if not data:
        return
    if not isinstance(data, dict):
        raise ValueError("Config must be a YAML mapping")

    for key, value in data.items():
        if key not in program.PARAMETERS:
            raise ValueError(f"Unknown parameter: {key}")
        if isinstance(value, list):
            value = tuple(value)
        try:
            program.set_parameter(key, value)
        except ValueError as exc:
            raise ValueError(f"Invalid value for parameter {key}: {exc}") from exc


def main() -> None:
    programs = discover_programs(PROGRAMS_DIR)
    if not programs:
        print(f"No programs found in {PROGRAMS_DIR}", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Run fybot programs (Program subclasses from programs/)."
    )
    parser.add_argument(
        "--program",
        required=True,
        choices=sorted(programs),
        metavar="NAME",
        help=f"program to run ({', '.join(sorted(programs))})",
    )
    parser.add_argument(
        "--config",
        type=Path,
        metavar="FILE",
        help="YAML file with parameter values for the selected program",
    )
    args = parser.parse_args()

    program_class = programs[args.program]
    program = program_class()

    if args.config:
        try:
            apply_config(program, args.config)
        except ValueError as exc:
            print(f"Config error: {exc}", file=sys.stderr)
            sys.exit(1)

    try:
        program.run()
    except KeyboardInterrupt:
        program.stop()
        print("Stopped.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
