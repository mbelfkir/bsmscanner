__all__ = [
    "GraphNode",
    "ModelDefinition",
    "ModelGraph",
    "ModelInvariantSummary",
    "PluginTermAccounting",
    "build_model_graph",
    "build_parity_section",
    "dead_scanned_parameters",
    "export_parity_report",
    "fixed_parameter_names",
    "free_parameter_names",
    "likelihood_term_names",
    "plugin_term_accounting",
    "require_free_parameter_set",
    "require_likelihood_coverage",
    "require_no_dead_scanned_parameters",
    "summarize_model_invariants",
]


def __getattr__(name: str):
    if name == "ModelDefinition":
        from .schema import ModelDefinition

        return ModelDefinition
    if name in {"GraphNode", "ModelGraph", "build_model_graph"}:
        from .graph import GraphNode, ModelGraph, build_model_graph

        namespace = {
            "GraphNode": GraphNode,
            "ModelGraph": ModelGraph,
            "build_model_graph": build_model_graph,
        }
        return namespace[name]
    if name in {
        "ModelInvariantSummary",
        "PluginTermAccounting",
        "build_parity_section",
        "dead_scanned_parameters",
        "export_parity_report",
        "fixed_parameter_names",
        "free_parameter_names",
        "likelihood_term_names",
        "plugin_term_accounting",
        "require_free_parameter_set",
        "require_likelihood_coverage",
        "require_no_dead_scanned_parameters",
        "summarize_model_invariants",
    }:
        from .validation import (
            ModelInvariantSummary,
            PluginTermAccounting,
            build_parity_section,
            dead_scanned_parameters,
            export_parity_report,
            fixed_parameter_names,
            free_parameter_names,
            likelihood_term_names,
            plugin_term_accounting,
            require_free_parameter_set,
            require_likelihood_coverage,
            require_no_dead_scanned_parameters,
            summarize_model_invariants,
        )

        namespace = {
            "ModelInvariantSummary": ModelInvariantSummary,
            "PluginTermAccounting": PluginTermAccounting,
            "build_parity_section": build_parity_section,
            "dead_scanned_parameters": dead_scanned_parameters,
            "export_parity_report": export_parity_report,
            "fixed_parameter_names": fixed_parameter_names,
            "free_parameter_names": free_parameter_names,
            "likelihood_term_names": likelihood_term_names,
            "plugin_term_accounting": plugin_term_accounting,
            "require_free_parameter_set": require_free_parameter_set,
            "require_likelihood_coverage": require_likelihood_coverage,
            "require_no_dead_scanned_parameters": require_no_dead_scanned_parameters,
            "summarize_model_invariants": summarize_model_invariants,
        }
        return namespace[name]
    raise AttributeError(name)
