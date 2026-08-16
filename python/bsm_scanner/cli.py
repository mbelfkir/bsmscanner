from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from bsm_scanner import __version__, compile_model, load_model, run_scan
from bsm_scanner.exceptions import ModelValidationError

try:
    from bsm_scanner import _core  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _core = None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bsm-scanner",
        description="Run YAML-defined BSMScanner model scans.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="Run a scan from a model YAML file.")
    model_source = run_parser.add_mutually_exclusive_group(required=True)
    model_source.add_argument("--model", type=Path, help="Path to the model YAML file.")
    model_source.add_argument(
        "--example",
        choices=["quadratic"],
        help="Run a built-in lightweight example model.",
    )
    run_parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Directory where scan artifacts will be written.",
    )
    run_parser.add_argument(
        "--no-native-backend",
        action="store_true",
        help="Compile only the Python plan before launching engines that still require the native adapter.",
    )

    new_parser = subparsers.add_parser(
        "new-model",
        help="Create a runnable starter model wired to the shipped core library.",
    )
    new_parser.add_argument("name", help="Name of the model (a directory is created).")
    new_parser.add_argument(
        "--directory", type=Path, default=None,
        help="Where to create it (default: current directory).",
    )

    core_parser = subparsers.add_parser(
        "core",
        help="Inspect the reusable core YAML library shipped with the package.",
    )
    core_sub = core_parser.add_subparsers(dest="core_command")
    core_sub.add_parser("path", help="Print the directory holding the core library.")
    core_sub.add_parser("list", help="List every reusable core block.")
    show = core_sub.add_parser("show", help="Show what a core block defines.")
    show.add_argument("block", help="Block reference, e.g. core:neutrino/observables_common.yaml")

    return parser


_TEMPLATE = """\
metadata:
  name: {name}
  version: 0.1.0
  description: Starter BSMScanner model. Edit freely.

imports:
  # Reusable blocks shipped with BSMScanner. List them all with:
  #     bsm-scanner core list
  # and inspect what one provides with:
  #     bsm-scanner core show core:neutrino/observables_common.yaml
  - core:constants/physics_constants.yaml

parameters:
- name: x
  value_type: real
  scan: true
  lower: -5.0
  upper: 5.0
  default: 1.0
  prior: flat
- name: y
  value_type: real
  scan: true
  lower: -5.0
  upper: 5.0
  default: -1.0
  prior: flat

derived_scalars:
- name: radius
  value_type: real
  expression: sqrt(x**2 + y**2)

observables:
- name: r_obs
  value_type: real
  expression: radius

theory_checks:
- name: radius_is_positive
  condition: radius >= 0.0
  fatal: true

likelihoods:
- name: r_measurement
  kind: gaussian
  observable: r_obs
  mean: 2.0
  sigma: 0.1

outputs:
  save:
    - x
    - y
    - r_obs

scan:
  engine: serial_random
  seed: 12345
  settings:
    objective: nll
    max_evaluations: 200
    invalid_penalty: 1.0e12
"""


def _new_model(args: argparse.Namespace) -> int:
    root = (args.directory or Path.cwd()) / args.name
    if root.exists():
        print(f"bsm-scanner: error: '{root}' already exists.", file=sys.stderr)
        return 2
    root.mkdir(parents=True)
    model_path = root / "model.yaml"
    model_path.write_text(_TEMPLATE.format(name=args.name), encoding="utf-8")
    print(f"Created {model_path}")
    print("\nRun it with:")
    print(f"    bsm-scanner run --model {model_path} --run-dir {root / 'runs' / 'first'}")
    print("\nDiscover reusable physics blocks with:")
    print("    bsm-scanner core list")
    return 0


def _core_library(args: argparse.Namespace) -> int:
    from bsm_scanner.library import (
        core_library_path,
        describe_core_block,
        list_core_blocks,
    )

    try:
        if args.core_command == "path":
            print(core_library_path())
        elif args.core_command == "list":
            for block in list_core_blocks():
                print(block)
        elif args.core_command == "show":
            summary = describe_core_block(args.block)
            if not summary:
                print(f"{args.block} defines no named entries.")
                return 0
            for section, names in summary.items():
                print(f"{section} ({len(names)}):")
                for name in names:
                    print(f"  {name}")
        else:
            print(
                "Usage: bsm-scanner core {path|list|show <block>}",
                file=sys.stderr,
            )
            return 2
    except ModelValidationError as exc:
        print(f"bsm-scanner: error: {exc}", file=sys.stderr)
        return 2
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        if args.example:
            resource = resources.files("bsm_scanner.examples").joinpath(f"{args.example}.yaml")
            with resources.as_file(resource) as model_path:
                model = load_model(model_path)
        else:
            model = load_model(args.model)
        if model.scan.engine == "diver" and (_core is None or not _core.has_diver_support()):
            raise RuntimeError(
                "This model requests the Diver engine, but this build does not include Diver support. "
                "Reinstall with BSM_SCANNER_BUILD_DIVER enabled or choose a model/configuration using "
                "serial_random, de_scipy, adaptive_diver, or basin_scan."
            )
        compiled = compile_model(model, build_backend=not args.no_native_backend)
        results = run_scan(model, compiled, run_directory=args.run_dir)
    except (FileNotFoundError, ModelValidationError, RuntimeError) as exc:
        print(f"bsm-scanner: error: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "run_directory": str(results.run_directory),
                "points_path": str(results.points_path),
                "metadata_path": str(results.metadata_path),
                "best_fit_path": str(results.best_fit_path),
                "summary_path": str(results.summary_path),
                "summary": results.summary,
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    if args.command == "core":
        return _core_library(args)
    if args.command == "new-model":
        return _new_model(args)
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
