__all__ = [
    "CompiledExpression",
    "CompiledModelSpec",
    "ExpressionCompiler",
    "GraphLowerer",
]


def __getattr__(name: str):
    if name == "CompiledExpression" or name == "ExpressionCompiler":
        from .expressions import CompiledExpression, ExpressionCompiler

        namespace = {
            "CompiledExpression": CompiledExpression,
            "ExpressionCompiler": ExpressionCompiler,
        }
        return namespace[name]
    if name == "CompiledModelSpec" or name == "GraphLowerer":
        from .lowering import CompiledModelSpec, GraphLowerer

        namespace = {
            "CompiledModelSpec": CompiledModelSpec,
            "GraphLowerer": GraphLowerer,
        }
        return namespace[name]
    raise AttributeError(name)
