#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "python"
if str(PYTHON) not in sys.path:
    sys.path.insert(0, str(PYTHON))

from bsm_scanner import compile_model, run_scan  # noqa: E402
from bsm_scanner.model.schema import ModelDefinition  # noqa: E402


OBJECTIVES: dict[str, dict[str, Any]] = {
    "quadratic": {
        "minimum": {"x": 1.0, "y": -2.0},
        "observables": [
            {"name": "x_obs", "expression": "x"},
            {"name": "y_obs", "expression": "y"},
        ],
        "likelihoods": [
            {"name": "x_term", "kind": "gaussian", "observable": "x_obs", "mean": 1.0, "sigma": 1.0},
            {"name": "y_term", "kind": "gaussian", "observable": "y_obs", "mean": -2.0, "sigma": 1.0},
        ],
    },
    "correlated_valley": {
        "minimum": {"x": 1.0, "y": 1.0},
        "observables": [
            {"name": "ridge", "expression": "y - x"},
            {"name": "center", "expression": "x + y"},
        ],
        "likelihoods": [
            {"name": "ridge_term", "kind": "gaussian", "observable": "ridge", "mean": 0.0, "sigma": 0.05},
            {"name": "center_term", "kind": "gaussian", "observable": "center", "mean": 2.0, "sigma": 1.0},
        ],
    },
    "rastrigin": {
        "minimum": {"x": 0.0, "y": 0.0},
        "observables": [
            {
                "name": "rastrigin_value",
                "expression": "20 + (x**2 - 10*cos(2*pi*x)) + (y**2 - 10*cos(2*pi*y))",
            }
        ],
        "likelihoods": [
            {
                "name": "rastrigin_term",
                "kind": "gaussian",
                "observable": "rastrigin_value",
                "mean": 0.0,
                "sigma": 1.0,
            }
        ],
    },
}


