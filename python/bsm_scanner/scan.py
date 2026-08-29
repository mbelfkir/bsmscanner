from __future__ import annotations

import copy
import csv
import importlib
import importlib.util
import inspect
import json
import uuid
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from math import ceil, isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import numpy as np

from bsm_scanner.exceptions import ModelValidationError
from bsm_scanner.model.schema import ModelDefinition, ValueType
from bsm_scanner.statistics import run_statistics

if TYPE_CHECKING:
    from bsm_scanner.api import CompiledModel

try:
    from . import _core  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _core = None


_SCAN_SETTING_ALIASES: dict[str, str] = {
    "objective": "objective_mode",
    "objective_mode": "objective_mode",
    "maximize": "maximize",
    "save_invalid_points": "save_invalid_points",
    "invalid_objective": "invalid_objective",
    "invalid_penalty": "invalid_objective",
    "max_evaluations": "max_evaluations",
    "max_generations": "max_generations",
    "maxgen": "max_generations",
    "maxiter": "max_generations",
    "population_size": "population_size",
    "NP": "population_size",
    "popsize": "population_size",
    "convergence_threshold": "convergence_threshold",
    "convthresh": "convergence_threshold",
    "convergence_steps": "convergence_steps",
    "convsteps": "convergence_steps",
    "max_init_attempts": "max_init_attempts",
    "verbose": "verbose",
    "strategy": "strategy",
    "tol": "tol",
    "atol": "atol",
    "mutation": "mutation",
    "recombination": "recombination",
    "init": "init",
    "updating": "updating",
    "workers": "workers",
    "polish": "polish",
    "x0": "x0",
    "seed": "seed",
    "progress_interval": "progress_interval",
    "progress_every": "progress_interval",
    "log_every": "progress_interval",
    "p_best_fraction": "p_best_fraction",
    "archive": "archive",
    "F_min": "F_min",
    "F_max": "F_max",
    "F_initial": "F_initial",
    "F_learning_rate": "F_learning_rate",
    "CR_min": "CR_min",
    "CR_max": "CR_max",
    "CR_initial": "CR_initial",
    "CR_learning_rate": "CR_learning_rate",
    "bounds_handling": "bounds_handling",
    "patience": "patience",
    "min_delta_chi2": "min_delta_chi2",
    "population_std_tol": "population_std_tol",
    "local_refinement": "local_refinement",
    "local_refinement_enabled": "local_refinement_enabled",
    "local_method": "local_method",
    "local_n_elites": "local_n_elites",
    "local_maxiter": "local_maxiter",
    "adaptive_statistics": "adaptive_statistics",
    "confidence_levels": "confidence_levels",
    "elite_size": "elite_size",
    "save_history": "save_history",
    "save_population": "save_population",
    "save_elites": "save_elites",
    "bounds": "bounds",
    "convergence": "convergence",
    "crossover": "crossover",
    "output": "output",
    "statistics": "statistics",
    "exploration": "exploration",
    "progressive_exploration": "progressive_exploration",
    "selection": "selection",
    "clustering": "clustering",
    "boxes": "boxes",
    "focused_engine": "focused_engine",
    "proposals": "proposals",
    "guided_sampling": "guided_sampling",
    "staged_evaluation": "staged_evaluation",
    "refinement": "refinement",
    "ml_focus": "ml_focus",
    "manifold_refocus": "manifold_refocus",
    "keep_fraction": "keep_fraction",
    "n_points": "n_points",
    "method": "method",
    "top_fraction": "top_fraction",
    "total_top_fraction": "total_top_fraction",
    "term_quantile_cut": "term_quantile_cut",
    "max_points": "max_points",
    "min_points": "min_points",
    "chi2_window": "chi2_window",
    "terms": "terms",
    "exclude_terms": "exclude_terms",
    "combine_with_top_fraction": "combine_with_top_fraction",
    "fallback_mode": "fallback_mode",
    "eps_fraction": "eps_fraction",
    "min_samples": "min_samples",
    "max_clusters": "max_clusters",
    "construction": "construction",
    "q_low": "q_low",
    "q_high": "q_high",
    "padding_fraction": "padding_fraction",
    "min_width_fraction": "min_width_fraction",
    "clip_to_original_bounds": "clip_to_original_bounds",
    "focused_engine_name": "focused_engine_name",
    "save_exploration_points": "save_exploration_points",
    "save_selected_points": "save_selected_points",
    "save_clusters": "save_clusters",
    "save_focused_boxes": "save_focused_boxes",
}

_DE_SCIPY_STRATEGIES = {
    "best1bin",
    "best1exp",
    "rand1bin",
    "rand1exp",
    "rand2bin",
    "rand2exp",
    "randtobest1bin",
    "randtobest1exp",
    "currenttobest1bin",
    "currenttobest1exp",
    "best2bin",
    "best2exp",
}

_DE_SCIPY_INIT_MODES = {"latinhypercube", "sobol", "halton", "random"}
_DE_SCIPY_UPDATING = {"immediate", "deferred"}
_ADAPTIVE_DIVER_STRATEGIES = {"current_to_pbest"}
_ADAPTIVE_DIVER_BOUND_HANDLING = {"clip", "reflect", "resample"}
_ADAPTIVE_DIVER_LOCAL_METHODS = {"Powell", "L-BFGS-B"}
_BASIN_EXPLORATION_METHODS = {"latin_hypercube", "sobol", "random"}
_BASIN_SELECTION_MODES = {"top_fraction", "chi2_window", "balanced_terms"}
_BASIN_CLUSTERING_METHODS = {"dbscan"}
_BASIN_BOX_CONSTRUCTION = {"quantile"}
_BASIN_PROGRESSIVE_ALLOCATION = {"equal", "proportional_volume", "mixed"}
_BASIN_PROPOSAL_TYPES = {
    "prior_profile",
    "complex_vector_norm",
    "parameter_rescale",
    "point_function",
}
_GUIDED_FUNCTION_CACHE: dict[str, Any] = {}


def _import_scipy_differential_evolution():
    try:
        optimize = importlib.import_module("scipy.optimize")
    except Exception as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError(
            "The 'de_scipy' engine requires SciPy. Install it with "
            "python -m pip install -e '.[de]' or add scipy to the active environment."
        ) from exc
    return optimize.differential_evolution


def _stringify_setting(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value)
    return str(value)


def _json_ready(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, complex):
        return {"re": value.real, "im": value.imag}
    if hasattr(value, "tolist"):
        return _json_ready(value.tolist())
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return str(value)


def _csv_ready(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, complex):
        sign = "+" if value.imag >= 0 else ""
        return f"{value.real}{sign}{value.imag}j"
    if hasattr(value, "tolist"):
        return json.dumps(value.tolist())
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(_json_ready(value))
    return str(value)


def _coerce_int(name: str, value: Any, *, minimum: int | None = None) -> int:
    try:
        coerced = int(value)
    except Exception as exc:
        raise ModelValidationError(f"scan.settings.{name} must be an integer.") from exc
    if minimum is not None and coerced < minimum:
        raise ModelValidationError(
            f"scan.settings.{name} must be >= {minimum}."
        )
    return coerced


def _coerce_float(name: str, value: Any, *, minimum: float | None = None) -> float:
    try:
        coerced = float(value)
    except Exception as exc:
        raise ModelValidationError(f"scan.settings.{name} must be a real number.") from exc
    if minimum is not None and coerced < minimum:
        raise ModelValidationError(
            f"scan.settings.{name} must be >= {minimum}."
        )
    return coerced


