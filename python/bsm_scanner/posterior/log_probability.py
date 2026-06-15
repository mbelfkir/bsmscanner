from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

import numpy as np

from .priors import ParameterInfo, log_prior, vector_to_dict


@dataclass(slots=True)
class LogProbabilityContext:
    compiled: Any
    request: Any
    parameters: list[ParameterInfo]
    objective_mode: str
    default_prior: str
    use_parameter_priors: bool
    include_log_prior: bool
    invalid_reasons: Counter[str] = field(default_factory=Counter)
    evaluations: int = 0


def objective_mode_for_posterior(configured: str, scan_objective: str) -> str:
    mode = scan_objective if configured == "auto" else configured
    mode = str(mode).lower()
    if mode not in {"nll", "chi2"}:
        raise ValueError("Posterior objective must be 'nll' or 'chi2'.")
    return mode


def evaluate_theta(theta: np.ndarray, context: LogProbabilityContext) -> dict[str, Any]:
    from bsm_scanner.scan import _core  # type: ignore

    if _core is None or not hasattr(_core, "evaluate_scan_point"):
        raise RuntimeError(
            "The native scan-point adapter is not available. Rebuild the extension with scan support enabled."
        )
    context.evaluations += 1
    request_dict = context.request.to_dict()
    # The native scan-point adapter evaluates a single model point and does not
    # run orchestration engines such as basin_scan/adaptive_diver. Existing
    # Python scan objectives use the same serial_random adapter convention.
    request_dict["engine"] = "serial_random"
    return _core.evaluate_scan_point(context.compiled.plan.to_dict(), request_dict, list(map(float, theta)))


def result_nll_and_chi2(result: dict[str, Any], objective_mode: str) -> tuple[float, float]:
    point_result = result.get("point_result", result)
    nll = point_result.get("total_nll", result.get("total_nll"))
    chi2 = point_result.get("chi2", result.get("chi2"))
    if nll is None and chi2 is not None:
        nll = 0.5 * float(chi2)
    if chi2 is None and nll is not None:
        chi2 = 2.0 * float(nll)
    if nll is None or chi2 is None:
        raise ValueError("Evaluator result did not contain total_nll or chi2.")
    return float(nll), float(chi2)


def log_probability(theta: np.ndarray, context: LogProbabilityContext) -> float:
    theta = np.asarray(theta, dtype=float)
    prior = log_prior(
        theta,
        context.parameters,
        default_prior=context.default_prior,
        use_parameter_priors=context.use_parameter_priors,
    )
    if not isfinite(prior):
        context.invalid_reasons["outside_bounds_or_prior"] += 1
        return float("-inf")

    try:
        result = evaluate_theta(theta, context)
    except Exception as exc:
        context.invalid_reasons[f"evaluation_error:{exc}"] += 1
        return float("-inf")

    point_result = result.get("point_result", result)
    if not bool(result.get("valid", point_result.get("valid", False))):
        reason = str(point_result.get("failure_reason") or point_result.get("status") or "invalid_point")
        context.invalid_reasons[reason] += 1
        return float("-inf")

    try:
        nll, chi2 = result_nll_and_chi2(result, context.objective_mode)
    except Exception as exc:
        context.invalid_reasons[f"objective_error:{exc}"] += 1
        return float("-inf")
    if not isfinite(nll) or not isfinite(chi2):
        context.invalid_reasons["non_finite_objective"] += 1
        return float("-inf")

    log_like = -nll if context.objective_mode == "nll" else -0.5 * chi2
    return float(log_like + prior) if context.include_log_prior else float(log_like)


def metadata_for_theta(theta: np.ndarray, context: LogProbabilityContext, log_prob_value: float | None = None) -> dict[str, Any]:
    theta = np.asarray(theta, dtype=float)
    payload: dict[str, Any] = {
        "parameters": vector_to_dict(theta, context.parameters),
        "log_prob": log_prob_value,
        "valid": False,
        "invalid_reason": "",
        "nll": None,
        "chi2": None,
        "outputs": {},
        "likelihood_terms": {},
    }
    prior = log_prior(
        theta,
        context.parameters,
        default_prior=context.default_prior,
        use_parameter_priors=context.use_parameter_priors,
    )
    if not isfinite(prior):
        payload["invalid_reason"] = "outside_bounds_or_prior"
        return payload
    try:
        result = evaluate_theta(theta, context)
    except Exception as exc:
        payload["invalid_reason"] = f"evaluation_error:{exc}"
        return payload

    point_result = result.get("point_result", result)
    payload["valid"] = bool(result.get("valid", point_result.get("valid", False)))
    payload["invalid_reason"] = "" if payload["valid"] else str(point_result.get("failure_reason") or point_result.get("status") or "invalid_point")
    try:
        nll, chi2 = result_nll_and_chi2(result, context.objective_mode)
        payload["nll"] = nll
        payload["chi2"] = chi2
    except Exception:
        pass
    payload["outputs"] = dict(point_result.get("outputs", {}))
    payload["likelihood_terms"] = dict(point_result.get("likelihood_terms", {}))
    return payload
