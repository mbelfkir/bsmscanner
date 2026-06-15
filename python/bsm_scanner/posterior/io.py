from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from .priors import ParameterInfo


def json_ready(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not np.isfinite(value):
            return None
        return value
    if isinstance(value, complex):
        return {"re": value.real, "im": value.imag}
    if hasattr(value, "tolist"):
        return json_ready(value.tolist())
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    return str(value)


def csv_ready(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and not np.isfinite(value):
        return ""
    if isinstance(value, complex):
        sign = "+" if value.imag >= 0 else ""
        return f"{value.real}{sign}{value.imag}j"
    if isinstance(value, (dict, list, tuple)) or hasattr(value, "tolist"):
        return json.dumps(json_ready(value))
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")


def write_rows_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: csv_ready(row.get(name)) for name in fieldnames})


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parameter_columns(parameters: list[ParameterInfo]) -> list[str]:
    return [item.name for item in parameters]