def _coerce_bool(name: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raise ModelValidationError(f"scan.settings.{name} must be true or false.")


def _coerce_optional_int(name: str, value: Any, *, minimum: int | None = None) -> int:
    if value is None:
        return 0
    return _coerce_int(name, value, minimum=minimum)


def _coerce_vector(name: str, value: Any, *, dimension: int) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise ModelValidationError(f"scan.settings.{name} must be a list of {dimension} numbers.")
    if len(value) != dimension:
        raise ModelValidationError(
            f"scan.settings.{name} must contain exactly {dimension} entries."
        )
    coerced = [_coerce_float(f"{name}[{index}]", item) for index, item in enumerate(value)]
    if not all(isfinite(item) for item in coerced):
        raise ModelValidationError(f"scan.settings.{name} entries must be finite.")
    return coerced


def _coerce_mutation(value: Any) -> float | tuple[float, float]:
    if isinstance(value, (int, float)):
        mutation = float(value)
        if not (0.0 <= mutation < 2.0):
            raise ModelValidationError("scan.settings.mutation must satisfy 0 <= mutation < 2.")
        return mutation
    if isinstance(value, (list, tuple)) and len(value) == 2:
        low = _coerce_float("mutation[0]", value[0], minimum=0.0)
        high = _coerce_float("mutation[1]", value[1], minimum=0.0)
        if not (low <= high < 2.0):
            raise ModelValidationError(
                "scan.settings.mutation range must satisfy 0 <= low <= high < 2."
            )
        return (low, high)
    raise ModelValidationError(
        "scan.settings.mutation must be a float or a two-element [low, high] list."
    )


def _section(settings: dict[str, Any], name: str) -> dict[str, Any]:
    value = settings.get(name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ModelValidationError(f"scan.settings.{name} must be a mapping.")
    return dict(value)


def _section_get(settings: dict[str, Any], section: str, key: str, default: Any) -> Any:
    payload = _section(settings, section)
    return payload.get(key, settings.get(key, default))


def _coerce_terms_config(value: Any) -> str | list[str]:
    if value is None:
        return "auto"
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    raise ModelValidationError("scan.settings.selection.terms must be 'auto' or a list of term names.")


def _coerce_string_list(name: str, value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ModelValidationError(f"scan.settings.{name} must be a list.")
    return [str(item) for item in value]


def _build_basin_selection_options(
    selection: dict[str, Any],
    *,
    prefix: str,
    mode_default: str,
    top_fraction_default: float,
    max_points_default: int,
    chi2_window_default: float,
) -> dict[str, Any]:
    mode = str(selection.get("mode", mode_default))
    if mode not in _BASIN_SELECTION_MODES:
        raise ModelValidationError(
            f"scan.basin_scan.{prefix}.mode must be one of: "
            + ", ".join(sorted(_BASIN_SELECTION_MODES))
        )
    top_fraction = _coerce_float(
        f"{prefix}.top_fraction",
        selection.get("top_fraction", top_fraction_default),
        minimum=0.0,
    )
    if top_fraction <= 0.0 or top_fraction > 1.0:
        raise ModelValidationError(f"scan.basin_scan.{prefix}.top_fraction must satisfy 0 < f <= 1.")
    max_points = _coerce_int(f"{prefix}.max_points", selection.get("max_points", max_points_default), minimum=1)
    chi2_window = _coerce_float(
        f"{prefix}.chi2_window",
        selection.get("chi2_window", chi2_window_default),
        minimum=0.0,
    )
    total_top_fraction = _coerce_float(
        f"{prefix}.total_top_fraction",
        selection.get("total_top_fraction", top_fraction),
        minimum=0.0,
    )
    if total_top_fraction <= 0.0 or total_top_fraction > 1.0:
        raise ModelValidationError(f"scan.basin_scan.{prefix}.total_top_fraction must satisfy 0 < f <= 1.")
    term_quantile_cut = _coerce_float(
        f"{prefix}.term_quantile_cut",
        selection.get("term_quantile_cut", 0.30),
        minimum=0.0,
    )
    if term_quantile_cut > 1.0:
        raise ModelValidationError(f"scan.basin_scan.{prefix}.term_quantile_cut must be <= 1.")
    min_points = _coerce_int(f"{prefix}.min_points", selection.get("min_points", 1), minimum=1)
    if min_points > max_points:
        raise ModelValidationError(f"scan.basin_scan.{prefix}.min_points must be <= max_points.")
    fallback_mode = str(selection.get("fallback_mode", "top_fraction"))
    if fallback_mode not in {"top_fraction", "chi2_window"}:
        raise ModelValidationError(
            f"scan.basin_scan.{prefix}.fallback_mode must be 'top_fraction' or 'chi2_window'."
        )
    return {
        "mode": mode,
        "top_fraction": top_fraction,
        "max_points": max_points,
        "chi2_window": chi2_window,
        "total_top_fraction": total_top_fraction,
        "term_quantile_cut": term_quantile_cut,
        "min_points": min_points,
        "terms": _coerce_terms_config(selection.get("terms", "auto")),
        "exclude_terms": _coerce_string_list(f"{prefix}.exclude_terms", selection.get("exclude_terms", [])),
        "combine_with_top_fraction": _coerce_bool(
            f"{prefix}.combine_with_top_fraction",
            selection.get("combine_with_top_fraction", True),
        ),
        "fallback_mode": fallback_mode,
    }


def _build_near_miss_options(
    near_miss: dict[str, Any],
    *,
    prefix: str,
    invalid_penalty: float,
) -> dict[str, Any]:
    return {
        "enabled": _coerce_bool(f"{prefix}.enabled", near_miss.get("enabled", False)),
        "keep_accepted": _coerce_bool(
            f"{prefix}.keep_accepted",
            near_miss.get("keep_accepted", True),
        ),
        "keep_per_term_best": _coerce_bool(
            f"{prefix}.keep_per_term_best",
            near_miss.get("keep_per_term_best", True),
        ),
        "include_invalid": _coerce_bool(
            f"{prefix}.include_invalid",
            near_miss.get("include_invalid", False),
        ),
        "max_hard_failures": _coerce_int(
            f"{prefix}.max_hard_failures",
            near_miss.get("max_hard_failures", 0),
            minimum=0,
        ),
        "max_fit_failures": _coerce_int(
            f"{prefix}.max_fit_failures",
            near_miss.get("max_fit_failures", 3),
            minimum=0,
        ),
        "objective_cap": _coerce_float(
            f"{prefix}.objective_cap",
            near_miss.get("objective_cap", invalid_penalty),
            minimum=0.0,
        ),
        "include_full_eval_points": _coerce_bool(
            f"{prefix}.include_full_eval_points",
            near_miss.get("include_full_eval_points", True),
        ),
        "max_accepted_points": _coerce_int(
            f"{prefix}.max_accepted_points",
            near_miss.get("max_accepted_points", 100),
            minimum=0,
        ),
        "max_near_miss_points": _coerce_int(
            f"{prefix}.max_near_miss_points",
            near_miss.get("max_near_miss_points", 100),
            minimum=0,
        ),
    }


def _coerce_real_list(name: str, value: Any, *, minimum_length: int = 1) -> list[float]:
    if not isinstance(value, (list, tuple)):
        raise ModelValidationError(f"scan.settings.{name} must be a list of real numbers.")
    if len(value) < minimum_length:
        raise ModelValidationError(
            f"scan.settings.{name} must contain at least {minimum_length} value(s)."
        )
    levels = [_coerce_float(f"{name}[{index}]", item) for index, item in enumerate(value)]
    if not all(isfinite(item) for item in levels):
        raise ModelValidationError(f"scan.settings.{name} entries must be finite.")
    return levels


def _build_de_scipy_options(
    settings: dict[str, Any],
    *,
    seed: int,
    dimension: int,
    invalid_penalty: float,
) -> dict[str, Any]:
    strategy = str(settings.get("strategy", "best1bin"))
    if strategy not in _DE_SCIPY_STRATEGIES:
        raise ModelValidationError(
            "scan.settings.strategy must be one of: "
            + ", ".join(sorted(_DE_SCIPY_STRATEGIES))
        )

    maxiter = _coerce_int("maxiter", settings.get("maxiter", settings.get("max_generations", settings.get("maxgen", 100))), minimum=0)
    popsize = _coerce_int("popsize", settings.get("popsize", settings.get("population_size", settings.get("NP", 15))), minimum=1)
    tol = _coerce_float("tol", settings.get("tol", settings.get("convergence_threshold", 0.01)), minimum=0.0)
    atol = _coerce_float("atol", settings.get("atol", 0.0), minimum=0.0)
    recombination = _coerce_float("recombination", settings.get("recombination", 0.7), minimum=0.0)
    if recombination > 1.0:
        raise ModelValidationError("scan.settings.recombination must be <= 1.")
    mutation = _coerce_mutation(settings.get("mutation", (0.5, 1.0)))

    init = str(settings.get("init", "latinhypercube"))
    if init not in _DE_SCIPY_INIT_MODES:
        raise ModelValidationError(
            "scan.settings.init must be one of: " + ", ".join(sorted(_DE_SCIPY_INIT_MODES))
        )

    updating = str(settings.get("updating", "deferred"))
    if updating not in _DE_SCIPY_UPDATING:
        raise ModelValidationError(
            "scan.settings.updating must be 'immediate' or 'deferred'."
        )

    workers = _coerce_int("workers", settings.get("workers", 1))
    if workers != 1:
        raise ModelValidationError(
            "The temporary 'de_scipy' reference engine currently supports scan.settings.workers = 1 only. "
            "This keeps artifact capture and evaluation semantics deterministic for native-engine comparison."
        )

    polish = _coerce_bool("polish", settings.get("polish", False))
    x0 = _coerce_vector("x0", settings.get("x0"), dimension=dimension)
    progress_interval = _coerce_int(
        "progress_interval",
        settings.get("progress_interval", settings.get("progress_every", settings.get("log_every", 100))),
        minimum=0,
    )

    return {
        "strategy": strategy,
        "maxiter": maxiter,
        "popsize": popsize,
        "tol": tol,
        "atol": atol,
        "mutation": mutation,
        "recombination": recombination,
        "seed": int(settings.get("seed", seed)),
        "init": init,
        "updating": updating,
        "workers": workers,
        "polish": polish,
        "invalid_penalty": invalid_penalty,
        "x0": x0,
        "progress_interval": progress_interval,
    }


def _build_adaptive_diver_options(
    settings: dict[str, Any],
    *,
    seed: int,
    dimension: int,
    invalid_penalty: float,
) -> dict[str, Any]:
    strategy = str(settings.get("strategy", "current_to_pbest"))
    if strategy not in _ADAPTIVE_DIVER_STRATEGIES:
        raise ModelValidationError(
            "scan.settings.strategy must be one of: "
            + ", ".join(sorted(_ADAPTIVE_DIVER_STRATEGIES))
        )

    population_size = _coerce_int(
        "population_size",
        settings.get("population_size", settings.get("popsize", settings.get("NP", 40))),
        minimum=4,
    )
    max_generations = _coerce_int(
        "max_generations",
        settings.get("max_generations", settings.get("maxiter", settings.get("maxgen", 1000))),
        minimum=0,
    )
    max_evaluations = _coerce_optional_int(
        "max_evaluations",
        settings.get("max_evaluations", 0),
        minimum=0,
    )
    if max_evaluations and max_evaluations < population_size:
        raise ModelValidationError(
            "adaptive_diver requires scan.settings.max_evaluations to be either unset/0 "
            "or at least the configured population_size."
        )

    p_best_fraction = _coerce_float(
        "p_best_fraction",
        settings.get("p_best_fraction", 0.1),
        minimum=0.0,
    )
    if p_best_fraction <= 0.0 or p_best_fraction > 1.0:
        raise ModelValidationError("scan.settings.p_best_fraction must satisfy 0 < p <= 1.")

    archive = _coerce_bool("archive", settings.get("archive", True))

    f_min = _coerce_float("F_min", _section_get(settings, "mutation", "F_min", 0.1), minimum=0.0)
    f_max = _coerce_float("F_max", _section_get(settings, "mutation", "F_max", 1.0), minimum=0.0)
    f_initial = _coerce_float("F_initial", _section_get(settings, "mutation", "initial_mean", settings.get("F_initial", 0.5)), minimum=0.0)
    f_learning_rate = _coerce_float(
        "F_learning_rate",
        _section_get(settings, "mutation", "learning_rate", settings.get("F_learning_rate", 0.1)),
        minimum=0.0,
    )
    if not (0.0 <= f_min <= f_initial <= f_max <= 2.0):
        raise ModelValidationError("Adaptive mutation settings must satisfy 0 <= F_min <= initial_mean <= F_max <= 2.")
    if f_learning_rate > 1.0:
        raise ModelValidationError("scan.settings.F_learning_rate must be <= 1.")

    cr_min = _coerce_float("CR_min", _section_get(settings, "crossover", "CR_min", 0.0), minimum=0.0)
    cr_max = _coerce_float("CR_max", _section_get(settings, "crossover", "CR_max", 1.0), minimum=0.0)
    cr_initial = _coerce_float(
        "CR_initial",
        _section_get(settings, "crossover", "initial_mean", settings.get("CR_initial", 0.9)),
        minimum=0.0,
    )
    cr_learning_rate = _coerce_float(
        "CR_learning_rate",
        _section_get(settings, "crossover", "learning_rate", settings.get("CR_learning_rate", 0.1)),
        minimum=0.0,
    )
    if not (0.0 <= cr_min <= cr_initial <= cr_max <= 1.0):
        raise ModelValidationError("Adaptive crossover settings must satisfy 0 <= CR_min <= initial_mean <= CR_max <= 1.")
    if cr_learning_rate > 1.0:
        raise ModelValidationError("scan.settings.CR_learning_rate must be <= 1.")

    bounds_handling = str(_section_get(settings, "bounds", "handling", settings.get("bounds_handling", "reflect")))
    if bounds_handling not in _ADAPTIVE_DIVER_BOUND_HANDLING:
        raise ModelValidationError(
            "scan.settings.bounds.handling must be one of: "
            + ", ".join(sorted(_ADAPTIVE_DIVER_BOUND_HANDLING))
        )

    patience = _coerce_int("patience", _section_get(settings, "convergence", "patience", 200), minimum=0)
    min_delta_chi2 = _coerce_float(
        "min_delta_chi2",
        _section_get(settings, "convergence", "min_delta_chi2", 1.0e-8),
        minimum=0.0,
    )
    population_std_tol = _coerce_float(
        "population_std_tol",
        _section_get(settings, "convergence", "population_std_tol", 0.0),
        minimum=0.0,
    )

    local_section = _section(settings, "local_refinement")
    local_refinement_enabled = _coerce_bool(
        "local_refinement.enabled",
        local_section.get("enabled", settings.get("local_refinement_enabled", settings.get("local_refinement", False))),
    )
    local_method = str(local_section.get("method", settings.get("local_method", "Powell")))
    if local_method not in _ADAPTIVE_DIVER_LOCAL_METHODS:
        raise ModelValidationError(
            "scan.settings.local_refinement.method must be one of: "
            + ", ".join(sorted(_ADAPTIVE_DIVER_LOCAL_METHODS))
        )
    local_n_elites = _coerce_int(
        "local_n_elites",
        local_section.get("n_elites", settings.get("local_n_elites", 5)),
        minimum=1,
    )
    local_maxiter = _coerce_int(
        "local_maxiter",
        local_section.get("maxiter", settings.get("local_maxiter", 2000)),
        minimum=1,
    )

    statistics_section = _section(settings, "statistics")
    adaptive_statistics = _coerce_bool(
        "adaptive_statistics",
        statistics_section.get("enabled", settings.get("adaptive_statistics", False)),
    )
    confidence_levels = _coerce_real_list(
        "confidence_levels",
        statistics_section.get("confidence_levels", settings.get("confidence_levels", [0.68, 0.95])),
    )
    for level in confidence_levels:
        if level <= 0.0 or level >= 1.0:
            raise ModelValidationError("scan.settings.confidence_levels entries must satisfy 0 < level < 1.")

    output_section = _section(settings, "output")
    progress_interval = _coerce_int(
        "progress_interval",
        settings.get("progress_interval", settings.get("progress_every", settings.get("log_every", 100))),
        minimum=0,
    )
    return {
        "strategy": strategy,
        "population_size": population_size,
        "max_generations": max_generations,
        "max_evaluations": max_evaluations,
        "p_best_fraction": p_best_fraction,
        "archive": archive,
        "F_min": f_min,
        "F_max": f_max,
        "F_initial": f_initial,
        "F_learning_rate": f_learning_rate,
        "CR_min": cr_min,
        "CR_max": cr_max,
        "CR_initial": cr_initial,
        "CR_learning_rate": cr_learning_rate,
        "bounds_handling": bounds_handling,
        "patience": patience,
        "min_delta_chi2": min_delta_chi2,
        "population_std_tol": population_std_tol,
        "local_refinement_enabled": local_refinement_enabled,
        "local_method": local_method,
        "local_n_elites": local_n_elites,
        "local_maxiter": local_maxiter,
        "adaptive_statistics": adaptive_statistics,
        "confidence_levels": confidence_levels,
        "elite_size": _coerce_int("elite_size", settings.get("elite_size", 10), minimum=1),
        "save_history": _coerce_bool("save_history", output_section.get("save_history", settings.get("save_history", True))),
        "save_population": _coerce_bool("save_population", output_section.get("save_population", settings.get("save_population", True))),
        "save_elites": _coerce_bool("save_elites", output_section.get("save_elites", settings.get("save_elites", True))),
        "progress_interval": progress_interval,
        "seed": int(settings.get("seed", seed)),
        "invalid_penalty": invalid_penalty,
    }


def _build_basin_scan_options(
    settings: dict[str, Any],
    *,
    seed: int,
    dimension: int,
    invalid_penalty: float,
) -> dict[str, Any]:
    exploration = _section(settings, "exploration")
    exploration_method = str(exploration.get("method", "latin_hypercube"))
    if exploration_method not in _BASIN_EXPLORATION_METHODS:
        raise ModelValidationError(
            "scan.basin_scan.exploration.method must be one of: "
            + ", ".join(sorted(_BASIN_EXPLORATION_METHODS))
        )
    n_points = _coerce_int("exploration.n_points", exploration.get("n_points", 50000), minimum=1)
    exploration_keep_fraction = _coerce_float(
        "exploration.keep_fraction",
        exploration.get("keep_fraction", 0.02),
        minimum=0.0,
    )
    if exploration_keep_fraction <= 0.0 or exploration_keep_fraction > 1.0:
        raise ModelValidationError("scan.basin_scan.exploration.keep_fraction must satisfy 0 < f <= 1.")

    selection = _section(settings, "selection")
    selection_options = _build_basin_selection_options(
        selection,
        prefix="selection",
        mode_default="top_fraction",
        top_fraction_default=exploration_keep_fraction,
        max_points_default=2000,
        chi2_window_default=0.0,
    )
    selection_mode = str(selection_options["mode"])
    top_fraction = float(selection_options["top_fraction"])
    max_points = int(selection_options["max_points"])
    chi2_window = float(selection_options["chi2_window"])
    near_miss = _section(selection, "near_miss")
    selection_options["near_miss"] = _build_near_miss_options(
        near_miss,
        prefix="selection.near_miss",
        invalid_penalty=invalid_penalty,
    )

    clustering = _section(settings, "clustering")
    clustering_enabled = _coerce_bool("clustering.enabled", clustering.get("enabled", True))
    clustering_method = str(clustering.get("method", "dbscan"))
    if clustering_method not in _BASIN_CLUSTERING_METHODS:
        raise ModelValidationError(
            "scan.basin_scan.clustering.method must be one of: "
            + ", ".join(sorted(_BASIN_CLUSTERING_METHODS))
        )
    eps_fraction = _coerce_float("clustering.eps_fraction", clustering.get("eps_fraction", 0.08), minimum=0.0)
    if eps_fraction <= 0.0:
        raise ModelValidationError("scan.basin_scan.clustering.eps_fraction must be > 0.")
    min_samples = _coerce_int("clustering.min_samples", clustering.get("min_samples", 10), minimum=1)
    max_clusters = _coerce_int("clustering.max_clusters", clustering.get("max_clusters", 8), minimum=1)

    boxes = _section(settings, "boxes")
    construction = str(boxes.get("construction", "quantile"))
    if construction not in _BASIN_BOX_CONSTRUCTION:
        raise ModelValidationError(
            "scan.basin_scan.boxes.construction must be one of: "
            + ", ".join(sorted(_BASIN_BOX_CONSTRUCTION))
        )
    q_low = _coerce_float("boxes.q_low", boxes.get("q_low", 0.05), minimum=0.0)
    q_high = _coerce_float("boxes.q_high", boxes.get("q_high", 0.95), minimum=0.0)
    if not (0.0 <= q_low < q_high <= 1.0):
        raise ModelValidationError("scan.basin_scan.boxes requires 0 <= q_low < q_high <= 1.")
    padding_fraction = _coerce_float("boxes.padding_fraction", boxes.get("padding_fraction", 0.25), minimum=0.0)
    min_width_fraction = _coerce_float("boxes.min_width_fraction", boxes.get("min_width_fraction", 0.02), minimum=0.0)
    if min_width_fraction > 1.0:
        raise ModelValidationError("scan.basin_scan.boxes.min_width_fraction must be <= 1.")
    clip_to_original_bounds = _coerce_bool(
        "boxes.clip_to_original_bounds",
        boxes.get("clip_to_original_bounds", True),
    )
    merge_overlapping = _coerce_bool(
        "boxes.merge_overlapping",
        boxes.get("merge_overlapping", False),
    )
    max_boxes = _coerce_int("boxes.max_boxes", boxes.get("max_boxes", 0), minimum=0)

    progressive = _section(settings, "progressive_exploration")
    progressive_enabled = _coerce_bool(
        "progressive_exploration.enabled",
        progressive.get("enabled", False),
    )
    progressive_options: dict[str, Any] = {"enabled": False}
    if progressive_enabled:
        n_rounds = _coerce_int(
            "progressive_exploration.n_rounds",
            progressive.get("n_rounds", 2),
            minimum=1,
        )
        raw_points = progressive.get("points_per_round", [n_points] * n_rounds)
        if not isinstance(raw_points, (list, tuple)):
            raise ModelValidationError("scan.basin_scan.progressive_exploration.points_per_round must be a list.")
        if len(raw_points) != n_rounds:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.points_per_round length must match n_rounds."
            )
        points_per_round = [
            _coerce_int(f"progressive_exploration.points_per_round[{index}]", item, minimum=1)
            for index, item in enumerate(raw_points)
        ]

        progressive_selection = _section(progressive, "selection")
        progressive_selection_options = _build_basin_selection_options(
            progressive_selection,
            prefix="progressive_exploration.selection",
            mode_default=selection_mode,
            top_fraction_default=top_fraction,
            max_points_default=max_points,
            chi2_window_default=chi2_window,
        )
        progressive_selection_options["near_miss"] = _build_near_miss_options(
            _section(progressive_selection, "near_miss"),
            prefix="progressive_exploration.selection.near_miss",
            invalid_penalty=invalid_penalty,
        )

        progressive_boxes = _section(progressive, "boxes")
        progressive_construction = str(progressive_boxes.get("construction", construction))
        if progressive_construction not in _BASIN_BOX_CONSTRUCTION:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.boxes.construction must be one of: "
                + ", ".join(sorted(_BASIN_BOX_CONSTRUCTION))
            )
        progressive_q_low = _coerce_float(
            "progressive_exploration.boxes.q_low",
            progressive_boxes.get("q_low", q_low),
            minimum=0.0,
        )
        progressive_q_high = _coerce_float(
            "progressive_exploration.boxes.q_high",
            progressive_boxes.get("q_high", q_high),
            minimum=0.0,
        )
        if not (0.0 <= progressive_q_low < progressive_q_high <= 1.0):
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.boxes requires 0 <= q_low < q_high <= 1."
            )
        progressive_padding_fraction = _coerce_float(
            "progressive_exploration.boxes.padding_fraction",
            progressive_boxes.get("padding_fraction", padding_fraction),
            minimum=0.0,
        )
        progressive_min_width_fraction = _coerce_float(
            "progressive_exploration.boxes.min_width_fraction",
            progressive_boxes.get("min_width_fraction", min_width_fraction),
            minimum=0.0,
        )
        if progressive_min_width_fraction > 1.0:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.boxes.min_width_fraction must be <= 1."
            )
        progressive_clip = _coerce_bool(
            "progressive_exploration.boxes.clip_to_original_bounds",
            progressive_boxes.get("clip_to_original_bounds", clip_to_original_bounds),
        )
        progressive_merge = _coerce_bool(
            "progressive_exploration.boxes.merge_overlapping",
            progressive_boxes.get("merge_overlapping", True),
        )
        progressive_max_boxes = _coerce_int(
            "progressive_exploration.boxes.max_boxes",
            progressive_boxes.get("max_boxes", max_clusters),
            minimum=1,
        )

        progressive_sampling = _section(progressive, "sampling")
        progressive_sampling_method = str(progressive_sampling.get("method", exploration_method))
        if progressive_sampling_method not in _BASIN_EXPLORATION_METHODS:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.sampling.method must be one of: "
                + ", ".join(sorted(_BASIN_EXPLORATION_METHODS))
            )
        allocation = str(progressive_sampling.get("allocate_points", "proportional_volume"))
        if allocation not in _BASIN_PROGRESSIVE_ALLOCATION:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.sampling.allocate_points must be one of: "
                + ", ".join(sorted(_BASIN_PROGRESSIVE_ALLOCATION))
            )
        min_points_per_box = _coerce_int(
            "progressive_exploration.sampling.min_points_per_box",
            progressive_sampling.get("min_points_per_box", 1),
            minimum=1,
        )
        fractions_section = _section(progressive_sampling, "fractions")
        mixed_fractions = {
            "elite_boxes": _coerce_float(
                "progressive_exploration.sampling.fractions.elite_boxes",
                fractions_section.get("elite_boxes", 0.5),
                minimum=0.0,
            ),
            "selected_boxes": _coerce_float(
                "progressive_exploration.sampling.fractions.selected_boxes",
                fractions_section.get("selected_boxes", 0.3),
                minimum=0.0,
            ),
            "global": _coerce_float(
                "progressive_exploration.sampling.fractions.global",
                fractions_section.get("global", 0.2),
                minimum=0.0,
            ),
        }
        if sum(mixed_fractions.values()) <= 0.0:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.sampling.fractions must sum to a positive value."
            )

        elite_preservation = _section(progressive, "elite_preservation")
        elite_preservation_enabled = _coerce_bool(
            "progressive_exploration.elite_preservation.enabled",
            elite_preservation.get("enabled", True),
        )
        archive_size = _coerce_int(
            "progressive_exploration.elite_preservation.archive_size",
            elite_preservation.get("archive_size", 500),
            minimum=1,
        )
        elite_fraction = _coerce_float(
            "progressive_exploration.elite_preservation.elite_fraction",
            elite_preservation.get("elite_fraction", 0.05),
            minimum=0.0,
        )
        if elite_fraction <= 0.0 or elite_fraction > 1.0:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.elite_preservation.elite_fraction must satisfy 0 < f <= 1."
            )
        min_elite_points = _coerce_int(
            "progressive_exploration.elite_preservation.min_elite_points",
            elite_preservation.get("min_elite_points", 20),
            minimum=1,
        )
        max_elite_points = _coerce_int(
            "progressive_exploration.elite_preservation.max_elite_points",
            elite_preservation.get("max_elite_points", 200),
            minimum=1,
        )
        if min_elite_points > max_elite_points:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.elite_preservation.min_elite_points must be <= max_elite_points."
            )

        elite_boxes_section = _section(progressive, "elite_boxes")
        elite_boxes_enabled = _coerce_bool(
            "progressive_exploration.elite_boxes.enabled",
            elite_boxes_section.get("enabled", True),
        )
        elite_box_construction = str(elite_boxes_section.get("construction", "quantile"))
        if elite_box_construction not in _BASIN_BOX_CONSTRUCTION:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.elite_boxes.construction must be one of: "
                + ", ".join(sorted(_BASIN_BOX_CONSTRUCTION))
            )
        elite_q_low = _coerce_float(
            "progressive_exploration.elite_boxes.q_low",
            elite_boxes_section.get("q_low", 0.05),
            minimum=0.0,
        )
        elite_q_high = _coerce_float(
            "progressive_exploration.elite_boxes.q_high",
            elite_boxes_section.get("q_high", 0.95),
            minimum=0.0,
        )
        if not (0.0 <= elite_q_low < elite_q_high <= 1.0):
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.elite_boxes requires 0 <= q_low < q_high <= 1."
            )
        elite_min_width = _coerce_float(
            "progressive_exploration.elite_boxes.min_width_fraction",
            elite_boxes_section.get("min_width_fraction", 0.01),
            minimum=0.0,
        )
        if elite_min_width > 1.0:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.elite_boxes.min_width_fraction must be <= 1."
            )

        best_centered = _section(progressive, "best_centered_box")
        best_centered_enabled = _coerce_bool(
            "progressive_exploration.best_centered_box.enabled",
            best_centered.get("enabled", True),
        )
        best_width_fraction = _coerce_float(
            "progressive_exploration.best_centered_box.width_fraction",
            best_centered.get("width_fraction", 0.15),
            minimum=0.0,
        )
        if best_width_fraction <= 0.0 or best_width_fraction > 1.0:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.best_centered_box.width_fraction must satisfy 0 < f <= 1."
            )
        best_shrink = _coerce_float(
            "progressive_exploration.best_centered_box.shrink_per_round",
            best_centered.get("shrink_per_round", 0.7),
            minimum=0.0,
        )
        if best_shrink <= 0.0 or best_shrink > 1.0:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.best_centered_box.shrink_per_round must satisfy 0 < f <= 1."
            )
        best_min_width = _coerce_float(
            "progressive_exploration.best_centered_box.min_width_fraction",
            best_centered.get("min_width_fraction", 0.005),
            minimum=0.0,
        )
        if best_min_width > 1.0:
            raise ModelValidationError(
                "scan.basin_scan.progressive_exploration.best_centered_box.min_width_fraction must be <= 1."
            )

        progressive_output = _section(progressive, "output")
        progressive_options = {
            "enabled": True,
            "n_rounds": n_rounds,
            "points_per_round": points_per_round,
            "combine_with_previous_selected": _coerce_bool(
                "progressive_exploration.combine_with_previous_selected",
                progressive.get("combine_with_previous_selected", True),
            ),
            "selection": progressive_selection_options,
            "boxes": {
                "construction": progressive_construction,
                "q_low": progressive_q_low,
                "q_high": progressive_q_high,
                "padding_fraction": progressive_padding_fraction,
                "min_width_fraction": progressive_min_width_fraction,
                "clip_to_original_bounds": progressive_clip,
                "merge_overlapping": progressive_merge,
                "max_boxes": progressive_max_boxes,
            },
            "sampling": {
                "method": progressive_sampling_method,
                "allocate_points": allocation,
                "min_points_per_box": min_points_per_box,
                "fractions": mixed_fractions,
            },
            "elite_preservation": {
                "enabled": elite_preservation_enabled,
                "always_keep_global_best": _coerce_bool(
                    "progressive_exploration.elite_preservation.always_keep_global_best",
                    elite_preservation.get("always_keep_global_best", True),
                ),
                "archive_size": archive_size,
                "elite_fraction": elite_fraction,
                "min_elite_points": min_elite_points,
                "max_elite_points": max_elite_points,
            },
            "elite_boxes": {
                "enabled": elite_boxes_enabled,
                "construction": elite_box_construction,
                "q_low": elite_q_low,
                "q_high": elite_q_high,
                "padding_fraction": _coerce_float(
                    "progressive_exploration.elite_boxes.padding_fraction",
                    elite_boxes_section.get("padding_fraction", 0.30),
                    minimum=0.0,
                ),
                "min_width_fraction": elite_min_width,
                "max_boxes": _coerce_int(
                    "progressive_exploration.elite_boxes.max_boxes",
                    elite_boxes_section.get("max_boxes", 4),
                    minimum=1,
                ),
            },
            "best_centered_box": {
                "enabled": best_centered_enabled,
                "width_fraction": best_width_fraction,
                "shrink_per_round": best_shrink,
                "min_width_fraction": best_min_width,
            },
            "output": {
                "save_round_points": _coerce_bool(
                    "progressive_exploration.output.save_round_points",
                    progressive_output.get("save_round_points", True),
                ),
                "save_round_selected": _coerce_bool(
                    "progressive_exploration.output.save_round_selected",
                    progressive_output.get("save_round_selected", True),
                ),
                "save_round_boxes": _coerce_bool(
                    "progressive_exploration.output.save_round_boxes",
                    progressive_output.get("save_round_boxes", True),
                ),
            },
        }

    focused_engine = _section(settings, "focused_engine")
    focused_name = str(focused_engine.get("name", focused_engine.get("engine", "adaptive_diver")))
    if focused_name == "adaptive_de":
        focused_name = "adaptive_diver"
    if focused_name != "adaptive_diver":
        raise ModelValidationError("basin_scan currently supports focused_engine.name = 'adaptive_diver' only.")
    focused_settings = {key: value for key, value in focused_engine.items() if key not in {"name", "engine"}}
    focused_settings.setdefault("population_size", 60)
    focused_settings.setdefault("max_generations", 1500)
    focused_settings.setdefault("p_best_fraction", 0.1)
    focused_settings.setdefault("archive", True)
    focused_settings.setdefault("invalid_penalty", invalid_penalty)
    focused_settings.setdefault("seed", seed)
    focused_settings.setdefault("verbose", 0)
    focused_settings.setdefault("save_invalid_points", False)
    focused_settings.setdefault("objective", settings.get("objective", settings.get("objective_mode", "nll")))
    focused_options = _build_adaptive_diver_options(
        focused_settings,
        seed=seed,
        dimension=dimension,
        invalid_penalty=invalid_penalty,
    )

    proposals = _section(settings, "proposals")
    guided_sampling = _section(settings, "guided_sampling")
    raw_proposal_stages = list(proposals.get("stages", []) or [])
    guided_stages = guided_sampling.get("stages", guided_sampling.get("proposals", []))
    if guided_stages:
        if not isinstance(guided_stages, list):
            raise ModelValidationError("scan.basin_scan.guided_sampling.stages must be a list.")
        default_apply_to = guided_sampling.get("apply_to", guided_sampling.get("stages_apply_to", None))
        normalized_guided_stages: list[dict[str, Any]] = []
        for index, raw_stage in enumerate(guided_stages):
            if not isinstance(raw_stage, dict):
                raise ModelValidationError(
                    f"scan.basin_scan.guided_sampling.stages[{index}] must be a mapping."
                )
            stage = dict(raw_stage)
            if default_apply_to is not None and "apply_to" not in stage:
                stage["apply_to"] = default_apply_to
            normalized_guided_stages.append(stage)
        raw_proposal_stages = [*normalized_guided_stages, *raw_proposal_stages]
    if not isinstance(raw_proposal_stages, list):
        raise ModelValidationError("scan.basin_scan.proposals.stages must be a list.")
    proposal_stages: list[dict[str, Any]] = []
    for index, raw_stage in enumerate(raw_proposal_stages):
        if not isinstance(raw_stage, dict):
            raise ModelValidationError(f"scan.basin_scan.proposals.stages[{index}] must be a mapping.")
        stage = dict(raw_stage)
        proposal_type = str(stage.get("type", ""))
        if proposal_type not in _BASIN_PROPOSAL_TYPES:
            raise ModelValidationError(
                f"scan.basin_scan.proposals.stages[{index}].type must be one of: "
                + ", ".join(sorted(_BASIN_PROPOSAL_TYPES))
            )
        probability = _coerce_float(
            f"proposals.stages[{index}].probability",
            stage.get("probability", 1.0),
            minimum=0.0,
        )
        if probability > 1.0:
            raise ModelValidationError(
                f"scan.basin_scan.proposals.stages[{index}].probability must be <= 1."
            )
        stage["name"] = str(stage.get("name", f"proposal_{index}"))
        stage["type"] = proposal_type
        stage["enabled"] = _coerce_bool(
            f"proposals.stages[{index}].enabled",
            stage.get("enabled", True),
        )
        stage["probability"] = probability
        if "apply_to" in stage:
            stage["apply_to"] = _coerce_string_list(
                f"proposals.stages[{index}].apply_to",
                stage["apply_to"],
            )
        proposal_stages.append(stage)

    staged = _section(settings, "staged_evaluation")
    cheap_stage = _section(staged, "cheap_stage")
    expensive_stage = _section(staged, "expensive_stage")
    full_eval_policy = _section(staged, "full_eval_policy")
    staged_options = {
        "enabled": _coerce_bool("staged_evaluation.enabled", staged.get("enabled", False)),
        "cheap_terms": _coerce_string_list(
            "staged_evaluation.cheap_stage.include_terms",
            cheap_stage.get("include_terms", []),
        ),
        "cheap_exclude_terms": _coerce_string_list(
            "staged_evaluation.cheap_stage.exclude_terms",
            cheap_stage.get("exclude_terms", []),
        ),
        "cheap_include_theory_checks": _coerce_string_list(
            "staged_evaluation.cheap_stage.include_theory_checks",
            cheap_stage.get("include_theory_checks", []),
        ),
        "cheap_exclude_theory_checks": _coerce_string_list(
            "staged_evaluation.cheap_stage.exclude_theory_checks",
            cheap_stage.get("exclude_theory_checks", []),
        ),
        "cheap_include_outputs": _coerce_string_list(
            "staged_evaluation.cheap_stage.include_outputs",
            cheap_stage.get("include_outputs", []),
        ),
        "cheap_exclude_outputs": _coerce_string_list(
            "staged_evaluation.cheap_stage.exclude_outputs",
            cheap_stage.get("exclude_outputs", []),
        ),
        "expensive_terms": _coerce_string_list(
            "staged_evaluation.expensive_stage.include_terms",
            expensive_stage.get("include_terms", []),
        ),
        "max_cheap_objective": _coerce_float(
            "staged_evaluation.full_eval_policy.max_cheap_objective",
            full_eval_policy.get("max_cheap_objective", invalid_penalty),
            minimum=0.0,
        ),
        "require_no_hard_failures": _coerce_bool(
            "staged_evaluation.full_eval_policy.require_no_hard_failures",
            full_eval_policy.get("require_no_hard_failures", True),
        ),
        "save_rejected_cheap_points": _coerce_bool(
            "staged_evaluation.save_rejected_cheap_points",
            staged.get("save_rejected_cheap_points", True),
        ),
        "save_full_eval_points": _coerce_bool(
            "staged_evaluation.save_full_eval_points",
            staged.get("save_full_eval_points", True),
        ),
    }

    refinement = _section(settings, "refinement")
    refinement_options = {
        "enabled": _coerce_bool("refinement.enabled", refinement.get("enabled", False)),
        "n_rounds": _coerce_int("refinement.n_rounds", refinement.get("n_rounds", 1), minimum=1),
        "points_per_seed": _coerce_int(
            "refinement.points_per_seed",
            refinement.get("points_per_seed", 10),
            minimum=1,
        ),
        "max_seeds": _coerce_int("refinement.max_seeds", refinement.get("max_seeds", 20), minimum=1),
        "seed_source": str(refinement.get("seed_source", "selected_plus_elite")),
        "jitter_fraction": _coerce_float(
            "refinement.jitter_fraction",
            refinement.get("jitter_fraction", 0.08),
            minimum=0.0,
        ),
        "apply_proposals": _coerce_bool(
            "refinement.apply_proposals",
            refinement.get("apply_proposals", True),
        ),
        "keep_near_miss": _coerce_bool(
            "refinement.keep_near_miss",
            refinement.get("keep_near_miss", True),
        ),
    }

    ml_focus = _section(settings, "ml_focus")
    ml_model = _section(ml_focus, "model")
    ml_training = _section(ml_focus, "training")
    ml_candidates = _section(ml_focus, "candidate_generation")
    ml_sources = _section(ml_candidates, "sources")
    ml_selection = _section(ml_focus, "selection")
    ml_box = _section(ml_focus, "focused_box")
    ml_seeds = _section(ml_focus, "seeds")
    ml_seed_composition = _section(ml_seeds, "composition")
    ml_local_mutation = _section(ml_seeds, "local_mutation")
    ml_focus_enabled = _coerce_bool("ml_focus.enabled", ml_focus.get("enabled", False))
    ml_model_type = str(ml_model.get("type", "extra_trees_regressor"))
    if ml_model_type != "extra_trees_regressor":
        raise ModelValidationError("scan.basin_scan.ml_focus.model.type currently supports only 'extra_trees_regressor'.")
    ml_target_transform = str(ml_training.get("target_transform", "log10_1p"))
    if ml_target_transform != "log10_1p":
        raise ModelValidationError("scan.basin_scan.ml_focus.training.target_transform currently supports only 'log10_1p'.")
    ml_top_fraction_raw = ml_training.get("top_fraction_for_training", None)
    ml_top_fraction = None if ml_top_fraction_raw is None else _coerce_float(
        "ml_focus.training.top_fraction_for_training",
        ml_top_fraction_raw,
        minimum=0.0,
    )
    if ml_top_fraction is not None and ml_top_fraction > 1.0:
        raise ModelValidationError("scan.basin_scan.ml_focus.training.top_fraction_for_training must be <= 1.")
    ml_source_fractions = {
        "selected_box_fraction": _coerce_float(
            "ml_focus.candidate_generation.sources.selected_box_fraction",
            ml_sources.get("selected_box_fraction", 0.50),
            minimum=0.0,
        ),
        "elite_local_fraction": _coerce_float(
            "ml_focus.candidate_generation.sources.elite_local_fraction",
            ml_sources.get("elite_local_fraction", 0.30),
            minimum=0.0,
        ),
        "global_fraction": _coerce_float(
            "ml_focus.candidate_generation.sources.global_fraction",
            ml_sources.get("global_fraction", 0.20),
            minimum=0.0,
        ),
    }
    if sum(ml_source_fractions.values()) <= 0.0:
        raise ModelValidationError("scan.basin_scan.ml_focus.candidate_generation.sources fractions must sum to > 0.")
    ml_seed_fractions = {
        "best_real_fraction": _coerce_float(
            "ml_focus.seeds.composition.best_real_fraction",
            ml_seed_composition.get("best_real_fraction", 0.40),
            minimum=0.0,
        ),
        "ml_selected_fraction": _coerce_float(
            "ml_focus.seeds.composition.ml_selected_fraction",
            ml_seed_composition.get("ml_selected_fraction", 0.40),
            minimum=0.0,
        ),
        "local_mutation_fraction": _coerce_float(
            "ml_focus.seeds.composition.local_mutation_fraction",
            ml_seed_composition.get("local_mutation_fraction", 0.20),
            minimum=0.0,
        ),
    }
    if sum(ml_seed_fractions.values()) <= 0.0:
        raise ModelValidationError("scan.basin_scan.ml_focus.seeds.composition fractions must sum to > 0.")
    ml_q_low = _coerce_float(
        "ml_focus.focused_box.quantile_low",
        ml_box.get("quantile_low", 0.02),
        minimum=0.0,
    )
    ml_q_high = _coerce_float(
        "ml_focus.focused_box.quantile_high",
        ml_box.get("quantile_high", 0.98),
        minimum=0.0,
    )
    if not (0.0 <= ml_q_low < ml_q_high <= 1.0):
        raise ModelValidationError("scan.basin_scan.ml_focus.focused_box requires 0 <= quantile_low < quantile_high <= 1.")
    ml_min_width_fraction = _coerce_float(
        "ml_focus.focused_box.min_width_fraction",
        ml_box.get("min_width_fraction", 0.05),
        minimum=0.0,
    )
    if ml_min_width_fraction > 1.0:
        raise ModelValidationError("scan.basin_scan.ml_focus.focused_box.min_width_fraction must be <= 1.")

    manifold = _section(settings, "manifold_refocus")
    manifold_box = _section(manifold, "box")
    manifold_sampling = _section(manifold, "sampling")
    manifold_enabled = _coerce_bool("manifold_refocus.enabled", manifold.get("enabled", False))
    manifold_method = str(manifold.get("method", "covariance"))
    if manifold_method not in {"covariance"}:
        raise ModelValidationError("scan.basin_scan.manifold_refocus.method currently supports only 'covariance'.")
    manifold_source = str(manifold.get("source", "selected"))
    if manifold_source not in {"selected", "exploration", "selected_plus_exploration"}:
        raise ModelValidationError(
            "scan.basin_scan.manifold_refocus.source must be one of: selected, exploration, selected_plus_exploration."
        )
    manifold_q_low = _coerce_float(
        "manifold_refocus.box.quantile_low",
        manifold_box.get("quantile_low", 0.02),
        minimum=0.0,
    )
    manifold_q_high = _coerce_float(
        "manifold_refocus.box.quantile_high",
        manifold_box.get("quantile_high", 0.98),
        minimum=0.0,
    )
    if not (0.0 <= manifold_q_low < manifold_q_high <= 1.0):
        raise ModelValidationError("scan.basin_scan.manifold_refocus.box requires 0 <= quantile_low < quantile_high <= 1.")
    manifold_min_width = _coerce_float(
        "manifold_refocus.box.min_width_fraction",
        manifold_box.get("min_width_fraction", 0.02),
        minimum=0.0,
    )
    if manifold_min_width > 1.0:
        raise ModelValidationError("scan.basin_scan.manifold_refocus.box.min_width_fraction must be <= 1.")

    output = _section(settings, "output")
    return {
        "seed": int(settings.get("seed", seed)),
        "invalid_penalty": invalid_penalty,
        "exploration": {
            "method": exploration_method,
            "n_points": n_points,
            "keep_fraction": exploration_keep_fraction,
        },
        "selection": selection_options,
        "clustering": {
            "enabled": clustering_enabled,
            "method": clustering_method,
            "eps_fraction": eps_fraction,
            "min_samples": min_samples,
            "max_clusters": max_clusters,
        },
        "boxes": {
            "construction": construction,
            "q_low": q_low,
            "q_high": q_high,
            "padding_fraction": padding_fraction,
            "min_width_fraction": min_width_fraction,
            "clip_to_original_bounds": clip_to_original_bounds,
            "merge_overlapping": merge_overlapping,
            "max_boxes": max_boxes,
        },
        "progressive_exploration": progressive_options,
        "proposals": {
            "enabled": (
                _coerce_bool("proposals.enabled", proposals.get("enabled", False))
                or _coerce_bool(
                    "guided_sampling.enabled",
                    guided_sampling.get("enabled", False),
                )
            ),
            "stages": proposal_stages,
        },
        "staged_evaluation": staged_options,
        "refinement": refinement_options,
        "ml_focus": {
            "enabled": ml_focus_enabled,
            "seed": int(ml_focus.get("seed", seed)),
            "model": {
                "type": ml_model_type,
                "n_estimators": _coerce_int(
                    "ml_focus.model.n_estimators",
                    ml_model.get("n_estimators", 300),
                    minimum=1,
                ),
                "min_samples_leaf": _coerce_int(
                    "ml_focus.model.min_samples_leaf",
                    ml_model.get("min_samples_leaf", 3),
                    minimum=1,
                ),
                "max_features": ml_model.get("max_features", "sqrt"),
            },
            "training": {
                "max_train_points": _coerce_int(
                    "ml_focus.training.max_train_points",
                    ml_training.get("max_train_points", 50000),
                    minimum=1,
                ),
                "min_train_points": _coerce_int(
                    "ml_focus.training.min_train_points",
                    ml_training.get("min_train_points", 100),
                    minimum=1,
                ),
                "require_valid": _coerce_bool(
                    "ml_focus.training.require_valid",
                    ml_training.get("require_valid", True),
                ),
                "finite_objective_only": _coerce_bool(
                    "ml_focus.training.finite_objective_only",
                    ml_training.get("finite_objective_only", True),
                ),
                "target_transform": ml_target_transform,
                "top_fraction_for_training": ml_top_fraction,
            },
            "candidate_generation": {
                "n_candidates": _coerce_int(
                    "ml_focus.candidate_generation.n_candidates",
                    ml_candidates.get("n_candidates", 100000),
                    minimum=1,
                ),
                "sources": ml_source_fractions,
            },
            "selection": {
                "n_ml_selected": _coerce_int(
                    "ml_focus.selection.n_ml_selected",
                    ml_selection.get("n_ml_selected", 5000),
                    minimum=1,
                ),
                "include_best_real_points": _coerce_bool(
                    "ml_focus.selection.include_best_real_points",
                    ml_selection.get("include_best_real_points", True),
                ),
                "n_best_real_points": _coerce_int(
                    "ml_focus.selection.n_best_real_points",
                    ml_selection.get("n_best_real_points", 500),
                    minimum=0,
                ),
                "include_elite_archive": _coerce_bool(
                    "ml_focus.selection.include_elite_archive",
                    ml_selection.get("include_elite_archive", True),
                ),
            },
            "focused_box": {
                "enabled": _coerce_bool("ml_focus.focused_box.enabled", ml_box.get("enabled", True)),
                "quantile_low": ml_q_low,
                "quantile_high": ml_q_high,
                "padding_fraction": _coerce_float(
                    "ml_focus.focused_box.padding_fraction",
                    ml_box.get("padding_fraction", 1.0),
                    minimum=0.0,
                ),
                "min_width_fraction": ml_min_width_fraction,
                "max_shrink_factor": _coerce_float(
                    "ml_focus.focused_box.max_shrink_factor",
                    ml_box.get("max_shrink_factor", 50.0),
                    minimum=1.0,
                ),
                "clip_to_original_bounds": _coerce_bool(
                    "ml_focus.focused_box.clip_to_original_bounds",
                    ml_box.get("clip_to_original_bounds", True),
                ),
            },
            "seeds": {
                "enabled": _coerce_bool("ml_focus.seeds.enabled", ml_seeds.get("enabled", True)),
                "max_seeds": _coerce_int("ml_focus.seeds.max_seeds", ml_seeds.get("max_seeds", 1000), minimum=1),
                "composition": ml_seed_fractions,
                "local_mutation": {
                    "relative_sigma": _coerce_float(
                        "ml_focus.seeds.local_mutation.relative_sigma",
                        ml_local_mutation.get("relative_sigma", 0.05),
                        minimum=0.0,
                    ),
                    "log_sigma": _coerce_float(
                        "ml_focus.seeds.local_mutation.log_sigma",
                        ml_local_mutation.get("log_sigma", 0.25),
                        minimum=0.0,
                    ),
                },
            },
        },
        "manifold_refocus": {
            "enabled": manifold_enabled,
            "method": manifold_method,
            "seed": int(manifold.get("seed", seed)),
            "source": manifold_source,
            "max_train_points": _coerce_int(
                "manifold_refocus.max_train_points",
                manifold.get("max_train_points", 5000),
                minimum=2,
            ),
            "min_train_points": _coerce_int(
                "manifold_refocus.min_train_points",
                manifold.get("min_train_points", 20),
                minimum=2,
            ),
            "top_fraction_for_training": _coerce_float(
                "manifold_refocus.top_fraction_for_training",
                manifold.get("top_fraction_for_training", 1.0),
                minimum=0.0,
            ),
            "n_candidates": _coerce_int(
                "manifold_refocus.sampling.n_candidates",
                manifold_sampling.get("n_candidates", 50000),
                minimum=1,
            ),
            "inflate": _coerce_float(
                "manifold_refocus.sampling.inflate",
                manifold_sampling.get("inflate", 1.5),
                minimum=0.0,
            ),
            "diagonal_jitter": _coerce_float(
                "manifold_refocus.sampling.diagonal_jitter",
                manifold_sampling.get("diagonal_jitter", 1.0e-6),
                minimum=0.0,
            ),
            "include_training_points": _coerce_bool(
                "manifold_refocus.sampling.include_training_points",
                manifold_sampling.get("include_training_points", True),
            ),
            "box": {
                "enabled": _coerce_bool("manifold_refocus.box.enabled", manifold_box.get("enabled", True)),
                "quantile_low": manifold_q_low,
                "quantile_high": manifold_q_high,
                "padding_fraction": _coerce_float(
                    "manifold_refocus.box.padding_fraction",
                    manifold_box.get("padding_fraction", 0.35),
                    minimum=0.0,
                ),
                "min_width_fraction": manifold_min_width,
                "max_shrink_factor": _coerce_float(
                    "manifold_refocus.box.max_shrink_factor",
                    manifold_box.get("max_shrink_factor", 100.0),
                    minimum=1.0,
                ),
                "clip_to_original_bounds": _coerce_bool(
                    "manifold_refocus.box.clip_to_original_bounds",
                    manifold_box.get("clip_to_original_bounds", True),
                ),
            },
        },
        "focused_engine": {
            "name": focused_name,
            "settings": focused_settings,
            "options": focused_options,
        },
        "output": {
            "save_exploration_points": _coerce_bool(
                "output.save_exploration_points",
                output.get("save_exploration_points", True),
            ),
            "save_selected_points": _coerce_bool(
                "output.save_selected_points",
                output.get("save_selected_points", True),
            ),
            "save_clusters": _coerce_bool("output.save_clusters", output.get("save_clusters", True)),
            "save_focused_boxes": _coerce_bool(
                "output.save_focused_boxes",
                output.get("save_focused_boxes", True),
            ),
        },
        "progress_interval": _coerce_int(
            "progress_interval",
            settings.get("progress_interval", settings.get("progress_every", settings.get("log_every", 1000))),
            minimum=0,
        ),
    }


