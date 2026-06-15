from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from bsm_scanner.compiler.lowering import GraphLowerer
from bsm_scanner.exceptions import ModelValidationError
from bsm_scanner.model.schema import ModelDefinition


@dataclass(frozen=True, slots=True)
class PluginTermAccounting:
    derived: tuple[str, ...]
    observables: tuple[str, ...]
    theory_checks: tuple[str, ...]
    likelihoods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModelInvariantSummary:
    model_name: str
    free_parameters: tuple[str, ...]
    fixed_parameters: tuple[str, ...]
    active_nodes: tuple[str, ...]
    dead_scanned_parameters: tuple[str, ...]
    likelihood_terms: tuple[str, ...]
    plugin_terms: PluginTermAccounting

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ParityEntry:
    old: Any
    new: Any
    match: bool
    difference: float | None
    mapped_to: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "old": self.old,
            "new": self.new,
            "match": self.match,
            "difference": self.difference,
            "mapped_to": list(self.mapped_to),
        }


def free_parameter_names(model: ModelDefinition) -> tuple[str, ...]:
    return tuple(sorted(parameter.name for parameter in model.parameters if parameter.scan))


def fixed_parameter_names(model: ModelDefinition) -> tuple[str, ...]:
    return tuple(sorted(parameter.name for parameter in model.parameters if not parameter.scan))


def likelihood_term_names(model: ModelDefinition) -> tuple[str, ...]:
    return tuple(sorted(likelihood.name for likelihood in model.likelihoods))


def plugin_term_accounting(model: ModelDefinition) -> PluginTermAccounting:
    return PluginTermAccounting(
        derived=tuple(
            sorted(
                item.name
                for item in (*model.derived_scalars, *model.derived_complex)
                if item.plugin_call is not None
            )
        ),
        observables=tuple(
            sorted(observable.name for observable in model.observables if observable.plugin_call is not None)
        ),
        theory_checks=tuple(
            sorted(check.name for check in model.theory_checks if check.plugin_call is not None)
        ),
        likelihoods=tuple(
            sorted(likelihood.name for likelihood in model.likelihoods if likelihood.plugin_call is not None)
        ),
    )


def dead_scanned_parameters(model: ModelDefinition) -> tuple[str, ...]:
    active_names = {node["name"] for node in GraphLowerer(model).lower().nodes}
    return tuple(
        sorted(
            parameter.name
            for parameter in model.parameters
            if parameter.scan and parameter.name not in active_names
        )
    )


def summarize_model_invariants(model: ModelDefinition) -> ModelInvariantSummary:
    lowered = GraphLowerer(model).lower()
    return ModelInvariantSummary(
        model_name=model.metadata.name,
        free_parameters=free_parameter_names(model),
        fixed_parameters=fixed_parameter_names(model),
        active_nodes=tuple(node["name"] for node in lowered.nodes),
        dead_scanned_parameters=dead_scanned_parameters(model),
        likelihood_terms=likelihood_term_names(model),
        plugin_terms=plugin_term_accounting(model),
    )


def require_free_parameter_set(
    model: ModelDefinition,
    *,
    expected: Iterable[str] | None = None,
    forbidden: Iterable[str] = (),
) -> None:
    free = set(free_parameter_names(model))
    forbidden_set = set(forbidden)
    offending = sorted(free & forbidden_set)
    if offending:
        raise ModelValidationError(
            f"Model '{model.metadata.name}' exposes forbidden free parameters: {', '.join(offending)}."
        )
    if expected is not None:
        expected_set = set(expected)
        if free != expected_set:
            missing = sorted(expected_set - free)
            unexpected = sorted(free - expected_set)
            details: list[str] = []
            if missing:
                details.append(f"missing: {', '.join(missing)}")
            if unexpected:
                details.append(f"unexpected: {', '.join(unexpected)}")
            raise ModelValidationError(
                f"Model '{model.metadata.name}' free-parameter set mismatch ({'; '.join(details)})."
            )


def require_no_dead_scanned_parameters(model: ModelDefinition) -> None:
    dead = dead_scanned_parameters(model)
    if dead:
        raise ModelValidationError(
            f"Model '{model.metadata.name}' contains dead scanned parameters: {', '.join(dead)}."
        )


def require_likelihood_coverage(model: ModelDefinition, expected_terms: Iterable[str]) -> None:
    actual = set(likelihood_term_names(model))
    expected = set(expected_terms)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected: {', '.join(unexpected)}")
        raise ModelValidationError(
            f"Model '{model.metadata.name}' likelihood coverage mismatch ({'; '.join(details)})."
        )


def values_match(old: Any, new: Any, *, rel_tol: float = 1e-8, abs_tol: float = 1e-10) -> bool:
    if isinstance(old, str) or isinstance(new, str):
        return old == new
    if old is None or new is None:
        return old is None and new is None
    if isinstance(old, bool) or isinstance(new, bool):
        return bool(old) == bool(new)
    if not math.isfinite(old) or not math.isfinite(new):
        return old == new
    return math.isclose(old, new, rel_tol=rel_tol, abs_tol=abs_tol)


def numeric_difference(old: Any, new: Any) -> float | None:
    if isinstance(old, str) or isinstance(new, str) or old is None or new is None:
        return None
    if isinstance(old, bool) or isinstance(new, bool):
        return None
    if not math.isfinite(old) or not math.isfinite(new):
        return None
    return old - new


def build_parity_section(
    old_values: Mapping[str, Any],
    new_values: Mapping[str, Any],
    *,
    mapping: Mapping[str, str | Iterable[str]] | None = None,
    rel_tol: float = 1e-8,
    abs_tol: float = 1e-10,
) -> dict[str, ParityEntry]:
    resolved_mapping: dict[str, tuple[str, ...]] = {}
    if mapping is None:
        resolved_mapping = {name: (name,) for name in old_values}
    else:
        for old_name, target in mapping.items():
            if isinstance(target, str):
                resolved_mapping[old_name] = (target,)
            else:
                resolved_mapping[old_name] = tuple(target)

    report: dict[str, ParityEntry] = {}
    for old_name, mapped_targets in resolved_mapping.items():
        old_value = old_values.get(old_name)
        if len(mapped_targets) == 1:
            new_value = new_values.get(mapped_targets[0])
        else:
            new_value = sum(float(new_values.get(target, 0.0)) for target in mapped_targets)
        report[old_name] = ParityEntry(
            old=old_value,
            new=new_value,
            match=values_match(old_value, new_value, rel_tol=rel_tol, abs_tol=abs_tol),
            difference=numeric_difference(old_value, new_value),
            mapped_to=mapped_targets,
        )
    return report


def export_parity_report(report: Mapping[str, ParityEntry], path: str | Path) -> None:
    destination = Path(path)
    payload = {name: item.to_dict() for name, item in report.items()}
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
