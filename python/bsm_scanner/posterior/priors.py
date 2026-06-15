from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log

import numpy as np


@dataclass(slots=True)
class ParameterInfo:
    name: str
    lower: float
    upper: float
    prior: str
    default: float | None = None


def parameter_order(parameters: list[ParameterInfo]) -> list[str]:
    return [item.name for item in parameters]


def bounds_arrays(parameters: list[ParameterInfo]) -> tuple[np.ndarray, np.ndarray]:
    lower = np.asarray([item.lower for item in parameters], dtype=float)
    upper = np.asarray([item.upper for item in parameters], dtype=float)
    return lower, upper


def vector_to_dict(theta: np.ndarray, parameters: list[ParameterInfo]) -> dict[str, float]:
    return {item.name: float(value) for item, value in zip(parameters, theta, strict=True)}


def inside_bounds(theta: np.ndarray, parameters: list[ParameterInfo]) -> bool:
    lower, upper = bounds_arrays(parameters)
    return bool(np.all(np.isfinite(theta)) and np.all(theta >= lower) and np.all(theta <= upper))


def log_prior(theta: np.ndarray, parameters: list[ParameterInfo], *, default_prior: str, use_parameter_priors: bool) -> float:
    if not inside_bounds(theta, parameters):
        return float("-inf")
    total = 0.0
    for value, parameter in zip(theta, parameters, strict=True):
        prior = parameter.prior if use_parameter_priors else default_prior
        prior = prior or default_prior
        if prior == "flat":
            continue
        if prior == "log":
            if value <= 0.0:
                return float("-inf")
            total -= log(float(value))
            continue
        if prior == "signed_log":
            min_abs = 1.0e-12
            if abs(value) <= min_abs:
                return float("-inf")
            total -= log(abs(float(value)))
            continue
        if prior == "fixed":
            continue
        return float("-inf")
    return total if isfinite(total) else float("-inf")
