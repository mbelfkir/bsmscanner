#!/usr/bin/env python3
"""Analyze basin_scan stress-test artifacts without touching framework code.

The script is intentionally lightweight and model-agnostic apart from the
reference point supplied by default for the arXiv:2006.03058 stress test.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

try:
    from scipy.stats import spearmanr
except Exception:  # pragma: no cover - optional diagnostic dependency
    spearmanr = None


PARAMETERS = ["Retau", "Imtau", "a2t", "a3t", "g2t", "g3t"]
GLOBAL_LOWER = {name: -10.0 for name in PARAMETERS}
GLOBAL_UPPER = {name: 10.0 for name in PARAMETERS}
REFERENCE = {
    "Retau": 0.026440890,
    "Imtau": 1.187476025,
    "a2t": 1.730159126,
    "a3t": 2.768453506,
    "g2t": 3.080703752,
    "g3t": -1.631334962,
}
REFERENCE_SIGN_DEGENERATE = {
    "Retau": -0.026441557,
    "Imtau": 1.187490493,
    "a2t": 1.730158540,
    "a3t": 2.768502712,
    "g2t": 3.080879954,
    "g3t": -1.631623365,
}


def _as_float(value: str | None) -> float:
    if value is None or value == "":
        return math.nan
    try:
        return float(value)
    except ValueError:
        return math.nan


def _as_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    return None


def _objective(row: dict[str, str]) -> float:
    for key in ("scanner_target", "metric_value", "total_nll"):
        value = _as_float(row.get(key))
        if math.isfinite(value):
            return value
    return math.nan


def _point(row: dict[str, str]) -> dict[str, float]:
    return {name: _as_float(row.get(f"param::{name}") or row.get(name)) for name in PARAMETERS}


def _raw_distance(point: dict[str, float], ref: dict[str, float] = REFERENCE) -> float:
    return math.sqrt(sum((point[name] - ref[name]) ** 2 for name in PARAMETERS))


def _normalized_distance(point: dict[str, float], ref: dict[str, float] = REFERENCE) -> float:
    total = 0.0
    for name in PARAMETERS:
        width = GLOBAL_UPPER[name] - GLOBAL_LOWER[name]
        total += ((point[name] - ref[name]) / width) ** 2
    return math.sqrt(total)


def _reference_fraction_in_box(
    lower: dict[str, float], upper: dict[str, float], ref: dict[str, float] = REFERENCE
) -> dict[str, float]:
    out: dict[str, float] = {}
    for name in PARAMETERS:
        width = upper[name] - lower[name]
        out[name] = math.nan if width == 0 else (ref[name] - lower[name]) / width
    return out


def _quantiles(values: list[float], probs: list[float]) -> dict[str, float]:
    finite = np.array([v for v in values if math.isfinite(v)], dtype=float)
    if finite.size == 0:
        return {str(p): math.nan for p in probs}
    return {str(p): float(np.quantile(finite, p)) for p in probs}


def _summary(values: list[float]) -> dict[str, float]:
    finite = np.array([v for v in values if math.isfinite(v)], dtype=float)
    if finite.size == 0:
        return {
            "min": math.nan,
            "max": math.nan,
            "median": math.nan,
            "q05": math.nan,
            "q10": math.nan,
            "q25": math.nan,
            "q75": math.nan,
            "q90": math.nan,
            "q95": math.nan,
            "q99": math.nan,
        }
    return {
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "median": float(np.median(finite)),
        "q05": float(np.quantile(finite, 0.05)),
        "q10": float(np.quantile(finite, 0.10)),
        "q25": float(np.quantile(finite, 0.25)),
        "q75": float(np.quantile(finite, 0.75)),
        "q90": float(np.quantile(finite, 0.90)),
        "q95": float(np.quantile(finite, 0.95)),
        "q99": float(np.quantile(finite, 0.99)),
    }


def _read_points(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            point = _point(row)
            obj = _objective(row)
            rows.append(
                {
                    "raw": row,
                    "objective": obj,
                    "valid": _as_bool(row.get("valid")),
                    "point": point,
                    "raw_distance": _raw_distance(point),
                    "normalized_distance": _normalized_distance(point),
                    "raw_distance_sign_degenerate": _raw_distance(point, REFERENCE_SIGN_DEGENERATE),
                    "normalized_distance_sign_degenerate": _normalized_distance(
                        point, REFERENCE_SIGN_DEGENERATE
                    ),
                }
            )
    return rows


def _objective_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [row["objective"] for row in rows]
    finite = [v for v in values if math.isfinite(v)]
    valid = [row for row in rows if row["valid"] is True]
    invalid = [row for row in rows if row["valid"] is False]
    best = min((row for row in rows if math.isfinite(row["objective"])), key=lambda r: r["objective"])
    return {
        "total_rows": len(rows),
        "finite_objectives": len(finite),
        "valid_points": len(valid),
        "invalid_points": len(invalid),
        "nan_or_inf_objectives": len(rows) - len(finite),
        "objective": _summary(values),
        "best_objective": float(best["objective"]),
        "best_chi2": float(2.0 * best["objective"]),
        "best_point": best["point"],
        "worst_finite_objective": float(max(finite)) if finite else math.nan,
    }


def _parameter_quantiles(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {name: _summary([row["point"][name] for row in rows]) for name in PARAMETERS}


def _reference_coverage(param_stats: dict[str, dict[str, float]]) -> dict[str, str]:
    coverage: dict[str, str] = {}
    for name, stats in param_stats.items():
        ref = REFERENCE[name]
        if stats["q05"] <= ref <= stats["q95"]:
            coverage[name] = "inside selected central 5%-95% range"
        elif stats["min"] <= ref <= stats["max"]:
            coverage[name] = "inside selected min/max but outside central range"
        else:
            coverage[name] = "outside selected-point range"
    return coverage


def _distance_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    closest = min(rows, key=lambda row: row["normalized_distance"])
    closest_sign = min(rows, key=lambda row: row["normalized_distance_sign_degenerate"])
    return {
        "raw_distance": _summary([row["raw_distance"] for row in rows]),
        "normalized_distance": _summary([row["normalized_distance"] for row in rows]),
        "normalized_distance_quantiles": _quantiles(
            [row["normalized_distance"] for row in rows], [0.01, 0.05, 0.10, 0.50]
        ),
        "closest_point": {
            "objective": float(closest["objective"]),
            "chi2": float(2.0 * closest["objective"]),
            "point": closest["point"],
            "raw_distance": float(closest["raw_distance"]),
            "normalized_distance": float(closest["normalized_distance"]),
        },
        "closest_sign_degenerate_point": {
            "objective": float(closest_sign["objective"]),
            "chi2": float(2.0 * closest_sign["objective"]),
            "point": closest_sign["point"],
            "raw_distance": float(closest_sign["raw_distance_sign_degenerate"]),
            "normalized_distance": float(closest_sign["normalized_distance_sign_degenerate"]),
        },
    }


def _best_n_diagnostics(rows: list[dict[str, Any]], n_values: list[int]) -> dict[str, Any]:
    finite_sorted = sorted(
        [row for row in rows if math.isfinite(row["objective"])], key=lambda row: row["objective"]
    )
    diagnostics: dict[str, Any] = {}
    for n in n_values:
        subset = finite_sorted[: min(n, len(finite_sorted))]
        param_stats = _parameter_quantiles(subset)
        envelope = {
            name: param_stats[name]["min"] <= REFERENCE[name] <= param_stats[name]["max"]
            for name in PARAMETERS
        }
        diagnostics[str(n)] = {
            "count": len(subset),
            "objective": _summary([row["objective"] for row in subset]),
            "parameter_ranges": param_stats,
            "distance_to_reference": _distance_summary(subset),
            "reference_inside_min_max_envelope": envelope,
            "reference_inside_all_parameter_envelopes": all(envelope.values()),
        }
    return diagnostics


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 2 or np.std(x) == 0 or np.std(y) == 0:
        return math.nan
    return float(np.corrcoef(x, y)[0, 1])


def _correlations(rows: list[dict[str, Any]]) -> dict[str, Any]:
    finite_rows = [row for row in rows if math.isfinite(row["objective"])]
    valid_rows = [row for row in finite_rows if row["valid"] is True]

    def objective_corr(subset: list[dict[str, Any]]) -> dict[str, Any]:
        y = np.array([row["objective"] for row in subset], dtype=float)
        pearson: dict[str, float] = {}
        spearman: dict[str, float | None] = {}
        for name in PARAMETERS:
            x = np.array([row["point"][name] for row in subset], dtype=float)
            pearson[name] = _pearson(x, y)
            if spearmanr is None:
                spearman[name] = None
            else:
                spearman[name] = float(spearmanr(x, y).statistic)
        return {"pearson": pearson, "spearman": spearman}

    selected_matrix = np.array([[row["point"][name] for name in PARAMETERS] for row in rows], dtype=float)
    selected_corr = np.corrcoef(selected_matrix, rowvar=False) if len(rows) > 1 else np.full((len(PARAMETERS), len(PARAMETERS)), math.nan)
    return {
        "objective_all_finite": objective_corr(finite_rows),
        "objective_valid_only": objective_corr(valid_rows),
        "parameter_correlation_selected_or_input_rows": {
            PARAMETERS[i]: {PARAMETERS[j]: float(selected_corr[i, j]) for j in range(len(PARAMETERS))}
            for i in range(len(PARAMETERS))
        },
    }


def _cluster_diagnostics(path: Path) -> dict[str, Any]:
    rows = _read_points(path)
    by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for i, row in enumerate(reader):
            by_cluster[row.get("cluster_id", "")].append(rows[i])
    clusters: dict[str, Any] = {}
    noise_points = 0
    for cid, cluster_rows in by_cluster.items():
        if cid in {"-1", "noise", ""}:
            noise_points += len(cluster_rows)
        best = min(cluster_rows, key=lambda row: row["objective"])
        clusters[cid] = {
            "size": len(cluster_rows),
            "best_objective": float(best["objective"]),
            "best_chi2": float(2.0 * best["objective"]),
            "parameter_ranges": _parameter_quantiles(cluster_rows),
        }
    return {
        "cluster_count": len([cid for cid in by_cluster if cid not in {"-1", "noise", ""}]),
        "noise_points": noise_points,
        "clusters": clusters,
    }


def _focused_box_diagnostics(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    boxes = payload.get("boxes", payload if isinstance(payload, list) else [])
    out = []
    for box in boxes:
        lower = {name: float(box["lower"][name]) for name in PARAMETERS}
        upper = {name: float(box["upper"][name]) for name in PARAMETERS}
        width = {name: upper[name] - lower[name] for name in PARAMETERS}
        width_fraction = {
            name: width[name] / (GLOBAL_UPPER[name] - GLOBAL_LOWER[name]) for name in PARAMETERS
        }
        contains_ref = all(lower[name] <= REFERENCE[name] <= upper[name] for name in PARAMETERS)
        contains_sign = all(
            lower[name] <= REFERENCE_SIGN_DEGENERATE[name] <= upper[name] for name in PARAMETERS
        )
        out.append(
            {
                **box,
                "width": width,
                "width_fraction": width_fraction,
                "reference_inside": contains_ref,
                "sign_degenerate_reference_inside": contains_sign,
                "reference_fractional_position": _reference_fraction_in_box(lower, upper),
                "sign_degenerate_reference_fractional_position": _reference_fraction_in_box(
                    lower, upper, REFERENCE_SIGN_DEGENERATE
                ),
            }
        )
    return {"boxes": out}


def _history_diagnostics(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    history = payload if isinstance(payload, list) else payload.get("history", [])
    if not history:
        return {}
    first = history[0]
    last = history[-1]
    def best_value(entry: dict[str, Any]) -> float:
        for key in ("best_scanner_target", "best_target", "best_objective"):
            if key in entry:
                return float(entry[key])
        return math.nan

    initial_best = best_value(first)
    final_best = best_value(last)
    return {
        "entries": len(history),
        "initial_best_objective": initial_best,
        "initial_best_chi2": 2.0 * initial_best,
        "final_best_objective": final_best,
        "final_best_chi2": 2.0 * final_best,
        "last_entry": last,
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def _markdown_table(rows: list[list[Any]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    lines = ["| " + " | ".join(map(str, header)) + " |"]
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(map(str, row)) + " |")
    return "\n".join(lines)


def _fmt(value: Any, digits: int = 6) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        return f"{value:.{digits}g}"
    return str(value)


def _write_report(path: Path, data: dict[str, Any], run_dir: Path) -> None:
    selected_param_stats = data["selected"]["parameter_quantiles"]
    coverage_rows = [["parameter", "selected min", "selected q05", "selected median", "selected q95", "selected max", "reference", "coverage"]]
    for name in PARAMETERS:
        stats = selected_param_stats[name]
        coverage_rows.append(
            [
                name,
                _fmt(stats["min"]),
                _fmt(stats["q05"]),
                _fmt(stats["median"]),
                _fmt(stats["q95"]),
                _fmt(stats["max"]),
                _fmt(REFERENCE[name]),
                data["selected"]["reference_coverage"][name],
            ]
        )

    top_rows = [["N", "obj min", "obj median", "obj max", "min d_norm", "median d_norm", "ref in all envelopes"]]
    for n, item in data["best_n"].items():
        top_rows.append(
            [
                n,
                _fmt(item["objective"]["min"]),
                _fmt(item["objective"]["median"]),
                _fmt(item["objective"]["max"]),
                _fmt(item["distance_to_reference"]["normalized_distance"]["min"]),
                _fmt(item["distance_to_reference"]["normalized_distance"]["median"]),
                item["reference_inside_all_parameter_envelopes"],
            ]
        )

    cluster_rows = [["cluster", "size", "best nLL", "best chi2"]]
    for cid, item in data["clusters"]["clusters"].items():
        cluster_rows.append([cid, item["size"], _fmt(item["best_objective"]), _fmt(item["best_chi2"])])

    box_rows = [["basin", "relative volume", "contains ref", "contains sign-ref"]]
    for box in data["focused_boxes"]["boxes"]:
        box_rows.append(
            [
                box.get("cluster_id"),
                _fmt(box.get("relative_box_volume")),
                box["reference_inside"],
                box["sign_degenerate_reference_inside"],
            ]
        )

    final = data["final"]
    report = f"""# basin_scan [-10, 10]^6 Stress Diagnostics

