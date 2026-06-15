from __future__ import annotations

from typing import Any

import numpy as np


def _numeric_values(rows: list[dict[str, Any]], name: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(name)
        if value in {"", None}:
            continue
        try:
            parsed = float(value)
        except Exception:
            continue
        if np.isfinite(parsed):
            values.append(parsed)
    return values


def scalar_summary(values: list[float]) -> dict[str, float | None]:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return {key: None for key in ["mean", "std", "median", "q16", "q84", "q025", "q975", "min", "max"]}
    return {
        "mean": float(np.mean(array)),
        "std": float(np.std(array, ddof=1)) if array.size > 1 else 0.0,
        "median": float(np.median(array)),
        "q16": float(np.quantile(array, 0.16)),
        "q84": float(np.quantile(array, 0.84)),
        "q025": float(np.quantile(array, 0.025)),
        "q975": float(np.quantile(array, 0.975)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }


def build_summary(rows: list[dict[str, Any]], parameter_names: list[str], observable_names: list[str]) -> dict[str, Any]:
    valid_rows = [row for row in rows if row.get("valid") is True and np.isfinite(float(row.get("log_prob", np.nan)))]
    return {
        "parameters": {
            name: scalar_summary(_numeric_values(valid_rows, name))
            for name in parameter_names
        },
        "observables": {
            name: scalar_summary(_numeric_values(valid_rows, name))
            for name in observable_names
        },
    }
