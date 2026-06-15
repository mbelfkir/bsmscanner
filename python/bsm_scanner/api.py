from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from bsm_scanner.compiler.lowering import CompiledModelSpec, GraphLowerer, export_plan
from bsm_scanner.model.loader import load_model_mapping
from bsm_scanner.model.schema import ModelDefinition
from bsm_scanner.scan import (
    ScanResults,
    build_scan_request as build_scan_request,
    evaluate_scan_point as evaluate_scan_point,
    load_scan_best_fit as load_scan_best_fit,
    load_scan_metadata as load_scan_metadata,
    load_scan_points as load_scan_points,
    load_scan_summary as load_scan_summary,
    run_scan as execute_scan,
)

try:
    from . import _core  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - exercised only when native module is absent
    _core = None


def load_model(path: str | Path) -> ModelDefinition:
    return ModelDefinition.from_mapping(load_model_mapping(path))


@dataclass
class CompiledModel:
    model: ModelDefinition
    plan: CompiledModelSpec
    backend: Any | None = None

    def evaluate(self, point: Mapping[str, Any]) -> dict[str, Any]:
        if self.backend is None:
            raise RuntimeError(
                "The native C++ backend is not available. Rebuild with the extension enabled."
            )
        return self.backend.evaluate(dict(point))

    def export_plan(self, path: str | Path) -> None:
        export_plan(self.plan, path)

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.model.metadata.name,
            "version": self.model.metadata.version,
            "n_nodes": len(self.plan.nodes),
            "n_saved_outputs": len(self.plan.saved_outputs),
        }


def compile_model(
    model_or_path: ModelDefinition | str | Path,
    *,
    build_backend: bool = True,
) -> CompiledModel:
    model = model_or_path if isinstance(model_or_path, ModelDefinition) else load_model(model_or_path)
    plan = GraphLowerer(model).lower()

    backend = None
    if build_backend:
        if _core is None:
            warnings.warn(
                "Native backend is unavailable; returning compiled plan without evaluator.",
                stacklevel=2,
            )
        else:
            backend = _core.build_model(plan.to_dict())

    return CompiledModel(model=model, plan=plan, backend=backend)


@dataclass
class ScanSession:
    compiled_model: CompiledModel

    def prepare_run_directory(self, run_dir: str | Path) -> Path:
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        self.compiled_model.export_plan(run_path / "compiled_model_plan.json")
        (run_path / "scan_config.json").write_text(
            json.dumps(self.compiled_model.plan.scan, indent=2),
            encoding="utf-8",
        )
        return run_path

    def run(
        self,
        run_dir: str | Path | None = None,
        *,
        run_id: str | None = None,
        timestamp_utc: str | None = None,
    ) -> ScanResults:
        return execute_scan(
            self.compiled_model.model,
            self.compiled_model,
            run_directory=run_dir,
            run_id=run_id,
            timestamp_utc=timestamp_utc,
        )


def load_results(path: str | Path):
    path = Path(path)
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("pandas is required for load_results().") from exc
    return pd.read_csv(path)


def run_scan(
    model_or_path: ModelDefinition | str | Path,
    compiled: CompiledModel | None = None,
    *,
    build_backend: bool = False,
    run_directory: str | Path | None = None,
    run_id: str | None = None,
    timestamp_utc: str | None = None,
) -> ScanResults:
    model = model_or_path if isinstance(model_or_path, ModelDefinition) else load_model(model_or_path)
    compiled_model = compiled or compile_model(model, build_backend=build_backend)
    return execute_scan(
        model,
        compiled_model,
        run_directory=run_directory,
        run_id=run_id,
        timestamp_utc=timestamp_utc,
    )