def _base_model(objective: str, engine: str, seed: int, *, population_size: int, generations: int) -> ModelDefinition:
    spec = OBJECTIVES[objective]
    scan: dict[str, Any]
    if engine == "serial_random":
        scan = {
            "engine": "serial_random",
            "save_every": 1,
            "seed": seed,
            "settings": {
                "objective": "nll",
                "max_evaluations": population_size * (generations + 1),
                "invalid_penalty": 1.0e12,
                "save_invalid_points": True,
                "verbose": 0,
            },
        }
    elif engine == "de_scipy":
        scan = {
            "engine": "de_scipy",
            "save_every": 1,
            "seed": seed,
            "settings": {
                "objective": "nll",
                "strategy": "rand1bin",
                "maxiter": generations,
                "popsize": max(1, population_size // 2),
                "tol": 0.0,
                "atol": 0.0,
                "mutation": [0.5, 1.0],
                "recombination": 0.7,
                "init": "latinhypercube",
                "updating": "deferred",
                "workers": 1,
                "polish": False,
                "invalid_penalty": 1.0e12,
                "save_invalid_points": True,
                "verbose": 0,
            },
        }
    else:
        local_refinement = engine == "adaptive_diver_local"
        scan = {
            "engine": "adaptive_diver",
            "save_every": 1,
            "seed": seed,
            "settings": {
                "objective": "nll",
                "invalid_penalty": 1.0e12,
                "save_invalid_points": True,
                "verbose": 0,
            },
            "adaptive_diver": {
                "population_size": population_size,
                "max_generations": generations,
                "p_best_fraction": 0.2,
                "archive": True,
                "bounds": {"handling": "reflect"},
                "convergence": {"patience": 0, "population_std_tol": 0.0},
                "local_refinement": {
                    "enabled": local_refinement,
                    "method": "Powell",
                    "n_elites": 3,
                    "maxiter": 200,
                },
                "statistics": {"enabled": True},
                "output": {"save_history": True, "save_population": True, "save_elites": True},
            },
        }
    return ModelDefinition.from_mapping(
        {
            "metadata": {"name": f"benchmark-{objective}-{engine}"},
            "parameters": [
                {
                    "name": "x",
                    "value_type": "real",
                    "scan": True,
                    "lower": -5.0,
                    "upper": 5.0,
                    "default": 0.0,
                    "prior": "flat",
                },
                {
                    "name": "y",
                    "value_type": "real",
                    "scan": True,
                    "lower": -5.0,
                    "upper": 5.0,
                    "default": 0.0,
                    "prior": "flat",
                },
            ],
            "observables": spec["observables"],
            "likelihoods": spec["likelihoods"],
            "outputs": {"save": [item["name"] for item in spec["observables"]]},
            "scan": scan,
        }
    )


def _distance(parameters: dict[str, Any], minimum: dict[str, float]) -> float | None:
    try:
        return math.sqrt(
            sum((float(parameters[name]) - float(value)) ** 2 for name, value in minimum.items())
        )
    except Exception:
        return None


def _run_case(
    objective: str,
    engine: str,
    seed: int,
    output_dir: Path,
    *,
    population_size: int,
    generations: int,
) -> dict[str, Any]:
    model = _base_model(objective, engine, seed, population_size=population_size, generations=generations)
    compiled = compile_model(model, build_backend=False)
    run_dir = output_dir / objective / engine / f"seed_{seed}"
    start = time.perf_counter()
    results = run_scan(
        model,
        compiled,
        run_directory=run_dir,
        run_id=f"{objective}-{engine}-{seed}",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )
    runtime = time.perf_counter() - start
    best_fit = json.loads(results.best_fit_path.read_text(encoding="utf-8"))
    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))
    parameters = best_fit.get("parameters", {})
    engine_details = summary.get("engine_details", {})
    has_best_point = bool(best_fit.get("has_best_point", False))
    engine_success = engine_details.get("success")
    return {
        "objective": objective,
        "engine": engine,
        "seed": seed,
        "best_chi2": best_fit.get("best_metric_value"),
        "best_x": parameters.get("x"),
        "best_y": parameters.get("y"),
        "distance_from_minimum": _distance(parameters, OBJECTIVES[objective]["minimum"]),
        "evaluations": summary.get("evaluations"),
        "valid_points": summary.get("valid_points"),
        "success": has_best_point,
        "engine_success": engine_success if engine_success is not None else has_best_point,
        "stop_reason": engine_details.get("stop_reason", engine_details.get("message", "")),
        "runtime_seconds": runtime,
        "run_directory": str(run_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark BSMScanner scan engines on toy objectives.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "benchmarks" / "runs" / "engine_benchmark")
    parser.add_argument("--seeds", type=int, nargs="+", default=[101, 202, 303])
    parser.add_argument("--population-size", type=int, default=16)
    parser.add_argument("--generations", type=int, default=30)
    parser.add_argument(
        "--engines",
        nargs="+",
        default=["serial_random", "de_scipy", "adaptive_diver", "adaptive_diver_local"],
    )
    args = parser.parse_args()

    engines = list(args.engines)
    if "de_scipy" in engines and importlib.util.find_spec("scipy") is None:
        engines.remove("de_scipy")
        print("Skipping de_scipy because scipy is not installed.", file=sys.stderr)
    if "adaptive_diver_local" in engines and importlib.util.find_spec("scipy") is None:
        engines.remove("adaptive_diver_local")
        print("Skipping adaptive_diver_local because scipy is not installed.", file=sys.stderr)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for objective in OBJECTIVES:
        for engine in engines:
            for seed in args.seeds:
                row = _run_case(
                    objective,
                    engine,
                    seed,
                    args.output_dir,
                    population_size=args.population_size,
                    generations=args.generations,
                )
                rows.append(row)
                print(
                    f"{objective:18s} {engine:22s} seed={seed} "
                    f"best={row['best_chi2']} distance={row['distance_from_minimum']} "
                    f"evals={row['evaluations']} runtime={row['runtime_seconds']:.3f}s"
                )

    csv_path = args.output_dir / "engine_benchmark.csv"
    json_path = args.output_dir / "engine_benchmark.json"
    fieldnames = [
        "objective",
        "engine",
        "seed",
        "best_chi2",
        "best_x",
        "best_y",
        "distance_from_minimum",
        "evaluations",
        "valid_points",
        "success",
        "engine_success",
        "stop_reason",
        "runtime_seconds",
        "run_directory",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