@dataclass(slots=True)
class ScanParameterSpec:
    name: str
    index: int
    lower: float
    upper: float
    prior: str
    default: float | None
    min_abs: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "index": self.index,
            "lower": self.lower,
            "upper": self.upper,
            "prior": self.prior,
            "default": self.default,
            "min_abs": self.min_abs,
        }


@dataclass(slots=True)
class FixedParameterSpec:
    name: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value}


@dataclass(slots=True)
class ScanRequest:
    engine: str
    run_directory: str
    model_name: str
    model_version: str
    framework_version: str
    run_id: str
    timestamp_utc: str
    objective_mode: str
    maximize: bool
    save_invalid_points: bool
    seed: int
    save_every: int
    invalid_objective: float
    max_evaluations: int
    max_init_attempts: int
    population_size: int
    max_generations: int
    convergence_threshold: float
    convergence_steps: int
    verbose: int
    scanned_parameters: list[ScanParameterSpec]
    fixed_parameters: list[FixedParameterSpec]
    selected_outputs: list[str]
    likelihood_names: list[str]
    parameter_order: list[str]
    raw_settings: dict[str, str]
    engine_options: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "run_directory": self.run_directory,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "framework_version": self.framework_version,
            "run_id": self.run_id,
            "timestamp_utc": self.timestamp_utc,
            "objective_mode": self.objective_mode,
            "maximize": self.maximize,
            "save_invalid_points": self.save_invalid_points,
            "seed": self.seed,
            "save_every": self.save_every,
            "invalid_objective": self.invalid_objective,
            "max_evaluations": self.max_evaluations,
            "max_init_attempts": self.max_init_attempts,
            "population_size": self.population_size,
            "max_generations": self.max_generations,
            "convergence_threshold": self.convergence_threshold,
            "convergence_steps": self.convergence_steps,
            "verbose": self.verbose,
            "scanned_parameters": [item.to_dict() for item in self.scanned_parameters],
            "fixed_parameters": [item.to_dict() for item in self.fixed_parameters],
            "selected_outputs": list(self.selected_outputs),
            "likelihood_names": list(self.likelihood_names),
            "parameter_order": list(self.parameter_order),
            "raw_settings": dict(self.raw_settings),
            "engine_options": _json_ready(self.engine_options),
        }


@dataclass(slots=True)
class ScanResults:
    run_directory: Path
    points_path: Path
    metadata_path: Path
    best_fit_path: Path
    summary_path: Path
    summary: dict[str, Any]
    statistics_directory: Path | None = None

    @classmethod
    def from_native_result(cls, payload: dict[str, Any]) -> "ScanResults":
        return cls(
            run_directory=Path(payload["run_directory"]),
            points_path=Path(payload["points_path"]),
            metadata_path=Path(payload["metadata_path"]),
            best_fit_path=Path(payload["best_fit_path"]),
            summary_path=Path(payload["summary_path"]),
            summary=payload["summary"],
            statistics_directory=None,
        )


def build_scan_request(
    model: ModelDefinition,
    compiled: "CompiledModel",
    *,
    run_directory: str | Path | None = None,
    run_id: str | None = None,
    timestamp_utc: str | None = None,
) -> ScanRequest:
    plan_scan = dict(compiled.plan.scan)

    engine = str(plan_scan.get("engine", model.scan.engine))
    if engine == "adaptive_de":
        engine = "adaptive_diver"

    settings = dict(plan_scan.get("settings", model.scan.settings))
    if engine == "adaptive_diver":
        settings.update(dict(plan_scan.get("adaptive_diver", getattr(model.scan, "adaptive_diver", {}))))
    elif engine == "basin_scan":
        settings.update(dict(plan_scan.get("basin_scan", getattr(model.scan, "basin_scan", {}))))
        guided_sampling = dict(getattr(model, "guided_sampling", {}) or {})
        if guided_sampling:
            existing_guided = settings.get("guided_sampling")
            if isinstance(existing_guided, dict):
                merged_guided = {**guided_sampling, **existing_guided}
                if "stages" in guided_sampling or "proposals" in guided_sampling:
                    base_stages = guided_sampling.get("stages", guided_sampling.get("proposals", []))
                    override_stages = existing_guided.get("stages", existing_guided.get("proposals", []))
                    if base_stages or override_stages:
                        merged_guided["stages"] = [*list(base_stages or []), *list(override_stages or [])]
                settings["guided_sampling"] = merged_guided
            else:
                settings["guided_sampling"] = guided_sampling

    unknown_settings = sorted(key for key in settings if key not in _SCAN_SETTING_ALIASES)
    if unknown_settings:
        joined = ", ".join(unknown_settings)
        raise ModelValidationError(
            "Unsupported scan.settings entries: "
            f"{joined}. Move non-runtime metadata out of scan.settings and keep only execution controls."
        )
    objective_mode = str(settings.get("objective", settings.get("objective_mode", "nll")))
    maximize = bool(settings.get("maximize", False))
    save_invalid_points = bool(settings.get("save_invalid_points", False))
    invalid_objective = float(settings.get("invalid_penalty", settings.get("invalid_objective", 1.0e300)))
    max_evaluations = _coerce_optional_int("max_evaluations", settings.get("max_evaluations", 0), minimum=0)
    max_generations = int(settings.get("maxiter", settings.get("max_generations", settings.get("maxgen", 0))))
    population_size = int(settings.get("popsize", settings.get("population_size", settings.get("NP", 0))))
    convergence_threshold = float(settings.get("convergence_threshold", settings.get("convthresh", 1.0e-3)))
    convergence_steps = int(settings.get("convergence_steps", settings.get("convsteps", 20)))
    max_init_attempts = int(settings.get("max_init_attempts", 30000))
    verbose = int(settings.get("verbose", 1))

    if engine not in {"diver", "serial_random", "de_scipy", "adaptive_diver", "basin_scan"}:
        raise ModelValidationError(
            f"Unsupported scan engine '{engine}'. Supported engines are 'diver', 'serial_random', 'de_scipy', 'adaptive_diver', and 'basin_scan'."
        )

    if engine == "serial_random" and max_evaluations <= 0:
        raise ModelValidationError("serial_random scans require settings.max_evaluations > 0.")

    if engine == "diver" and max_generations <= 0 and max_evaluations <= 0:
        raise ModelValidationError(
            "diver scans require settings.max_generations or settings.max_evaluations."
        )

    scanned_parameters: list[ScanParameterSpec] = []
    fixed_parameters: list[FixedParameterSpec] = []
    parameter_order: list[str] = []

    for parameter in model.parameters:
        parameter_order.append(parameter.name)

        if parameter.scan:
            if parameter.value_type != ValueType.REAL:
                raise ModelValidationError(
                    f"Scanned parameter '{parameter.name}' must currently be a real scalar."
                )
            assert parameter.lower is not None and parameter.upper is not None
            if parameter.prior.value == "log" and parameter.lower <= 0:
                raise ModelValidationError(
                    f"Log prior for '{parameter.name}' requires a strictly positive lower bound."
                )
            if parameter.prior.value == "signed_log":
                min_abs = 1.0e-12 if parameter.min_abs is None else float(parameter.min_abs)
                if not (parameter.lower < 0.0 < parameter.upper):
                    raise ModelValidationError(
                        f"Signed-log prior for '{parameter.name}' requires bounds that straddle zero."
                    )
                if min_abs <= 0.0 or min_abs >= max(abs(float(parameter.lower)), abs(float(parameter.upper))):
                    raise ModelValidationError(
                        f"Signed-log prior for '{parameter.name}' requires 0 < min_abs < max(abs(lower), abs(upper))."
                    )
            scanned_parameters.append(
                ScanParameterSpec(
                    name=parameter.name,
                    index=len(scanned_parameters),
                    lower=float(parameter.lower),
                    upper=float(parameter.upper),
                    prior=parameter.prior.value,
                    default=float(parameter.default) if parameter.default is not None else None,
                    min_abs=float(parameter.min_abs) if parameter.min_abs is not None else None,
                )
            )
        else:
            fixed_parameters.append(
                FixedParameterSpec(name=parameter.name, value=parameter.default)
            )

    if not scanned_parameters:
        raise ModelValidationError("The scan configuration requires at least one scanned parameter.")

    seed = int(settings.get("seed", plan_scan.get("seed", model.scan.seed)))
    engine_options: dict[str, Any] = {}
    if engine == "de_scipy":
        engine_options = _build_de_scipy_options(
            settings,
            seed=seed,
            dimension=len(scanned_parameters),
            invalid_penalty=invalid_objective,
        )
    elif engine == "adaptive_diver":
        engine_options = _build_adaptive_diver_options(
            settings,
            seed=seed,
            dimension=len(scanned_parameters),
            invalid_penalty=invalid_objective,
        )
    elif engine == "basin_scan":
        engine_options = _build_basin_scan_options(
            settings,
            seed=seed,
            dimension=len(scanned_parameters),
            invalid_penalty=invalid_objective,
        )

    likelihood_names = [
        node["name"]
        for node in compiled.plan.nodes
        if node["kind"] == "constraint"
    ]

    actual_run_id = run_id or f"{model.metadata.name}-{uuid.uuid4().hex[:12]}"
    actual_timestamp = timestamp_utc or datetime.now(timezone.utc).isoformat()
    resolved_run_dir = Path(run_directory or Path.cwd() / "runs" / actual_run_id).resolve()

    return ScanRequest(
        engine=engine,
        run_directory=str(resolved_run_dir),
        model_name=model.metadata.name,
        model_version=model.metadata.version,
        framework_version="0.1.0",
        run_id=actual_run_id,
        timestamp_utc=actual_timestamp,
        objective_mode=objective_mode,
        maximize=maximize,
        save_invalid_points=save_invalid_points,
        seed=seed,
        save_every=int(plan_scan.get("save_every", model.scan.save_every)),
        invalid_objective=invalid_objective,
        max_evaluations=max_evaluations,
        max_init_attempts=max_init_attempts,
        population_size=population_size,
        max_generations=max_generations,
        convergence_threshold=convergence_threshold,
        convergence_steps=convergence_steps,
        verbose=verbose,
        scanned_parameters=scanned_parameters,
        fixed_parameters=fixed_parameters,
        selected_outputs=list(compiled.plan.saved_outputs),
        likelihood_names=likelihood_names,
        parameter_order=parameter_order,
        raw_settings={key: _stringify_setting(value) for key, value in settings.items()},
        engine_options=engine_options,
    )


class _PythonScanArtifactsWriter:
    def __init__(self, request: ScanRequest):
        self.request = request
        self.run_directory = Path(request.run_directory)
        self.run_directory.mkdir(parents=True, exist_ok=True)
        self.points_path = self.run_directory / "points.csv"
        self.metadata_path = self.run_directory / "metadata.json"
        self.best_fit_path = self.run_directory / "best_fit.json"
        self.summary_path = self.run_directory / "summary.json"
        self.history_path = self.run_directory / "history.json"
        self._stream = self.points_path.open("w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._stream)
        self._writer.writerow(
            [
                "evaluation",
                "status",
                "valid",
                "failure_reason",
                "scanner_target",
                "metric_value",
                "total_nll",
                *[f"param::{item.name}" for item in self.request.scanned_parameters],
                *[f"output::{item}" for item in self.request.selected_outputs],
                *_likelihood_component_columns(self.request),
                *[f"likelihood::{item}" for item in self.request.likelihood_names],
            ]
        )
        self.write_metadata()

    def write_metadata(self) -> None:
        payload = {
            "model_name": self.request.model_name,
            "model_version": self.request.model_version,
            "framework_version": self.request.framework_version,
            "run_id": self.request.run_id,
            "timestamp_utc": self.request.timestamp_utc,
            "engine": self.request.engine,
            "objective_mode": self.request.objective_mode,
            "maximize": self.request.maximize,
            "seed": self.request.seed,
            "save_every": self.request.save_every,
            "parameter_order": list(self.request.parameter_order),
            "scanned_parameters": [item.to_dict() for item in self.request.scanned_parameters],
            "fixed_parameters": [item.to_dict() for item in self.request.fixed_parameters],
            "selected_outputs": list(self.request.selected_outputs),
            "likelihood_terms": list(self.request.likelihood_names),
            "point_component_columns": _likelihood_component_columns(self.request),
            "raw_settings": dict(sorted(self.request.raw_settings.items())),
            "engine_options": _json_ready(self.request.engine_options),
            "history_path": "history.json",
        }
        self.metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def write_point(self, evaluation_id: int, record: dict[str, Any]) -> None:
        point_result = record["point_result"]
        outputs = point_result.get("outputs", {})
        likelihood_terms = point_result.get("likelihood_terms", {})
        self._writer.writerow(
            [
                evaluation_id,
                point_result.get("status", ""),
                "true" if record.get("valid", False) else "false",
                point_result.get("failure_reason", ""),
                record.get("scanner_target", self.request.invalid_objective),
                record.get("metric_value", self.request.invalid_objective),
                point_result.get("total_nll", self.request.invalid_objective),
                *record.get("scanned_values", []),
                *[_csv_ready(outputs.get(name)) for name in self.request.selected_outputs],
                *[likelihood_terms.get(name, "") for name in self.request.likelihood_names],
                *[likelihood_terms.get(name, "") for name in self.request.likelihood_names],
            ]
        )

    def write_best_fit(self, best_record: dict[str, Any] | None) -> None:
        if best_record is None:
            payload = {"has_best_point": False}
        else:
            payload = {
                "has_best_point": True,
                "best_metric_value": best_record["metric_value"],
                "best_scanner_target": best_record["scanner_target"],
                "parameters": {
                    item.name: value
                    for item, value in zip(self.request.scanned_parameters, best_record["scanned_values"], strict=True)
                },
                "outputs": _json_ready(best_record["point_result"].get("outputs", {})),
                "likelihood_terms": _json_ready(best_record["point_result"].get("likelihood_terms", {})),
            }
        self.best_fit_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def write_summary(
        self,
        *,
        evaluations: int,
        saved_points: int,
        valid_points: int,
        interrupted: bool,
        best_record: dict[str, Any] | None,
        failure_counters: Counter[str],
        failure_reasons: Counter[str],
        engine_details: dict[str, Any],
    ) -> None:
        payload = {
            "evaluations": evaluations,
            "saved_points": saved_points,
            "valid_points": valid_points,
            "interrupted": interrupted,
            "has_best_point": best_record is not None,
            "best_metric_value": best_record["metric_value"] if best_record is not None else self.request.invalid_objective,
            "best_scanner_target": best_record["scanner_target"] if best_record is not None else self.request.invalid_objective,
            "failure_counters": {
                "ok": failure_counters.get("ok", 0),
                "missing_input": failure_counters.get("missing_input", 0),
                "invalid_point": failure_counters.get("invalid_point", 0),
                "numerical_error": failure_counters.get("numerical_error", 0),
                "evaluation_error": failure_counters.get("evaluation_error", 0),
                "non_finite_objective": failure_counters.get("non_finite_objective", 0),
            },
            "failure_reasons": dict(sorted(failure_reasons.items())),
            "engine_details": _json_ready(engine_details),
        }
        self.summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def write_history(self, history: list[dict[str, Any]]) -> None:
        self.history_path.write_text(json.dumps(_json_ready(history), indent=2), encoding="utf-8")

    def flush(self) -> None:
        self._stream.flush()

    def close(self) -> None:
        self.flush()
        self._stream.close()


class _ScipyDEObjective:
    def __init__(self, compiled: "CompiledModel", request: ScanRequest, writer: _PythonScanArtifactsWriter):
        if _core is None or not hasattr(_core, "evaluate_scan_point"):
            raise RuntimeError(
                "The native scan-point adapter is not available. Rebuild the extension with scan support enabled."
            )
        self._compiled = compiled
        self._request = request
        self._writer = writer
        self._plan_dict = compiled.plan.to_dict()
        self._request_dict = request.to_dict()
        self._request_dict["engine"] = "serial_random"
        self.evaluations = 0
        self.saved_points = 0
        self.valid_points = 0
        self.best_record: dict[str, Any] | None = None
        self.failure_counters: Counter[str] = Counter()
        self.failure_reasons: Counter[str] = Counter()
        self.history: list[dict[str, Any]] = []
        self._progress_interval = int(request.engine_options.get("progress_interval", 100))

    def _synthetic_error_record(self, point: list[float], exc: Exception) -> dict[str, Any]:
        message = f"de_scipy objective evaluation failed: {exc}"
        return {
            "metric_value": self._request.invalid_objective,
            "scanner_target": self._request.invalid_objective,
            "valid": False,
            "scanned_values": list(point),
            "point_result": {
                "status": "evaluation_error",
                "failure_reason": message,
                "total_nll": self._request.invalid_objective,
                "likelihood_terms": {},
                "outputs": {},
                "flags": [],
            },
        }

    def evaluate(self, point: list[float]) -> float:
        try:
            record = _core.evaluate_scan_point(self._plan_dict, self._request_dict, list(point))
        except Exception as exc:
            record = self._synthetic_error_record(list(point), exc)

        self.evaluations += 1
        status = record["point_result"]["status"]
        self.failure_counters[status] += 1
        if not record["valid"] and status == "ok":
            self.failure_counters["invalid_point"] += 1
        if not isfinite(record["metric_value"]):
            self.failure_counters["non_finite_objective"] += 1
        reason = record["point_result"].get("failure_reason", "")
        if reason:
            self.failure_reasons[reason] += 1

        if record["valid"]:
            self.valid_points += 1
            if self.best_record is None or record["scanner_target"] < self.best_record["scanner_target"]:
                self.best_record = record

        if record["valid"] or self._request.save_invalid_points:
            self._writer.write_point(self.evaluations, record)
            self.saved_points += 1

        if self._request.save_every > 0 and self.evaluations % self._request.save_every == 0:
            self._writer.flush()

        return float(record["scanner_target"])

    def callback(self, *args: Any, **kwargs: Any) -> bool:
        # SciPy calls this callback once per completed DE generation. Keep the
        # stored iteration one-based so it matches user-facing progress logs.
        iteration = len(self.history) + 1
        best_vector: list[float] | None = None
        convergence = None
        if "intermediate_result" in kwargs:
            result = kwargs["intermediate_result"]
            best_vector = getattr(result, "x", None)
            convergence = getattr(result, "convergence", None)
        else:
            if args:
                best_vector = args[0]
            if len(args) > 1:
                convergence = args[1]
        if hasattr(best_vector, "tolist"):
            best_vector = best_vector.tolist()
        self.history.append(
            {
                "iteration": iteration,
                "best_scanner_target": None if self.best_record is None else self.best_record["scanner_target"],
                "best_metric_value": None if self.best_record is None else self.best_record["metric_value"],
                "best_parameters": best_vector,
                "convergence": convergence,
                "evaluations": self.evaluations,
            }
        )
        self.report_progress(iteration=iteration, convergence=convergence)
        return False

    def _best_parameter_map(self) -> dict[str, float]:
        if self.best_record is None:
            return {}
        return {
            item.name: float(value)
            for item, value in zip(
                self._request.scanned_parameters,
                self.best_record["scanned_values"],
                strict=True,
            )
        }

    def report_progress(self, *, iteration: int | None, convergence: Any = None, force: bool = False) -> None:
        if self._request.verbose <= 0:
            return
        if not force:
            if self._progress_interval <= 0 or iteration is None:
                return
            if iteration % self._progress_interval != 0:
                return

        stage = "generation" if iteration is not None else "final"
        label = f"{stage}={iteration}" if iteration is not None else "final"
        best_target = None if self.best_record is None else self.best_record["scanner_target"]
        best_metric = None if self.best_record is None else self.best_record["metric_value"]
        fields = [
            f"[de_scipy] {label}",
            f"evaluations={self.evaluations}",
            f"valid={self.valid_points}",
            f"saved={self.saved_points}",
        ]
        if best_target is not None:
            fields.append(f"best_target={best_target:.12g}")
        if best_metric is not None:
            fields.append(f"best_metric={best_metric:.12g}")
        if convergence is not None:
            fields.append(f"convergence={convergence}")
        parameters = self._best_parameter_map()
        if parameters:
            formatted = ", ".join(f"{name}={value:.8g}" for name, value in parameters.items())
            fields.append(f"best_parameters={{ {formatted} }}")
        print(" | ".join(fields), flush=True)


class _AdaptiveDiverObjective:
    def __init__(self, compiled: "CompiledModel", request: ScanRequest, writer: _PythonScanArtifactsWriter):
        if _core is None or not hasattr(_core, "evaluate_scan_point"):
            raise RuntimeError(
                "The native scan-point adapter is not available. Rebuild the extension with scan support enabled."
            )
        self._compiled = compiled
        self._request = request
        self._writer = writer
        self._plan_dict = compiled.plan.to_dict()
        self._request_dict = request.to_dict()
        self._request_dict["engine"] = "serial_random"
        self.evaluations = 0
        self.saved_points = 0
        self.valid_points = 0
        self.best_record: dict[str, Any] | None = None
        self.failure_counters: Counter[str] = Counter()
        self.failure_reasons: Counter[str] = Counter()

    def _synthetic_error_record(self, point: list[float], exc: Exception) -> dict[str, Any]:
        message = f"adaptive_diver objective evaluation failed: {exc}"
        return {
            "metric_value": self._request.invalid_objective,
            "scanner_target": self._request.invalid_objective,
            "valid": False,
            "scanned_values": list(point),
            "point_result": {
                "status": "evaluation_error",
                "valid": False,
                "failure_reason": message,
                "total_nll": self._request.invalid_objective,
                "likelihood_terms": {},
                "outputs": {},
                "flags": [],
            },
        }

    def _normalise_record(self, record: dict[str, Any]) -> dict[str, Any]:
        if not isfinite(float(record.get("scanner_target", self._request.invalid_objective))):
            record["scanner_target"] = self._request.invalid_objective
            record["metric_value"] = self._request.invalid_objective
            record["valid"] = False
            point_result = record.setdefault("point_result", {})
            point_result["status"] = point_result.get("status", "ok")
            point_result["valid"] = False
            point_result["failure_reason"] = point_result.get("failure_reason") or "non_finite_objective"
        return record

    def record_evaluation(
        self,
        record: dict[str, Any],
        *,
        write: bool = True,
        count_valid: bool = True,
        count_best: bool = True,
    ) -> dict[str, Any]:
        record = self._normalise_record(record)
        self.evaluations += 1
        status = record["point_result"].get("status", "")
        self.failure_counters[status] += 1
        if not record.get("valid", False) and status == "ok":
            self.failure_counters["invalid_point"] += 1
        if not isfinite(float(record.get("metric_value", self._request.invalid_objective))):
            self.failure_counters["non_finite_objective"] += 1
        reason = record["point_result"].get("failure_reason", "")
        if reason:
            self.failure_reasons[reason] += 1

        if count_valid and record.get("valid", False):
            self.valid_points += 1
            if count_best and (
                self.best_record is None or record["scanner_target"] < self.best_record["scanner_target"]
            ):
                self.best_record = record

        if write and (record.get("valid", False) or self._request.save_invalid_points):
            self._writer.write_point(self.evaluations, record)
            self.saved_points += 1

        if self._request.save_every > 0 and self.evaluations % self._request.save_every == 0:
            self._writer.flush()

        return record

    def evaluate(self, point: np.ndarray | list[float], *, write: bool = True) -> dict[str, Any]:
        values = [float(item) for item in point]
        try:
            record = _core.evaluate_scan_point(self._plan_dict, self._request_dict, values)
        except Exception as exc:
            record = self._synthetic_error_record(values, exc)
        return self.record_evaluation(record, write=write)


def _likelihood_component_columns(request: ScanRequest) -> list[str]:
    return [f"like__{item}" for item in request.likelihood_names]


def _record_likelihood_terms(record: dict[str, Any]) -> dict[str, Any]:
    point_result = record.get("point_result", {})
    terms = point_result.get("likelihood_terms", {})
    return terms if isinstance(terms, dict) else {}


def _add_likelihood_components(row: dict[str, Any], record: dict[str, Any], request: ScanRequest) -> None:
    terms = _record_likelihood_terms(record)
    for name in request.likelihood_names:
        row[f"like__{name}"] = terms.get(name, "")


def _record_target(record: dict[str, Any], invalid_objective: float) -> float:
    try:
        value = float(record.get("scanner_target", invalid_objective))
    except Exception:
        return invalid_objective
    return value if isfinite(value) else invalid_objective


def _coerce_sort_target(value: Any, invalid_objective: float) -> float:
    if value is None:
        return invalid_objective
    try:
        numeric = float(value)
    except Exception:
        return invalid_objective
    return numeric if isfinite(numeric) else invalid_objective


def _parameter_min_abs(parameter: ScanParameterSpec) -> float:
    return 1.0e-12 if parameter.min_abs is None else float(parameter.min_abs)


def _signed_log_from_unit(unit: np.ndarray | float, lower: float, upper: float, min_abs: float) -> np.ndarray | float:
    if min_abs <= 0.0:
        raise ModelValidationError("Signed-log sampling requires min_abs > 0.")
    neg_min = max(min_abs, abs(min(upper, 0.0)))
    neg_max = abs(lower) if lower < -min_abs else 0.0
    pos_min = max(min_abs, max(lower, 0.0))
    pos_max = upper if upper > min_abs else 0.0
    neg_span = np.log(neg_max / neg_min) if neg_max > neg_min else 0.0
    pos_span = np.log(pos_max / pos_min) if pos_max > pos_min else 0.0
    total_span = neg_span + pos_span
    if not (total_span > 0.0) or not np.isfinite(total_span):
        raise ModelValidationError("Signed-log sampling has no nonzero logarithmic support.")

    u = np.asarray(unit, dtype=float)
    cutoff = neg_span / total_span
    out = np.empty_like(u, dtype=float)
    neg_mask = u < cutoff
    if neg_span > 0.0:
        local = np.where(cutoff > 0.0, u / cutoff, 0.0)
        # Negative values run from the more negative bound toward zero as u increases.
        out[neg_mask] = -np.exp(np.log(neg_max) - local[neg_mask] * neg_span)
    if pos_span > 0.0:
        local = np.where(cutoff < 1.0, (u - cutoff) / (1.0 - cutoff), 0.0)
        out[~neg_mask] = np.exp(np.log(pos_min) + local[~neg_mask] * pos_span)
    if np.isscalar(unit):
        return float(out)
    return out


def _sample_parameter_from_unit(unit: np.ndarray | float, parameter: ScanParameterSpec) -> np.ndarray | float:
    return _sample_parameter_bounds_from_unit(unit, parameter, parameter.lower, parameter.upper)


def _sample_parameter_bounds_from_unit(
    unit: np.ndarray | float,
    parameter: ScanParameterSpec,
    lower: float,
    upper: float,
) -> np.ndarray | float:
    if parameter.prior == "log":
        if lower <= 0.0 or upper <= 0.0:
            raise ModelValidationError("Log prior sampling requires strictly positive bounds.")
        u = np.asarray(unit, dtype=float)
        out = np.exp(np.log(lower) + u * (np.log(upper) - np.log(lower)))
        return float(out) if np.isscalar(unit) else out
    if parameter.prior == "signed_log":
        return _signed_log_from_unit(unit, lower, upper, _parameter_min_abs(parameter))
    u = np.asarray(unit, dtype=float)
    out = lower + u * (upper - lower)
    return float(out) if np.isscalar(unit) else out


def _scale_unit_points(
    unit: np.ndarray,
    parameters: Sequence[ScanParameterSpec],
    lower: np.ndarray,
    upper: np.ndarray,
) -> np.ndarray:
    points = np.empty_like(unit, dtype=float)
    for index, parameter in enumerate(parameters):
        points[:, index] = _sample_parameter_bounds_from_unit(
            unit[:, index],
            parameter,
            float(lower[index]),
            float(upper[index]),
        )
    return points


def _sample_prior_points(
    *,
    n_points: int,
    parameters: Sequence[ScanParameterSpec],
    seed: int,
    method: str = "random",
) -> np.ndarray:
    dimension = len(parameters)
    if n_points <= 0:
        return np.empty((0, dimension), dtype=float)
    unit: np.ndarray
    if method in {"latin_hypercube", "sobol"}:
        try:
            qmc = importlib.import_module("scipy.stats.qmc")
            sampler = qmc.Sobol(d=dimension, scramble=True, seed=seed) if method == "sobol" else qmc.LatinHypercube(d=dimension, seed=seed)
            unit = np.asarray(sampler.random(n_points), dtype=float)
        except Exception:
            unit = np.random.default_rng(seed).random((n_points, dimension))
    else:
        unit = np.random.default_rng(seed).random((n_points, dimension))
    lower = np.asarray([item.lower for item in parameters], dtype=float)
    upper = np.asarray([item.upper for item in parameters], dtype=float)
    return _scale_unit_points(unit, parameters, lower, upper)


def _apply_initial_population_seeds(
    population: np.ndarray,
    *,
    seeds: Any,
    lower: np.ndarray,
    upper: np.ndarray,
) -> tuple[np.ndarray, int]:
    if seeds is None:
        return population, 0
    try:
        seed_array = np.asarray(seeds, dtype=float)
    except Exception:
        return population, 0
    if seed_array.ndim == 1:
        seed_array = seed_array.reshape(1, -1)
    if seed_array.ndim != 2 or seed_array.shape[1] != population.shape[1]:
        return population, 0
    if seed_array.shape[0] == 0:
        return population, 0
    finite_mask = np.all(np.isfinite(seed_array), axis=1)
    seed_array = seed_array[finite_mask]
    if seed_array.shape[0] == 0:
        return population, 0
    count = min(population.shape[0], seed_array.shape[0])
    seeded = np.asarray(population, dtype=float).copy()
    seeded[:count, :] = np.clip(seed_array[:count, :], lower, upper)
    return seeded, count


def _repair_bounds(
    vector: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    rng: np.random.Generator,
    handling: str,
) -> np.ndarray:
    repaired = np.asarray(vector, dtype=float).copy()
    span = upper - lower
    if handling == "clip":
        return np.clip(repaired, lower, upper)
    if handling == "resample":
        mask = (repaired < lower) | (repaired > upper)
        if np.any(mask):
            repaired[mask] = rng.uniform(lower[mask], upper[mask])
        return repaired

    # Reflect can cross a boundary by more than one width, so use modulo on a
    # doubled interval. Degenerate spans are not allowed by parameter validation.
    shifted = np.mod(repaired - lower, 2.0 * span)
    reflected = np.where(shifted <= span, lower + shifted, upper - (shifted - span))
    return np.clip(reflected, lower, upper)


def _sample_adaptive_f_cr(options: dict[str, Any], rng: np.random.Generator, mu_f: float, mu_cr: float) -> tuple[float, float]:
    f_min = float(options["F_min"])
    f_max = float(options["F_max"])
    cr_min = float(options["CR_min"])
    cr_max = float(options["CR_max"])
    # This intentionally stays simple and deterministic under the engine RNG.
    # The sampler is isolated so it can later be replaced by a stricter JADE
    # Cauchy/normal implementation without changing the scan pipeline.
    f = float(np.clip(rng.normal(mu_f, 0.1), f_min, f_max))
    cr = float(np.clip(rng.normal(mu_cr, 0.1), cr_min, cr_max))
    return f, cr


def _update_adaptive_means(
    options: dict[str, Any],
    mu_f: float,
    mu_cr: float,
    successful_f: list[float],
    successful_cr: list[float],
) -> tuple[float, float]:
    if successful_f:
        denominator = sum(successful_f)
        if denominator > 0.0:
            lehmer_f = sum(item * item for item in successful_f) / denominator
            rate = float(options["F_learning_rate"])
            mu_f = (1.0 - rate) * mu_f + rate * lehmer_f
    if successful_cr:
        rate = float(options["CR_learning_rate"])
        mu_cr = (1.0 - rate) * mu_cr + rate * (sum(successful_cr) / len(successful_cr))
    return mu_f, mu_cr


def _write_rows_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_ready(row.get(key)) for key in fieldnames})