Run directory: `{run_dir}`

This is an artifact-only diagnostic report. It does not modify framework code,
physics code, `adaptive_diver`, or `basin_scan`.

## Reference

- Reference chi2: `{data['reference_chi2']}`
- Reference point: `{json.dumps(REFERENCE)}`
- Sign/CP-degenerate reference: `{json.dumps(REFERENCE_SIGN_DEGENERATE)}`

## Exploration Summary

- Total rows: `{data['exploration']['summary']['total_rows']}`
- Finite objectives: `{data['exploration']['summary']['finite_objectives']}`
- Valid points: `{data['exploration']['summary']['valid_points']}`
- Invalid points: `{data['exploration']['summary']['invalid_points']}`
- NaN/inf objectives: `{data['exploration']['summary']['nan_or_inf_objectives']}`
- Best exploration nLL: `{data['exploration']['summary']['best_objective']}`
- Best exploration chi2: `{data['exploration']['summary']['best_chi2']}`
- Worst finite nLL: `{data['exploration']['summary']['worst_finite_objective']}`
- Median nLL: `{data['exploration']['summary']['objective']['median']}`
- Objective quantiles: q10 `{data['exploration']['summary']['objective']['q10']}`, q25 `{data['exploration']['summary']['objective']['q25']}`, q75 `{data['exploration']['summary']['objective']['q75']}`, q90 `{data['exploration']['summary']['objective']['q90']}`, q99 `{data['exploration']['summary']['objective']['q99']}`
- Best exploration point: `{json.dumps(data['exploration']['summary']['best_point'])}`

