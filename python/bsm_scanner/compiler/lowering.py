from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bsm_scanner.compiler.expressions import ExpressionCompiler
from bsm_scanner.model.graph import build_model_graph
from bsm_scanner.model.schema import ModelDefinition, ValueType


@dataclass(slots=True)
class CompiledModelSpec:
    name: str
    version: str
    nodes: list[dict]
    evaluation_order: list[str]
    saved_outputs: list[str]
    scan: dict

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "nodes": self.nodes,
            "evaluation_order": self.evaluation_order,
            "saved_outputs": self.saved_outputs,
            "scan": self.scan,
        }


class GraphLowerer:
    def __init__(self, model: ModelDefinition) -> None:
        self.model = model
        self.compiler = ExpressionCompiler(model.functions)

    def lower(self) -> CompiledModelSpec:
        graph = build_model_graph(self.model)
        roots = [f"output::{name}" for name in self.model.outputs.save]
        roots.extend(item.name for item in self.model.likelihoods)
        roots.extend(item.name for item in self.model.theory_checks)

        active = graph.active_subgraph(roots)
        order = [name for name in graph.topological_order() if name in active.nodes]
        nodes: list[dict] = []

        for name in order:
            node = active.nodes[name]
            lowered = {
                "name": node.name,
                "kind": node.kind,
                "value_type": node.value_type,
                "dependencies": sorted(node.dependencies),
                "active": True,
            }

            if node.kind in {"external_parameter", "constant"}:
                lowered["literal"] = self._literal_payload(node.payload.get("value", node.payload.get("default")))
                lowered["metadata"] = node.payload

            elif node.kind == "function":
                lowered["metadata"] = node.payload

            elif node.kind in {"derived", "observable", "theory_check"} and "expression" in node.payload:
                program = self.compiler.compile(
                    node.payload["expression"],
                    node.value_type,
                )
                lowered["program"] = program.to_dict()
                lowered["metadata"] = node.payload

            elif node.kind in {"derived", "observable", "theory_check"} and "plugin_call" in node.payload:
                lowered["plugin_call"] = self._lower_plugin_call(node.payload["plugin_call"])
                lowered["metadata"] = node.payload

            elif node.kind == "theory_check":
                program = self.compiler.compile(
                    node.payload["condition"],
                    ValueType.BOOL,
                )
                lowered["program"] = program.to_dict()
                lowered["metadata"] = node.payload

            elif node.kind == "observable" and "projection" in node.payload:
                lowered["projection"] = node.payload["projection"]

            elif node.kind == "matrix":
                rows = node.payload["rows"]
                cell_type = ValueType.COMPLEX if node.value_type == ValueType.COMPLEX_MATRIX.value else ValueType.REAL
                lowered["matrix"] = {
                    "rows": len(rows),
                    "cols": len(rows[0]),
                    "cells": [
                        self.compiler.compile(cell, cell_type).to_dict()
                        for row in rows
                        for cell in row
                    ],
                }
                lowered["metadata"] = {
                    key: value
                    for key, value in node.payload.items()
                    if key in {"matrix_type", "role", "diagonalize"}
                }

            elif node.kind == "diagonalization":
                lowered["diagonalization"] = {
                    "input": node.payload["input"],
                    "method": node.payload["method"],
                }

            elif node.kind == "mixing_matrix":
                lowered["mixing_matrix"] = {
                    "type": node.payload["type"],
                    "convention": node.payload["convention"],
                    "left": node.payload["left"],
                    "right": node.payload["right"],
                }
                lowered["metadata"] = {"name": node.payload["name"]}

            elif node.kind == "constraint":
                constraint = dict(node.payload)
                if "plugin_call" in constraint:
                    constraint["plugin_call"] = self._lower_plugin_call(constraint["plugin_call"])
                lowered["constraint"] = constraint

            elif node.kind == "output":
                lowered["output"] = node.payload

            nodes.append(lowered)

        return CompiledModelSpec(
            name=self.model.metadata.name,
            version=self.model.metadata.version,
            nodes=nodes,
            evaluation_order=order,
            saved_outputs=list(self.model.outputs.save),
            scan={
                "engine": self.model.scan.engine,
                "save_every": self.model.scan.save_every,
                "seed": self.model.scan.seed,
                "settings": self.model.scan.settings,
                "adaptive_diver": self.model.scan.adaptive_diver,
                "basin_scan": self.model.scan.basin_scan,
                "posterior": self.model.scan.posterior,
                "statistics": self.model.statistics.to_dict(),
            },
        )

    @staticmethod
    def _literal_payload(value):
        if isinstance(value, bool):
            return {"kind": "bool", "value": value}
        if isinstance(value, complex):
            return {"kind": "complex", "re": value.real, "im": value.imag}
        if isinstance(value, str):
            return {"kind": "string", "value": value}
        if value is None:
            return None
        return {"kind": "real", "value": float(value)}

    @classmethod
    def _lower_plugin_call(cls, payload: dict) -> dict:
        return {
            "plugin": payload["plugin"],
            "function": payload["function"],
            "output": payload.get("output"),
            "bindings": [
                {"argument": argument, "source": source}
                for argument, source in sorted(payload["bindings"].items())
            ],
            "options": [
                {"name": name, "value": cls._literal_payload(value)}
                for name, value in sorted(payload.get("options", {}).items())
            ],
        }


def export_plan(spec: CompiledModelSpec, path: str | Path) -> None:
    import json

    destination = Path(path)
    destination.write_text(json.dumps(spec.to_dict(), indent=2), encoding="utf-8")
