from __future__ import annotations

from dataclasses import dataclass, field

from bsm_scanner.compiler.expressions import ExpressionCompiler
from bsm_scanner.exceptions import GraphCycleError, ModelValidationError
from bsm_scanner.model.schema import ModelDefinition, ValueType


def _plugin_call_payload(spec) -> dict[str, object]:
    return {
        "plugin": spec.plugin,
        "function": spec.function,
        "bindings": dict(spec.bindings),
        "options": dict(spec.options),
        "output": spec.output,
    }


@dataclass(slots=True)
class GraphNode:
    name: str
    kind: str
    value_type: str
    dependencies: set[str] = field(default_factory=set)
    payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class ModelGraph:
    nodes: dict[str, GraphNode]

    def topological_order(self) -> list[str]:
        priority = {
            "external_parameter": 0,
            "constant": 0,
            "function": 0,
            "derived": 1,
            "matrix": 1,
            "diagonalization": 2,
            "mixing_matrix": 3,
            "observable": 4,
            "theory_check": 5,
            "constraint": 6,
            "output": 7,
        }

        def sort_key(name: str) -> tuple[int, str]:
            return priority.get(self.nodes[name].kind, 99), name

        indegree = {name: 0 for name in self.nodes}
        outgoing = {name: set() for name in self.nodes}

        for name, node in self.nodes.items():
            for dependency in node.dependencies:
                if dependency not in self.nodes:
                    raise ModelValidationError(
                        f"Node '{name}' depends on unknown node '{dependency}'."
                    )
                indegree[name] += 1
                outgoing[dependency].add(name)

        ready = sorted(
            (name for name, degree in indegree.items() if degree == 0),
            key=sort_key,
        )
        order: list[str] = []

        while ready:
            current = ready.pop(0)
            order.append(current)
            for child in sorted(outgoing[current]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
                    ready.sort(key=sort_key)

        if len(order) != len(self.nodes):
            cyclic = sorted(name for name, degree in indegree.items() if degree > 0)
            raise GraphCycleError(f"Dependency cycle detected involving: {', '.join(cyclic)}")

        return order

    def active_subgraph(self, roots: list[str]) -> "ModelGraph":
        missing = [name for name in roots if name not in self.nodes]
        if missing:
            raise ModelValidationError(f"Unknown active roots: {', '.join(sorted(missing))}")

        keep: set[str] = set()
        stack = list(roots)
        while stack:
            current = stack.pop()
            if current in keep:
                continue
            keep.add(current)
            stack.extend(self.nodes[current].dependencies)

        return ModelGraph(nodes={name: self.nodes[name] for name in keep})


def build_model_graph(model: ModelDefinition) -> ModelGraph:
    compiler = ExpressionCompiler(model.functions)
    nodes: dict[str, GraphNode] = {}

    for parameter in model.parameters:
        nodes[parameter.name] = GraphNode(
            name=parameter.name,
            kind="external_parameter",
            value_type=parameter.value_type.value,
            payload={
                "scan": parameter.scan,
                "lower": parameter.lower,
                "upper": parameter.upper,
                "default": parameter.default,
                "prior": parameter.prior.value,
                "min_abs": parameter.min_abs,
            },
        )

    for constant in model.constants:
        nodes[constant.name] = GraphNode(
            name=constant.name,
            kind="constant",
            value_type=constant.resolved_type().value,
            payload={"value": constant.value},
        )

    for function in model.functions:
        compiled = compiler.compile(
            function.expression,
            function.value_type,
            local_names=set(function.args),
        )
        nodes[function.name] = GraphNode(
            name=function.name,
            kind="function",
            value_type=function.value_type.value,
            dependencies=set(compiled.dependencies),
            payload={"args": function.args, "expression": function.expression},
        )

    for derived in model.derived_scalars + model.derived_complex:
        if derived.expression is not None:
            compiled = compiler.compile(derived.expression, derived.value_type)
            dependencies = set(compiled.dependencies)
            payload = {"expression": derived.expression}
        else:
            assert derived.plugin_call is not None
            dependencies = set(derived.plugin_call.bindings.values())
            payload = {"plugin_call": _plugin_call_payload(derived.plugin_call)}
        nodes[derived.name] = GraphNode(
            name=derived.name,
            kind="derived",
            value_type=derived.value_type.value,
            dependencies=dependencies,
            payload=payload,
        )

    for matrix in model.matrices:
        matrix_dependencies: set[str] = set()
        cell_value_type = ValueType.COMPLEX if matrix.value_type == ValueType.COMPLEX_MATRIX else ValueType.REAL
        for row in matrix.rows:
            for cell in row:
                matrix_dependencies |= set(compiler.compile(cell, cell_value_type).dependencies)
        nodes[matrix.name] = GraphNode(
            name=matrix.name,
            kind="matrix",
            value_type=matrix.value_type.value,
            dependencies=matrix_dependencies,
            payload={
                "rows": matrix.rows,
                "matrix_type": matrix.matrix_type.value if matrix.matrix_type is not None else None,
                "role": matrix.role,
                "diagonalize": matrix.diagonalize,
            },
        )

    for diag in model.resolved_diagonalizations():
        nodes[diag.name] = GraphNode(
            name=diag.name,
            kind="diagonalization",
            value_type="diagonalization",
            dependencies={diag.input},
            payload={"input": diag.input, "method": diag.method},
        )

    for mixing in model.mixing_matrices:
        left, right = mixing.resolved_inputs()
        dependencies = {source for source in (left, right) if source != "identity"}
        nodes[mixing.resolved_output()] = GraphNode(
            name=mixing.resolved_output(),
            kind="mixing_matrix",
            value_type=ValueType.COMPLEX_MATRIX.value,
            dependencies=dependencies,
            payload={
                "name": mixing.name,
                "type": mixing.kind.value,
                "convention": mixing.convention.value,
                "left": left,
                "right": right,
            },
        )

    for observable in model.resolved_observables():
        if observable.expression is not None:
            compiled = compiler.compile(observable.expression, observable.value_type)
            deps = set(compiled.dependencies)
            payload = {"expression": observable.expression}
        elif observable.plugin_call is not None:
            deps = set(observable.plugin_call.bindings.values())
            payload = {"plugin_call": _plugin_call_payload(observable.plugin_call)}
        else:
            assert observable.projection is not None
            deps = {observable.projection.from_node}
            payload = {
                "projection": {
                    "from": observable.projection.from_node,
                    "quantity": observable.projection.quantity,
                    "index": observable.projection.index,
                    "row": observable.projection.row,
                    "col": observable.projection.col,
                }
            }
        nodes[observable.name] = GraphNode(
            name=observable.name,
            kind="observable",
            value_type=observable.value_type.value,
            dependencies=deps,
            payload=payload,
        )

    for check in model.theory_checks:
        if check.condition is not None:
            compiled = compiler.compile(check.condition, ValueType.BOOL)
            dependencies = set(compiled.dependencies)
            payload = {
                "condition": check.condition,
                "fatal": check.fatal,
                "message": check.message or check.name,
            }
        else:
            assert check.plugin_call is not None
            dependencies = set(check.plugin_call.bindings.values())
            payload = {
                "plugin_call": _plugin_call_payload(check.plugin_call),
                "fatal": check.fatal,
                "message": check.message or check.name,
            }
        nodes[check.name] = GraphNode(
            name=check.name,
            kind="theory_check",
            value_type=ValueType.BOOL.value,
            dependencies=dependencies,
            payload=payload,
        )

    for likelihood in model.likelihoods:
        dependencies = set(likelihood.observables)
        if likelihood.observable:
            dependencies.add(likelihood.observable)
        if likelihood.plugin_call is not None:
            dependencies |= set(likelihood.plugin_call.bindings.values())
        payload = {
            "kind": likelihood.kind.value,
            "observable": likelihood.observable,
            "observables": likelihood.observables,
            "mean": likelihood.mean,
            "means": likelihood.means,
            "sigma": likelihood.sigma,
            "sigma_up": likelihood.sigma_up,
            "sigma_down": likelihood.sigma_down,
            "lower": likelihood.lower,
            "upper": likelihood.upper,
            "covariance": likelihood.covariance,
            "table": likelihood.table,
            "plugin": likelihood.plugin,
            "out_of_range_penalty_scale": likelihood.out_of_range_penalty_scale,
            "out_of_range_penalty_cap": likelihood.out_of_range_penalty_cap,
            "interpolation": likelihood.interpolation.value,
            "in_range_offset": likelihood.in_range_offset,
            "quadratic_form_prefactor": likelihood.quadratic_form_prefactor,
        }
        if likelihood.plugin_call is not None:
            payload["plugin_call"] = _plugin_call_payload(likelihood.plugin_call)
        nodes[likelihood.name] = GraphNode(
            name=likelihood.name,
            kind="constraint",
            value_type=ValueType.REAL.value,
            dependencies=dependencies,
            payload=payload,
        )

    for source in model.outputs.save:
        nodes[f"output::{source}"] = GraphNode(
            name=f"output::{source}",
            kind="output",
            value_type=nodes[source].value_type if source in nodes else ValueType.REAL.value,
            dependencies={source},
            payload={"source": source, "label": source},
        )

    return ModelGraph(nodes=nodes)
