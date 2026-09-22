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

    dm_parser = subparsers.add_parser(
        "generate-dm-config",
        help="Assemble plugin_call YAML + a CMake cache script for the generic "
             "micromegas dark-matter plugin, from a binding map you supply.",
    )
    dm_parser.add_argument(
        "--map", type=Path, required=True,
        help="YAML (or JSON) file mapping CalcHEP parameter name -> model.yaml node "
             "name, e.g. 'MH01: MH1'. You author this; nothing is auto-matched.",
    )
    dm_parser.add_argument(
        "--dm-target-name", default=None,
        help="micrOMEGAs particle name of the intended dark-matter candidate, e.g. '~chi'. "
             "Omit to let micrOMEGAs choose the candidate itself (no target-match check "
             "is generated in that case).",
    )
    dm_parser.add_argument(
        "--vars-mdl", type=Path, default=None,
        help="Optional: the CalcHEP model's vars1.mdl, used only to validate that every "
             "--map key is a real independent CalcHEP parameter (catches typos early).",
    )
    dm_parser.add_argument(
        "--CalcHEP", dest="calchep_model_root", type=Path, default=None,
        help="Path to the compiled CalcHEP model directory (e.g. containing lib/aLib.a). "
             "Together with --micromegas-root, generates a CMake cache script.",
    )
    dm_parser.add_argument(
        "--micromegas-root", type=Path, default=None,
        help="Path to the micrOMEGAs installation. Required together with --CalcHEP "
             "to generate the CMake cache script.",
    )
    dm_parser.add_argument(
        "--calchep-src-root", type=Path, default=None,
        help="Path to CalcHEP_src inside the micrOMEGAs installation "
             "(default: <--micromegas-root>/CalcHEP_src).",
    )
    dm_parser.add_argument(
        "--plugin-name", default="micromegas",
        help="Registered BSMScanner plugin name referenced in plugin_call blocks (default: micromegas).",
    )
    dm_parser.add_argument("--dd-pvalue-threshold", type=float, default=0.1)
    dm_parser.add_argument(
        "--omega-mean", type=float, default=0.12,
        help="Relic-density central value (default: Planck 2018 Omega_c h^2).",
    )
    dm_parser.add_argument("--omega-sigma", type=float, default=0.0012)
    dm_parser.add_argument("--output-dir", type=Path, required=True)

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


def _generate_dm_config(args: argparse.Namespace) -> int:
    from bsm_scanner.tools.micromegas_config import (
        MicromegasConfigError,
        generate_dm_config,
        load_binding_map,
        parse_vars_mdl,
    )

    try:
        bindings = load_binding_map(args.map)
        calchep_params = parse_vars_mdl(args.vars_mdl) if args.vars_mdl is not None else None
        result = generate_dm_config(
            bindings,
            dm_target_name=args.dm_target_name,
            plugin_name=args.plugin_name,
            dd_pvalue_threshold=args.dd_pvalue_threshold,
            omega_mean=args.omega_mean,
            omega_sigma=args.omega_sigma,
            calchep_params_for_validation=calchep_params,
            micromegas_root=str(args.micromegas_root) if args.micromegas_root else None,
            calchep_model_root=str(args.calchep_model_root) if args.calchep_model_root else None,
            calchep_src_root=str(args.calchep_src_root) if args.calchep_src_root else None,
        )
    except (FileNotFoundError, MicromegasConfigError) as exc:
        print(f"bsm-scanner: error: {exc}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "dm_observables.yaml").write_text(result.observables_yaml, encoding="utf-8")
    (args.output_dir / "dm_likelihoods.yaml").write_text(result.likelihoods_yaml, encoding="utf-8")
    (args.output_dir / "dm_theory_checks.yaml").write_text(result.theory_checks_yaml, encoding="utf-8")
    written = ["dm_observables.yaml", "dm_likelihoods.yaml", "dm_theory_checks.yaml"]

    if result.constants_yaml is not None:
        (args.output_dir / "dm_constants.yaml").write_text(result.constants_yaml, encoding="utf-8")
        written.append("dm_constants.yaml")

    if result.cmake_cache_script is not None:
        (args.output_dir / "micromegas_build_cache.cmake").write_text(result.cmake_cache_script, encoding="utf-8")
        written.append("micromegas_build_cache.cmake")

    print(f"Wrote {', '.join(written)} to {args.output_dir}")
    print(f"Bound {len(bindings)} CalcHEP parameter(s) from {args.map}, unchanged.")
    if args.dm_target_name is None:
        print("No --dm-target-name given: micrOMEGAs will choose the dark-matter candidate itself.")
    imports = [name for name in written if name.endswith(".yaml")]
    print(f"\nImport {', '.join(imports)} from model.yaml.")
    if result.cmake_cache_script is not None:
        print(f"Build with: cmake -S . -B build -C {args.output_dir / 'micromegas_build_cache.cmake'}")
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
    if args.command == "generate-dm-config":
        return _generate_dm_config(args)
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