## Selected Points

- Selected points: `{data['selected']['summary']['total_rows']}`
- Best selected nLL: `{data['selected']['summary']['best_objective']}`
- Best selected chi2: `{data['selected']['summary']['best_chi2']}`
- Worst selected nLL: `{data['selected']['summary']['worst_finite_objective']}`
- Median selected nLL: `{data['selected']['summary']['objective']['median']}`
- Selected objective quantiles: q10 `{data['selected']['summary']['objective']['q10']}`, q25 `{data['selected']['summary']['objective']['q25']}`, q75 `{data['selected']['summary']['objective']['q75']}`, q90 `{data['selected']['summary']['objective']['q90']}`, q99 `{data['selected']['summary']['objective']['q99']}`

{_markdown_table(coverage_rows)}

## Distance To Reference

Exploration:

- Minimum raw distance: `{data['exploration']['distance']['raw_distance']['min']}`
- Minimum normalized distance: `{data['exploration']['distance']['normalized_distance']['min']}`
- Median normalized distance: `{data['exploration']['distance']['normalized_distance']['median']}`
- Normalized-distance quantiles: `{json.dumps(data['exploration']['distance']['normalized_distance_quantiles'])}`
- Closest exploration point: `{json.dumps(data['exploration']['distance']['closest_point'])}`

