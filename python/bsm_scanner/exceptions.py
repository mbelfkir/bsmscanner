class BSMScannerError(Exception):
    """Base exception for the framework."""


class ModelValidationError(BSMScannerError):
    """Raised when a model definition is malformed."""


class GraphCycleError(BSMScannerError):
    """Raised when the dependency graph contains a cycle."""


class ExpressionCompileError(BSMScannerError):
    """Raised when an expression cannot be lowered safely."""

