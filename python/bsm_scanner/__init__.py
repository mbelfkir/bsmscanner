from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("bsm-scanner")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.2.0"

__all__ = [
    "CompiledModel",
    "core_library_path",
    "describe_core_block",
    "list_core_blocks",
    "ScanSession",
    "ScanRequest",
    "ScanResults",
    "build_scan_request",
    "compile_model",
    "delta_deg_signed",
    "evaluate_scan_point",
    "load_scan_best_fit",
    "load_scan_metadata",
    "load_scan_points",
    "load_scan_summary",
    "load_model",
    "load_results",
    "pmns_observables_from_matrix",
    "register_plugin_function",
    "run_statistics",
    "run_scan",
    "wrap_2pi",
]


def register_plugin_function(plugin: str, function: str, callback):
    """Register a Python-implemented plugin function under (plugin, function),
    callable from YAML via the same `plugin_call` contract a C++ plugin uses
    (see docs/core_plugin_boundaries.md). `callback(arguments: dict, options: dict) -> value`
    receives the resolved bindings/options as plain Python values and returns
    a scalar (float/bool/complex/str). Must be called before compiling/running
    any model that references this (plugin, function) in a plugin_call.
    """
    try:
        from bsm_scanner import _core
    except Exception as exc:  # pragma: no cover - native backend not built
        raise RuntimeError(
            "The native C++ backend is not available. Rebuild with the extension enabled."
        ) from exc
    _core.register_plugin_function(plugin, function, callback)


def __getattr__(name: str):
    if name == "register_plugin_function":
        return register_plugin_function
    if name in __all__:
        from .api import (
            CompiledModel,
            ScanSession,
            compile_model,
            load_model,
            load_results,
            run_scan,
        )
        from .core import delta_deg_signed, pmns_observables_from_matrix, wrap_2pi
        from .library import core_library_path, describe_core_block, list_core_blocks
        from .scan import (
            ScanRequest,
            ScanResults,
            build_scan_request,
            evaluate_scan_point,
            load_scan_best_fit,
            load_scan_metadata,
            load_scan_points,
            load_scan_summary,
        )
        from .statistics import run_statistics

        namespace = {
            "CompiledModel": CompiledModel,
            "core_library_path": core_library_path,
            "describe_core_block": describe_core_block,
            "list_core_blocks": list_core_blocks,
            "ScanSession": ScanSession,
            "ScanRequest": ScanRequest,
            "ScanResults": ScanResults,
            "build_scan_request": build_scan_request,
            "compile_model": compile_model,
            "delta_deg_signed": delta_deg_signed,
            "evaluate_scan_point": evaluate_scan_point,
            "load_scan_best_fit": load_scan_best_fit,
            "load_scan_metadata": load_scan_metadata,
            "load_scan_points": load_scan_points,
            "load_scan_summary": load_scan_summary,
            "load_model": load_model,
            "load_results": load_results,
            "pmns_observables_from_matrix": pmns_observables_from_matrix,
            "run_statistics": run_statistics,
            "run_scan": run_scan,
            "wrap_2pi": wrap_2pi,
        }
        return namespace[name]
    raise AttributeError(name)