Selected:

- Minimum raw distance: `{data['selected']['distance']['raw_distance']['min']}`
- Minimum normalized distance: `{data['selected']['distance']['normalized_distance']['min']}`
- Median normalized distance: `{data['selected']['distance']['normalized_distance']['median']}`
- Normalized-distance quantiles: `{json.dumps(data['selected']['distance']['normalized_distance_quantiles'])}`
- Closest selected point: `{json.dumps(data['selected']['distance']['closest_point'])}`

The closest-to-reference points are not low-objective points. The closest
exploration point has chi2 `{data['exploration']['distance']['closest_point']['chi2']}`,
whereas the best exploration chi2 is `{data['exploration']['summary']['best_chi2']}`.

## Best-N Exploration Diagnostics

{_markdown_table(top_rows)}

## Correlations

Pearson correlations between parameters and objective using all finite
exploration rows:

`{json.dumps(data['correlations']['exploration']['objective_all_finite']['pearson'])}`

Spearman correlations between parameters and objective using all finite
exploration rows:

`{json.dumps(data['correlations']['exploration']['objective_all_finite']['spearman'])}`

Pearson correlations using valid-only exploration rows:

`{json.dumps(data['correlations']['exploration']['objective_valid_only']['pearson'])}`

These correlations are weak/misleading as one-dimensional guidance: the best
region selected by objective is far from the known low-chi2 basin.

