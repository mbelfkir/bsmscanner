#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from bsm_scanner import compile_model, load_model, run_scan  # noqa: E402


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_command(command: list[str]) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def detect_generated_artifacts() -> dict[str, list[str]]:
    artifact_map: dict[str, list[str]] = {
        "local_build_dirs": [],
        "local_cache_dirs": [],
        "generated_run_dirs": [],
    }

    for relative in ("build", ".pytest_cache", ".venv"):
        path = ROOT / relative
        if path.exists():
            key = "local_build_dirs" if relative == "build" else "local_cache_dirs"
            artifact_map[key].append(relative)

    for run_dir in sorted(ROOT.glob("examples/**/runs")):
        if not run_dir.is_dir():
            continue
        if any(run_dir.iterdir()):
            artifact_map["generated_run_dirs"].append(str(run_dir.relative_to(ROOT)))

    return artifact_map


def default_point(model: Any) -> dict[str, Any]:
    return {parameter.name: parameter.default for parameter in model.parameters}


def tighten_scan_bounds_around_default(model: Any) -> None:
    for parameter in model.parameters:
        if not parameter.scan or parameter.default is None:
            continue
        center = float(parameter.default)
        span = max(abs(center) * 1.0e-6, 1.0e-6)
        parameter.lower = center - span
        parameter.upper = center + span


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a release-readiness audit for the current BSMScanner milestone."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT / "models" / "oneloop" / "model.yaml",
        help="Model manifest to audit.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path for a JSON report.",
    )
    args = parser.parse_args()

    git_probe = run_command(["git", "rev-parse", "--show-toplevel"])
    git_available = git_probe.returncode == 0

    pytest_result = run_command([sys.executable, "-m", "pytest", "tests", "-q"])
    if pytest_result.returncode != 0:
        print(pytest_result.stdout, end="")
        print(pytest_result.stderr, end="", file=sys.stderr)
        return pytest_result.returncode

    model = load_model(args.model)
    compiled = compile_model(model, build_backend=True)
    point_result = compiled.evaluate(default_point(model))

    if point_result["status"] != "ok":
        raise SystemExit(
            f"Default-point evaluation failed for {args.model}: {point_result['failure_reason']}"
        )

    smoke_model = load_model(args.model)
    smoke_model.scan.engine = "serial_random"
    smoke_model.scan.save_every = 1
    smoke_model.scan.seed = 20260410
    smoke_model.scan.settings = {
        "objective": "nll",
        "max_evaluations": 2,
        "invalid_objective": 1.0e30,
        "save_invalid_points": True,
        "verbose": 0,
    }
    tighten_scan_bounds_around_default(smoke_model)
    smoke_compiled = compile_model(smoke_model, build_backend=False)
    with tempfile.TemporaryDirectory(prefix="bsm_release_audit_") as tmpdir:
        scan_result = run_scan(
            smoke_model,
            smoke_compiled,
            run_directory=Path(tmpdir) / "scan",
            run_id="release-audit-smoke",
            timestamp_utc="2026-04-10T00:00:00+00:00",
        )

    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "repository_root": str(ROOT),
        "git_repository_detected": git_available,
        "model": {
            "path": str(args.model),
            "name": model.metadata.name,
            "version": model.metadata.version,
            "tags": list(model.metadata.tags),
        },
        "generated_artifacts": detect_generated_artifacts(),
        "pytest": asdict(pytest_result),
        "one_point_evaluation": {
            "status": point_result["status"],
            "total_nll": point_result["total_nll"],
            "saved_output_count": len(point_result["outputs"]),
        },
        "scan_smoke_test": {
            "engine": smoke_model.scan.engine,
            "evaluations": scan_result.summary["evaluations"],
            "saved_points": scan_result.summary["saved_points"],
            "valid_points": scan_result.summary["valid_points"],
            "has_best_point": scan_result.summary["has_best_point"],
        },
    }

    payload = json.dumps(report, indent=2)
    if args.json_out is not None:
        output_path = args.json_out
        if not output_path.is_absolute():
            output_path = ROOT / output_path
        output_path.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote release audit report to {output_path}")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