def _population_rows(
    *,
    generation: int,
    population: np.ndarray,
    targets: np.ndarray,
    records: list[dict[str, Any]],
    request: ScanRequest,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (point, target, record) in enumerate(zip(population, targets, records, strict=True)):
        point_result = record.get("point_result", {})
        row = {
            "generation": generation,
            "individual": index,
            "valid": bool(record.get("valid", False)),
            "status": point_result.get("status", ""),
            "failure_reason": point_result.get("failure_reason", ""),
            "scanner_target": float(target),
            "metric_value": record.get("metric_value", request.invalid_objective),
            "total_nll": point_result.get("total_nll", request.invalid_objective),
        }
        for parameter, value in zip(request.scanned_parameters, point, strict=True):
            row[f"param::{parameter.name}"] = float(value)
        _add_likelihood_components(row, record, request)
        rows.append(row)
    return rows


def _write_population_artifacts(
    writer: _PythonScanArtifactsWriter,
    request: ScanRequest,
    *,
    generation: int,
    population: np.ndarray,
    targets: np.ndarray,
    records: list[dict[str, Any]],
    options: dict[str, Any],
) -> dict[str, str]:
    rows = _population_rows(
        generation=generation,
        population=population,
        targets=targets,
        records=records,
        request=request,
    )
    fieldnames = [
        "generation",
        "individual",
        "valid",
        "status",
        "failure_reason",
        "scanner_target",
        "metric_value",
        "total_nll",
        *[f"param::{item.name}" for item in request.scanned_parameters],
        *_likelihood_component_columns(request),
    ]
    paths: dict[str, str] = {}
    if options["save_population"]:
        _write_rows_csv(writer.run_directory / "final_population.csv", fieldnames, rows)
        paths["final_population_path"] = "final_population.csv"
    if options["save_elites"]:
        order = np.argsort(targets)
        elite_size = min(int(options["elite_size"]), len(order))
        elite_rows = [rows[int(index)] for index in order[:elite_size]]
        _write_rows_csv(writer.run_directory / "elite_points.csv", fieldnames, elite_rows)
        paths["elite_points_path"] = "elite_points.csv"
    return paths


def _write_population_statistics(
    writer: _PythonScanArtifactsWriter,
    request: ScanRequest,
    *,
    population: np.ndarray,
    targets: np.ndarray,
    best_record: dict[str, Any] | None,
    options: dict[str, Any],
) -> dict[str, str]:
    finite_mask = np.isfinite(targets)
    selected = population[finite_mask]
    paths: dict[str, str] = {}
    if selected.size == 0:
        summary = {
            "method": "adaptive_diver_final_population",
            "note": "Population summary is not a Bayesian posterior.",
            "parameters": {},
        }
        corr = {
            "method": "adaptive_diver_final_population",
            "parameters": [item.name for item in request.scanned_parameters],
            "matrix": [],
        }
    else:
        best_values = {}
        if best_record is not None:
            best_values = {
                item.name: float(value)
                for item, value in zip(
                    request.scanned_parameters,
                    best_record["scanned_values"],
                    strict=True,
                )
            }
        parameters: dict[str, Any] = {}
        for column, parameter in enumerate(request.scanned_parameters):
            values = selected[:, column]
            parameters[parameter.name] = {
                "best_fit": best_values.get(parameter.name),
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "median": float(np.percentile(values, 50.0)),
                "p16": float(np.percentile(values, 16.0)),
                "p84": float(np.percentile(values, 84.0)),
                "p2_5": float(np.percentile(values, 2.5)),
                "p97_5": float(np.percentile(values, 97.5)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
            }
        summary = {
            "method": "adaptive_diver_final_population",
            "note": "These are final-population summaries, not rigorous posterior credible intervals.",
            "n_points": int(selected.shape[0]),
            "confidence_levels": list(options["confidence_levels"]),
            "parameters": parameters,
        }
        if selected.shape[0] >= 2:
            matrix = np.corrcoef(selected, rowvar=False)
            matrix = np.nan_to_num(matrix, nan=0.0).tolist()
        else:
            matrix = np.eye(len(request.scanned_parameters)).tolist()
        corr = {
            "method": "adaptive_diver_final_population",
            "parameters": [item.name for item in request.scanned_parameters],
            "matrix": matrix,
        }
    (writer.run_directory / "parameter_summary.json").write_text(
        json.dumps(_json_ready(summary), indent=2),
        encoding="utf-8",
    )
    (writer.run_directory / "correlation_matrix.json").write_text(
        json.dumps(_json_ready(corr), indent=2),
        encoding="utf-8",
    )
    paths["parameter_summary_path"] = "parameter_summary.json"
    paths["correlation_matrix_path"] = "correlation_matrix.json"
    return paths


def _run_adaptive_local_refinement(
    objective: _AdaptiveDiverObjective,
    request: ScanRequest,
    *,
    population: np.ndarray,
    targets: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    options: dict[str, Any],
) -> list[dict[str, Any]]:
    if not options["local_refinement_enabled"]:
        return []
    try:
        optimize = importlib.import_module("scipy.optimize")
    except Exception as exc:
        return [
            {
                "enabled": True,
                "available": False,
                "error": (
                    "scipy.optimize is required for adaptive_diver local refinement. "
                    f"Install scipy or disable local_refinement. Original error: {exc}"
                ),
            }
        ]

    results: list[dict[str, Any]] = []
    method = str(options["local_method"])
    order = np.argsort(targets)
    n_elites = min(int(options["local_n_elites"]), len(order))
    bounds = list(zip(lower.tolist(), upper.tolist(), strict=True))

    def local_objective(raw_point: np.ndarray) -> float:
        point = np.clip(np.asarray(raw_point, dtype=float), lower, upper)
        record = objective.evaluate(point)
        return _record_target(record, request.invalid_objective)

    for rank, index in enumerate(order[:n_elites]):
        start = np.asarray(population[int(index)], dtype=float)
        try:
            result = optimize.minimize(
                local_objective,
                start,
                method=method,
                bounds=bounds,
                options={"maxiter": int(options["local_maxiter"])},
            )
            refined = np.clip(np.asarray(getattr(result, "x", start), dtype=float), lower, upper)
            results.append(
                {
                    "rank": rank,
                    "start_target": float(targets[int(index)]),
                    "success": bool(getattr(result, "success", False)),
                    "message": str(getattr(result, "message", "")),
                    "fun": float(getattr(result, "fun", request.invalid_objective)),
                    "parameters": {
                        parameter.name: float(value)
                        for parameter, value in zip(request.scanned_parameters, refined, strict=True)
                    },
                }
            )
        except Exception as exc:
            results.append(
                {
                    "rank": rank,
                    "start_target": float(targets[int(index)]),
                    "success": False,
                    "message": f"local refinement failed: {exc}",
                }
            )
    return results


def _run_adaptive_diver_scan(
    model: ModelDefinition,
    compiled: "CompiledModel",
    request: ScanRequest,
) -> ScanResults:
    writer = _PythonScanArtifactsWriter(request)
    objective = _AdaptiveDiverObjective(compiled, request, writer)
    options = dict(request.engine_options)
    rng = np.random.default_rng(int(options["seed"]))
    lower = np.asarray([item.lower for item in request.scanned_parameters], dtype=float)
    upper = np.asarray([item.upper for item in request.scanned_parameters], dtype=float)
    dimension = len(request.scanned_parameters)
    population_size = int(options["population_size"])
    max_generations = int(options["max_generations"])
    max_evaluations = int(options["max_evaluations"])

    if request.verbose > 0:
        print(
            "[adaptive_diver] start | "
            f"max_generations={max_generations} | population_size={population_size} | "
            f"dimension={dimension} | progress_interval={options.get('progress_interval', 100)}",
            flush=True,
        )

    population = _sample_prior_points(
        n_points=population_size,
        parameters=request.scanned_parameters,
        seed=int(options["seed"]),
        method="random",
    )
    population, initial_seed_count = _apply_initial_population_seeds(
        population,
        seeds=options.get("initial_population"),
        lower=lower,
        upper=upper,
    )
    records = [objective.evaluate(population[index]) for index in range(population_size)]
    targets = np.asarray([_record_target(record, request.invalid_objective) for record in records], dtype=float)

    archive: list[np.ndarray] = []
    history: list[dict[str, Any]] = []
    mu_f = float(options["F_initial"])
    mu_cr = float(options["CR_initial"])
    best_seen = float(np.min(targets))
    last_improvement_generation = 0
    stop_reason = "max_generations"
    completed_generations = 0

    for generation in range(1, max_generations + 1):
        if max_evaluations and objective.evaluations >= max_evaluations:
            stop_reason = "max_evaluations"
            break

        successful_f: list[float] = []
        successful_cr: list[float] = []
        successful_replacements = 0
        order = np.argsort(targets)
        p_count = max(2, min(population_size, int(ceil(float(options["p_best_fraction"]) * population_size))))

        for index in range(population_size):
            if max_evaluations and objective.evaluations >= max_evaluations:
                stop_reason = "max_evaluations"
                break

            f, cr = _sample_adaptive_f_cr(options, rng, mu_f, mu_cr)
            pbest_index = int(rng.choice(order[:p_count]))
            candidates = [candidate for candidate in range(population_size) if candidate != index]
            r1_index = int(rng.choice(candidates))

            if options["archive"] and archive:
                pool = np.vstack([population, np.asarray(archive, dtype=float)])
                r2_pool_index = int(rng.integers(0, pool.shape[0]))
                r2 = pool[r2_pool_index]
            else:
                r2_candidates = [
                    candidate
                    for candidate in range(population_size)
                    if candidate not in {index, r1_index}
                ]
                r2 = population[int(rng.choice(r2_candidates))]

            mutant = (
                population[index]
                + f * (population[pbest_index] - population[index])
                + f * (population[r1_index] - r2)
            )
            mutant = _repair_bounds(mutant, lower, upper, rng, str(options["bounds_handling"]))
            crossover_mask = rng.random(dimension) < cr
            crossover_mask[int(rng.integers(0, dimension))] = True
            trial = np.where(crossover_mask, mutant, population[index])
            trial = _repair_bounds(trial, lower, upper, rng, str(options["bounds_handling"]))

            trial_record = objective.evaluate(trial)
            trial_target = _record_target(trial_record, request.invalid_objective)
            if trial_target <= targets[index]:
                if options["archive"]:
                    archive.append(population[index].copy())
                    if len(archive) > population_size:
                        del archive[int(rng.integers(0, len(archive)))]
                population[index] = trial
                targets[index] = trial_target
                records[index] = trial_record
                successful_f.append(f)
                successful_cr.append(cr)
                successful_replacements += 1

        mu_f, mu_cr = _update_adaptive_means(options, mu_f, mu_cr, successful_f, successful_cr)
        finite_targets = targets[np.isfinite(targets)]
        current_best = float(np.min(finite_targets)) if finite_targets.size else request.invalid_objective
        mean_target = float(np.mean(finite_targets)) if finite_targets.size else request.invalid_objective
        std_target = float(np.std(finite_targets)) if finite_targets.size else request.invalid_objective
        if current_best < best_seen - float(options["min_delta_chi2"]):
            best_seen = current_best
            last_improvement_generation = generation

        entry = {
            "generation": generation,
            "best_scanner_target": current_best,
            "mean_scanner_target": mean_target,
            "std_scanner_target": std_target,
            "successful_replacements": successful_replacements,
            "mu_F": mu_f,
            "mu_CR": mu_cr,
            "evaluations": objective.evaluations,
            "valid_points": objective.valid_points,
        }
        history.append(entry)
        completed_generations = generation

        progress_interval = int(options["progress_interval"])
        if request.verbose > 0 and progress_interval > 0 and generation % progress_interval == 0:
            best_parameters = {}
            if objective.best_record is not None:
                best_parameters = {
                    item.name: value
                    for item, value in zip(
                        request.scanned_parameters,
                        objective.best_record["scanned_values"],
                        strict=True,
                    )
                }
            formatted = ", ".join(f"{name}={float(value):.8g}" for name, value in best_parameters.items())
            print(
                "[adaptive_diver] "
                f"generation={generation} | evaluations={objective.evaluations} | "
                f"valid={objective.valid_points} | best_target={current_best:.12g} | "
                f"mean={mean_target:.12g} | std={std_target:.12g} | "
                f"successes={successful_replacements} | mu_F={mu_f:.6g} | mu_CR={mu_cr:.6g}"
                + (f" | best_parameters={{ {formatted} }}" if formatted else ""),
                flush=True,
            )

        if max_evaluations and objective.evaluations >= max_evaluations:
            stop_reason = "max_evaluations"
            break
        if int(options["patience"]) > 0 and generation - last_improvement_generation >= int(options["patience"]):
            stop_reason = "patience"
            break
        if float(options["population_std_tol"]) > 0.0 and std_target <= float(options["population_std_tol"]):
            stop_reason = "population_std_tol"
            break
    else:
        stop_reason = "max_generations"

    local_results = _run_adaptive_local_refinement(
        objective,
        request,
        population=population,
        targets=targets,
        lower=lower,
        upper=upper,
        options=options,
    )
    if options["local_refinement_enabled"]:
        (writer.run_directory / "local_refinement.json").write_text(
            json.dumps(_json_ready({"enabled": True, "results": local_results}), indent=2),
            encoding="utf-8",
        )

    artifact_paths = _write_population_artifacts(
        writer,
        request,
        generation=completed_generations,
        population=population,
        targets=targets,
        records=records,
        options=options,
    )
    if options["adaptive_statistics"]:
        artifact_paths.update(
            _write_population_statistics(
                writer,
                request,
                population=population,
                targets=targets,
                best_record=objective.best_record,
                options=options,
            )
        )

    if request.verbose > 0:
        best_target = None if objective.best_record is None else objective.best_record["scanner_target"]
        print(
            "[adaptive_diver] final | "
            f"generations={completed_generations} | evaluations={objective.evaluations} | "
            f"valid={objective.valid_points} | stop_reason={stop_reason}"
            + (f" | best_target={float(best_target):.12g}" if best_target is not None else ""),
            flush=True,
        )

    if options["save_history"]:
        writer.write_history(history)
    else:
        writer.write_history([])
    writer.write_best_fit(objective.best_record)
    writer.write_summary(
        evaluations=objective.evaluations,
        saved_points=objective.saved_points,
        valid_points=objective.valid_points,
        interrupted=False,
        best_record=objective.best_record,
        failure_counters=objective.failure_counters,
        failure_reasons=objective.failure_reasons,
        engine_details={
            "native_backend": "adaptive_diver",
            "success": stop_reason != "max_generations",
            "stop_reason": stop_reason,
            "generations": completed_generations,
            "population_size": population_size,
            "initial_seed_count": initial_seed_count,
            "mu_F": mu_f,
            "mu_CR": mu_cr,
            "archive_size": len(archive),
            "local_refinement_enabled": bool(options["local_refinement_enabled"]),
            "local_refinement_attempts": len(local_results),
            "history_path": "history.json",
            **artifact_paths,
        },
    )
    writer.close()

    return ScanResults(
        run_directory=writer.run_directory,
        points_path=writer.points_path,
        metadata_path=writer.metadata_path,
        best_fit_path=writer.best_fit_path,
        summary_path=writer.summary_path,
        summary=json.loads(writer.summary_path.read_text(encoding="utf-8")),
    )


def _sample_basin_exploration(
    *,
    n_points: int,
    dimension: int,
    lower: np.ndarray,
    upper: np.ndarray,
    method: str,
    seed: int,
    parameters: Sequence[ScanParameterSpec] | None = None,
) -> np.ndarray:
    unit: np.ndarray
    if method in {"latin_hypercube", "sobol"}:
        try:
            qmc = importlib.import_module("scipy.stats.qmc")
            if method == "sobol":
                sampler = qmc.Sobol(d=dimension, scramble=True, seed=seed)
            else:
                sampler = qmc.LatinHypercube(d=dimension, seed=seed)
            unit = np.asarray(sampler.random(n_points), dtype=float)
        except Exception:
            rng = np.random.default_rng(seed)
            unit = rng.random((n_points, dimension))
    else:
        rng = np.random.default_rng(seed)
        unit = rng.random((n_points, dimension))
    if parameters is not None:
        return _scale_unit_points(unit, parameters, lower, upper)
    return lower + unit * (upper - lower)


def _parameter_index(request: ScanRequest) -> dict[str, int]:
    return {parameter.name: parameter.index for parameter in request.scanned_parameters}


def _draw_scaled_value(rng: np.random.Generator, low: float, high: float, scale: str) -> float:
    if scale == "log":
        if low <= 0.0 or high <= 0.0:
            raise ModelValidationError("Log-scaled proposal ranges must be strictly positive.")
        return float(10.0 ** rng.uniform(np.log10(low), np.log10(high)))
    return float(rng.uniform(low, high))


def _proposal_applies_to_stage(stage: dict[str, Any], sampling_stage: str) -> bool:
    apply_to = stage.get("apply_to")
    if not apply_to:
        return True
    aliases = {
        "basin_exploration": "exploration",
        "initial_exploration": "exploration",
        "progressive": "progressive_exploration",
        "progressive_round": "progressive_exploration",
        "local_refinement": "refinement",
    }
    normalized_stage = aliases.get(sampling_stage, sampling_stage)
    requested = {aliases.get(str(item), str(item)) for item in apply_to}
    return normalized_stage in requested or "all" in requested or "*" in requested


def _load_guided_sampling_function(function_path: str) -> Any:
    if function_path in _GUIDED_FUNCTION_CACHE:
        return _GUIDED_FUNCTION_CACHE[function_path]

    if ":" in function_path:
        module_name, function_name = function_path.split(":", 1)
    else:
        module_name, function_name = function_path.rsplit(".", 1)

    if module_name.endswith(".py") or "/" in module_name:
        module_path = Path(module_name).expanduser().resolve()
        if not module_path.exists():
            raise ModelValidationError(f"Guided sampling function module does not exist: {module_path}")
        spec = importlib.util.spec_from_file_location(
            f"bsm_scanner_guided_sampling_{abs(hash(str(module_path)))}",
            module_path,
        )
        if spec is None or spec.loader is None:
            raise ModelValidationError(f"Could not import guided sampling module: {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(module_name)

    function = getattr(module, function_name, None)
    if function is None or not callable(function):
        raise ModelValidationError(f"Guided sampling function is not callable: {function_path}")
    _GUIDED_FUNCTION_CACHE[function_path] = function
    return function


def _call_guided_sampling_function(
    function: Any,
    point: dict[str, float],
    *,
    rng: np.random.Generator,
    options: dict[str, Any],
    context: dict[str, Any],
) -> Any:
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return function(dict(point), rng=rng, options=options, context=context)

    kwargs: dict[str, Any] = {}
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if accepts_kwargs or "rng" in signature.parameters:
        kwargs["rng"] = rng
    if accepts_kwargs or "options" in signature.parameters:
        kwargs["options"] = options
    if accepts_kwargs or "context" in signature.parameters:
        kwargs["context"] = context
    return function(dict(point), **kwargs)


def _apply_basin_proposals(
    *,
    points: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    seed: int,
    sampling_stage: str = "exploration",
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    proposal_options = options["proposals"]
    if not proposal_options["enabled"] or not proposal_options["stages"] or points.size == 0:
        return points, ["" for _ in range(points.shape[0])], {
            "enabled": False,
            "evaluated_points": int(points.shape[0]),
            "applications": {},
        }

    transformed = np.asarray(points, dtype=float).copy()
    lower = np.asarray([item.lower for item in request.scanned_parameters], dtype=float)
    upper = np.asarray([item.upper for item in request.scanned_parameters], dtype=float)
    indices = _parameter_index(request)
    rng = np.random.default_rng(seed)
    used: list[list[str]] = [[] for _ in range(points.shape[0])]
    applications: Counter[str] = Counter()
    errors: Counter[str] = Counter()

    parameter_names = [parameter.name for parameter in request.scanned_parameters]
    lower_by_name = {parameter.name: parameter.lower for parameter in request.scanned_parameters}
    upper_by_name = {parameter.name: parameter.upper for parameter in request.scanned_parameters}
    function_cache: dict[str, Any] = {}

    for stage in proposal_options["stages"]:
        if not stage["enabled"] or not _proposal_applies_to_stage(stage, sampling_stage):
            continue
        name = str(stage["name"])
        proposal_type = str(stage["type"])
        function = None
        if proposal_type == "point_function":
            function_path = str(stage.get("function", stage.get("callable", "")))
            if not function_path:
                raise ModelValidationError(f"Proposal stage '{name}' requires a function path.")
            function = function_cache.setdefault(function_path, _load_guided_sampling_function(function_path))
        for row_index in range(transformed.shape[0]):
            if rng.random() > float(stage["probability"]):
                continue
            row = transformed[row_index]
            changed = False
            if proposal_type == "prior_profile":
                for parameter in stage.get("parameters", []):
                    if not isinstance(parameter, dict) or str(parameter.get("name", "")) not in indices:
                        continue
                    index = indices[str(parameter["name"])]
                    if "values" in parameter:
                        values = np.asarray(parameter["values"], dtype=float)
                        weights = np.asarray(parameter.get("weights", np.ones(values.size)), dtype=float)
                        if values.size == 0 or weights.size != values.size or np.sum(weights) <= 0.0:
                            continue
                        row[index] = float(rng.choice(values, p=weights / np.sum(weights)))
                    else:
                        mean = float(parameter.get("mean", row[index]))
                        sigma = float(parameter.get("sigma", 0.1 * (upper[index] - lower[index])))
                        row[index] = float(rng.normal(mean, sigma))
                    changed = True
            elif proposal_type == "complex_vector_norm":
                for vector in stage.get("vectors", []):
                    if not isinstance(vector, dict):
                        continue
                    components = vector.get("components", {})
                    real_names = list(components.get("real", []))
                    imag_names = list(components.get("imag", []))
                    component_names = [*real_names, *imag_names]
                    if not component_names or any(str(item) not in indices for item in component_names):
                        continue
                    norm_range = vector.get("norm_range", [0.0, 1.0])
                    norm = _draw_scaled_value(
                        rng,
                        float(norm_range[0]),
                        float(norm_range[1]),
                        str(vector.get("scale", "linear")),
                    )
                    if real_names and imag_names and len(real_names) == len(imag_names):
                        direction = rng.normal(size=len(real_names)) + 1j * rng.normal(size=len(real_names))
                        direction_norm = float(np.linalg.norm(direction))
                        if direction_norm <= 0.0:
                            continue
                        values = norm * direction / direction_norm
                        for real_name, imag_name, value in zip(real_names, imag_names, values, strict=True):
                            row[indices[str(real_name)]] = float(np.real(value))
                            row[indices[str(imag_name)]] = float(np.imag(value))
                    else:
                        direction = rng.normal(size=len(component_names))
                        direction_norm = float(np.linalg.norm(direction))
                        if direction_norm <= 0.0:
                            continue
                        values = norm * direction / direction_norm
                        for component_name, value in zip(component_names, values, strict=True):
                            row[indices[str(component_name)]] = float(value)
                    changed = True
            elif proposal_type == "parameter_rescale":
                factor_range = stage.get("factor_range", [0.5, 2.0])
                factor = _draw_scaled_value(
                    rng,
                    float(factor_range[0]),
                    float(factor_range[1]),
                    str(stage.get("scale", "linear")),
                )
                for parameter_name in stage.get("parameters", []):
                    if str(parameter_name) in indices:
                        index = indices[str(parameter_name)]
                        row[index] *= factor
                        changed = True
            elif proposal_type == "point_function":
                assert function is not None
                point = {name_: float(row[indices[name_]]) for name_ in parameter_names}
                context = {
                    "sampling_stage": sampling_stage,
                    "parameter_names": list(parameter_names),
                    "lower": dict(lower_by_name),
                    "upper": dict(upper_by_name),
                    "proposal": dict(stage),
                    "row_index": row_index,
                }
                try:
                    result = _call_guided_sampling_function(
                        function,
                        point,
                        rng=rng,
                        options=dict(stage.get("options", {})),
                        context=context,
                    )
                except Exception:
                    errors[name] += 1
                    continue
                if result is None:
                    continue
                if not isinstance(result, dict):
                    raise ModelValidationError(
                        f"Proposal stage '{name}' function must return a mapping or None."
                    )
                for parameter_name, value in result.items():
                    key = str(parameter_name)
                    if key not in indices:
                        continue
                    numeric = float(value)
                    if not np.isfinite(numeric):
                        continue
                    row[indices[key]] = numeric
                    changed = True
            if changed:
                transformed[row_index] = np.clip(row, lower, upper)
                used[row_index].append(name)
                applications[name] += 1

    return transformed, [";".join(items) for items in used], {
        "enabled": True,
        "evaluated_points": int(points.shape[0]),
        "applications": dict(sorted(applications.items())),
        "errors": dict(sorted(errors.items())),
        "sampling_stage": sampling_stage,
        "stages": [
            str(stage["name"])
            for stage in proposal_options["stages"]
            if stage["enabled"] and _proposal_applies_to_stage(stage, sampling_stage)
        ],
    }


def _filter_staged_model(model: ModelDefinition, staged: dict[str, Any]) -> ModelDefinition:
    cheap_model = copy.deepcopy(model)
    cheap_terms = set(staged["cheap_terms"])
    excluded_terms = set(staged["cheap_exclude_terms"]) | set(staged["expensive_terms"])
    if cheap_terms:
        cheap_model.likelihoods = [item for item in cheap_model.likelihoods if item.name in cheap_terms]
    elif excluded_terms:
        cheap_model.likelihoods = [item for item in cheap_model.likelihoods if item.name not in excluded_terms]

    included_checks = set(staged["cheap_include_theory_checks"])
    excluded_checks = set(staged["cheap_exclude_theory_checks"])
    if included_checks:
        cheap_model.theory_checks = [item for item in cheap_model.theory_checks if item.name in included_checks]
    elif excluded_checks:
        cheap_model.theory_checks = [item for item in cheap_model.theory_checks if item.name not in excluded_checks]

    included_outputs = set(staged["cheap_include_outputs"])
    excluded_outputs = set(staged["cheap_exclude_outputs"])
    if included_outputs:
        cheap_model.outputs.save = [name for name in cheap_model.outputs.save if name in included_outputs]
    elif excluded_outputs:
        cheap_model.outputs.save = [name for name in cheap_model.outputs.save if name not in excluded_outputs]
    else:
        # Cheap-stage outputs are opt-in. Otherwise diagnostic output roots can
        # accidentally activate expensive backend nodes during preselection.
        cheap_model.outputs.save = []
    return cheap_model


def _build_staged_evaluation_context(
    model: ModelDefinition,
    request: ScanRequest,
    options: dict[str, Any],
) -> dict[str, Any] | None:
    staged = options["staged_evaluation"]
    if not staged["enabled"]:
        return None
    if _core is None or not hasattr(_core, "evaluate_scan_point"):
        return None
    from bsm_scanner.api import compile_model

    cheap_model = _filter_staged_model(model, staged)
    cheap_compiled = compile_model(cheap_model, build_backend=True)
    cheap_request = build_scan_request(
        cheap_model,
        cheap_compiled,
        run_directory=request.run_directory,
        run_id=f"{request.run_id}-cheap-stage",
        timestamp_utc=request.timestamp_utc,
    )
    cheap_request = replace(
        cheap_request,
        engine="serial_random",
        save_invalid_points=False,
        verbose=0,
    )
    return {
        "cheap_model": cheap_model,
        "cheap_compiled": cheap_compiled,
        "cheap_plan_dict": cheap_compiled.plan.to_dict(),
        "cheap_request": cheap_request,
        "cheap_request_dict": cheap_request.to_dict(),
        "cheap_likelihood_terms": list(cheap_request.likelihood_names),
        "cheap_outputs": list(cheap_request.selected_outputs),
    }


def _synthetic_stage_error_record(
    point: list[float],
    request: ScanRequest,
    exc: Exception,
    *,
    stage: str,
) -> dict[str, Any]:
    message = f"{stage} evaluation failed: {exc}"
    return {
        "metric_value": request.invalid_objective,
        "scanner_target": request.invalid_objective,
        "valid": False,
        "scanned_values": list(point),
        "point_result": {
            "status": "evaluation_error",
            "valid": False,
            "failure_reason": message,
            "total_nll": request.invalid_objective,
            "likelihood_terms": {},
            "outputs": {},
            "flags": [],
        },
    }


def _evaluate_cheap_stage_record(
    context: dict[str, Any],
    request: ScanRequest,
    point: np.ndarray | list[float],
) -> dict[str, Any]:
    values = [float(item) for item in point]
    try:
        return _core.evaluate_scan_point(
            context["cheap_plan_dict"],
            context["cheap_request_dict"],
            values,
        )
    except Exception as exc:
        return _synthetic_stage_error_record(values, request, exc, stage="cheap-stage")


def _cheap_stage_passes(record: dict[str, Any], options: dict[str, Any]) -> tuple[bool, float, int, list[str]]:
    staged = options["staged_evaluation"]
    terms = _record_likelihood_terms(record)
    cheap_names = staged["cheap_terms"] or [
        name for name in terms if name not in set(staged["expensive_terms"])
    ]
    cheap_values = [
        float(terms[name])
        for name in cheap_names
        if name in terms and isfinite(float(terms[name]))
    ]
    cheap_objective = float(sum(cheap_values)) if cheap_values else _record_target(
        record,
        float(options["invalid_penalty"]),
    )
    hard_failures = _record_hard_failures(record)
    passes = cheap_objective <= float(staged["max_cheap_objective"])
    if staged["require_no_hard_failures"]:
        passes = passes and hard_failures == 0
    return bool(passes), cheap_objective, hard_failures, sorted(terms)


def _annotate_staged_records(records: list[dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
    staged = options["staged_evaluation"]
    if not staged["enabled"]:
        for record in records:
            record["stage_reached"] = "full"
            record["objective_cheap"] = record.get("scanner_target")
            record["objective_full"] = record.get("scanner_target")
            record["hard_failures"] = _record_hard_failures(record)
            record["fit_failures"] = _record_fit_failures(record)
            record["accepted"] = _record_accepted(record, float(options["invalid_penalty"]))
        return {"enabled": False, "full_evaluations": len(records), "cheap_rejections": 0}

    if any(record.get("_staged_materialized", False) for record in records):
        cheap_rejections = sum(1 for record in records if record.get("stage_reached") == "cheap_rejected")
        full_evaluations = sum(1 for record in records if record.get("stage_reached") == "full")
        return {
            "enabled": True,
            "mode": "cheap_graph_preselection",
            "full_evaluations": int(full_evaluations),
            "full_candidates": int(full_evaluations),
            "cheap_rejections": int(cheap_rejections),
            "cheap_terms": list(staged["cheap_terms"]),
            "cheap_exclude_terms": list(staged["cheap_exclude_terms"]),
            "cheap_exclude_theory_checks": list(staged["cheap_exclude_theory_checks"]),
            "cheap_exclude_outputs": list(staged["cheap_exclude_outputs"]),
            "expensive_terms": list(staged["expensive_terms"]),
        }

    cheap_rejections = 0
    full_candidates = 0
    for record in records:
        terms = _record_likelihood_terms(record)
        cheap_names = staged["cheap_terms"] or [
            name for name in terms if name not in set(staged["expensive_terms"])
        ]
        cheap_values = [float(terms[name]) for name in cheap_names if name in terms and isfinite(float(terms[name]))]
        cheap_objective = float(sum(cheap_values)) if cheap_values else _record_target(
            record, float(options["invalid_penalty"])
        )
        hard_failures = 0 if bool(record.get("valid", False)) else 1
        passes = cheap_objective <= float(staged["max_cheap_objective"])
        if staged["require_no_hard_failures"]:
            passes = passes and hard_failures == 0
        record["objective_cheap"] = cheap_objective
        record["objective_full"] = _record_target(record, float(options["invalid_penalty"]))
        record["hard_failures"] = hard_failures
        record["fit_failures"] = 0
        record["stage_reached"] = "full" if passes else "cheap_rejected"
        record["accepted"] = bool(passes and record.get("valid", False))
        record["terms_evaluated"] = sorted(terms)
        if passes:
            full_candidates += 1
        else:
            cheap_rejections += 1
    return {
        "enabled": True,
        "mode": "single_pass_compatibility",
        "note": (
            "The current compiled evaluator computes one active graph. Staged policy classifies "
            "cheap/full eligibility from existing term outputs; backend call elision requires "
            "future evaluator support for partial active closures."
        ),
        "full_candidates": full_candidates,
        "cheap_rejections": cheap_rejections,
        "cheap_terms": list(staged["cheap_terms"]),
        "expensive_terms": list(staged["expensive_terms"]),
    }


def _jitter_refinement_points(
    *,
    seeds: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    seed: int,
) -> np.ndarray:
    refinement = options["refinement"]
    if not refinement["enabled"] or seeds.size == 0:
        return np.empty((0, len(request.scanned_parameters)), dtype=float)
    rng = np.random.default_rng(seed)
    rows: list[np.ndarray] = []
    jitter_fraction = float(refinement["jitter_fraction"])
    for _round in range(int(refinement["n_rounds"])):
        for seed_point in seeds[: int(refinement["max_seeds"])]:
            for _ in range(int(refinement["points_per_seed"])):
                point = np.asarray(seed_point, dtype=float).copy()
                for index, parameter in enumerate(request.scanned_parameters):
                    if parameter.prior == "log" and point[index] > 0.0 and parameter.lower > 0.0:
                        log_value = np.log(point[index])
                        log_span = np.log(parameter.upper) - np.log(parameter.lower)
                        point[index] = np.exp(log_value + rng.normal(0.0, jitter_fraction * log_span))
                    elif parameter.prior == "signed_log" and abs(point[index]) > _parameter_min_abs(parameter):
                        sign = -1.0 if point[index] < 0.0 else 1.0
                        max_abs = max(abs(parameter.lower), abs(parameter.upper))
                        log_span = np.log(max_abs) - np.log(_parameter_min_abs(parameter))
                        log_value = np.log(abs(point[index]))
                        point[index] = sign * np.exp(log_value + rng.normal(0.0, jitter_fraction * log_span))
                    else:
                        span = parameter.upper - parameter.lower
                        point[index] += rng.normal(0.0, jitter_fraction * span)
                rows.append(point)
    if not rows:
        return np.empty((0, len(request.scanned_parameters)), dtype=float)
    lower = np.asarray([item.lower for item in request.scanned_parameters], dtype=float)
    upper = np.asarray([item.upper for item in request.scanned_parameters], dtype=float)
    return np.clip(np.asarray(rows, dtype=float), lower, upper)


def _records_to_summary_rows(
    *,
    points: np.ndarray,
    records: list[dict[str, Any]],
    request: ScanRequest,
    extra: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    extras = extra or [{} for _ in records]
    for index, (point, record, extra_values) in enumerate(zip(points, records, extras, strict=True)):
        point_result = record.get("point_result", {})
        row = {
            "point_id": index,
            "accepted": _record_accepted(record, request.invalid_objective),
            "valid": bool(record.get("valid", False)),
            "status": point_result.get("status", ""),
            "failure_reason": point_result.get("failure_reason", ""),
            "scanner_target": _record_target(record, request.invalid_objective),
            "metric_value": record.get("metric_value", request.invalid_objective),
            "total_nll": point_result.get("total_nll", request.invalid_objective),
            "objective_cheap": record.get("objective_cheap", ""),
            "objective_full": record.get("objective_full", ""),
            "stage_reached": record.get("stage_reached", ""),
            "hard_failures": _record_hard_failures(record),
            "fit_failures": _record_fit_failures(record),
            "terms_evaluated": ";".join(record.get("terms_evaluated", [])),
            **extra_values,
        }
        for parameter, value in zip(request.scanned_parameters, point, strict=True):
            row[f"param::{parameter.name}"] = float(value)
        _add_likelihood_components(row, record, request)
        rows.append(row)
    return rows


def _basin_diagnostic_columns() -> list[str]:
    return [
        "objective_cheap",
        "objective_full",
        "stage_reached",
        "accepted",
        "hard_failures",
        "fit_failures",
        "terms_evaluated",
    ]


def _normalise_likelihood_term_name(name: str) -> str:
    return name[6:] if name.startswith("like__") else name


def _discover_record_likelihood_terms(records: list[dict[str, Any]], candidate_indices: np.ndarray) -> list[str]:
    names: set[str] = set()
    for index in candidate_indices:
        for name, value in _record_likelihood_terms(records[int(index)]).items():
            try:
                numeric = float(value)
            except Exception:
                continue
            if isfinite(numeric):
                names.add(str(name))
    return sorted(names)


def _resolve_balanced_terms(
    records: list[dict[str, Any]],
    candidate_indices: np.ndarray,
    selection: dict[str, Any],
) -> list[str]:
    available = _discover_record_likelihood_terms(records, candidate_indices)
    available_by_name = {_normalise_likelihood_term_name(item): item for item in available}
    excluded = {_normalise_likelihood_term_name(item) for item in selection.get("exclude_terms", [])}
    configured = selection.get("terms", "auto")
    if configured == "auto":
        return [item for item in available if _normalise_likelihood_term_name(item) not in excluded]
    if isinstance(configured, str):
        requested = [configured]
    else:
        requested = [str(item) for item in configured]
    resolved: list[str] = []
    for item in requested:
        normalised = _normalise_likelihood_term_name(item)
        if normalised in excluded:
            continue
        if normalised in available_by_name:
            resolved.append(available_by_name[normalised])
    return resolved


def _term_value(record: dict[str, Any], term: str) -> float:
    terms = _record_likelihood_terms(record)
    try:
        value = float(terms.get(term))
    except Exception:
        return float("nan")
    return value if isfinite(value) else float("nan")


def _record_hard_failures(record: dict[str, Any]) -> int:
    if record.get("hard_failures") is not None:
        return int(record.get("hard_failures", 0))
    return 0 if bool(record.get("valid", False)) else 1


def _record_fit_failures(record: dict[str, Any]) -> int:
    return int(record.get("fit_failures", 0) or 0)


def _record_accepted(record: dict[str, Any], invalid_objective: float) -> bool:
    if record.get("accepted") is not None:
        return bool(record.get("accepted"))
    target = _record_target(record, invalid_objective)
    return bool(record.get("valid", False)) and isfinite(target) and target < invalid_objective


def _basic_selection_indices(
    *,
    targets: np.ndarray,
    candidate_indices: np.ndarray,
    selection: dict[str, Any],
    mode: str,
) -> np.ndarray:
    if candidate_indices.size == 0:
        return np.asarray([], dtype=int)
    order = candidate_indices[np.argsort(targets[candidate_indices])]
    if mode == "chi2_window":
        best = float(targets[order[0]])
        selected = order[targets[order] <= best + float(selection["chi2_window"])]
        return selected if selected.size else order[:1]
    keep = max(1, int(ceil(float(selection["top_fraction"]) * candidate_indices.size)))
    return order[:keep]


def _balanced_selection_indices(
    *,
    records: list[dict[str, Any]],
    targets: np.ndarray,
    candidate_indices: np.ndarray,
    selection: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    diagnostics: dict[str, Any] = {
        "mode": "balanced_terms",
        "candidate_points": int(len(records)),
        "finite_points": int(candidate_indices.size),
        "number_after_total_top_fraction": 0,
        "number_after_balanced_term_cuts": 0,
        "final_selected_count": 0,
        "likelihood_terms_used": [],
        "thresholds": {},
        "fallback_used": False,
        "fallback_reason": "",
        "relaxation_attempts": [],
        "best_objective_selected": None,
        "worst_objective_selected": None,
    }
    if candidate_indices.size == 0:
        return np.asarray([], dtype=int), diagnostics

    terms = _resolve_balanced_terms(records, candidate_indices, selection)
    diagnostics["likelihood_terms_used"] = terms
    if not terms:
        fallback = _basic_selection_indices(
            targets=targets,
            candidate_indices=candidate_indices,
            selection=selection,
            mode=str(selection.get("fallback_mode", "top_fraction")),
        )
        diagnostics["fallback_used"] = True
        diagnostics["fallback_reason"] = "no_likelihood_terms_available"
        diagnostics["final_selected_count"] = int(min(fallback.size, int(selection["max_points"])))
        return fallback[: int(selection["max_points"])], diagnostics

    order = candidate_indices[np.argsort(targets[candidate_indices])]
    total_keep = max(1, int(ceil(float(selection["total_top_fraction"]) * candidate_indices.size)))
    total_selected = order[:total_keep]
    diagnostics["number_after_total_top_fraction"] = int(total_selected.size)
    base_q = float(selection["term_quantile_cut"])
    quantiles = [base_q, min(0.5, base_q + 0.1), min(0.7, base_q + 0.2)]
    min_points = int(selection["min_points"])
    selected = np.asarray([], dtype=int)

    for q in dict.fromkeys(quantiles):
        thresholds: dict[str, float] = {}
        masks = np.ones(total_selected.size, dtype=bool)
        for term in terms:
            values = np.asarray([_term_value(records[int(index)], term) for index in candidate_indices], dtype=float)
            finite_values = values[np.isfinite(values)]
            if finite_values.size == 0:
                masks &= False
                continue
            threshold = float(np.quantile(finite_values, q))
            thresholds[term] = threshold
            selected_values = np.asarray(
                [_term_value(records[int(index)], term) for index in total_selected],
                dtype=float,
            )
            masks &= np.isfinite(selected_values) & (selected_values <= threshold)
        attempt_selected = total_selected[masks]
        diagnostics["relaxation_attempts"].append(
            {
                "term_quantile_cut": float(q),
                "thresholds": thresholds,
                "selected_count": int(attempt_selected.size),
            }
        )
        if attempt_selected.size >= min_points:
            selected = attempt_selected
            diagnostics["thresholds"] = thresholds
            break

    if selected.size == 0:
        selected = _basic_selection_indices(
            targets=targets,
            candidate_indices=candidate_indices,
            selection=selection,
            mode=str(selection.get("fallback_mode", "top_fraction")),
        )
        diagnostics["fallback_used"] = True
        diagnostics["fallback_reason"] = "balanced_term_cuts_below_min_points"
    diagnostics["number_after_balanced_term_cuts"] = int(selected.size)
    selected = selected[np.argsort(targets[selected])][: int(selection["max_points"])]
    diagnostics["final_selected_count"] = int(selected.size)
    if selected.size:
        diagnostics["best_objective_selected"] = float(np.min(targets[selected]))
        diagnostics["worst_objective_selected"] = float(np.max(targets[selected]))
    return selected, diagnostics


def _select_basin_points(
    *,
    points: np.ndarray,
    records: list[dict[str, Any]],
    options: dict[str, Any],
    invalid_objective: float,
    return_diagnostics: bool = False,
) -> tuple[np.ndarray, list[dict[str, Any]], np.ndarray] | tuple[np.ndarray, list[dict[str, Any]], np.ndarray, dict[str, Any]]:
    targets = np.asarray([_record_target(record, invalid_objective) for record in records], dtype=float)
    valid_mask = np.asarray([bool(record.get("valid", False)) for record in records], dtype=bool)
    finite_mask = np.isfinite(targets) & valid_mask & (targets < invalid_objective)
    candidate_indices = np.flatnonzero(finite_mask)
    selection = options["selection"]
    diagnostics: dict[str, Any] = {
        "mode": selection["mode"],
        "candidate_points": int(len(records)),
        "finite_points": int(candidate_indices.size),
        "number_after_total_top_fraction": None,
        "number_after_balanced_term_cuts": None,
        "final_selected_count": 0,
        "likelihood_terms_used": [],
        "thresholds": {},
        "fallback_used": False,
        "fallback_reason": "",
        "relaxation_attempts": [],
        "best_objective_selected": None,
        "worst_objective_selected": None,
    }
    selected = np.asarray([], dtype=int)
    if candidate_indices.size == 0:
        diagnostics["fallback_reason"] = "no_valid_finite_points"
    elif selection["mode"] == "chi2_window":
        selected = _basic_selection_indices(
            targets=targets,
            candidate_indices=candidate_indices,
            selection=selection,
            mode="chi2_window",
        )
    elif selection["mode"] == "balanced_terms":
        selected, diagnostics = _balanced_selection_indices(
            records=records,
            targets=targets,
            candidate_indices=candidate_indices,
            selection=selection,
        )
    else:
        selected = _basic_selection_indices(
            targets=targets,
            candidate_indices=candidate_indices,
            selection=selection,
            mode="top_fraction",
        )
    near_miss = selection.get("near_miss", {})
    near_miss_added: list[int] = []
    accepted_added: list[int] = []
    per_term_added: list[int] = []
    full_eval_added: list[int] = []
    if near_miss.get("enabled", False):
        selected_set = {int(index) for index in selected}
        objective_cap = float(near_miss["objective_cap"])
        finite_target_indices = np.flatnonzero(np.isfinite(targets) & (targets <= objective_cap))
        if not near_miss.get("include_invalid", False):
            finite_target_indices = np.asarray(
                [int(index) for index in finite_target_indices if bool(records[int(index)].get("valid", False))],
                dtype=int,
            )
        eligible = [
            int(index)
            for index in finite_target_indices
            if targets[int(index)] <= objective_cap
            and _record_hard_failures(records[int(index)]) <= int(near_miss["max_hard_failures"])
            and _record_fit_failures(records[int(index)]) <= int(near_miss["max_fit_failures"])
        ]
        max_accepted_points = int(near_miss.get("max_accepted_points", 100))
        max_near_miss_points = int(near_miss.get("max_near_miss_points", 100))
        if near_miss.get("keep_per_term_best", True) and max_near_miss_points > 0:
            for term in _discover_record_likelihood_terms(records, np.asarray(eligible, dtype=int)):
                ranked = sorted(eligible, key=lambda index: _term_value(records[index], term))
                for index in ranked:
                    if index not in selected_set:
                        selected_set.add(index)
                        near_miss_added.append(index)
                        per_term_added.append(index)
                        break
                if len(near_miss_added) >= max_near_miss_points:
                    break
        if near_miss.get("keep_accepted", True) and max_accepted_points > 0:
            accepted_ranked = sorted(
                (index for index in eligible if _record_accepted(records[index], invalid_objective)),
                key=lambda index: targets[index],
            )
            for index in accepted_ranked[:max_accepted_points]:
                if index not in selected_set:
                    selected_set.add(index)
                    accepted_added.append(index)
        if near_miss.get("include_full_eval_points", True):
            full_ranked = sorted(
                (
                    index
                    for index in eligible
                    if records[index].get("stage_reached", "full") == "full"
                    and index not in selected_set
                ),
                key=lambda index: targets[index],
            )
            if full_ranked:
                selected_set.add(full_ranked[0])
                near_miss_added.append(full_ranked[0])
                full_eval_added.append(full_ranked[0])
        retention_added = [*accepted_added, *near_miss_added]
        if retention_added:
            selected = np.asarray(
                sorted(selected_set, key=lambda index: targets[index]),
                dtype=int,
            )
    selected = selected[: int(selection["max_points"])]
    diagnostics["near_miss_enabled"] = bool(near_miss.get("enabled", False))
    diagnostics["near_miss_added"] = int(
        sum(1 for index in near_miss_added if int(index) in {int(item) for item in selected})
    )
    diagnostics["accepted_retention_added"] = int(
        sum(1 for index in accepted_added if int(index) in {int(item) for item in selected})
    )
    diagnostics["near_miss_per_term_added"] = int(
        sum(1 for index in per_term_added if int(index) in {int(item) for item in selected})
    )
    diagnostics["near_miss_full_eval_added"] = int(
        sum(1 for index in full_eval_added if int(index) in {int(item) for item in selected})
    )
    diagnostics["near_miss_candidate_count"] = int(len(eligible)) if near_miss.get("enabled", False) else 0
    diagnostics["near_miss_include_invalid"] = bool(near_miss.get("include_invalid", False))
    if not diagnostics["final_selected_count"]:
        diagnostics["final_selected_count"] = int(selected.size)
    if selected.size and diagnostics["best_objective_selected"] is None:
        diagnostics["best_objective_selected"] = float(np.min(targets[selected]))
        diagnostics["worst_objective_selected"] = float(np.max(targets[selected]))
    result = (points[selected], [records[int(index)] for index in selected], selected)
    return (*result, diagnostics) if return_diagnostics else result


def _dbscan_labels(points: np.ndarray, *, eps: float, min_samples: int) -> np.ndarray:
    n_points = points.shape[0]
    labels = np.full(n_points, -1, dtype=int)
    if n_points == 0:
        return labels
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    neighbors = [np.flatnonzero(distances[index] <= eps).tolist() for index in range(n_points)]
    cluster_id = 0
    visited = np.zeros(n_points, dtype=bool)

    for start in range(n_points):
        if visited[start]:
            continue
        visited[start] = True
        if len(neighbors[start]) < min_samples:
            labels[start] = -1
            continue
        labels[start] = cluster_id
        seeds = list(neighbors[start])
        cursor = 0
        while cursor < len(seeds):
            point = seeds[cursor]
            if not visited[point]:
                visited[point] = True
                if len(neighbors[point]) >= min_samples:
                    for neighbor in neighbors[point]:
                        if neighbor not in seeds:
                            seeds.append(neighbor)
            if labels[point] < 0:
                labels[point] = cluster_id
            cursor += 1
        cluster_id += 1
    return labels


def _cluster_basin_points(
    *,
    selected_points: np.ndarray,
    selected_records: list[dict[str, Any]],
    lower: np.ndarray,
    upper: np.ndarray,
    options: dict[str, Any],
    invalid_objective: float,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    clustering = options["clustering"]
    if selected_points.shape[0] == 0:
        return np.asarray([], dtype=int), []
    if not clustering["enabled"] or selected_points.shape[0] < int(clustering["min_samples"]):
        labels = np.zeros(selected_points.shape[0], dtype=int)
    else:
        normalized = (selected_points - lower) / (upper - lower)
        labels = _dbscan_labels(
            normalized,
            eps=float(clustering["eps_fraction"]),
            min_samples=int(clustering["min_samples"]),
        )
        if not np.any(labels >= 0):
            labels = np.zeros(selected_points.shape[0], dtype=int)

    clusters: list[dict[str, Any]] = []
    for label in sorted({int(item) for item in labels if int(item) >= 0}):
        indices = np.flatnonzero(labels == label)
        targets = [_record_target(selected_records[int(index)], invalid_objective) for index in indices]
        clusters.append(
            {
                "cluster_id": label,
                "indices": indices.tolist(),
                "size": int(indices.size),
                "best_scanner_target": float(min(targets)) if targets else invalid_objective,
            }
        )
    clusters.sort(key=lambda item: item["best_scanner_target"])
    kept = clusters[: int(clustering["max_clusters"])]
    remap = {int(cluster["cluster_id"]): index for index, cluster in enumerate(kept)}
    remapped = np.full_like(labels, -1)
    for old_label, new_label in remap.items():
        remapped[labels == old_label] = new_label
    for cluster in kept:
        old_label = int(cluster["cluster_id"])
        cluster["cluster_id"] = remap[old_label]
        cluster["indices"] = np.flatnonzero(remapped == cluster["cluster_id"]).tolist()
        cluster["size"] = len(cluster["indices"])
    return remapped, kept


def _boxes_overlap(left: dict[str, Any], right: dict[str, Any], parameter_names: list[str]) -> bool:
    return all(
        float(left["lower"][name]) <= float(right["upper"][name])
        and float(right["lower"][name]) <= float(left["upper"][name])
        for name in parameter_names
    )


def _merge_basin_boxes(boxes: list[dict[str, Any]], *, parameter_names: list[str]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for box in boxes:
        current = json.loads(json.dumps(_json_ready(box)))
        did_merge = True
        while did_merge:
            did_merge = False
            for index, existing in enumerate(merged):
                if not _boxes_overlap(current, existing, parameter_names):
                    continue
                combined_lower = {
                    name: min(float(current["lower"][name]), float(existing["lower"][name]))
                    for name in parameter_names
                }
                combined_upper = {
                    name: max(float(current["upper"][name]), float(existing["upper"][name]))
                    for name in parameter_names
                }
                current = {
                    "cluster_id": min(int(current.get("cluster_id", 0)), int(existing.get("cluster_id", 0))),
                    "box_id": min(int(current.get("box_id", 0)), int(existing.get("box_id", 0))),
                    "box_type": current.get("box_type", existing.get("box_type", "selected_cloud")),
                    "source_round": current.get("source_round", existing.get("source_round", -1)),
                    "selected_count": int(current.get("selected_count", 0)) + int(existing.get("selected_count", 0)),
                    "source_point_count": int(current.get("source_point_count", 0))
                    + int(existing.get("source_point_count", 0)),
                    "best_objective_in_source": min(
                        float(current.get("best_objective_in_source", np.inf)),
                        float(existing.get("best_objective_in_source", np.inf)),
                    ),
                    "best_exploration_target": min(
                        float(current.get("best_exploration_target", np.inf)),
                        float(existing.get("best_exploration_target", np.inf)),
                    ),
                    "relative_box_volume": 0.0,
                    "lower": combined_lower,
                    "upper": combined_upper,
                }
                del merged[index]
                did_merge = True
                break
        merged.append(current)
    return merged


def _finalize_box_volumes(
    boxes: list[dict[str, Any]],
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
) -> list[dict[str, Any]]:
    parameter_names = [parameter.name for parameter in request.scanned_parameters]
    original_width = upper - lower
    for new_index, box in enumerate(boxes):
        widths = np.asarray(
            [float(box["upper"][name]) - float(box["lower"][name]) for name in parameter_names],
            dtype=float,
        )
        relative_width = np.clip(widths / original_width, 0.0, 1.0)
        box["cluster_id"] = new_index
        box["relative_box_volume"] = float(np.prod(relative_width))
    return boxes


def _contains_point(box: dict[str, Any], point: np.ndarray, request: ScanRequest) -> bool:
    return all(
        float(box["lower"][parameter.name]) <= float(value) <= float(box["upper"][parameter.name])
        for parameter, value in zip(request.scanned_parameters, point, strict=True)
    )


def _box_from_bounds(
    *,
    box_id: int,
    box_type: str,
    low: np.ndarray,
    high: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    source_round: int,
    source_point_count: int,
    best_objective: float,
    global_best_point: np.ndarray | None,
) -> dict[str, Any]:
    low = np.clip(low, lower, upper)
    high = np.clip(high, lower, upper)
    high = np.maximum(high, low)
    relative_width = np.clip((high - low) / (upper - lower), 0.0, 1.0)
    box = {
        "box_id": int(box_id),
        "cluster_id": int(box_id),
        "box_type": box_type,
        "source_round": int(source_round),
        "source_point_count": int(source_point_count),
        "selected_count": int(source_point_count),
        "best_objective_in_source": float(best_objective),
        "best_exploration_target": float(best_objective),
        "relative_box_volume": float(np.prod(relative_width)),
        "lower": {
            parameter.name: float(value)
            for parameter, value in zip(request.scanned_parameters, low, strict=True)
        },
        "upper": {
            parameter.name: float(value)
            for parameter, value in zip(request.scanned_parameters, high, strict=True)
        },
    }
    box["contains_global_best"] = (
        False if global_best_point is None else _contains_point(box, global_best_point, request)
    )
    return box


def _construct_basin_boxes(
    *,
    selected_points: np.ndarray,
    labels: np.ndarray,
    clusters: list[dict[str, Any]],
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
) -> list[dict[str, Any]]:
    boxes_options = options["boxes"]
    original_width = upper - lower
    boxes: list[dict[str, Any]] = []
    for cluster in clusters:
        indices = np.asarray(cluster["indices"], dtype=int)
        cluster_points = selected_points[indices]
        q_low = np.quantile(cluster_points, float(boxes_options["q_low"]), axis=0)
        q_high = np.quantile(cluster_points, float(boxes_options["q_high"]), axis=0)
        width = q_high - q_low
        padded_low = q_low - float(boxes_options["padding_fraction"]) * width
        padded_high = q_high + float(boxes_options["padding_fraction"]) * width
        min_width = float(boxes_options["min_width_fraction"]) * original_width
        current_width = padded_high - padded_low
        too_narrow = current_width < min_width
        if np.any(too_narrow):
            center = 0.5 * (padded_low + padded_high)
            padded_low = np.where(too_narrow, center - 0.5 * min_width, padded_low)
            padded_high = np.where(too_narrow, center + 0.5 * min_width, padded_high)
        if boxes_options["clip_to_original_bounds"]:
            padded_low = np.clip(padded_low, lower, upper)
            padded_high = np.clip(padded_high, lower, upper)
        relative_width = np.clip((padded_high - padded_low) / original_width, 0.0, 1.0)
        box = {
            "cluster_id": int(cluster["cluster_id"]),
            "box_id": int(cluster["cluster_id"]),
            "box_type": str(boxes_options.get("box_type", "selected_cloud")),
            "source_round": int(boxes_options.get("source_round", -1)),
            "source_point_count": int(cluster["size"]),
            "selected_count": int(cluster["size"]),
            "best_objective_in_source": float(cluster["best_scanner_target"]),
            "best_exploration_target": float(cluster["best_scanner_target"]),
            "relative_box_volume": float(np.prod(relative_width)),
            "lower": {
                parameter.name: float(value)
                for parameter, value in zip(request.scanned_parameters, padded_low, strict=True)
            },
            "upper": {
                parameter.name: float(value)
                for parameter, value in zip(request.scanned_parameters, padded_high, strict=True)
            },
        }
        boxes.append(box)
    parameter_names = [parameter.name for parameter in request.scanned_parameters]
    if boxes_options.get("merge_overlapping", False):
        boxes = _merge_basin_boxes(boxes, parameter_names=parameter_names)
    max_boxes = int(boxes_options.get("max_boxes", 0))
    if max_boxes > 0:
        boxes = sorted(boxes, key=lambda item: float(item.get("best_exploration_target", np.inf)))[:max_boxes]
    boxes = _finalize_box_volumes(boxes, lower=lower, upper=upper, request=request)
    global_best_point = boxes_options.get("global_best_point")
    if global_best_point is not None:
        global_best_array = np.asarray(global_best_point, dtype=float)
        for box in boxes:
            box["contains_global_best"] = _contains_point(box, global_best_array, request)
    else:
        for box in boxes:
            box.setdefault("contains_global_best", False)
    return boxes


def _subrequest_for_basin(
    request: ScanRequest,
    *,
    box: dict[str, Any],
    run_directory: Path,
    seed: int,
    options: dict[str, Any],
) -> ScanRequest:
    focused_parameters: list[ScanParameterSpec] = []
    for parameter in request.scanned_parameters:
        focused_parameters.append(
            replace(
                parameter,
                lower=float(box["lower"][parameter.name]),
                upper=float(box["upper"][parameter.name]),
            )
        )
    focused_options = dict(options["focused_engine"]["options"])
    focused_options["seed"] = seed
    raw_settings = {
        key: _stringify_setting(value)
        for key, value in options["focused_engine"]["settings"].items()
    }
    return replace(
        request,
        engine="adaptive_diver",
        run_directory=str(run_directory),
        run_id=f"{request.run_id}-basin-{box['cluster_id']}",
        seed=seed,
        scanned_parameters=focused_parameters,
        raw_settings=raw_settings,
        engine_options=focused_options,
    )


def _boundary_fraction(
    values: dict[str, float],
    *,
    lower: dict[str, float],
    upper: dict[str, float],
) -> dict[str, float]:
    fractions: dict[str, float] = {}
    for name, value in values.items():
        width = float(upper[name]) - float(lower[name])
        fractions[name] = 0.0 if width == 0.0 else (float(value) - float(lower[name])) / width
    return fractions


def _focused_seed_points_for_box(
    *,
    selected_points: np.ndarray,
    selected_records: list[dict[str, Any]],
    labels: np.ndarray,
    box: dict[str, Any],
    invalid_objective: float,
) -> list[list[float]]:
    if selected_points.size == 0 or labels.size == 0:
        return []
    cluster_id = int(box.get("cluster_id", -1))
    indices = [
        index
        for index, label in enumerate(labels.tolist())
        if int(label) == cluster_id
        and index < len(selected_records)
        and bool(selected_records[index].get("valid", False))
        and _record_target(selected_records[index], invalid_objective) < invalid_objective
    ]
    indices.sort(key=lambda index: _record_target(selected_records[index], invalid_objective))
    return [[float(value) for value in selected_points[index].tolist()] for index in indices]


def _ml_focus_transform_values(values: np.ndarray, parameters: Sequence[ScanParameterSpec]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    was_1d = array.ndim == 1
    if was_1d:
        array = array.reshape(1, -1)
    transformed = np.empty_like(array, dtype=float)
    eps = 1.0e-300
    for index, parameter in enumerate(parameters):
        lower = float(parameter.lower)
        upper = float(parameter.upper)
        column = np.clip(array[:, index], lower, upper)
        if parameter.prior == "log" and lower > 0.0 and upper > 0.0:
            low_t = np.log10(max(lower, eps))
            high_t = np.log10(max(upper, eps))
            values_t = np.log10(np.clip(column, max(lower, eps), upper))
        elif parameter.prior == "signed_log":
            scale = _parameter_min_abs(parameter)

            def signed(value: np.ndarray | float) -> np.ndarray | float:
                return np.sign(value) * np.log10(1.0 + np.abs(value) / scale)

            low_t = float(signed(lower))
            high_t = float(signed(upper))
            values_t = signed(column)
        else:
            low_t = lower
            high_t = upper
            values_t = column
        denom = high_t - low_t
        if not np.isfinite(denom) or abs(denom) <= 0.0:
            transformed[:, index] = 0.5
        else:
            transformed[:, index] = np.clip((values_t - low_t) / denom, 0.0, 1.0)
    return transformed[0] if was_1d else transformed


def _inverse_prior_transform_values(values: np.ndarray, parameters: Sequence[ScanParameterSpec]) -> np.ndarray:
    unit = np.clip(np.asarray(values, dtype=float), 0.0, 1.0)
    was_1d = unit.ndim == 1
    if was_1d:
        unit = unit.reshape(1, -1)
    lower = np.asarray([parameter.lower for parameter in parameters], dtype=float)
    upper = np.asarray([parameter.upper for parameter in parameters], dtype=float)
    points = _scale_unit_points(unit, parameters, lower, upper)
    return points[0] if was_1d else points


def _generic_box_from_points(
    *,
    points: np.ndarray,
    best_objective: float,
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    box_options: dict[str, Any],
    box_type: str,
    source_point_count: int,
    global_best_point: np.ndarray | None = None,
) -> dict[str, Any] | None:
    if points.size == 0 or not box_options.get("enabled", True):
        return None
    original_width = upper - lower
    q_low = np.quantile(points, float(box_options["quantile_low"]), axis=0)
    q_high = np.quantile(points, float(box_options["quantile_high"]), axis=0)
    width = q_high - q_low
    low = q_low - float(box_options["padding_fraction"]) * width
    high = q_high + float(box_options["padding_fraction"]) * width
    min_width = np.maximum(
        float(box_options["min_width_fraction"]) * original_width,
        original_width / float(box_options["max_shrink_factor"]),
    )
    current_width = high - low
    too_narrow = (~np.isfinite(current_width)) | (current_width < min_width)
    center = 0.5 * (q_low + q_high)
    low = np.where(too_narrow, center - 0.5 * min_width, low)
    high = np.where(too_narrow, center + 0.5 * min_width, high)
    invalid = (~np.isfinite(low)) | (~np.isfinite(high)) | (high <= low)
    low = np.where(invalid, lower, low)
    high = np.where(invalid, upper, high)
    if box_options["clip_to_original_bounds"]:
        low = np.clip(low, lower, upper)
        high = np.clip(high, lower, upper)
    high = np.maximum(high, low)
    return _box_from_bounds(
        box_id=0,
        box_type=box_type,
        low=low,
        high=high,
        lower=lower,
        upper=upper,
        request=request,
        source_round=-1,
        source_point_count=source_point_count,
        best_objective=best_objective,
        global_best_point=global_best_point,
    )


def _write_parameter_points_csv(
    path: Path,
    *,
    points: np.ndarray,
    request: ScanRequest,
    extras: list[dict[str, Any]] | None = None,
) -> None:
    extras = extras or [{} for _ in range(points.shape[0])]
    extra_keys = sorted({key for item in extras for key in item})
    fieldnames = ["point_id", *extra_keys, *[f"param::{parameter.name}" for parameter in request.scanned_parameters]]
    rows: list[dict[str, Any]] = []
    for index, point in enumerate(points):
        row: dict[str, Any] = {"point_id": index}
        row.update(extras[index] if index < len(extras) else {})
        for parameter, value in zip(request.scanned_parameters, point, strict=True):
            row[f"param::{parameter.name}"] = float(value)
        rows.append(row)
    _write_rows_csv(path, fieldnames, rows)


def _manifold_source_arrays(
    *,
    exploration_points: np.ndarray,
    exploration_records: list[dict[str, Any]],
    selected_points: np.ndarray,
    selected_records: list[dict[str, Any]],
    options: dict[str, Any],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    source = options["manifold_refocus"]["source"]
    if source == "exploration":
        return exploration_points, exploration_records
    if source == "selected_plus_exploration":
        if selected_points.size == 0:
            return exploration_points, exploration_records
        if exploration_points.size == 0:
            return selected_points, selected_records
        return np.vstack([selected_points, exploration_points]), [*selected_records, *exploration_records]
    return selected_points, selected_records


def _manifold_training_indices(
    *,
    records: list[dict[str, Any]],
    invalid_objective: float,
    options: dict[str, Any],
) -> np.ndarray:
    manifold = options["manifold_refocus"]
    targets = np.asarray([_record_target(record, invalid_objective) for record in records], dtype=float)
    valid = np.asarray([bool(record.get("valid", False)) for record in records], dtype=bool)
    finite = np.isfinite(targets) & valid & (targets < invalid_objective)
    candidates = np.flatnonzero(finite)
    if candidates.size == 0:
        return candidates
    order = candidates[np.argsort(targets[candidates])]
    top_fraction = float(manifold["top_fraction_for_training"])
    if top_fraction <= 0.0 or top_fraction > 1.0:
        top_fraction = 1.0
    n_top = max(int(np.ceil(order.size * top_fraction)), int(manifold["min_train_points"]))
    n_top = min(n_top, order.size, int(manifold["max_train_points"]))
    return order[:n_top]


def _run_manifold_refocus_stage(
    *,
    exploration_points: np.ndarray,
    exploration_records: list[dict[str, Any]],
    selected_points: np.ndarray,
    selected_records: list[dict[str, Any]],
    boxes: list[dict[str, Any]],
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    writer: _PythonScanArtifactsWriter,
) -> dict[str, Any]:
    manifold = options["manifold_refocus"]
    diagnostics: dict[str, Any] = {
        "enabled": bool(manifold["enabled"]),
        "method": manifold["method"],
        "box_created": False,
        "fallback_used": False,
        "fallback_reason": None,
    }
    if not manifold["enabled"]:
        return {"boxes": boxes, "diagnostics": diagnostics}

    source_points, source_records = _manifold_source_arrays(
        exploration_points=exploration_points,
        exploration_records=exploration_records,
        selected_points=selected_points,
        selected_records=selected_records,
        options=options,
    )
    train_indices = _manifold_training_indices(
        records=source_records,
        invalid_objective=request.invalid_objective,
        options=options,
    )
    min_train = int(manifold["min_train_points"])
    if train_indices.size < min_train:
        diagnostics.update(
            {
                "fallback_used": True,
                "fallback_reason": "too_few_training_points",
                "n_train_points": int(train_indices.size),
            }
        )
        (writer.run_directory / "manifold_refocus_diagnostics.json").write_text(
            json.dumps(_json_ready(diagnostics), indent=2),
            encoding="utf-8",
        )
        return {"boxes": boxes, "diagnostics": diagnostics}

    targets = np.asarray([_record_target(record, request.invalid_objective) for record in source_records], dtype=float)
    train_points = source_points[train_indices]
    train_targets = targets[train_indices]
    train_features = _ml_focus_transform_values(train_points, request.scanned_parameters)
    center = np.mean(train_features, axis=0)
    if train_features.shape[0] > 1:
        covariance = np.cov(train_features, rowvar=False)
    else:
        covariance = np.eye(train_features.shape[1], dtype=float) * float(manifold["diagonal_jitter"])
    covariance = np.atleast_2d(np.asarray(covariance, dtype=float))
    jitter = float(manifold["diagonal_jitter"])
    covariance = covariance + np.eye(covariance.shape[0]) * jitter
    inflate = float(manifold["inflate"])
    covariance = covariance * max(inflate, 0.0) ** 2
    rng = np.random.default_rng(int(manifold["seed"]))
    try:
        sampled_features = rng.multivariate_normal(
            mean=center,
            cov=covariance,
            size=int(manifold["n_candidates"]),
            check_valid="ignore",
        )
    except Exception:
        sampled_features = rng.normal(
            loc=center,
            scale=np.sqrt(np.clip(np.diag(covariance), 1.0e-12, None)),
            size=(int(manifold["n_candidates"]), train_features.shape[1]),
        )
    sampled_features = np.clip(sampled_features, 0.0, 1.0)
    candidate_points = _inverse_prior_transform_values(sampled_features, request.scanned_parameters)
    candidate_points = np.clip(candidate_points, lower, upper)
    focus_chunks = [candidate_points]
    candidate_extras = [{"source": "covariance_sample"} for _ in range(candidate_points.shape[0])]
    if manifold["include_training_points"]:
        focus_chunks.append(train_points)
    focus_points = _deduplicate_points(np.vstack(focus_chunks))
    best_index = int(train_indices[int(np.argmin(train_targets))])
    best_point = source_points[best_index]
    best_objective = float(np.min(train_targets))
    box = _generic_box_from_points(
        points=focus_points,
        best_objective=best_objective,
        lower=lower,
        upper=upper,
        request=request,
        box_options=manifold["box"],
        box_type="manifold_refocus",
        source_point_count=int(train_points.shape[0]),
        global_best_point=best_point,
    )
    if box is None:
        diagnostics.update(
            {
                "fallback_used": True,
                "fallback_reason": "box_disabled_or_failed",
                "n_train_points": int(train_indices.size),
            }
        )
        (writer.run_directory / "manifold_refocus_diagnostics.json").write_text(
            json.dumps(_json_ready(diagnostics), indent=2),
            encoding="utf-8",
        )
        return {"boxes": boxes, "diagnostics": diagnostics}

    original_widths = {parameter.name: float(upper[index] - lower[index]) for index, parameter in enumerate(request.scanned_parameters)}
    focused_widths = {
        parameter.name: float(box["upper"][parameter.name]) - float(box["lower"][parameter.name])
        for parameter in request.scanned_parameters
    }
    shrink_factors = {
        name: (original_widths[name] / focused_widths[name] if focused_widths[name] > 0.0 else np.inf)
        for name in original_widths
    }
    diagnostics.update(
        {
            "box_created": True,
            "fallback_used": False,
            "fallback_reason": None,
            "source": manifold["source"],
            "n_source_points": int(source_points.shape[0]),
            "n_train_points": int(train_points.shape[0]),
            "n_candidates": int(candidate_points.shape[0]),
            "n_focus_points": int(focus_points.shape[0]),
            "best_training_objective": best_objective,
            "relative_box_volume": float(box["relative_box_volume"]),
            "original_widths": original_widths,
            "focused_widths": focused_widths,
            "shrink_factors": shrink_factors,
        }
    )
    train_extras = [
        {
            "objective": float(train_targets[index]),
            "valid": bool(source_records[int(train_indices[index])].get("valid", False)),
        }
        for index in range(train_points.shape[0])
    ]
    _write_parameter_points_csv(
        writer.run_directory / "manifold_refocus_training.csv",
        points=train_points,
        request=request,
        extras=train_extras,
    )
    _write_parameter_points_csv(
        writer.run_directory / "manifold_refocus_candidates.csv",
        points=candidate_points,
        request=request,
        extras=candidate_extras,
    )
    (writer.run_directory / "manifold_refocus_box.json").write_text(
        json.dumps(_json_ready({"box": box}), indent=2),
        encoding="utf-8",
    )
    (writer.run_directory / "manifold_refocus_diagnostics.json").write_text(
        json.dumps(_json_ready(diagnostics), indent=2),
        encoding="utf-8",
    )
    return {"boxes": [box], "diagnostics": diagnostics}


def _ml_focus_training_indices(
    *,
    records: list[dict[str, Any]],
    invalid_objective: float,
    options: dict[str, Any],
) -> np.ndarray:
    training = options["ml_focus"]["training"]
    targets = np.asarray([_record_target(record, invalid_objective) for record in records], dtype=float)
    finite = np.isfinite(targets) & (targets < invalid_objective)
    if training["finite_objective_only"]:
        mask = finite
    else:
        mask = targets < invalid_objective
    if training["require_valid"]:
        valid = np.asarray([bool(record.get("valid", False)) for record in records], dtype=bool)
        valid_mask = mask & valid
        if np.count_nonzero(valid_mask) >= int(training["min_train_points"]):
            mask = valid_mask
    indices = np.flatnonzero(mask)
    if indices.size == 0:
        return indices
    indices = indices[np.argsort(targets[indices])]
    top_fraction = training.get("top_fraction_for_training")
    if top_fraction is not None and 0.0 < float(top_fraction) < 1.0:
        keep = max(int(training["min_train_points"]), int(ceil(float(top_fraction) * indices.size)))
        indices = indices[:keep]
    max_train = int(training["max_train_points"])
    if indices.size > max_train:
        best_keep = max(1, max_train // 2)
        rng = np.random.default_rng(int(options["ml_focus"]["seed"]) + 17)
        head = indices[:best_keep]
        tail = indices[best_keep:]
        sampled_tail = rng.choice(tail, size=max_train - best_keep, replace=False) if tail.size else np.asarray([], dtype=int)
        indices = np.asarray([*head.tolist(), *sampled_tail.tolist()], dtype=int)
        indices = indices[np.argsort(targets[indices])]
    return indices


def _ml_focus_target(values: np.ndarray) -> np.ndarray:
    return np.log10(np.maximum(1.0 + np.asarray(values, dtype=float), 1.0e-300))


def _sample_points_in_box(
    *,
    n_points: int,
    box: dict[str, Any],
    request: ScanRequest,
    method: str,
    seed: int,
) -> np.ndarray:
    if n_points <= 0:
        return np.empty((0, len(request.scanned_parameters)), dtype=float)
    focused_parameters = [
        replace(
            parameter,
            lower=float(box["lower"][parameter.name]),
            upper=float(box["upper"][parameter.name]),
        )
        for parameter in request.scanned_parameters
    ]
    return _sample_prior_points(
        n_points=n_points,
        parameters=focused_parameters,
        seed=seed,
        method=method,
    )


def _deduplicate_points(points: np.ndarray, *, decimals: int = 12) -> np.ndarray:
    array = np.asarray(points, dtype=float)
    if array.size == 0:
        return array.reshape(0, 0) if array.ndim == 1 else array
    if array.ndim == 1:
        array = array.reshape(1, -1)
    rounded = np.round(array, decimals=decimals)
    _, indices = np.unique(rounded, axis=0, return_index=True)
    return array[np.sort(indices)]


def _ml_focus_local_mutations(
    *,
    seeds: np.ndarray,
    n_points: int,
    request: ScanRequest,
    lower: np.ndarray,
    upper: np.ndarray,
    rng: np.random.Generator,
    relative_sigma: float,
    log_sigma: float,
) -> np.ndarray:
    dimension = len(request.scanned_parameters)
    if n_points <= 0 or seeds.size == 0:
        return np.empty((0, dimension), dtype=float)
    seeds = np.asarray(seeds, dtype=float).reshape(-1, dimension)
    original_width = upper - lower
    output = np.empty((n_points, dimension), dtype=float)
    for row in range(n_points):
        base = seeds[int(rng.integers(0, seeds.shape[0]))].copy()
        proposal = base.copy()
        for index, parameter in enumerate(request.scanned_parameters):
            if parameter.prior == "log" and base[index] > 0.0 and lower[index] > 0.0:
                proposal[index] = 10.0 ** (np.log10(base[index]) + rng.normal(0.0, log_sigma))
            else:
                proposal[index] = base[index] + rng.normal(0.0, relative_sigma * original_width[index])
        output[row, :] = np.clip(proposal, lower, upper)
    return output


def _ml_focus_candidate_points(
    *,
    boxes: list[dict[str, Any]],
    best_real_points: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    lower: np.ndarray,
    upper: np.ndarray,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    ml_options = options["ml_focus"]
    n_candidates = int(ml_options["candidate_generation"]["n_candidates"])
    fractions = dict(ml_options["candidate_generation"]["sources"])
    total_fraction = sum(float(value) for value in fractions.values())
    normalized = {key: float(value) / total_fraction for key, value in fractions.items()}
    counts = {key: int(np.floor(n_candidates * fraction)) for key, fraction in normalized.items()}
    remainder = n_candidates - sum(counts.values())
    for key in sorted(normalized, key=normalized.get, reverse=True)[:remainder]:
        counts[key] += 1
    rng = np.random.default_rng(int(ml_options["seed"]) + 101)
    chunks: list[np.ndarray] = []
    extras: list[dict[str, Any]] = []
    method = str(options["exploration"]["method"])
    selected_count = counts.get("selected_box_fraction", 0)
    if selected_count > 0 and boxes:
        per_box = [selected_count // len(boxes)] * len(boxes)
        for index in range(selected_count % len(boxes)):
            per_box[index] += 1
        for box_index, (box, count) in enumerate(zip(boxes, per_box, strict=True)):
            sampled = _sample_points_in_box(
                n_points=count,
                box=box,
                request=request,
                method=method,
                seed=int(ml_options["seed"]) + 1000 + box_index,
            )
            chunks.append(sampled)
            extras.extend({"candidate_source": "selected_box", "box_id": box_index} for _ in range(sampled.shape[0]))
    global_count = counts.get("global_fraction", 0)
    if global_count > 0:
        sampled = _sample_basin_exploration(
            n_points=global_count,
            dimension=len(request.scanned_parameters),
            lower=lower,
            upper=upper,
            method=method,
            seed=int(ml_options["seed"]) + 2000,
            parameters=request.scanned_parameters,
        )
        chunks.append(sampled)
        extras.extend({"candidate_source": "global", "box_id": ""} for _ in range(sampled.shape[0]))
    elite_count = counts.get("elite_local_fraction", 0)
    if elite_count > 0 and best_real_points.size:
        sampled = _ml_focus_local_mutations(
            seeds=best_real_points,
            n_points=elite_count,
            request=request,
            lower=lower,
            upper=upper,
            rng=rng,
            relative_sigma=float(ml_options["seeds"]["local_mutation"]["relative_sigma"]),
            log_sigma=float(ml_options["seeds"]["local_mutation"]["log_sigma"]),
        )
        chunks.append(sampled)
        extras.extend({"candidate_source": "elite_local", "box_id": ""} for _ in range(sampled.shape[0]))
    if not chunks:
        return np.empty((0, len(request.scanned_parameters)), dtype=float), []
    return np.vstack(chunks), extras


def _ml_focus_box_from_points(
    *,
    points: np.ndarray,
    best_objective: float,
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
) -> dict[str, Any] | None:
    if points.size == 0:
        return None
    box_options = options["ml_focus"]["focused_box"]
    original_width = upper - lower
    q_low = np.quantile(points, float(box_options["quantile_low"]), axis=0)
    q_high = np.quantile(points, float(box_options["quantile_high"]), axis=0)
    width = q_high - q_low
    low = q_low - float(box_options["padding_fraction"]) * width
    high = q_high + float(box_options["padding_fraction"]) * width
    min_width = np.maximum(
        float(box_options["min_width_fraction"]) * original_width,
        original_width / float(box_options["max_shrink_factor"]),
    )
    current_width = high - low
    too_narrow = (~np.isfinite(current_width)) | (current_width < min_width)
    center = 0.5 * (q_low + q_high)
    low = np.where(too_narrow, center - 0.5 * min_width, low)
    high = np.where(too_narrow, center + 0.5 * min_width, high)
    invalid = (~np.isfinite(low)) | (~np.isfinite(high)) | (high <= low)
    low = np.where(invalid, lower, low)
    high = np.where(invalid, upper, high)
    if box_options["clip_to_original_bounds"]:
        low = np.clip(low, lower, upper)
        high = np.clip(high, lower, upper)
    high = np.maximum(high, low)
    return _box_from_bounds(
        box_id=0,
        box_type="ml_focus",
        low=low,
        high=high,
        lower=lower,
        upper=upper,
        request=request,
        source_round=-1,
        source_point_count=int(points.shape[0]),
        best_objective=best_objective,
        global_best_point=points[0] if points.size else None,
    )


def _points_inside_box(points: np.ndarray, box: dict[str, Any], request: ScanRequest) -> np.ndarray:
    if points.size == 0:
        return points.reshape(0, len(request.scanned_parameters))
    lower = np.asarray([float(box["lower"][parameter.name]) for parameter in request.scanned_parameters], dtype=float)
    upper = np.asarray([float(box["upper"][parameter.name]) for parameter in request.scanned_parameters], dtype=float)
    mask = np.all((points >= lower) & (points <= upper), axis=1)
    return points[mask]


def _build_ml_focus_seeds(
    *,
    best_real_points: np.ndarray,
    ml_selected_points: np.ndarray,
    box: dict[str, Any],
    request: ScanRequest,
    options: dict[str, Any],
    lower: np.ndarray,
    upper: np.ndarray,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    seed_options = options["ml_focus"]["seeds"]
    if not seed_options["enabled"]:
        return np.empty((0, len(request.scanned_parameters)), dtype=float), []
    max_seeds = int(seed_options["max_seeds"])
    fractions = dict(seed_options["composition"])
    total = sum(float(value) for value in fractions.values())
    normalized = {key: float(value) / total for key, value in fractions.items()}
    counts = {key: int(np.floor(max_seeds * value)) for key, value in normalized.items()}
    remainder = max_seeds - sum(counts.values())
    for key in sorted(normalized, key=normalized.get, reverse=True)[:remainder]:
        counts[key] += 1
    chunks: list[np.ndarray] = []
    extras: list[dict[str, Any]] = []
    best_inside = _points_inside_box(best_real_points, box, request)
    ml_inside = _points_inside_box(ml_selected_points, box, request)
    best_count = min(counts.get("best_real_fraction", 0), best_inside.shape[0])
    if best_count:
        chunks.append(best_inside[:best_count])
        extras.extend({"seed_source": "best_real"} for _ in range(best_count))
    ml_count = min(counts.get("ml_selected_fraction", 0), ml_inside.shape[0])
    if ml_count:
        chunks.append(ml_inside[:ml_count])
        extras.extend({"seed_source": "ml_selected"} for _ in range(ml_count))
    mutation_count = counts.get("local_mutation_fraction", 0)
    mutation_bases = best_inside if best_inside.size else best_real_points
    if mutation_count and mutation_bases.size:
        box_lower = np.asarray([float(box["lower"][parameter.name]) for parameter in request.scanned_parameters], dtype=float)
        box_upper = np.asarray([float(box["upper"][parameter.name]) for parameter in request.scanned_parameters], dtype=float)
        sampled = _ml_focus_local_mutations(
            seeds=mutation_bases,
            n_points=mutation_count,
            request=request,
            lower=box_lower,
            upper=box_upper,
            rng=np.random.default_rng(int(options["ml_focus"]["seed"]) + 303),
            relative_sigma=float(seed_options["local_mutation"]["relative_sigma"]),
            log_sigma=float(seed_options["local_mutation"]["log_sigma"]),
        )
        sampled = np.clip(sampled, lower, upper)
        chunks.append(sampled)
        extras.extend({"seed_source": "local_mutation"} for _ in range(sampled.shape[0]))
    if not chunks:
        return np.empty((0, len(request.scanned_parameters)), dtype=float), []
    seeds = _deduplicate_points(np.vstack(chunks))[:max_seeds]
    return seeds, extras[: seeds.shape[0]]


def _write_ml_focus_points_csv(
    path: Path,
    *,
    points: np.ndarray,
    request: ScanRequest,
    extras: list[dict[str, Any]] | None = None,
) -> None:
    extras = extras or [{} for _ in range(points.shape[0])]
    extra_keys = sorted({key for item in extras for key in item})
    fieldnames = ["point_id", *extra_keys, *[f"param::{parameter.name}" for parameter in request.scanned_parameters]]
    rows: list[dict[str, Any]] = []
    for index, point in enumerate(points):
        row: dict[str, Any] = {"point_id": index}
        row.update(extras[index] if index < len(extras) else {})
        for parameter, value in zip(request.scanned_parameters, point, strict=True):
            row[f"param::{parameter.name}"] = float(value)
        rows.append(row)
    _write_rows_csv(path, fieldnames, rows)


def _run_ml_focus_stage(
    *,
    exploration_points: np.ndarray,
    exploration_records: list[dict[str, Any]],
    selected_points: np.ndarray,
    selected_records: list[dict[str, Any]],
    boxes: list[dict[str, Any]],
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    writer: _PythonScanArtifactsWriter,
) -> dict[str, Any]:
    ml_options = options["ml_focus"]
    diagnostics: dict[str, Any] = {
        "enabled": bool(ml_options["enabled"]),
        "target": "log10_1p_objective",
        "model": "ExtraTreesRegressor",
        "focused_box_created": False,
        "fallback_used": False,
        "fallback_reason": None,
    }
    if not ml_options["enabled"]:
        return {"boxes": boxes, "seeds_by_box": {}, "diagnostics": diagnostics}
    try:
        ensemble = importlib.import_module("sklearn.ensemble")
    except Exception as exc:
        raise ModelValidationError(
            "basin_scan.ml_focus requires scikit-learn when enabled. Install scikit-learn or set ml_focus.enabled: false."
        ) from exc

    train_indices = _ml_focus_training_indices(
        records=exploration_records,
        invalid_objective=request.invalid_objective,
        options=options,
    )
    min_train = int(ml_options["training"]["min_train_points"])
    if train_indices.size < min_train:
        diagnostics.update(
            {
                "fallback_used": True,
                "fallback_reason": "too_few_training_points",
                "n_train_points": int(train_indices.size),
            }
        )
        (writer.run_directory / "ml_focus_diagnostics.json").write_text(
            json.dumps(_json_ready(diagnostics), indent=2),
            encoding="utf-8",
        )
        return {"boxes": boxes, "seeds_by_box": {}, "diagnostics": diagnostics}

    targets = np.asarray([_record_target(record, request.invalid_objective) for record in exploration_records], dtype=float)
    train_points = exploration_points[train_indices]
    train_targets = targets[train_indices]
    train_features = _ml_focus_transform_values(train_points, request.scanned_parameters)
    y_train = _ml_focus_target(train_targets)
    model = ensemble.ExtraTreesRegressor(
        n_estimators=int(ml_options["model"]["n_estimators"]),
        min_samples_leaf=int(ml_options["model"]["min_samples_leaf"]),
        max_features=ml_options["model"]["max_features"],
        random_state=int(ml_options["seed"]),
        n_jobs=1,
    )
    model.fit(train_features, y_train)

    order = train_indices[np.argsort(targets[train_indices])]
    n_best = min(int(ml_options["selection"]["n_best_real_points"]), order.size)
    best_real_points = exploration_points[order[:n_best]] if n_best else np.empty((0, len(request.scanned_parameters)))
    candidate_points, candidate_extras = _ml_focus_candidate_points(
        boxes=boxes,
        best_real_points=best_real_points,
        request=request,
        options=options,
        lower=lower,
        upper=upper,
    )
    if candidate_points.size == 0:
        diagnostics.update(
            {
                "fallback_used": True,
                "fallback_reason": "no_candidates_generated",
                "n_train_points": int(train_indices.size),
            }
        )
        (writer.run_directory / "ml_focus_diagnostics.json").write_text(
            json.dumps(_json_ready(diagnostics), indent=2),
            encoding="utf-8",
        )
        return {"boxes": boxes, "seeds_by_box": {}, "diagnostics": diagnostics}

    predicted = np.asarray(model.predict(_ml_focus_transform_values(candidate_points, request.scanned_parameters)), dtype=float)
    ranked = np.argsort(predicted)
    n_selected = min(int(ml_options["selection"]["n_ml_selected"]), ranked.size)
    selected_candidate_indices = ranked[:n_selected]
    ml_selected_points = candidate_points[selected_candidate_indices]
    ml_selected_extras = [
        {
            **candidate_extras[int(index)],
            "predicted_log10_1p_nll": float(predicted[int(index)]),
        }
        for index in selected_candidate_indices
    ]
    selected_for_focus_chunks = [ml_selected_points]
    if ml_options["selection"]["include_best_real_points"] and best_real_points.size:
        selected_for_focus_chunks.append(best_real_points)
    if ml_options["selection"]["include_elite_archive"] and selected_points.size:
        selected_for_focus_chunks.append(selected_points)
    selected_for_focus = _deduplicate_points(np.vstack(selected_for_focus_chunks))
    best_training_objective = float(np.min(train_targets))
    ml_box = _ml_focus_box_from_points(
        points=selected_for_focus,
        best_objective=best_training_objective,
        lower=lower,
        upper=upper,
        request=request,
        options=options,
    )
    if ml_box is None or not ml_options["focused_box"]["enabled"]:
        diagnostics.update(
            {
                "fallback_used": True,
                "fallback_reason": "focused_box_disabled_or_failed",
                "n_train_points": int(train_indices.size),
            }
        )
        (writer.run_directory / "ml_focus_diagnostics.json").write_text(
            json.dumps(_json_ready(diagnostics), indent=2),
            encoding="utf-8",
        )
        return {"boxes": boxes, "seeds_by_box": {}, "diagnostics": diagnostics}

    seed_points, seed_extras = _build_ml_focus_seeds(
        best_real_points=best_real_points,
        ml_selected_points=ml_selected_points,
        box=ml_box,
        request=request,
        options=options,
        lower=lower,
        upper=upper,
    )
    original_widths = {parameter.name: float(upper[index] - lower[index]) for index, parameter in enumerate(request.scanned_parameters)}
    focused_widths = {
        parameter.name: float(ml_box["upper"][parameter.name]) - float(ml_box["lower"][parameter.name])
        for parameter in request.scanned_parameters
    }
    shrink_factors = {
        name: (original_widths[name] / focused_widths[name] if focused_widths[name] > 0.0 else np.inf)
        for name in original_widths
    }
    feature_importance = {
        parameter.name: float(value)
        for parameter, value in zip(request.scanned_parameters, getattr(model, "feature_importances_", []), strict=False)
    }
    diagnostics.update(
        {
            "n_train_points": int(train_indices.size),
            "n_candidates": int(candidate_points.shape[0]),
            "n_ml_selected": int(ml_selected_points.shape[0]),
            "n_best_real_points": int(best_real_points.shape[0]),
            "n_seeds": int(seed_points.shape[0]),
            "focused_box_created": True,
            "fallback_used": False,
            "fallback_reason": None,
            "best_training_objective": best_training_objective,
            "best_predicted_candidate_score": float(np.min(predicted)) if predicted.size else None,
            "original_widths": original_widths,
            "focused_widths": focused_widths,
            "shrink_factors": shrink_factors,
            "feature_importance": feature_importance,
        }
    )

    train_extras = [
        {
            "objective": float(train_targets[index]),
            "target_log10_1p_objective": float(y_train[index]),
            "valid": bool(exploration_records[int(train_indices[index])].get("valid", False)),
        }
        for index in range(train_points.shape[0])
    ]
    candidate_output_extras = [
        {
            **candidate_extras[index],
            "predicted_log10_1p_nll": float(predicted[index]),
        }
        for index in range(candidate_points.shape[0])
    ]
    _write_ml_focus_points_csv(writer.run_directory / "ml_focus_training.csv", points=train_points, request=request, extras=train_extras)
    _write_ml_focus_points_csv(writer.run_directory / "ml_focus_candidates.csv", points=candidate_points, request=request, extras=candidate_output_extras)
    _write_ml_focus_points_csv(writer.run_directory / "ml_focus_selected.csv", points=ml_selected_points, request=request, extras=ml_selected_extras)
    _write_ml_focus_points_csv(writer.run_directory / "ml_focus_seeds.csv", points=seed_points, request=request, extras=seed_extras)
    (writer.run_directory / "ml_focus_box.json").write_text(
        json.dumps(_json_ready({"box": ml_box}), indent=2),
        encoding="utf-8",
    )
    (writer.run_directory / "ml_focus_diagnostics.json").write_text(
        json.dumps(_json_ready(diagnostics), indent=2),
        encoding="utf-8",
    )
    return {"boxes": [ml_box], "seeds_by_box": {0: seed_points.tolist()}, "diagnostics": diagnostics}


def _evaluate_basin_points(
    *,
    objective: _AdaptiveDiverObjective,
    points: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    label: str,
    start_index: int = 0,
    staged_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    progress_interval = int(options["progress_interval"])
    total = points.shape[0]
    for local_index, point in enumerate(points, start=1):
        if staged_context is None:
            record = objective.evaluate(point)
        else:
            cheap_record = _evaluate_cheap_stage_record(staged_context, request, point)
            passes, cheap_objective, hard_failures, cheap_terms = _cheap_stage_passes(
                cheap_record,
                options,
            )
            cheap_record["objective_cheap"] = cheap_objective
            cheap_record["objective_full"] = ""
            cheap_record["hard_failures"] = hard_failures
            cheap_record["fit_failures"] = 0
            cheap_record["terms_evaluated"] = cheap_terms
            cheap_record["_staged_materialized"] = True
            if passes:
                objective.record_evaluation(
                    cheap_record,
                    write=False,
                    count_valid=False,
                    count_best=False,
                )
                record = objective.evaluate(
                    point,
                    write=bool(options["staged_evaluation"]["save_full_eval_points"]),
                )
                record["objective_cheap"] = cheap_objective
                record["objective_full"] = _record_target(record, request.invalid_objective)
                record["hard_failures"] = _record_hard_failures(record)
                record["fit_failures"] = _record_fit_failures(record)
                record["stage_reached"] = "full"
                record["accepted"] = _record_accepted(record, request.invalid_objective)
                record["terms_evaluated"] = sorted(set(cheap_terms) | set(_record_likelihood_terms(record)))
                record["_staged_materialized"] = True
            else:
                cheap_record["stage_reached"] = "cheap_rejected"
                cheap_record["accepted"] = False
                cheap_record["valid"] = False
                point_result = cheap_record.setdefault("point_result", {})
                point_result["valid"] = False
                if not point_result.get("failure_reason"):
                    point_result["failure_reason"] = "cheap_stage_rejected"
                record = objective.record_evaluation(
                    cheap_record,
                    write=bool(options["staged_evaluation"]["save_rejected_cheap_points"]),
                    count_valid=False,
                    count_best=False,
                )
        records.append(record)
        absolute_index = start_index + local_index
        if request.verbose > 0 and progress_interval > 0 and absolute_index % progress_interval == 0:
            best = None if objective.best_record is None else objective.best_record["scanner_target"]
            print(
                "[basin_scan] "
                f"{label} evaluated={local_index}/{total} | total={absolute_index} | valid={objective.valid_points}"
                + (f" | best_target={float(best):.12g}" if best is not None else ""),
                flush=True,
            )
    return records


def _allocate_points_to_boxes(
    *,
    total_points: int,
    boxes: list[dict[str, Any]],
    method: str,
    min_points_per_box: int,
) -> list[int]:
    n_boxes = len(boxes)
    if n_boxes == 0:
        return []
    if total_points <= 0:
        return [0 for _ in boxes]
    if method == "equal":
        base = total_points // n_boxes
        counts = [base for _ in boxes]
        for index in range(total_points - base * n_boxes):
            counts[index % n_boxes] += 1
        return counts

    volumes = np.asarray([max(float(box.get("relative_box_volume", 0.0)), 0.0) for box in boxes], dtype=float)
    if not np.isfinite(volumes).all() or float(np.sum(volumes)) <= 0.0:
        return _allocate_points_to_boxes(
            total_points=total_points,
            boxes=boxes,
            method="equal",
            min_points_per_box=min_points_per_box,
        )
    weights = volumes / float(np.sum(volumes))
    raw = weights * total_points
    counts = np.floor(raw).astype(int)
    minimum = min_points_per_box if total_points >= min_points_per_box * n_boxes else 1
    counts = np.maximum(counts, minimum)

    while int(np.sum(counts)) > total_points:
        candidates = np.flatnonzero(counts > minimum)
        if candidates.size == 0:
            candidates = np.flatnonzero(counts > 0)
        index = int(candidates[np.argmax(counts[candidates])])
        counts[index] -= 1
    while int(np.sum(counts)) < total_points:
        deficit_order = np.argsort(raw - counts)[::-1]
        for index in deficit_order:
            if int(np.sum(counts)) >= total_points:
                break
            counts[int(index)] += 1
    return [int(item) for item in counts]


def _box_bounds_arrays(
    box: dict[str, Any],
    *,
    request: ScanRequest,
) -> tuple[np.ndarray, np.ndarray]:
    lower = np.asarray([float(box["lower"][parameter.name]) for parameter in request.scanned_parameters], dtype=float)
    upper = np.asarray([float(box["upper"][parameter.name]) for parameter in request.scanned_parameters], dtype=float)
    return lower, upper


def _sample_box_points(
    *,
    box: dict[str, Any],
    count: int,
    dimension: int,
    request: ScanRequest,
    method: str,
    seed: int,
    global_lower: np.ndarray,
    global_upper: np.ndarray,
) -> np.ndarray:
    box_lower, box_upper = _box_bounds_arrays(box, request=request)
    chunk = _sample_basin_exploration(
        n_points=count,
        dimension=dimension,
        lower=box_lower,
        upper=box_upper,
        method=method,
        seed=seed,
        parameters=request.scanned_parameters,
    )
    return np.clip(chunk, global_lower, global_upper)


def _normalize_mixed_fractions(
    *,
    boxes_by_type: dict[str, list[dict[str, Any]]],
    requested: dict[str, float],
) -> dict[str, float]:
    category_available = {
        "elite_boxes": bool(boxes_by_type["elite_boxes"]),
        "selected_boxes": bool(boxes_by_type["selected_boxes"]),
        "global": True,
    }
    available = {key: value for key, value in requested.items() if category_available.get(key, False)}
    if not available:
        return {"global": 1.0}
    total = float(sum(available.values()))
    if total <= 0.0:
        return {"global": 1.0}
    return {key: float(value) / total for key, value in available.items()}


def _sample_progressive_round_points(
    *,
    round_index: int,
    n_points: int,
    boxes: list[dict[str, Any]],
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    seed: int,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    sampling = options["progressive_exploration"]["sampling"]
    method = str(sampling["method"])
    dimension = lower.size
    if round_index == 0 or not boxes:
        points = _sample_basin_exploration(
            n_points=n_points,
            dimension=dimension,
            lower=lower,
            upper=upper,
            method=method,
            seed=seed,
            parameters=request.scanned_parameters,
        )
        return points, [
            {"round_id": round_index, "box_id": -1, "source_type": "global"}
            for _ in range(points.shape[0])
        ]

    if str(sampling["allocate_points"]) == "mixed":
        boxes_by_type = {
            "elite_boxes": [box for box in boxes if box.get("box_type") in {"elite", "best_centered"}],
            "selected_boxes": [box for box in boxes if box.get("box_type") == "selected_cloud"],
        }
        fractions = _normalize_mixed_fractions(
            boxes_by_type=boxes_by_type,
            requested=dict(sampling["fractions"]),
        )
        category_counts = {key: int(np.floor(n_points * value)) for key, value in fractions.items()}
        while sum(category_counts.values()) < n_points:
            key = max(fractions, key=lambda item: fractions[item] * n_points - category_counts.get(item, 0))
            category_counts[key] = category_counts.get(key, 0) + 1
        point_chunks: list[np.ndarray] = []
        extras: list[dict[str, Any]] = []

        global_count = int(category_counts.get("global", 0))
        if global_count > 0:
            chunk = _sample_basin_exploration(
                n_points=global_count,
                dimension=dimension,
                lower=lower,
                upper=upper,
                method=method,
                seed=seed + 17,
                parameters=request.scanned_parameters,
            )
            point_chunks.append(chunk)
            extras.extend(
                {"round_id": round_index, "box_id": -1, "source_type": "global"}
                for _ in range(chunk.shape[0])
            )

        for category, source_type in [("elite_boxes", "elite"), ("selected_boxes", "selected_cloud")]:
            category_boxes = boxes_by_type[category]
            count = int(category_counts.get(category, 0))
            if count <= 0 or not category_boxes:
                continue
            counts = _allocate_points_to_boxes(
                total_points=count,
                boxes=category_boxes,
                method="proportional_volume",
                min_points_per_box=int(sampling["min_points_per_box"]),
            )
            for local_box_index, (box, box_count) in enumerate(zip(category_boxes, counts, strict=True)):
                if box_count <= 0:
                    continue
                actual_source_type = str(box.get("box_type", source_type))
                chunk = _sample_box_points(
                    box=box,
                    count=box_count,
                    dimension=dimension,
                    request=request,
                    method=method,
                    seed=seed + 1009 * round_index + 37 * local_box_index + (0 if category == "elite_boxes" else 5003),
                    global_lower=lower,
                    global_upper=upper,
                )
                point_chunks.append(chunk)
                extras.extend(
                    {
                        "round_id": round_index,
                        "box_id": int(box.get("box_id", local_box_index)),
                        "source_type": actual_source_type,
                    }
                    for _ in range(chunk.shape[0])
                )
        if not point_chunks:
            return np.empty((0, dimension), dtype=float), []
        return np.vstack(point_chunks), extras

    counts = _allocate_points_to_boxes(
        total_points=n_points,
        boxes=boxes,
        method=str(sampling["allocate_points"]),
        min_points_per_box=int(sampling["min_points_per_box"]),
    )
    point_chunks: list[np.ndarray] = []
    extras: list[dict[str, Any]] = []
    for box_index, (box, count) in enumerate(zip(boxes, counts, strict=True)):
        if count <= 0:
            continue
        chunk = _sample_box_points(
            box=box,
            count=count,
            dimension=dimension,
            request=request,
            method=method,
            seed=seed + 1009 * round_index + box_index,
            global_lower=lower,
            global_upper=upper,
        )
        point_chunks.append(chunk)
        extras.extend(
            {
                "round_id": round_index,
                "box_id": int(box.get("box_id", box_index)),
                "source_type": str(box.get("box_type", "selected_cloud")),
            }
            for _ in range(chunk.shape[0])
        )
    if not point_chunks:
        return np.empty((0, dimension), dtype=float), []
    return np.vstack(point_chunks), extras


def _round_selection_options(options: dict[str, Any]) -> dict[str, Any]:
    return {"selection": dict(options["progressive_exploration"]["selection"])}


def _round_box_options(
    options: dict[str, Any],
    *,
    round_index: int = -1,
    global_best_point: np.ndarray | None = None,
) -> dict[str, Any]:
    progressive = options["progressive_exploration"]
    clustering = dict(options["clustering"])
    clustering["max_clusters"] = int(progressive["boxes"]["max_boxes"])
    boxes = dict(progressive["boxes"])
    boxes["box_type"] = "selected_cloud"
    boxes["source_round"] = round_index
    if global_best_point is not None:
        boxes["global_best_point"] = global_best_point.tolist()
    return {
        "clustering": clustering,
        "boxes": boxes,
    }


def _round_summary(
    *,
    round_index: int,
    points: np.ndarray,
    records: list[dict[str, Any]],
    selected_points: np.ndarray,
    boxes: list[dict[str, Any]],
    extras: list[dict[str, Any]],
    invalid_objective: float,
    global_best_target: float,
    global_best_round: int,
    improved_global_best: bool,
) -> dict[str, Any]:
    valid_records = [record for record in records if bool(record.get("valid", False))]
    finite_targets = [
        _record_target(record, invalid_objective)
        for record in records
        if np.isfinite(_record_target(record, invalid_objective))
    ]
    valid_targets = [
        _record_target(record, invalid_objective)
        for record in valid_records
        if np.isfinite(_record_target(record, invalid_objective))
        and _record_target(record, invalid_objective) < invalid_objective
    ]
    best = min(valid_targets) if valid_targets else (min(finite_targets) if finite_targets else invalid_objective)
    return {
        "round_id": round_index,
        "evaluated_points": int(points.shape[0]),
        "finite_points": int(len(finite_targets)),
        "valid_points": int(len(valid_records)),
        "best_objective": float(best),
        "best_chi2": float(2.0 * best),
        "global_best_objective_after_round": float(global_best_target),
        "global_best_chi2_after_round": float(2.0 * global_best_target),
        "global_best_round": int(global_best_round),
        "improved_global_best": bool(improved_global_best),
        "selected_points": int(selected_points.shape[0]),
        "boxes": len(boxes),
        "box_type_counts": _box_type_counts(boxes),
        "box_relative_volumes": [float(box.get("relative_box_volume", 0.0)) for box in boxes],
        "box_relative_volumes_by_type": {
            box_type: [
                float(box.get("relative_box_volume", 0.0))
                for box in boxes
                if str(box.get("box_type", "selected_cloud")) == box_type
            ]
            for box_type in sorted({str(box.get("box_type", "selected_cloud")) for box in boxes})
        },
        "sampling_fractions_actual": _actual_source_fractions(extras),
    }


def _valid_archive_candidates(
    *,
    points: np.ndarray,
    records: list[dict[str, Any]],
    indices: np.ndarray,
    invalid_objective: float,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for point, record, index in zip(points, records, indices, strict=True):
        target = _record_target(record, invalid_objective)
        if bool(record.get("valid", False)) and np.isfinite(target) and target < invalid_objective:
            candidates.append({"target": float(target), "index": int(index), "point": np.asarray(point, dtype=float)})
    return candidates


def _update_elite_archive(
    archive: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    archive_size: int,
) -> list[dict[str, Any]]:
    dedup: dict[tuple[float, ...], dict[str, Any]] = {}
    for item in [*archive, *candidates]:
        key = tuple(float(f"{value:.15g}") for value in item["point"])
        existing = dedup.get(key)
        if existing is None or float(item["target"]) < float(existing["target"]):
            dedup[key] = item
    return sorted(dedup.values(), key=lambda item: float(item["target"]))[:archive_size]


def _elite_point_count(archive: list[dict[str, Any]], options: dict[str, Any]) -> int:
    elite = options["progressive_exploration"]["elite_preservation"]
    requested = int(ceil(float(elite["elite_fraction"]) * len(archive)))
    requested = max(int(elite["min_elite_points"]), requested)
    requested = min(int(elite["max_elite_points"]), requested)
    return min(len(archive), requested)


def _construct_quantile_box_from_points(
    *,
    points: np.ndarray,
    targets: list[float],
    box_id: int,
    box_type: str,
    source_round: int,
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    global_best_point: np.ndarray | None,
) -> dict[str, Any]:
    original_width = upper - lower
    q_low = np.quantile(points, float(options["q_low"]), axis=0)
    q_high = np.quantile(points, float(options["q_high"]), axis=0)
    width = q_high - q_low
    padded_low = q_low - float(options["padding_fraction"]) * width
    padded_high = q_high + float(options["padding_fraction"]) * width
    min_width = float(options["min_width_fraction"]) * original_width
    current_width = padded_high - padded_low
    too_narrow = current_width < min_width
    if np.any(too_narrow):
        center = 0.5 * (padded_low + padded_high)
        padded_low = np.where(too_narrow, center - 0.5 * min_width, padded_low)
        padded_high = np.where(too_narrow, center + 0.5 * min_width, padded_high)
    return _box_from_bounds(
        box_id=box_id,
        box_type=box_type,
        low=padded_low,
        high=padded_high,
        lower=lower,
        upper=upper,
        request=request,
        source_round=source_round,
        source_point_count=points.shape[0],
        best_objective=min(targets) if targets else np.inf,
        global_best_point=global_best_point,
    )


def _construct_elite_boxes(
    *,
    archive: list[dict[str, Any]],
    round_index: int,
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    global_best_point: np.ndarray | None,
    start_box_id: int,
) -> list[dict[str, Any]]:
    progressive = options["progressive_exploration"]
    if not progressive["elite_boxes"]["enabled"] or not archive:
        return []
    count = _elite_point_count(archive, options)
    if count < int(progressive["elite_preservation"]["min_elite_points"]):
        return []
    elite_items = archive[:count]
    max_boxes = min(int(progressive["elite_boxes"]["max_boxes"]), count)
    chunks = np.array_split(np.arange(count), max_boxes)
    boxes: list[dict[str, Any]] = []
    box_options = progressive["elite_boxes"]
    for chunk in chunks:
        if chunk.size == 0:
            continue
        points = np.asarray([elite_items[int(index)]["point"] for index in chunk], dtype=float)
        targets = [float(elite_items[int(index)]["target"]) for index in chunk]
        boxes.append(
            _construct_quantile_box_from_points(
                points=points,
                targets=targets,
                box_id=start_box_id + len(boxes),
                box_type="elite",
                source_round=round_index,
                lower=lower,
                upper=upper,
                request=request,
                options=box_options,
                global_best_point=global_best_point,
            )
        )
    return boxes


def _construct_best_centered_box(
    *,
    global_best_point: np.ndarray | None,
    global_best_target: float,
    round_index: int,
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    box_id: int,
) -> dict[str, Any] | None:
    progressive = options["progressive_exploration"]
    if not progressive["best_centered_box"]["enabled"] or global_best_point is None:
        return None
    config = progressive["best_centered_box"]
    original_width = upper - lower
    width_fraction = max(
        float(config["min_width_fraction"]),
        float(config["width_fraction"]) * (float(config["shrink_per_round"]) ** round_index),
    )
    width = width_fraction * original_width
    low = global_best_point - 0.5 * width
    high = global_best_point + 0.5 * width
    min_width = float(config["min_width_fraction"]) * original_width
    too_narrow = (high - low) < min_width
    if np.any(too_narrow):
        low = np.where(too_narrow, global_best_point - 0.5 * min_width, low)
        high = np.where(too_narrow, global_best_point + 0.5 * min_width, high)
    return _box_from_bounds(
        box_id=box_id,
        box_type="best_centered",
        low=low,
        high=high,
        lower=lower,
        upper=upper,
        request=request,
        source_round=round_index,
        source_point_count=1,
        best_objective=global_best_target,
        global_best_point=global_best_point,
    )


def _combine_progressive_boxes(
    *,
    selected_boxes: list[dict[str, Any]],
    archive: list[dict[str, Any]],
    round_index: int,
    lower: np.ndarray,
    upper: np.ndarray,
    request: ScanRequest,
    options: dict[str, Any],
    global_best_point: np.ndarray | None,
    global_best_target: float,
) -> list[dict[str, Any]]:
    boxes = list(selected_boxes)
    next_box_id = len(boxes)
    elite_boxes = _construct_elite_boxes(
        archive=archive,
        round_index=round_index,
        lower=lower,
        upper=upper,
        request=request,
        options=options,
        global_best_point=global_best_point,
        start_box_id=next_box_id,
    )
    boxes.extend(elite_boxes)
    next_box_id += len(elite_boxes)
    best_box = _construct_best_centered_box(
        global_best_point=global_best_point,
        global_best_target=global_best_target,
        round_index=round_index,
        lower=lower,
        upper=upper,
        request=request,
        options=options,
        box_id=next_box_id,
    )
    if best_box is not None:
        boxes.append(best_box)
    for index, box in enumerate(boxes):
        box["box_id"] = index
    return boxes


def _box_type_counts(boxes: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter(str(box.get("box_type", "selected_cloud")) for box in boxes)
    return dict(sorted(counts.items()))


def _actual_source_fractions(extras: list[dict[str, Any]]) -> dict[str, float]:
    if not extras:
        return {}
    counts: Counter[str] = Counter(str(item.get("source_type", "unknown")) for item in extras)
    total = float(len(extras))
    return {key: value / total for key, value in sorted(counts.items())}


def _run_progressive_exploration(
    *,
    objective: _AdaptiveDiverObjective,
    request: ScanRequest,
    options: dict[str, Any],
    lower: np.ndarray,
    upper: np.ndarray,
    writer: _PythonScanArtifactsWriter,
    staged_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    progressive = options["progressive_exploration"]
    outdir = writer.run_directory / "progressive_exploration"
    outdir.mkdir(parents=True, exist_ok=True)
    dimension = lower.size
    seed = int(options["seed"])
    all_points: list[np.ndarray] = []
    all_records: list[dict[str, Any]] = []
    all_extras: list[dict[str, Any]] = []
    selected_points = np.empty((0, dimension), dtype=float)
    selected_records: list[dict[str, Any]] = []
    selected_indices = np.asarray([], dtype=int)
    boxes: list[dict[str, Any]] = []
    round_summaries: list[dict[str, Any]] = []
    total_evaluated = 0
    elite_archive: list[dict[str, Any]] = []
    global_best_point: np.ndarray | None = None
    global_best_target = request.invalid_objective
    global_best_round = -1
    proposal_summaries: list[dict[str, Any]] = []
    staged_summaries: list[dict[str, Any]] = []

    for round_index, n_points in enumerate(progressive["points_per_round"]):
        points, extras = _sample_progressive_round_points(
            round_index=round_index,
            n_points=int(n_points),
            boxes=boxes,
            lower=lower,
            upper=upper,
            request=request,
            options=options,
            seed=seed + 7919 * round_index,
        )
        points, proposal_used, proposal_summary = _apply_basin_proposals(
            points=points,
            request=request,
            options=options,
            seed=seed + 104729 * (round_index + 1),
            sampling_stage="progressive_exploration",
        )
        for extra, used in zip(extras, proposal_used, strict=True):
            extra["proposal_used"] = used
        proposal_summary["round_id"] = round_index
        proposal_summaries.append(proposal_summary)
        records = _evaluate_basin_points(
            objective=objective,
            points=points,
            request=request,
            options=options,
            label=f"progressive_round={round_index}",
            start_index=total_evaluated,
            staged_context=staged_context,
        )
        staged_summary = _annotate_staged_records(records, options)
        staged_summary["round_id"] = round_index
        staged_summaries.append(staged_summary)
        round_start = len(all_records)
        round_indices = np.arange(round_start, round_start + points.shape[0], dtype=int)
        all_points.append(points)
        all_records.extend(records)
        all_extras.extend(extras)
        total_evaluated += points.shape[0]

        candidates = _valid_archive_candidates(
            points=points,
            records=records,
            indices=round_indices,
            invalid_objective=request.invalid_objective,
        )
        previous_global_best = global_best_target
        if progressive["elite_preservation"]["enabled"]:
            elite_archive = _update_elite_archive(
                elite_archive,
                candidates,
                archive_size=int(progressive["elite_preservation"]["archive_size"]),
            )
        elif candidates:
            elite_archive = _update_elite_archive(elite_archive, candidates, archive_size=1)
        if elite_archive:
            global_best_target = float(elite_archive[0]["target"])
            global_best_point = np.asarray(elite_archive[0]["point"], dtype=float)
            global_best_round = int(all_extras[int(elite_archive[0]["index"])]["round_id"])
        improved_global_best = global_best_target < previous_global_best

        if progressive["output"]["save_round_points"]:
            _write_rows_csv(
                outdir / f"round_{round_index:02d}_points.csv",
                [
                    "point_id",
                    "round_id",
                    "source_type",
                    "box_id",
                    "proposal_used",
                    "valid",
                    "status",
                    "failure_reason",
                    "scanner_target",
                    "metric_value",
                    "total_nll",
                    *_basin_diagnostic_columns(),
                    *[f"param::{item.name}" for item in request.scanned_parameters],
                    *_likelihood_component_columns(request),
                ],
                _records_to_summary_rows(points=points, records=records, request=request, extra=extras),
            )

        if progressive["combine_with_previous_selected"] and selected_records:
            pool_points = np.vstack([selected_points, points])
            pool_records = [*selected_records, *records]
            pool_indices = np.concatenate([selected_indices, round_indices])
            if progressive["elite_preservation"]["always_keep_global_best"] and elite_archive:
                best_index = int(elite_archive[0]["index"])
                if best_index < round_start:
                    pool_points = np.vstack([pool_points, elite_archive[0]["point"]])
                    pool_records = [*pool_records, all_records[best_index]]
                    pool_indices = np.concatenate([pool_indices, np.asarray([best_index], dtype=int)])
        else:
            pool_points = points
            pool_records = records
            pool_indices = round_indices

        selected_points, selected_records, pool_selected_indices, selection_diagnostics = _select_basin_points(
            points=pool_points,
            records=pool_records,
            options=_round_selection_options(options),
            invalid_objective=request.invalid_objective,
            return_diagnostics=True,
        )
        selected_indices = pool_indices[pool_selected_indices] if pool_selected_indices.size else np.asarray([], dtype=int)

        selected_extras = [
            {
                "round_id": round_index,
                "exploration_index": int(index),
                "source_round_id": int(all_extras[int(index)]["round_id"]),
                "source_type": str(all_extras[int(index)].get("source_type", "unknown")),
                "source_box_id": int(all_extras[int(index)]["box_id"]),
                "proposal_used": str(all_extras[int(index)].get("proposal_used", "")),
            }
            for index in selected_indices
        ]
        if progressive["output"]["save_round_selected"]:
            _write_rows_csv(
                outdir / f"round_{round_index:02d}_selected.csv",
                [
                    "point_id",
                    "round_id",
                    "exploration_index",
                    "source_round_id",
                    "source_type",
                    "source_box_id",
                    "proposal_used",
                    "valid",
                    "status",
                    "failure_reason",
                    "scanner_target",
                    "metric_value",
                    "total_nll",
                    *_basin_diagnostic_columns(),
                    *[f"param::{item.name}" for item in request.scanned_parameters],
                    *_likelihood_component_columns(request),
                ],
                _records_to_summary_rows(
                    points=selected_points,
                    records=selected_records,
                    request=request,
                    extra=selected_extras,
                ),
            )
            (outdir / f"round_{round_index:02d}_selection_summary.json").write_text(
                json.dumps(_json_ready(selection_diagnostics), indent=2),
                encoding="utf-8",
            )
        elif progressive["output"]["save_round_points"] or progressive["output"]["save_round_boxes"]:
            (outdir / f"round_{round_index:02d}_selection_summary.json").write_text(
                json.dumps(_json_ready(selection_diagnostics), indent=2),
                encoding="utf-8",
            )

        round_options = _round_box_options(
            options,
            round_index=round_index,
            global_best_point=global_best_point,
        )
        labels, clusters = _cluster_basin_points(
            selected_points=selected_points,
            selected_records=selected_records,
            lower=lower,
            upper=upper,
            options=round_options,
            invalid_objective=request.invalid_objective,
        )
        boxes = _construct_basin_boxes(
            selected_points=selected_points,
            labels=labels,
            clusters=clusters,
            lower=lower,
            upper=upper,
            request=request,
            options=round_options,
        )
        boxes = _combine_progressive_boxes(
            selected_boxes=boxes,
            archive=elite_archive,
            round_index=round_index,
            lower=lower,
            upper=upper,
            request=request,
            options=options,
            global_best_point=global_best_point,
            global_best_target=global_best_target,
        )
        if progressive["output"]["save_round_boxes"]:
            (outdir / f"round_{round_index:02d}_boxes.json").write_text(
                json.dumps(_json_ready({"boxes": boxes}), indent=2),
                encoding="utf-8",
            )
        round_summaries.append(
            _round_summary(
                round_index=round_index,
                points=points,
                records=records,
                selected_points=selected_points,
                boxes=boxes,
                extras=extras,
                invalid_objective=request.invalid_objective,
                global_best_target=global_best_target,
                global_best_round=global_best_round,
                improved_global_best=improved_global_best,
            )
        )
        round_summaries[-1]["selection_summary"] = selection_diagnostics

    all_points_array = np.vstack(all_points) if all_points else np.empty((0, dimension), dtype=float)
    summary = {
        "enabled": True,
        "n_rounds": int(progressive["n_rounds"]),
        "points_per_round": [int(item) for item in progressive["points_per_round"]],
        "combine_with_previous_selected": bool(progressive["combine_with_previous_selected"]),
        "rounds": round_summaries,
        "global_best_objective": float(global_best_target),
        "global_best_chi2": float(2.0 * global_best_target),
        "global_best_round": int(global_best_round),
        "elite_archive_size": int(len(elite_archive)),
        "global_best_point": None
        if global_best_point is None
        else {
            parameter.name: float(value)
            for parameter, value in zip(request.scanned_parameters, global_best_point, strict=True)
        },
        "final_selected_count": int(selected_points.shape[0]),
        "total_progressive_exploration_evaluations": int(total_evaluated),
        "artifacts_directory": "progressive_exploration",
        "proposal_summaries": proposal_summaries,
        "staged_evaluation_summaries": staged_summaries,
    }
    (writer.run_directory / "progressive_exploration_summary.json").write_text(
        json.dumps(_json_ready(summary), indent=2),
        encoding="utf-8",
    )
    return {
        "points": all_points_array,
        "records": all_records,
        "extras": all_extras,
        "selected_points": selected_points,
        "selected_records": selected_records,
        "selected_indices": selected_indices,
        "summary": summary,
    }


def _run_basin_scan(
    model: ModelDefinition,
    compiled: "CompiledModel",
    request: ScanRequest,
) -> ScanResults:
    writer = _PythonScanArtifactsWriter(request)
    objective = _AdaptiveDiverObjective(compiled, request, writer)
    options = dict(request.engine_options)
    lower = np.asarray([item.lower for item in request.scanned_parameters], dtype=float)
    upper = np.asarray([item.upper for item in request.scanned_parameters], dtype=float)
    dimension = len(request.scanned_parameters)
    seed = int(options["seed"])
    staged_context = _build_staged_evaluation_context(model, request, options)

    exploration = options["exploration"]
    n_points = int(exploration["n_points"])
    progressive_enabled = bool(options["progressive_exploration"].get("enabled", False))
    if request.verbose > 0:
        if progressive_enabled:
            points_per_round = options["progressive_exploration"]["points_per_round"]
            print(
                "[basin_scan] start | "
                f"progressive_exploration=true | rounds={len(points_per_round)} | "
                f"points_per_round={points_per_round} | dimension={dimension}",
                flush=True,
            )
        else:
            print(
                "[basin_scan] start | "
                f"exploration_points={n_points} | dimension={dimension} | "
                f"method={exploration['method']}",
                flush=True,
            )

    progressive_summary: dict[str, Any] | None = None
    exploration_extras: list[dict[str, Any]] | None = None
    proposal_summary: dict[str, Any] = {"enabled": False, "applications": {}}
    staged_summary: dict[str, Any] = {"enabled": False}
    if progressive_enabled:
        progressive_result = _run_progressive_exploration(
            objective=objective,
            request=request,
            options=options,
            lower=lower,
            upper=upper,
            writer=writer,
            staged_context=staged_context,
        )
        exploration_points = progressive_result["points"]
        exploration_records = progressive_result["records"]
        exploration_extras = progressive_result["extras"]
        progressive_summary = progressive_result["summary"]
        selected_points, selected_records, selected_indices, selection_diagnostics = _select_basin_points(
            points=exploration_points,
            records=exploration_records,
            options=options,
            invalid_objective=request.invalid_objective,
            return_diagnostics=True,
        )
    else:
        exploration_points = _sample_basin_exploration(
            n_points=n_points,
            dimension=dimension,
            lower=lower,
            upper=upper,
            method=str(exploration["method"]),
            seed=seed,
            parameters=request.scanned_parameters,
        )
        exploration_points, proposal_used, proposal_summary = _apply_basin_proposals(
            points=exploration_points,
            request=request,
            options=options,
            seed=seed + 104729,
            sampling_stage="exploration",
        )
        exploration_extras = [{"proposal_used": used} for used in proposal_used]
        exploration_records = _evaluate_basin_points(
            objective=objective,
            points=exploration_points,
            request=request,
            options=options,
            label="exploration",
            staged_context=staged_context,
        )
        staged_summary = _annotate_staged_records(exploration_records, options)
        selected_points, selected_records, selected_indices, selection_diagnostics = _select_basin_points(
            points=exploration_points,
            records=exploration_records,
            options=options,
            invalid_objective=request.invalid_objective,
            return_diagnostics=True,
        )
    if progressive_enabled:
        proposal_summary = {
            "enabled": bool(options["proposals"]["enabled"]),
            "rounds": (progressive_summary or {}).get("proposal_summaries", []),
        }
        staged_summary = {
            "enabled": bool(options["staged_evaluation"]["enabled"]),
            "rounds": (progressive_summary or {}).get("staged_evaluation_summaries", []),
        }

    refinement_points = _jitter_refinement_points(
        seeds=selected_points,
        request=request,
        options=options,
        seed=seed + 32452843,
    )
    refinement_records: list[dict[str, Any]] = []
    refinement_summary: dict[str, Any] = {
        "enabled": bool(options["refinement"]["enabled"]),
        "evaluated_points": 0,
        "improved_best": False,
    }
    if refinement_points.size:
        initial_best = min(
            (_record_target(record, request.invalid_objective) for record in selected_records),
            default=request.invalid_objective,
        )
        refinement_proposals = ["" for _ in range(refinement_points.shape[0])]
        if options["refinement"]["apply_proposals"]:
            refinement_points, refinement_proposals, refinement_proposal_summary = _apply_basin_proposals(
                points=refinement_points,
                request=request,
                options=options,
                seed=seed + 49979687,
                sampling_stage="refinement",
            )
            refinement_summary["proposal_summary"] = refinement_proposal_summary
        refinement_records = _evaluate_basin_points(
            objective=objective,
            points=refinement_points,
            request=request,
            options=options,
            label="refinement",
            start_index=len(exploration_records),
            staged_context=staged_context,
        )
        refinement_summary["staged_evaluation"] = _annotate_staged_records(refinement_records, options)
        combined_points = np.vstack([exploration_points, refinement_points])
        combined_records = [*exploration_records, *refinement_records]
        selected_points, selected_records, selected_indices, selection_diagnostics = _select_basin_points(
            points=combined_points,
            records=combined_records,
            options=options,
            invalid_objective=request.invalid_objective,
            return_diagnostics=True,
        )
        refinement_best = min(
            (_record_target(record, request.invalid_objective) for record in refinement_records),
            default=request.invalid_objective,
        )
        refinement_summary.update(
            {
                "evaluated_points": int(refinement_points.shape[0]),
                "initial_best_objective": float(initial_best),
                "best_refinement_objective": float(refinement_best),
                "improved_best": bool(refinement_best < initial_best),
            }
        )
        _write_rows_csv(
            writer.run_directory / "refinement_points.csv",
            [
                "point_id",
                "proposal_used",
                "valid",
                "status",
                "failure_reason",
                "scanner_target",
                "metric_value",
                "total_nll",
                *_basin_diagnostic_columns(),
                *[f"param::{item.name}" for item in request.scanned_parameters],
                *_likelihood_component_columns(request),
            ],
            _records_to_summary_rows(
                points=refinement_points,
                records=refinement_records,
                request=request,
                extra=[{"proposal_used": item} for item in refinement_proposals],
            ),
        )

    (writer.run_directory / "proposal_summary.json").write_text(
        json.dumps(_json_ready(proposal_summary), indent=2),
        encoding="utf-8",
    )
    (writer.run_directory / "staged_evaluation_summary.json").write_text(
        json.dumps(_json_ready(staged_summary), indent=2),
        encoding="utf-8",
    )
    if options["refinement"]["enabled"]:
        (writer.run_directory / "refinement_summary.json").write_text(
            json.dumps(_json_ready(refinement_summary), indent=2),
            encoding="utf-8",
        )
    if progressive_enabled:
        selection_diagnostics["source"] = "post_progressive_final_selection"
        selection_diagnostics["progressive_final_selected_count_before_final_selection"] = int(
            progressive_result["selected_points"].shape[0]
        )
        selection_diagnostics["progressive_selection_summaries"] = [
            item.get("selection_summary", {}) for item in (progressive_summary or {}).get("rounds", [])
        ]
    (writer.run_directory / "selection_summary.json").write_text(
        json.dumps(_json_ready(selection_diagnostics), indent=2),
        encoding="utf-8",
    )

    if options["output"]["save_exploration_points"]:
        exploration_header = [
            "point_id",
            *(
                []
                if exploration_extras is None
                else [
                    *(
                        ["round_id", "source_type", "box_id"]
                        if exploration_extras and "round_id" in exploration_extras[0]
                        else []
                    ),
                    "proposal_used",
                ]
            ),
            "valid",
            "status",
            "failure_reason",
            "scanner_target",
            "metric_value",
            "total_nll",
            *_basin_diagnostic_columns(),
            *[f"param::{item.name}" for item in request.scanned_parameters],
            *_likelihood_component_columns(request),
        ]
        _write_rows_csv(
            writer.run_directory / "exploration_points.csv",
            exploration_header,
            _records_to_summary_rows(
                points=exploration_points,
                records=exploration_records,
                request=request,
                extra=exploration_extras,
            ),
        )

    selected_rows = _records_to_summary_rows(
        points=selected_points,
        records=selected_records,
        request=request,
        extra=[{"exploration_index": int(index)} for index in selected_indices],
    )
    selected_header = [
        "point_id",
        "exploration_index",
        "valid",
        "status",
        "failure_reason",
        "scanner_target",
        "metric_value",
        "total_nll",
        *_basin_diagnostic_columns(),
        *[f"param::{item.name}" for item in request.scanned_parameters],
        *_likelihood_component_columns(request),
    ]
    if options["output"]["save_selected_points"]:
        _write_rows_csv(
            writer.run_directory / "selected_points.csv",
            selected_header,
            selected_rows,
        )
    accepted_rows = [row for row in selected_rows if bool(row.get("accepted", False))]
    near_miss_rows = [
        row
        for row in selected_rows
        if not bool(row.get("accepted", False))
        or int(row.get("hard_failures", 0) or 0) > 0
        or int(row.get("fit_failures", 0) or 0) > 0
        or str(row.get("stage_reached", "")) == "cheap_rejected"
    ]
    _write_rows_csv(writer.run_directory / "accepted_points.csv", selected_header, accepted_rows)
    _write_rows_csv(writer.run_directory / "near_miss_points.csv", selected_header, near_miss_rows)

    labels, clusters = _cluster_basin_points(
        selected_points=selected_points,
        selected_records=selected_records,
        lower=lower,
        upper=upper,
        options=options,
        invalid_objective=request.invalid_objective,
    )
    if options["output"]["save_clusters"]:
        cluster_rows = _records_to_summary_rows(
            points=selected_points,
            records=selected_records,
            request=request,
            extra=[
                {"cluster_id": int(label), "exploration_index": int(index)}
                for label, index in zip(labels, selected_indices, strict=True)
            ],
        )
        _write_rows_csv(
            writer.run_directory / "clusters.csv",
            [
                "point_id",
                "exploration_index",
                "cluster_id",
                "valid",
                "status",
                "failure_reason",
                "scanner_target",
                "metric_value",
                "total_nll",
                *_basin_diagnostic_columns(),
                *[f"param::{item.name}" for item in request.scanned_parameters],
                *_likelihood_component_columns(request),
            ],
            cluster_rows,
        )

    boxes = _construct_basin_boxes(
        selected_points=selected_points,
        labels=labels,
        clusters=clusters,
        lower=lower,
        upper=upper,
        request=request,
        options=options,
    )
    manifold_refocus_result: dict[str, Any] = {"boxes": boxes, "diagnostics": {"enabled": False}}
    if options["manifold_refocus"]["enabled"]:
        manifold_refocus_result = _run_manifold_refocus_stage(
            exploration_points=exploration_points,
            exploration_records=exploration_records,
            selected_points=selected_points,
            selected_records=selected_records,
            boxes=boxes,
            lower=lower,
            upper=upper,
            request=request,
            options=options,
            writer=writer,
        )
        boxes = list(manifold_refocus_result.get("boxes", boxes))
    ml_focus_result: dict[str, Any] = {"boxes": boxes, "seeds_by_box": {}, "diagnostics": {"enabled": False}}
    if options["ml_focus"]["enabled"]:
        ml_focus_result = _run_ml_focus_stage(
            exploration_points=exploration_points,
            exploration_records=exploration_records,
            selected_points=selected_points,
            selected_records=selected_records,
            boxes=boxes,
            lower=lower,
            upper=upper,
            request=request,
            options=options,
            writer=writer,
        )
        boxes = list(ml_focus_result.get("boxes", boxes))
    if options["output"]["save_focused_boxes"]:
        (writer.run_directory / "focused_boxes.json").write_text(
            json.dumps(_json_ready({"boxes": boxes}), indent=2),
            encoding="utf-8",
        )

    basin_results: list[dict[str, Any]] = []
    original_lower = {item.name: item.lower for item in request.scanned_parameters}
    original_upper = {item.name: item.upper for item in request.scanned_parameters}
    focused_evaluations = 0
    focused_valid_points = 0
    for basin_index, box in enumerate(boxes):
        subdir = writer.run_directory / f"basin_{basin_index:02d}"
        subrequest = _subrequest_for_basin(
            request,
            box=box,
            run_directory=subdir,
            seed=seed + basin_index + 1,
            options=options,
        )
        focused_seed_points = _focused_seed_points_for_box(
            selected_points=selected_points,
            selected_records=selected_records,
            labels=labels,
            box=box,
            invalid_objective=request.invalid_objective,
        )
        ml_seed_points = ml_focus_result.get("seeds_by_box", {}).get(basin_index, [])
        if ml_seed_points:
            focused_seed_points = [*ml_seed_points, *focused_seed_points]
        if focused_seed_points:
            subrequest = replace(
                subrequest,
                engine_options={
                    **subrequest.engine_options,
                    "initial_population": focused_seed_points,
                },
            )
        if request.verbose > 0:
            print(
                "[basin_scan] focused "
                f"cluster={box['cluster_id']} | selected={box['selected_count']} | "
                f"seeded={len(focused_seed_points)} | run_dir={subdir.name}",
                flush=True,
            )
        subresults = _run_adaptive_diver_scan(model, compiled, subrequest)
        focused_evaluations += int(subresults.summary.get("evaluations", 0))
        focused_valid_points += int(subresults.summary.get("valid_points", 0))
        best_payload = json.loads(subresults.best_fit_path.read_text(encoding="utf-8"))
        best_parameters = {
            name: float(value)
            for name, value in best_payload.get("parameters", {}).items()
        }
        if best_payload.get("has_best_point") and best_parameters:
            record = objective.evaluate([best_parameters[item.name] for item in request.scanned_parameters])
            best_payload["reevaluated_top_level_target"] = _record_target(record, request.invalid_objective)
        box["best_fit_fractional_position"] = _boundary_fraction(
            best_parameters,
            lower=box["lower"],
            upper=box["upper"],
        ) if best_parameters else {}
        box["best_fit_original_fractional_position"] = _boundary_fraction(
            best_parameters,
            lower=original_lower,
            upper=original_upper,
        ) if best_parameters else {}
        basin_results.append(
            {
                "cluster_id": int(box["cluster_id"]),
                "run_directory": subdir.name,
                "selected_count": int(box["selected_count"]),
                "best_metric_value": best_payload.get("best_metric_value"),
                "best_scanner_target": best_payload.get("best_scanner_target"),
                "parameters": best_parameters,
                "focused_box": box,
                "initial_seed_points": len(focused_seed_points),
                "summary": subresults.summary,
            }
        )

    basin_results.sort(
        key=lambda item: _coerce_sort_target(
            item.get("best_scanner_target"),
            request.invalid_objective,
        )
    )
    (writer.run_directory / "basin_results.json").write_text(
        json.dumps(
            _json_ready(
                {
                    "method": "basin_scan",
                    "ranked_results": basin_results,
                    "n_clusters": len(clusters),
                    "n_focused_boxes": len(boxes),
                    "ml_focus": ml_focus_result.get("diagnostics", {"enabled": False}),
                    "manifold_refocus": manifold_refocus_result.get("diagnostics", {"enabled": False}),
                }
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    (writer.run_directory / "focused_boxes.json").write_text(
        json.dumps(_json_ready({"boxes": boxes}), indent=2),
        encoding="utf-8",
    )

    history = [
        {
            "stage": "progressive_exploration" if progressive_enabled else "exploration",
            "evaluations": len(exploration_records),
            "valid_points": sum(1 for record in exploration_records if record.get("valid", False)),
            "best_scanner_target": None if objective.best_record is None else objective.best_record["scanner_target"],
            **({} if progressive_summary is None else {"progressive_summary": progressive_summary}),
        },
        {
            "stage": "refinement",
            **refinement_summary,
        },
        {
            "stage": "focused",
            "focused_runs": len(basin_results),
            "focused_evaluations": focused_evaluations,
            "focused_valid_points": focused_valid_points,
            "best_scanner_target": None if objective.best_record is None else objective.best_record["scanner_target"],
        },
    ]
    writer.write_history(history)
    writer.write_best_fit(objective.best_record)
    writer.write_summary(
        evaluations=objective.evaluations + focused_evaluations,
        saved_points=objective.saved_points,
        valid_points=objective.valid_points + focused_valid_points,
        interrupted=False,
        best_record=objective.best_record,
        failure_counters=objective.failure_counters,
        failure_reasons=objective.failure_reasons,
        engine_details={
            "orchestrator": "basin_scan",
            "success": objective.best_record is not None,
            "exploration_evaluations": len(exploration_records),
            "exploration_valid_points": sum(1 for record in exploration_records if record.get("valid", False)),
            "selected_points": int(selected_points.shape[0]),
            "accepted_selected_points": int(len(accepted_rows)),
            "near_miss_selected_points": int(len(near_miss_rows)),
            "proposal_assisted_sampling_enabled": bool(options["proposals"]["enabled"]),
            "staged_evaluation_enabled": bool(options["staged_evaluation"]["enabled"]),
            "refinement_enabled": bool(options["refinement"]["enabled"]),
            "refinement_evaluations": len(refinement_records),
            "ml_focus_enabled": bool(options["ml_focus"]["enabled"]),
            "ml_focus_focused_box_created": bool(
                ml_focus_result.get("diagnostics", {}).get("focused_box_created", False)
            ),
            "manifold_refocus_enabled": bool(options["manifold_refocus"]["enabled"]),
            "manifold_refocus_box_created": bool(
                manifold_refocus_result.get("diagnostics", {}).get("box_created", False)
            ),
            "clusters": len(clusters),
            "focused_boxes": len(boxes),
            "focused_engine": options["focused_engine"]["name"],
            "focused_evaluations": focused_evaluations,
            "focused_valid_points": focused_valid_points,
            "progressive_exploration_enabled": progressive_enabled,
            **(
                {}
                if progressive_summary is None
                else {
                    "progressive_exploration_summary_path": "progressive_exploration_summary.json",
                    "progressive_exploration_rounds": progressive_summary["n_rounds"],
                    "progressive_exploration_evaluations": progressive_summary[
                        "total_progressive_exploration_evaluations"
                    ],
                }
            ),
            "history_path": "history.json",
            "exploration_points_path": "exploration_points.csv",
            "selected_points_path": "selected_points.csv",
            "accepted_points_path": "accepted_points.csv",
            "near_miss_points_path": "near_miss_points.csv",
            "clusters_path": "clusters.csv",
            "focused_boxes_path": "focused_boxes.json",
            "basin_results_path": "basin_results.json",
            "proposal_summary_path": "proposal_summary.json",
            "staged_evaluation_summary_path": "staged_evaluation_summary.json",
            **(
                {
                    "ml_focus_diagnostics_path": "ml_focus_diagnostics.json",
                    "ml_focus_box_path": "ml_focus_box.json",
                    "ml_focus_seeds_path": "ml_focus_seeds.csv",
                }
                if options["ml_focus"]["enabled"]
                else {}
            ),
            **(
                {
                    "manifold_refocus_diagnostics_path": "manifold_refocus_diagnostics.json",
                    "manifold_refocus_box_path": "manifold_refocus_box.json",
                    "manifold_refocus_training_path": "manifold_refocus_training.csv",
                    "manifold_refocus_candidates_path": "manifold_refocus_candidates.csv",
                }
                if options["manifold_refocus"]["enabled"]
                else {}
            ),
            **(
                {
                    "refinement_points_path": "refinement_points.csv",
                    "refinement_summary_path": "refinement_summary.json",
                }
                if options["refinement"]["enabled"]
                else {}
            ),
        },
    )
    writer.close()

    if request.verbose > 0:
        best_target = None if objective.best_record is None else objective.best_record["scanner_target"]
        print(
            "[basin_scan] final | "
            f"exploration={len(exploration_records)} | focused_runs={len(basin_results)} | "
            f"focused_evaluations={focused_evaluations}"
            + (f" | best_target={float(best_target):.12g}" if best_target is not None else ""),
            flush=True,
        )

    return ScanResults(
        run_directory=writer.run_directory,
        points_path=writer.points_path,
        metadata_path=writer.metadata_path,
        best_fit_path=writer.best_fit_path,
        summary_path=writer.summary_path,
        summary=json.loads(writer.summary_path.read_text(encoding="utf-8")),
    )


def _run_de_scipy_scan(
    model: ModelDefinition,
    compiled: "CompiledModel",
    request: ScanRequest,
) -> ScanResults:
    differential_evolution = _import_scipy_differential_evolution()
    writer = _PythonScanArtifactsWriter(request)
    objective = _ScipyDEObjective(compiled, request, writer)
    bounds = [(item.lower, item.upper) for item in request.scanned_parameters]
    options = dict(request.engine_options)
    if request.verbose > 0:
        print(
            "[de_scipy] start | "
            f"maxiter={options['maxiter']} | popsize={options['popsize']} | "
            f"dimension={len(bounds)} | progress_interval={options.get('progress_interval', 100)}",
            flush=True,
        )

    kwargs: dict[str, Any] = {
        "strategy": options["strategy"],
        "maxiter": options["maxiter"],
        "popsize": options["popsize"],
        "tol": options["tol"],
        "atol": options["atol"],
        "mutation": options["mutation"],
        "recombination": options["recombination"],
        "seed": options["seed"],
        "init": options["init"],
        "updating": options["updating"],
        "workers": options["workers"],
        "polish": options["polish"],
        "callback": objective.callback,
    }
    if options["x0"] is not None:
        kwargs["x0"] = options["x0"]

    result = differential_evolution(objective.evaluate, bounds, **kwargs)
    objective.report_progress(iteration=None, convergence=getattr(result, "message", None), force=True)
    writer.write_history(objective.history)
    writer.write_best_fit(objective.best_record)
    writer.write_summary(
        evaluations=objective.evaluations,
        saved_points=objective.saved_points,
        valid_points=objective.valid_points,
        interrupted=False,
        best_record=objective.best_record,
        failure_counters=objective.failure_counters,
        failure_reasons=objective.failure_reasons,
        engine_details={
            "reference_backend": "scipy.optimize.differential_evolution",
            "success": getattr(result, "success", None),
            "message": str(getattr(result, "message", "")),
            "nit": getattr(result, "nit", None),
            "nfev": getattr(result, "nfev", objective.evaluations),
            "fun": getattr(result, "fun", None),
            "polish": options["polish"],
            "workers": options["workers"],
            "history_path": "history.json",
        },
    )
    writer.close()

    return ScanResults(
        run_directory=writer.run_directory,
        points_path=writer.points_path,
        metadata_path=writer.metadata_path,
        best_fit_path=writer.best_fit_path,
        summary_path=writer.summary_path,
        summary=json.loads(writer.summary_path.read_text(encoding="utf-8")),
    )


def run_scan(
    model: ModelDefinition,
    compiled: "CompiledModel",
    *,
    run_directory: str | Path | None = None,
    run_id: str | None = None,
    timestamp_utc: str | None = None,
) -> ScanResults:
    request = build_scan_request(
        model,
        compiled,
        run_directory=run_directory,
        run_id=run_id,
        timestamp_utc=timestamp_utc,
    )

    if request.engine == "de_scipy":
        results = _run_de_scipy_scan(model, compiled, request)
    elif request.engine == "adaptive_diver":
        results = _run_adaptive_diver_scan(model, compiled, request)
    elif request.engine == "basin_scan":
        results = _run_basin_scan(model, compiled, request)
    else:
        if _core is None or not hasattr(_core, "run_scan"):
            raise RuntimeError(
                "The native scan runner is not available. Rebuild the extension with scan support enabled."
            )

        payload = _core.run_scan(compiled.plan.to_dict(), request.to_dict())
        results = ScanResults.from_native_result(payload)

    statistics_artifacts = run_statistics(results.run_directory, model.statistics)
    if statistics_artifacts is not None:
        results.statistics_directory = statistics_artifacts.directory
    posterior_config = dict(getattr(model.scan, "posterior", {}) or {})
    if bool(posterior_config.get("enabled", False)):
        from bsm_scanner.posterior import run_posterior_stage

        posterior_summary = run_posterior_stage(
            model,
            compiled,
            request,
            results.run_directory,
            posterior_config,
        )
        if posterior_summary is not None:
            results.summary["posterior"] = posterior_summary
            results.summary_path.write_text(json.dumps(_json_ready(results.summary), indent=2), encoding="utf-8")
    return results


def evaluate_scan_point(
    model: ModelDefinition,
    compiled: "CompiledModel",
    point_vector: list[float],
    *,
    run_directory: str | Path | None = None,
) -> dict[str, Any]:
    if _core is None or not hasattr(_core, "evaluate_scan_point"):
        raise RuntimeError(
            "The native scan-point adapter is not available. Rebuild the extension with scan support enabled."
        )

    request = replace(build_scan_request(model, compiled, run_directory=run_directory), engine="serial_random")
    return _core.evaluate_scan_point(compiled.plan.to_dict(), request.to_dict(), point_vector)


def load_scan_metadata(run_directory: str | Path) -> dict[str, Any]:
    path = Path(run_directory) / "metadata.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_scan_summary(run_directory: str | Path) -> dict[str, Any]:
    path = Path(run_directory) / "summary.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_scan_best_fit(run_directory: str | Path) -> dict[str, Any]:
    path = Path(run_directory) / "best_fit.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_scan_points(run_directory: str | Path):
    path = Path(run_directory) / "points.csv"
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pandas is required for load_scan_points().") from exc
    return pd.read_csv(path)