## Cluster And Focused-Box Diagnostics

- Number of clusters: `{data['clusters']['cluster_count']}`
- Noise points: `{data['clusters']['noise_points']}`

{_markdown_table(cluster_rows)}

{_markdown_table(box_rows)}

Winning box bounds:

```json
{json.dumps(data['focused_boxes']['boxes'][0] if data['focused_boxes']['boxes'] else {}, indent=2)}
```

The reference is inside the focused box, but the relative volume is
`{data['focused_boxes']['boxes'][0].get('relative_box_volume') if data['focused_boxes']['boxes'] else math.nan}`.
This means containment is not localization: the box is still roughly half of
the original six-dimensional volume.

## Focused adaptive_diver Diagnostics

- History entries: `{data['focused']['history'].get('entries')}`
- Initial best nLL: `{data['focused']['history'].get('initial_best_objective')}`
- Initial best chi2: `{data['focused']['history'].get('initial_best_chi2')}`
- Final history best nLL: `{data['focused']['history'].get('final_best_objective')}`
- Final history best chi2: `{data['focused']['history'].get('final_best_chi2')}`
- Final adaptive_diver best nLL: `{final['best_objective']}`
- Final adaptive_diver chi2: `{final['best_chi2']}`
- Final adaptive_diver best point: `{json.dumps(final['best_point'])}`
- Closest final-population point to reference: `{json.dumps(data['focused']['final_population_distance']['closest_point'])}`
- Closest elite point to reference: `{json.dumps(data['focused']['elite_distance']['closest_point'])}`

