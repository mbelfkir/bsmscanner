from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import Iterable, Mapping

from bsm_scanner.exceptions import ExpressionCompileError
from bsm_scanner.model.schema import FunctionSpec, ValueType

BUILTIN_CONSTANTS = {
    "pi": 3.141592653589793,
    "e": 2.718281828459045,
    "True": True,
    "False": False,
}

BUILTIN_FUNCTIONS = {
    "sqrt",
    "log",
    "exp",
    "sin",
    "cos",
    "asin",
    "atan",
    "atan2",
    "abs",
    "arg",
    "real",
    "imag",
    "conj",
    "fmod",
    "min",
    "max",
    "isfinite",
    "if_else",
    "nan",
}


@dataclass(slots=True)
class CompiledExpression:
    return_type: str
    instructions: list[dict]
    dependencies: list[str]

    def to_dict(self) -> dict:
        return {
            "return_type": self.return_type,
            "instructions": self.instructions,
            "dependencies": self.dependencies,
        }


class ExpressionCompiler:
    def __init__(self, functions: Iterable[FunctionSpec] = ()) -> None:
        self._functions = {item.name: item for item in functions}

    def compile(
        self,
        expression: str,
        return_type: ValueType | str,
        *,
        local_names: set[str] | None = None,
    ) -> CompiledExpression:
        local_names = local_names or set()
        node = ast.parse(expression, mode="eval").body
        instructions, dependencies = self._compile_node(node, local_names, {})
        return CompiledExpression(
            return_type=return_type.value if isinstance(return_type, ValueType) else str(return_type),
            instructions=instructions,
            dependencies=sorted(dependencies),
        )

    def _compile_node(
        self,
        node: ast.AST,
        local_names: set[str],
        substitutions: Mapping[str, ast.AST],
    ) -> tuple[list[dict], set[str]]:
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool):
                return ([{"op": "push_bool", "value": value}], set())
            if isinstance(value, complex):
                return (
                    [{"op": "push_complex", "re": value.real, "im": value.imag}],
                    set(),
                )
            if isinstance(value, (int, float)):
                return ([{"op": "push_real", "value": float(value)}], set())
            raise ExpressionCompileError(f"Unsupported constant {value!r}.")

        if isinstance(node, ast.Name):
            if node.id in substitutions:
                replacement = substitutions[node.id]
                if not (isinstance(replacement, ast.Name) and replacement.id == node.id):
                    return self._compile_node(replacement, local_names, substitutions)
            if node.id in BUILTIN_CONSTANTS:
                value = BUILTIN_CONSTANTS[node.id]
                if isinstance(value, bool):
                    return ([{"op": "push_bool", "value": value}], set())
                return ([{"op": "push_real", "value": float(value)}], set())
            if node.id in local_names:
                return ([{"op": "load_local", "name": node.id}], set())
            return ([{"op": "load", "name": node.id}], {node.id})

        if isinstance(node, ast.UnaryOp):
            instructions, deps = self._compile_node(node.operand, local_names, substitutions)
            if isinstance(node.op, ast.USub):
                instructions.append({"op": "neg"})
                return instructions, deps
            if isinstance(node.op, ast.UAdd):
                return instructions, deps
            if isinstance(node.op, ast.Not):
                instructions.append({"op": "not"})
                return instructions, deps
            raise ExpressionCompileError(f"Unsupported unary operator: {ast.dump(node.op)}")

        if isinstance(node, ast.BinOp):
            left, left_deps = self._compile_node(node.left, local_names, substitutions)
            right, right_deps = self._compile_node(node.right, local_names, substitutions)
            op_map = {
                ast.Add: "add",
                ast.Sub: "sub",
                ast.Mult: "mul",
                ast.Div: "div",
                ast.Pow: "pow",
            }
            op_name = op_map.get(type(node.op))
            if op_name is None:
                raise ExpressionCompileError(f"Unsupported binary operator: {ast.dump(node.op)}")
            return left + right + [{"op": op_name}], left_deps | right_deps

        if isinstance(node, ast.BoolOp):
            instructions: list[dict] = []
            deps: set[str] = set()
            op_name = "and" if isinstance(node.op, ast.And) else "or"
            for idx, value in enumerate(node.values):
                compiled, child_deps = self._compile_node(value, local_names, substitutions)
                instructions.extend(compiled)
                deps |= child_deps
                if idx:
                    instructions.append({"op": op_name})
            return instructions, deps

        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise ExpressionCompileError("Only single comparisons are supported.")
            left, left_deps = self._compile_node(node.left, local_names, substitutions)
            right, right_deps = self._compile_node(node.comparators[0], local_names, substitutions)
            op_map = {
                ast.Lt: "cmp_lt",
                ast.LtE: "cmp_le",
                ast.Gt: "cmp_gt",
                ast.GtE: "cmp_ge",
                ast.Eq: "cmp_eq",
                ast.NotEq: "cmp_ne",
            }
            op_name = op_map.get(type(node.ops[0]))
            if op_name is None:
                raise ExpressionCompileError(f"Unsupported comparison operator: {ast.dump(node.ops[0])}")
            return left + right + [{"op": op_name}], left_deps | right_deps

        if isinstance(node, ast.IfExp):
            test, deps_test = self._compile_node(node.test, local_names, substitutions)
            body, deps_body = self._compile_node(node.body, local_names, substitutions)
            other, deps_else = self._compile_node(node.orelse, local_names, substitutions)
            return (
                test + body + other + [{"op": "call", "name": "if_else", "argc": 3}],
                deps_test | deps_body | deps_else,
            )

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ExpressionCompileError("Only direct function calls are supported.")

            function_name = node.func.id
            if function_name in self._functions:
                definition = self._functions[function_name]
                if len(node.args) != len(definition.args):
                    raise ExpressionCompileError(
                        f"Function '{function_name}' expected {len(definition.args)} arguments."
                    )
                bindings = {
                    name: self._apply_substitutions(argument, substitutions)
                    for name, argument in zip(definition.args, node.args)
                }
                function_ast = ast.parse(definition.expression, mode="eval").body
                return self._compile_node(function_ast, local_names, bindings)

            if function_name not in BUILTIN_FUNCTIONS:
                raise ExpressionCompileError(f"Unsupported function '{function_name}'.")

            instructions: list[dict] = []
            deps: set[str] = set()
            for arg in node.args:
                compiled, child_deps = self._compile_node(arg, local_names, substitutions)
                instructions.extend(compiled)
                deps |= child_deps
            instructions.append({"op": "call", "name": function_name, "argc": len(node.args)})
            return instructions, deps

        raise ExpressionCompileError(f"Unsupported expression construct: {ast.dump(node)}")

    def _apply_substitutions(
        self,
        node: ast.AST,
        substitutions: Mapping[str, ast.AST],
    ) -> ast.AST:
        class SubstitutionTransformer(ast.NodeTransformer):
            def visit_Name(self, name_node: ast.Name) -> ast.AST:
                if name_node.id in substitutions:
                    replacement = substitutions[name_node.id]
                    if not (isinstance(replacement, ast.Name) and replacement.id == name_node.id):
                        return self.visit(copy.deepcopy(replacement))
                return ast.copy_location(ast.Name(id=name_node.id, ctx=name_node.ctx), name_node)

        transformed = SubstitutionTransformer().visit(copy.deepcopy(node))
        return ast.fix_missing_locations(transformed)
