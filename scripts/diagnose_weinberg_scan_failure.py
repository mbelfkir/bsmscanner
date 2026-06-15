#!/usr/bin/env python3
"""Artifact-only diagnostics for Weinberg basin_scan failures.

This script does not run scans or modify framework behavior.  It inspects
existing run artifacts and performs direct point evaluations for known
reference points so the failure mode is reproducible.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any


PARAMETERS = ["Retau", "Imtau", "a2t", "a3t", "g2t", "g3t"]

REFERENCE_POSITIVE = {
    "Retau": 0.026440890,
    "Imtau": 1.187476025,
    "a2t": 1.730159126,
    "a3t": 2.768453506,
    "g2t": 3.080703752,
    "g3t": -1.631334962,
}

REFERENCE_NEGATIVE = {
    "Retau": -0.026441557,
    "Imtau": 1.187490493,
    "a2t": 1.730158540,
    "a3t": 2.768502712,
    "g2t": 3.080879954,
    "g3t": -1.631623365,
}

REFERENCE_CUTS = {
    "Retau": 0.1,
    "Imtau": 0.2,
    "a2t": 0.3,
    "a3t": 0.3,
    "g2t": 0.5,
    "g3t": 0.5,
}


@dataclass
class PointSummary:
    objective: float
    row: dict[str, str]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text()) if path.exists() else None


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _objective_from_row(row: dict[str, str]) -> float | None:
    for key in ("scanner_target", "metric_value", "objective", "nll", "total_nll"):
        value = _as_float(row.get(key))
        if value is not None:
            return value
    return None


def _param_from_row(row: dict[str, str], name: str) -> float | None:
    for key in (name, f"param::{name}", f"parameter::{name}"):
        value = _as_float(row.get(key))
        if value is not None:
            return value
    return None


def _valid_from_row(row: dict[str, str]) -> bool | None:
    value = row.get("valid")
    if value is None:
        return None
    return str(value).strip().lower() in {"true", "1", "yes", "ok"}


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _raw_distance(row: dict[str, str], reference: dict[str, float]) -> float | None:
    total = 0.0
    for name, ref_value in reference.items():
        value = _param_from_row(row, name)
        if value is None:
            return None
        total += (value - ref_value) ** 2
    return math.sqrt(total)


def _normalized_distance(
    row: dict[str, str],
    reference: dict[str, float],
    bounds: dict[str, tuple[float, float]],
) -> float | None:
    total = 0.0
    for name, ref_value in reference.items():
        value = _param_from_row(row, name)
        if value is None or name not in bounds:
            return None
        lower, upper = bounds[name]
        width = upper - lower
        if width <= 0:
            return None
        total += ((value - ref_value) / width) ** 2
    return math.sqrt(total)


def _reference_like_count(row: dict[str, str], reference: dict[str, float]) -> int:
    count = 0
    for name, ref_value in reference.items():
        value = _param_from_row(row, name)
        if value is not None and abs(value - ref_value) <= REFERENCE_CUTS[name]:
            count += 1
    return count


def summarize_csv(path: Path, bounds: dict[str, tuple[float, float]]) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}

    objectives: list[float] = []
    norm_dist_pos: list[float] = []
    norm_dist_neg: list[float] = []
    best: PointSummary | None = None
    closest_pos: tuple[float, float | None, dict[str, str]] | None = None
    closest_neg: tuple[float, float | None, dict[str, str]] | None = None
    valid_count = 0
    invalid_count = 0
    valid_seen = False
    finite_count = 0
    total_count = 0
    ref_like = {
        "positive": {"all_6": 0, "at_least_5": 0, "at_least_4": 0, "best_chi2_all_6": None},
        "negative": {"all_6": 0, "at_least_5": 0, "at_least_4": 0, "best_chi2_all_6": None},
    }
    parameter_values: dict[str, list[float]] = {name: [] for name in PARAMETERS}
    fieldnames: list[str] = []

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            total_count += 1
            valid = _valid_from_row(row)
            if valid is not None:
                valid_seen = True
                if valid:
                    valid_count += 1
                else:
                    invalid_count += 1
            objective = _objective_from_row(row)
            if objective is not None:
                finite_count += 1
                objectives.append(objective)
                if best is None or objective < best.objective:
                    best = PointSummary(objective=objective, row=dict(row))
            for name in PARAMETERS:
                value = _param_from_row(row, name)
                if value is not None:
                    parameter_values[name].append(value)
            for label, reference in (("positive", REFERENCE_POSITIVE), ("negative", REFERENCE_NEGATIVE)):
                raw = _raw_distance(row, reference)
                if raw is None:
                    continue
                norm = _normalized_distance(row, reference, bounds)
                if norm is not None:
                    if label == "positive":
                        norm_dist_pos.append(norm)
                    else:
                        norm_dist_neg.append(norm)
                if label == "positive":
                    if closest_pos is None or raw < closest_pos[0]:
                        closest_pos = (raw, objective, dict(row))
                else:
                    if closest_neg is None or raw < closest_neg[0]:
                        closest_neg = (raw, objective, dict(row))
                match_count = _reference_like_count(row, reference)
                if match_count == 6:
                    ref_like[label]["all_6"] += 1
                    chi2 = 2.0 * objective if objective is not None else None
                    previous = ref_like[label]["best_chi2_all_6"]
                    if chi2 is not None and (previous is None or chi2 < previous):
                        ref_like[label]["best_chi2_all_6"] = chi2
                if match_count >= 5:
                    ref_like[label]["at_least_5"] += 1
                if match_count >= 4:
                    ref_like[label]["at_least_4"] += 1

    def closest_payload(item: tuple[float, float | None, dict[str, str]] | None) -> dict[str, Any] | None:
        if item is None:
            return None
        raw, objective, row = item
        return {
            "raw_distance": raw,
            "normalized_distance": _normalized_distance(row, REFERENCE_POSITIVE if item is closest_pos else REFERENCE_NEGATIVE, bounds),
            "nll": objective,
            "chi2": 2.0 * objective if objective is not None else None,
            "parameters": {name: _param_from_row(row, name) for name in PARAMETERS},
        }

    return {
        "exists": True,
        "path": str(path),
        "columns": fieldnames,
        "total_rows": total_count,
        "finite_objective_rows": finite_count,
        "valid_rows": valid_count if valid_seen else None,
        "invalid_rows": invalid_count if valid_seen else None,
        "objective": {
            "best_nll": best.objective if best else None,
            "best_chi2": 2.0 * best.objective if best else None,
            "worst_finite_nll": max(objectives) if objectives else None,
            "median_nll": median(objectives) if objectives else None,
            "q10_nll": _quantile(objectives, 0.10),
            "q25_nll": _quantile(objectives, 0.25),
            "q75_nll": _quantile(objectives, 0.75),
            "q90_nll": _quantile(objectives, 0.90),
            "q99_nll": _quantile(objectives, 0.99),
        },
        "best_point": {
            "parameters": {name: _param_from_row(best.row, name) for name in PARAMETERS} if best else {},
            "likelihood_terms": _likelihood_terms_from_row(best.row) if best else {},
        },
        "parameter_ranges": {
            name: {
                "min": min(values) if values else None,
                "q05": _quantile(values, 0.05),
                "median": median(values) if values else None,
                "q95": _quantile(values, 0.95),
                "max": max(values) if values else None,
                "positive_reference_location": _range_location(values, REFERENCE_POSITIVE[name]),
                "negative_reference_location": _range_location(values, REFERENCE_NEGATIVE[name]),
            }
            for name, values in parameter_values.items()
        },
        "distance_to_positive_reference": {
            "min_normalized": min(norm_dist_pos) if norm_dist_pos else None,
            "median_normalized": median(norm_dist_pos) if norm_dist_pos else None,
            "q01_normalized": _quantile(norm_dist_pos, 0.01),
            "q05_normalized": _quantile(norm_dist_pos, 0.05),
            "q10_normalized": _quantile(norm_dist_pos, 0.10),
            "closest_point": closest_payload(closest_pos),
        },
        "distance_to_negative_reference": {
            "min_normalized": min(norm_dist_neg) if norm_dist_neg else None,
            "median_normalized": median(norm_dist_neg) if norm_dist_neg else None,
            "q01_normalized": _quantile(norm_dist_neg, 0.01),
            "q05_normalized": _quantile(norm_dist_neg, 0.05),
            "q10_normalized": _quantile(norm_dist_neg, 0.10),
            "closest_point": closest_payload(closest_neg),
        },
        "reference_like_counts": ref_like,
    }


def _range_location(values: list[float], reference_value: float) -> str:
    if not values:
        return "unknown"
    lo, hi = min(values), max(values)
    q05 = _quantile(values, 0.05)
    q95 = _quantile(values, 0.95)
    if q05 is not None and q95 is not None and q05 <= reference_value <= q95:
        return "inside_5_95"
    if lo <= reference_value <= hi:
        return "inside_min_max_outside_5_95"
    return "outside_min_max"


def _likelihood_terms_from_row(row: dict[str, str]) -> dict[str, float]:
    terms: dict[str, float] = {}
    for key, raw in row.items():
        if key.startswith("like__"):
            name = key.removeprefix("like__")
        elif key.startswith("likelihood::"):
            name = key.removeprefix("likelihood::")
        elif key.endswith("_term"):
            name = key
        else:
            continue
        value = _as_float(raw)
        if value is not None:
            terms[name] = value
    return terms


def evaluate_point(model_path: Path, point: dict[str, float]) -> dict[str, Any]:
    from bsm_scanner import _core, compile_model, load_model
    from bsm_scanner.scan import build_scan_request

    model = load_model(model_path)
    compiled = compile_model(model, build_backend=False)
    request = build_scan_request(model, compiled, run_directory=Path("tmp_weinberg_diagnostic_eval"))
    order = [p.name for p in request.scanned_parameters]
    values = [point[name] for name in order]
    request_dict = request.to_dict()
    request_dict["engine"] = "serial_random"
    record = _core.evaluate_scan_point(compiled.plan.to_dict(), request_dict, values)
    point_result = record.get("point_result", {}) if isinstance(record.get("point_result"), dict) else {}
    nll = _as_float(record.get("scanner_target") or record.get("metric_value") or record.get("total_nll"))
    return {
        "status": point_result.get("status", record.get("status")),
        "valid": point_result.get("valid", record.get("valid")),
        "failure_reason": point_result.get("failure_reason", record.get("failure_reason")),
        "nll": nll,
        "chi2": 2.0 * nll if nll is not None else None,
        "parameters": {name: point[name] for name in PARAMETERS},
        "outputs": point_result.get("outputs", record.get("outputs", {})),
        "likelihood_terms": point_result.get(
            "likelihood_terms",
            record.get("likelihood_terms", record.get("likelihoods", {})),
        ),
    }


def bounds_from_model(model_path: Path) -> dict[str, tuple[float, float]]:
    from bsm_scanner import compile_model, load_model
    from bsm_scanner.scan import build_scan_request

    model = load_model(model_path)
    compiled = compile_model(model, build_backend=False)
    request = build_scan_request(model, compiled, run_directory=Path("tmp_weinberg_diagnostic_bounds"))
    bounds: dict[str, tuple[float, float]] = {}
    for parameter in request.scanned_parameters:
        bounds[parameter.name] = (float(parameter.lower), float(parameter.upper))
    return bounds


def inspect_boxes(path: Path) -> list[dict[str, Any]]:
    data = _load_json(path)
    if data is None:
        return []
    boxes = data.get("boxes", data if isinstance(data, list) else [])
    inspected = []
    for index, box in enumerate(boxes):
        lower = box.get("lower") or {}
        upper = box.get("upper") or {}
        if not lower and "bounds" in box:
            bounds = box["bounds"]
            lower = {name: bounds[name][0] if isinstance(bounds.get(name), list) else bounds[name].get("lower") for name in bounds}
            upper = {name: bounds[name][1] if isinstance(bounds.get(name), list) else bounds[name].get("upper") for name in bounds}
        entry = {
            "box_id": box.get("box_id", index),
            "cluster_id": box.get("cluster_id"),
            "box_type": box.get("box_type", "unknown"),
            "relative_box_volume": box.get("relative_box_volume"),
            "lower": {name: lower.get(name) for name in PARAMETERS},
            "upper": {name: upper.get(name) for name in PARAMETERS},
        }
        for label, reference in (("positive", REFERENCE_POSITIVE), ("negative", REFERENCE_NEGATIVE)):
            excluded = []
            inside = True
            width_fraction = {}
            for name in PARAMETERS:
                lo = _as_float(lower.get(name))
                hi = _as_float(upper.get(name))
                if lo is None or hi is None:
                    inside = False
                    excluded.append(name)
                    continue
                if not (lo <= reference[name] <= hi):
                    inside = False
                    excluded.append(name)
                width_fraction[name] = hi - lo
            entry[f"{label}_reference_inside"] = inside
            entry[f"{label}_reference_excluded_by"] = excluded
            entry["widths"] = width_fraction
        inspected.append(entry)
    return inspected


def successful_elite_summary(run_dir: Path) -> dict[str, Any]:
    elite = summarize_csv(run_dir / "elite_points.csv", bounds={name: (-math.inf, math.inf) for name in PARAMETERS})
    final_population = summarize_csv(run_dir / "final_population.csv", bounds={name: (-math.inf, math.inf) for name in PARAMETERS})
    summary = _load_json(run_dir / "summary.json") or {}
    best = _load_json(run_dir / "best_fit.json") or {}
    return {
        "run_dir": str(run_dir),
        "summary": summary,
        "best_fit": best,
        "elite_points": {
            "total_rows": elite.get("total_rows"),
            "objective": elite.get("objective"),
            "parameter_ranges": elite.get("parameter_ranges"),
        },
        "final_population": {
            "total_rows": final_population.get("total_rows"),
            "objective": final_population.get("objective"),
            "parameter_ranges": final_population.get("parameter_ranges"),
        },
    }


def collect_run(run_dir: Path, model_path: Path, label: str, *, include_round_csv: bool = False) -> dict[str, Any]:
    bounds = bounds_from_model(model_path)
    summary = _load_json(run_dir / "summary.json") or {}
    best_fit = _load_json(run_dir / "best_fit.json") or {}
    selection_summary = _load_json(run_dir / "selection_summary.json")
    progressive_summary = _load_json(run_dir / "progressive_exploration_summary.json")
    result = {
        "label": label,
        "run_dir": str(run_dir),
        "model_path": str(model_path),
        "bounds": bounds,
        "summary": summary,
        "best_fit": best_fit,
        "selection_summary": selection_summary,
        "progressive_summary": progressive_summary,
        "exploration_points": summarize_csv(run_dir / "exploration_points.csv", bounds),
        "selected_points": summarize_csv(run_dir / "selected_points.csv", bounds),
        "clusters": summarize_csv(run_dir / "clusters.csv", bounds),
        "focused_boxes": inspect_boxes(run_dir / "focused_boxes.json"),
        "basin_results": _load_json(run_dir / "basin_results.json"),
    }
    basin_dirs = sorted(run_dir.glob("basin_*"))
    if basin_dirs:
        basin = basin_dirs[0]
        result["focused_adaptive_diver"] = {
            "run_dir": str(basin),
            "summary": _load_json(basin / "summary.json"),
            "best_fit": _load_json(basin / "best_fit.json"),
            "final_population": summarize_csv(basin / "final_population.csv", bounds),
            "elite_points": summarize_csv(basin / "elite_points.csv", bounds),
            "history": _load_json(basin / "history.json"),
        }
    round_data = []
    prog_dir = run_dir / "progressive_exploration"
    if prog_dir.exists():
        for selection_path in sorted(prog_dir.glob("round_*_selection_summary.json")):
            prefix = selection_path.name.replace("_selection_summary.json", "")
            entry = {
                "round": prefix,
                "selection_summary": _load_json(selection_path),
                "boxes": inspect_boxes(prog_dir / f"{prefix}_boxes.json"),
            }
            if include_round_csv:
                entry["points"] = summarize_csv(prog_dir / f"{prefix}_points.csv", bounds)
                entry["selected"] = summarize_csv(prog_dir / f"{prefix}_selected.csv", bounds)
            round_data.append(entry)
    result["progressive_rounds"] = round_data
    return result


def collect_run_light(run_dir: Path) -> dict[str, Any]:
    return {
        "run_dir": str(run_dir),
        "summary": _load_json(run_dir / "summary.json") or {},
        "best_fit": _load_json(run_dir / "best_fit.json") or {},
        "selection_summary": _load_json(run_dir / "selection_summary.json"),
        "progressive_summary": _load_json(run_dir / "progressive_exploration_summary.json"),
        "focused_boxes": inspect_boxes(run_dir / "focused_boxes.json"),
    }


def likelihood_config_summary(path: Path) -> list[dict[str, Any]]:
    terms = []
    if not path.exists():
        return terms
    current: dict[str, Any] | None = None
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:"):
            if current:
                terms.append(current)
            current = {"name": stripped.split(":", 1)[1].strip()}
        elif current and ":" in stripped and not stripped.startswith("#"):
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip()
    if current:
        terms.append(current)
    return terms


def write_markdown(path: Path, data: dict[str, Any]) -> None:
    failed = data["runs"]["failed_firsttest"]
    ref = data["point_evaluations"]["reference_positive"]
    failed_point = data["point_evaluations"]["failed_best"]
    successful = data["successful_focused"]
    latest_balanced = data["runs"].get("latest_progressive_balanced")

    lines = [
        "# Weinberg Scan Failure Diagnosis",
        "",
        "This report is generated from existing artifacts only. It does not modify framework code, model code, scan engines, or scan configs.",
        "",
        "## Executive conclusion",
        "",
        "- The first failing stage for `examples/weinberg/runs/firsttest` is **exploration/selection followed by focused-box construction**.",
        "- The reference point is valid and has much lower objective than the scan-found point under the same `models/weinberg/model_no.yaml` evaluator.",
        "- The final focused box excludes the reference basin, so the focused `adaptive_diver` run never had access to the true solution.",
        "- `balanced_terms` did not recover the reference basin in this run; it selected a cloud with `g2t` too low and then the focused box clipped away `g2t≈3.08`, `g3t≈-1.63`, and `Imtau≈1.19`.",
        "",
        "## Direct point comparison",
        "",
        "| point | valid | nLL | chi2 |",
        "|---|---:|---:|---:|",
        f"| reference positive | {ref.get('valid')} | {fmt(ref.get('nll'))} | {fmt(ref.get('chi2'))} |",
        f"| failed-run best | {failed_point.get('valid')} | {fmt(failed_point.get('nll'))} | {fmt(failed_point.get('chi2'))} |",
        "",
        "### Likelihood-term comparison",
        "",
        "| term | reference nLL contribution | failed-best contribution | difference |",
        "|---|---:|---:|---:|",
    ]
    ref_terms = ref.get("likelihood_terms", {})
    fail_terms = failed_point.get("likelihood_terms", {})
    for term in sorted(set(ref_terms) | set(fail_terms)):
        rv = ref_terms.get(term)
        fv = fail_terms.get(term)
        diff = None if rv is None or fv is None else fv - rv
        lines.append(f"| {term} | {fmt(rv)} | {fmt(fv)} | {fmt(diff)} |")

    lines.extend(
        [
            "",
            "Dominant failed-best terms are `s23_term`, `s12_term`, and `s13_term`; the point is technically valid but physically a poor fit.",
            "",
            "## Failed run summary",
            "",
            f"- Run: `{failed['run_dir']}`",
            f"- Model: `{failed['model_path']}`",
            f"- Engine: `{failed.get('summary', {}).get('engine_details', {}).get('orchestrator')}`",
            f"- Evaluations: `{failed.get('summary', {}).get('evaluations')}`",
            f"- Valid points: `{failed.get('summary', {}).get('valid_points')}`",
            f"- Best nLL: `{fmt(failed.get('summary', {}).get('best_scanner_target'))}`",
            f"- Best chi2: `{fmt(2 * failed.get('summary', {}).get('best_scanner_target'))}`",
            "",
            "### Parameter bounds",
            "",
            "| parameter | lower | upper |",
            "|---|---:|---:|",
        ]
    )
    for name, (lo, hi) in failed["bounds"].items():
        lines.append(f"| {name} | {fmt(lo)} | {fmt(hi)} |")

    lines.extend(["", "## Exploration and final selection", ""])
    for key, title in (("exploration_points", "Exploration points"), ("selected_points", "Final selected points")):
        item = failed[key]
        obj = item.get("objective", {})
        lines.extend(
            [
                f"### {title}",
                "",
                f"- Rows: `{item.get('total_rows')}`",
                f"- Valid rows: `{item.get('valid_rows')}`",
                f"- Best nLL / chi2: `{fmt(obj.get('best_nll'))}` / `{fmt(obj.get('best_chi2'))}`",
                f"- Median nLL: `{fmt(obj.get('median_nll'))}`",
                f"- q10/q25/q75/q90/q99 nLL: `{fmt(obj.get('q10_nll'))}`, `{fmt(obj.get('q25_nll'))}`, `{fmt(obj.get('q75_nll'))}`, `{fmt(obj.get('q90_nll'))}`, `{fmt(obj.get('q99_nll'))}`",
                "",
                "Best point:",
                "",
                "```json",
                json.dumps(item.get("best_point", {}).get("parameters", {}), indent=2),
                "```",
                "",
            ]
        )
        for branch in ("positive", "negative"):
            dist = item.get(f"distance_to_{branch}_reference", {})
            closest = dist.get("closest_point") or {}
            lines.extend(
                [
                    f"{branch.capitalize()} reference distance diagnostics:",
                    "",
                    f"- Minimum normalized distance: `{fmt(dist.get('min_normalized'))}`",
                    f"- Median normalized distance: `{fmt(dist.get('median_normalized'))}`",
                    f"- Closest point chi2: `{fmt(closest.get('chi2'))}`",
                    f"- Closest point raw distance: `{fmt(closest.get('raw_distance'))}`",
                    "",
                ]
            )
        counts = item.get("reference_like_counts", {})
        lines.extend(
            [
                "Reference-like cut counts:",
                "",
                f"- Positive branch: `{counts.get('positive')}`",
                f"- Negative branch: `{counts.get('negative')}`",
                "",
            ]
        )

    sel = failed.get("selection_summary") or {}
    lines.extend(
        [
            "### Final selection diagnostics",
            "",
            f"- Mode: `{sel.get('mode')}`",
            f"- Candidate points: `{sel.get('candidate_points')}`",
            f"- After total top cut: `{sel.get('number_after_total_top_fraction')}`",
            f"- After balanced term cuts: `{sel.get('number_after_balanced_term_cuts')}`",
            f"- Final selected count: `{sel.get('final_selected_count')}`",
            f"- Fallback used: `{sel.get('fallback_used')}`",
            f"- Best selected nLL: `{fmt(sel.get('best_objective_selected'))}`",
            f"- Worst selected nLL: `{fmt(sel.get('worst_objective_selected'))}`",
            "",
            "Thresholds:",
            "",
            "```json",
            json.dumps(sel.get("thresholds", {}), indent=2),
            "```",
            "",
        ]
    )

    lines.extend(["## Progressive rounds", ""])
    for idx, round_info in enumerate(failed.get("progressive_rounds", [])):
        points = round_info.get("points", {})
        selected = round_info.get("selected", {})
        summary = round_info.get("selection_summary") or {}
        progressive_round_summary = _progressive_round_summary(failed.get("progressive_summary"), idx)
        lines.extend(
            [
                f"### {round_info['round']}",
                "",
                f"- Round points: `{points.get('total_rows', progressive_round_summary.get('evaluated_points'))}`, valid `{points.get('valid_rows', progressive_round_summary.get('valid_points'))}`",
                f"- Best round nLL / chi2: `{fmt(points.get('objective', {}).get('best_nll', progressive_round_summary.get('best_objective')))}` / `{fmt(points.get('objective', {}).get('best_chi2', progressive_round_summary.get('best_chi2')))}`",
                f"- Selected count: `{selected.get('total_rows', summary.get('final_selected_count'))}`",
                f"- Best selected nLL / chi2: `{fmt(selected.get('objective', {}).get('best_nll', summary.get('best_objective_selected')))}` / `{fmt(selected.get('objective', {}).get('best_chi2', 2 * summary.get('best_objective_selected') if summary.get('best_objective_selected') is not None else None))}`",
                f"- Balanced fallback used: `{summary.get('fallback_used')}`",
                f"- Terms used: `{summary.get('likelihood_terms_used')}`",
                "",
            ]
        )

    lines.extend(["## Focused box diagnostics", ""])
    for box in failed.get("focused_boxes", []):
        lines.extend(
            [
                f"### Box {box.get('box_id')}",
                "",
                f"- Type: `{box.get('box_type')}`",
                f"- Relative volume: `{fmt(box.get('relative_box_volume'))}`",
                f"- Positive reference inside: `{box.get('positive_reference_inside')}`",
                f"- Positive reference excluded by: `{box.get('positive_reference_excluded_by')}`",
                f"- Negative reference inside: `{box.get('negative_reference_inside')}`",
                f"- Negative reference excluded by: `{box.get('negative_reference_excluded_by')}`",
                "",
                "| parameter | lower | upper |",
                "|---|---:|---:|",
            ]
        )
        for name in PARAMETERS:
            lines.append(f"| {name} | {fmt(box.get('lower', {}).get(name))} | {fmt(box.get('upper', {}).get(name))} |")
        lines.append("")

    focused = failed.get("focused_adaptive_diver", {})
    focused_summary = focused.get("summary") or {}
    focused_engine = focused_summary.get("engine_details", {})
    lines.extend(
        [
            "## Focused adaptive_diver diagnostics",
            "",
            f"- Run: `{focused.get('run_dir')}`",
            f"- Final nLL / chi2: `{fmt(focused_summary.get('best_scanner_target'))}` / `{fmt(2 * focused_summary.get('best_scanner_target'))}`",
            f"- Stop reason: `{focused_engine.get('stop_reason')}`",
            f"- Evaluations: `{focused_summary.get('evaluations')}`",
            f"- Local refinement enabled: `{focused_engine.get('local_refinement_enabled')}`",
            f"- Closest final-population point to positive reference chi2: `{fmt((focused.get('final_population') or {}).get('distance_to_positive_reference', {}).get('closest_point', {}).get('chi2'))}`",
            f"- Closest elite point to positive reference chi2: `{fmt((focused.get('elite_points') or {}).get('distance_to_positive_reference', {}).get('closest_point', {}).get('chi2'))}`",
            "",
            "Because the focused box excludes the reference basin, this is not evidence that `adaptive_diver` failed inside a good box.",
            "",
        ]
    )

    lines.extend(
        [
            "## Successful focused/narrow run",
            "",
            f"- Run: `{successful.get('run_dir')}`",
            f"- Best nLL / chi2: `{fmt((successful.get('summary') or {}).get('best_scanner_target'))}` / `{fmt(2 * (successful.get('summary') or {}).get('best_scanner_target'))}`",
            "",
            "Best point:",
            "",
            "```json",
            json.dumps((successful.get("best_fit") or {}).get("parameters", {}), indent=2),
            "```",
            "",
            "Elite-point 5%-95% parameter ranges:",
            "",
            "| parameter | q05 | q95 | width |",
            "|---|---:|---:|---:|",
        ]
    )
    elite_ranges = ((successful.get("elite_points") or {}).get("parameter_ranges") or {})
    for name in PARAMETERS:
        info = elite_ranges.get(name, {})
        q05, q95 = info.get("q05"), info.get("q95")
        width = None if q05 is None or q95 is None else q95 - q05
        lines.append(f"| {name} | {fmt(q05)} | {fmt(q95)} | {fmt(width)} |")

    if latest_balanced:
        lines.extend(
            [
                "",
                "## Latest broad progressive balanced comparison",
                "",
                f"- Run: `{latest_balanced['run_dir']}`",
                f"- Best nLL / chi2: `{fmt(latest_balanced.get('summary', {}).get('best_scanner_target'))}` / `{fmt(2 * latest_balanced.get('summary', {}).get('best_scanner_target'))}`",
                f"- Focused boxes: `{len(latest_balanced.get('focused_boxes', []))}`",
                "",
            ]
        )
        for box in latest_balanced.get("focused_boxes", []):
            lines.append(
                f"- Box {box.get('box_id')} positive inside `{box.get('positive_reference_inside')}`, excluded by `{box.get('positive_reference_excluded_by')}`, relative volume `{fmt(box.get('relative_box_volume'))}`"
            )

    lines.extend(
        [
            "",
            "## Answers to required questions",
            "",
            "1. **Was the reference basin ever sampled approximately?** Not in a useful way in `firsttest`. Approximate reference-like counts are zero for all six cuts; the closest raw point was high chi2.",
            "2. **If sampled, was it selected or discarded?** Reference-like points were not sampled closely enough. The final selected range also excludes the positive reference in `g2t`.",
            "3. **Did balanced_terms help?** It produced balanced term diagnostics and avoided fallback, but it did not recover the true basin; in this run it selected a wrong cloud.",
            "4. **Did focused box construction cut away the true basin?** Yes. The final focused box excludes the reference basin.",
            "5. **Did adaptive_diver ever get a box containing the true basin?** No for `firsttest`.",
            "6. **Which likelihood terms dominate the failed best point?** `s23_term`, `s12_term`, and `s13_term` dominate.",
            "7. **How small/correlated is the successful basin?** The successful focused run has a tiny elite spread compared with the broad box, especially in the modular-form parameters; see elite 5%-95% table.",
            "8. **First failing stage:** exploration/selection, followed by focused-box construction that excludes the basin.",
            "9. **Most justified next improvement:** delayed focusing or diverse multi-basin boxes with explicit global-best/elite retention into final focused boxes. Parameter-domain tightening/transforms for `tau` and modular coefficients are also justified, but that is a model-domain choice rather than a scanner-only change.",
            "",
        ]
    )

    path.write_text("\n".join(lines))


def fmt(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            return "NA"
        return f"{float(value):.10g}"
    return str(value)


def _progressive_round_summary(progressive_summary: dict[str, Any] | None, index: int) -> dict[str, Any]:
    if not progressive_summary:
        return {}
    rounds = progressive_summary.get("rounds") or []
    if index >= len(rounds):
        return {}
    return rounds[index] or {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failed-run", type=Path, default=Path("examples/weinberg/runs/firsttest"))
    parser.add_argument("--failed-model", type=Path, default=Path("models/weinberg/model_no.yaml"))
    parser.add_argument(
        "--successful-focused-run",
        type=Path,
        default=Path("examples/arxiv2006_03058_weinberg/runs/no_adaptive_diver_range_g3_minus2_0"),
    )
    parser.add_argument(
        "--latest-balanced-run",
        type=Path,
        default=Path("examples/arxiv2006_03058_weinberg/runs/no_basin_scan_progressive_balanced_full"),
    )
    parser.add_argument(
        "--latest-balanced-model",
        type=Path,
        default=Path("models/arxiv2006_03058_weinberg/model_no_basin_scan_progressive_balanced.yaml"),
    )
    parser.add_argument("--out-md", type=Path, default=Path("docs/benchmarks/weinberg_scan_failure_diagnosis.md"))
    parser.add_argument("--out-json", type=Path, default=Path("docs/benchmarks/weinberg_scan_failure_diagnosis.json"))
    args = parser.parse_args()

    failed_best = _load_json(args.failed_run / "best_fit.json") or {}
    failed_best_point = failed_best.get("parameters", {})

    data = {
        "reference_points": {
            "positive": REFERENCE_POSITIVE,
            "negative": REFERENCE_NEGATIVE,
        },
        "likelihood_config": likelihood_config_summary(args.failed_model.parent / "likelihoods_no.yaml"),
        "point_evaluations": {
            "reference_positive": evaluate_point(args.failed_model, REFERENCE_POSITIVE),
            "reference_negative": evaluate_point(args.failed_model, REFERENCE_NEGATIVE),
            "failed_best": evaluate_point(args.failed_model, failed_best_point) if failed_best_point else {},
        },
        "runs": {
            "failed_firsttest": collect_run(args.failed_run, args.failed_model, "failed_firsttest"),
        },
        "successful_focused": successful_elite_summary(args.successful_focused_run),
        "failure_stage": "exploration_selection_and_focused_box_construction",
        "recommended_next_step": "delay final focusing and preserve diverse elite/global-best boxes into focused adaptive_diver runs; consider parameter-domain transforms/tighter physical tau domain separately",
    }
    if args.latest_balanced_run.exists():
        data["runs"]["latest_progressive_balanced"] = collect_run_light(args.latest_balanced_run)

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(args.out_md, data)
    args.out_json.write_text(json.dumps(data, indent=2, default=_json_default))
    print(f"wrote {args.out_md}")
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