The final population did not move toward the known basin. Even the closest
final-population and elite points remain high chi2 compared with the reference.

## Failure-Stage Conclusion

Failure stage: `{data['failure_stage']}`.

The first failure is exploration/selection. The broad Latin-hypercube pass did
not sample an informative point near the known low-chi2 basin. Selection
therefore retained high-chi2 points from a different broad region. Clustering
was not meaningful as a physics-basin identifier because it only clustered that
wrong selected population. The focused box included the reference only because
it was very broad, not because the basin was localized. adaptive_diver then
optimized the wrong broad region.

## Recommended Next Step

{data['recommended_next_step']}
"""
    path.write_text(report)


def analyze(run_dir: Path) -> dict[str, Any]:
    exploration = _read_points(run_dir / "exploration_points.csv")
    selected = _read_points(run_dir / "selected_points.csv")
    final_population = _read_points(run_dir / "basin_00" / "final_population.csv")
    elite_points = _read_points(run_dir / "basin_00" / "elite_points.csv")

    best_fit = _load_json(run_dir / "best_fit.json")
    final_point = best_fit.get("parameters", {})
    final_objective = float(best_fit.get("best_scanner_target", best_fit.get("best_metric_value", math.nan)))

    data: dict[str, Any] = {
        "run_directory": str(run_dir),
        "reference": REFERENCE,
        "reference_sign_degenerate": REFERENCE_SIGN_DEGENERATE,
        "reference_chi2": 0.000953766671751,
        "exploration": {
            "summary": _objective_summary(exploration),
            "distance": _distance_summary(exploration),
        },
        "selected": {
            "summary": _objective_summary(selected),
            "parameter_quantiles": _parameter_quantiles(selected),
            "distance": _distance_summary(selected),
        },
        "best_n": _best_n_diagnostics(exploration, [20, 100, 1000]),
        "correlations": {
            "exploration": _correlations(exploration),
            "selected": _correlations(selected),
        },
        "clusters": _cluster_diagnostics(run_dir / "clusters.csv"),
        "focused_boxes": _focused_box_diagnostics(run_dir / "focused_boxes.json"),
        "basin_results": _load_json(run_dir / "basin_results.json"),
        "focused": {
            "history": _history_diagnostics(run_dir / "basin_00" / "history.json"),
            "summary": _load_json(run_dir / "basin_00" / "summary.json"),
            "final_population_distance": _distance_summary(final_population),
            "elite_distance": _distance_summary(elite_points),
        },
        "final": {
            "best_objective": final_objective,
            "best_chi2": 2.0 * final_objective,
            "best_point": final_point,
            "raw_distance": _raw_distance(final_point),
            "normalized_distance": _normalized_distance(final_point),
        },
        "failure_stage": "exploration_selection",
        "recommended_next_step": (
            "Before adding second-stage refocusing, prefer progressive exploration rounds "
            "or physically motivated/transformed domains. A larger one-shot exploration "
            "budget alone is unlikely to be efficient because the selected population did "
            "not contain informative low-chi2 points near the known basin."
        ),
    }
    data["selected"]["reference_coverage"] = _reference_coverage(data["selected"]["parameter_quantiles"])
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--markdown-out", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()

    data = analyze(args.run_dir)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    _write_report(args.markdown_out, data, args.run_dir)
    args.json_out.write_text(json.dumps(data, indent=2, sort_keys=True))
    print(json.dumps({
        "markdown": str(args.markdown_out),
        "json": str(args.json_out),
        "failure_stage": data["failure_stage"],
        "best_exploration_chi2": data["exploration"]["summary"]["best_chi2"],
        "best_selected_chi2": data["selected"]["summary"]["best_chi2"],
        "final_chi2": data["final"]["best_chi2"],
        "min_exploration_normalized_distance": data["exploration"]["distance"]["normalized_distance"]["min"],
        "min_selected_normalized_distance": data["selected"]["distance"]["normalized_distance"]["min"],
        "min_final_population_normalized_distance": data["focused"]["final_population_distance"]["normalized_distance"]["min"],
    }, indent=2))


if __name__ == "__main__":
    main()
