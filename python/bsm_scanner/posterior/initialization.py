from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from .config import StartFromConfig
from .priors import ParameterInfo, bounds_arrays


def _parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if np.isfinite(parsed) else None


def _is_valid_row(row: dict[str, Any]) -> bool:
    value = str(row.get("valid", row.get("status", "true"))).strip().lower()
    return value in {"true", "1", "yes", "ok"}


def _row_objective(row: dict[str, Any]) -> float | None:
    for key in ("total_nll", "scanner_target", "metric_value", "objective", "nll", "chi2"):
        value = _parse_float(row.get(key))
        if value is not None:
            return value
    return None


def _row_vector(row: dict[str, Any], parameters: list[ParameterInfo]) -> np.ndarray | None:
    values: list[float] = []
    for parameter in parameters:
        value = row.get(f"param::{parameter.name}", row.get(parameter.name))
        parsed = _parse_float(value)
        if parsed is None:
            return None
        values.append(parsed)
    return np.asarray(values, dtype=float)


def _load_csv_candidates(path: Path, parameters: list[ParameterInfo]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not path.exists():
        return candidates
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            vector = _row_vector(row, parameters)
            objective = _row_objective(row)
            if vector is None or objective is None or not _is_valid_row(row):
                continue
            candidates.append({"theta": vector, "objective": objective, "source": path.name})
    return candidates


def _load_best_fit(path: Path, parameters: list[ParameterInfo]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    param_map = payload.get("parameters") or payload.get("best_parameters") or {}
    if not param_map:
        return []
    values: list[float] = []
    for parameter in parameters:
        parsed = _parse_float(param_map.get(parameter.name))
        if parsed is None:
            return []
        values.append(parsed)
    objective = _parse_float(payload.get("best_scanner_target", payload.get("best_nll", payload.get("best_metric_value", 0.0))))
    return [{"theta": np.asarray(values, dtype=float), "objective": objective or 0.0, "source": path.name}]


def load_candidate_points(run_dir: Path, parameters: list[ParameterInfo], source: str = "auto") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_files = [
        "ranked_points.csv",
        "selected_points.csv",
        "elite_points.csv",
        "final_population.csv",
        "exploration_points.csv",
        "points.csv",
    ]
    if source != "auto":
        source_files = [source]
    candidates: list[dict[str, Any]] = []
    sources_checked: list[str] = []
    for filename in source_files:
        path = run_dir / filename
        sources_checked.append(filename)
        loaded = _load_csv_candidates(path, parameters)
        if loaded:
            candidates.extend(loaded)
            if source == "auto":
                break
    if not candidates and source == "auto":
        candidates.extend(_load_best_fit(run_dir / "best_fit.json", parameters))
        sources_checked.append("best_fit.json")
    candidates.sort(key=lambda item: float(item["objective"]))
    diagnostics = {
        "sources_checked": sources_checked,
        "source_file_used": candidates[0]["source"] if candidates else None,
        "number_of_candidate_points": len(candidates),
    }
    return candidates, diagnostics


def _repair_or_resample(theta: np.ndarray, rng: np.random.Generator, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    repaired = np.asarray(theta, dtype=float).copy()
    bad = (~np.isfinite(repaired)) | (repaired < lower) | (repaired > upper)
    if np.any(bad):
        repaired[bad] = rng.uniform(lower[bad], upper[bad])
    return repaired


def initialize_walkers(
    run_dir: Path,
    parameters: list[ParameterInfo],
    config: StartFromConfig,
    *,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict[str, Any], np.ndarray]:
    lower, upper = bounds_arrays(parameters)
    widths = upper - lower
    candidates, diagnostics = load_candidate_points(run_dir, parameters, config.source)
    if not candidates:
        center = np.asarray([(item.default if item.default is not None else 0.5 * (item.lower + item.upper)) for item in parameters])
        candidates = [{"theta": _repair_or_resample(center, rng, lower, upper), "objective": 0.0, "source": "defaults"}]
        diagnostics["source_file_used"] = "defaults"

    n_elite = max(config.min_elite_points, int(np.ceil(config.elite_fraction * len(candidates))))
    n_elite = min(config.max_elite_points, len(candidates), max(1, n_elite))
    elite = np.asarray([item["theta"] for item in candidates[:n_elite]], dtype=float)
    best = elite[0]
    covariance = np.diag((np.maximum(widths * config.jitter_scale, 1.0e-12)) ** 2)

    if config.initialization == "elite_covariance" and elite.shape[0] >= 2:
        covariance = np.cov(elite, rowvar=False)
        covariance = np.atleast_2d(covariance)
        covariance = covariance + np.eye(len(parameters)) * config.covariance_regularization
    elif config.initialization == "elite_jitter":
        covariance = np.diag((np.maximum(widths * config.jitter_scale, 1.0e-12)) ** 2)
    elif config.initialization == "best_fit_jitter":
        elite = best.reshape(1, -1)
        covariance = np.diag((np.maximum(widths * config.jitter_scale, 1.0e-12)) ** 2)

    positions: list[np.ndarray] = []
    failed = 0
    attempts = 0
    while len(positions) < config.n_walkers and attempts < config.max_initialization_attempts:
        attempts += 1
        if config.initialization == "elite_jitter" and elite.shape[0] > 0:
            center = elite[int(rng.integers(0, elite.shape[0]))]
        else:
            center = best
        try:
            proposal = rng.multivariate_normal(center, covariance)
        except Exception:
            proposal = center + rng.normal(0.0, np.maximum(widths * config.jitter_scale, 1.0e-12))
        if np.all(np.isfinite(proposal)) and np.all(proposal >= lower) and np.all(proposal <= upper):
            positions.append(proposal)
        else:
            failed += 1

    while len(positions) < config.n_walkers:
        positions.append(rng.uniform(lower, upper))

    array = np.asarray(positions, dtype=float)
    diagnostics.update(
        {
            "number_of_valid_candidate_points": len(candidates),
            "number_of_elite_points_used": int(n_elite),
            "initial_center": best,
            "initial_standard_deviations": np.sqrt(np.maximum(np.diag(covariance), 0.0)),
            "covariance_regularization_used": config.covariance_regularization,
            "number_of_failed_initialization_proposals": failed,
            "final_number_of_walkers": config.n_walkers,
            "ndim": len(parameters),
        }
    )
    return array, diagnostics, covariance
