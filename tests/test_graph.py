from pathlib import Path

import pytest
from bsm_scanner.api import load_model
from bsm_scanner.compiler.expressions import BUILTIN_FUNCTIONS
from bsm_scanner.compiler.lowering import GraphLowerer
from bsm_scanner.exceptions import GraphCycleError
from bsm_scanner.model.graph import build_model_graph
from bsm_scanner.model.schema import ModelDefinition

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "oneloop_minimal" / "model.yaml"


def test_example_graph_contains_expected_stages():
    model = load_model(EXAMPLE)
    graph = build_model_graph(model)
    order = graph.topological_order()

    assert "Mpsi" in order
    assert "mphi_sq" in order
    assert "neutrino_mass_matrix" in order
    assert "neutrino_svd" in order
    assert "m1" in order
    assert "higgs_mass_term" in order
    assert "output::HiggsMass" in order
    assert order.index("mphi_sq") < order.index("mphi")
    assert order.index("neutrino_mass_matrix") < order.index("neutrino_svd")
    assert order.index("neutrino_svd") < order.index("m1")


def test_lowering_prunes_to_active_subgraph():
    model = load_model(EXAMPLE)
    compiled = GraphLowerer(model).lower()
    node_names = {node["name"] for node in compiled.nodes}

    assert "output::dm21" in node_names
    assert "dm21_term" in node_names
    assert "positive_mphi_sq" in node_names
    assert "I3" not in node_names


def test_cycle_detection_is_explicit():
    raw = {
        "metadata": {"name": "cycle"},
        "derived_scalars": [
            {"name": "a", "expression": "b + 1"},
            {"name": "b", "expression": "a + 1"},
        ],
        "outputs": {"save": ["a"]},
    }
    model = ModelDefinition.from_mapping(raw)
    graph = build_model_graph(model)

    with pytest.raises(GraphCycleError):
        graph.topological_order()


def test_function_expansion_handles_same_name_arguments():
    raw = {
        "metadata": {"name": "fn-identity"},
        "parameters": [
            {"name": "mphi", "value_type": "real", "scan": True, "lower": 0.0, "upper": 10.0, "default": 1.0, "prior": "flat"},
            {"name": "mphip", "value_type": "real", "scan": True, "lower": 0.0, "upper": 10.0, "default": 2.0, "prior": "flat"},
            {"name": "mpsi", "value_type": "real", "scan": True, "lower": 0.0, "upper": 10.0, "default": 3.0, "prior": "flat"},
        ],
        "functions": [
            {"name": "I3lite", "args": ["mphi", "mphip", "mpsi"], "expression": "mphi + mphip + mpsi"}
        ],
        "derived_scalars": [
            {"name": "combo", "expression": "I3lite(mphi, mphip, mpsi)"}
        ],
        "observables": [
            {"name": "obs", "expression": "combo"}
        ],
        "outputs": {"save": ["obs"]},
    }
    model = ModelDefinition.from_mapping(raw)
    graph = build_model_graph(model)
    order = graph.topological_order()

    assert "combo" in order
    assert graph.nodes["combo"].dependencies == {"mphi", "mphip", "mpsi"}


def test_generic_builtin_set_has_no_oneloop_specific_entries():
    assert all(not name.startswith("oneloop_") for name in BUILTIN_FUNCTIONS)


def test_plugin_call_nodes_lower_as_generic_external_calls():
    raw = {
        "metadata": {"name": "plugin-node"},
        "constants": [
            {"name": "mass", "value": 42.0},
            {"name": "tag", "value": "toy", "value_type": "string"},
        ],
        "derived_scalars": [
            {
                "name": "external_mass",
                "value_type": "real",
                "plugin_call": {
                    "plugin": "toy_backend",
                    "function": "mass_like",
                    "bindings": {
                        "mass_in": "mass",
                        "label": "tag",
                    },
                },
            }
        ],
        "observables": [{"name": "obs", "expression": "external_mass"}],
        "outputs": {"save": ["obs"]},
    }
    model = ModelDefinition.from_mapping(raw)
    graph = build_model_graph(model)
    compiled = GraphLowerer(model).lower()

    assert graph.nodes["external_mass"].dependencies == {"mass", "tag"}
    lowered = next(node for node in compiled.nodes if node["name"] == "external_mass")
    assert lowered["plugin_call"]["plugin"] == "toy_backend"
    assert lowered["plugin_call"]["function"] == "mass_like"
    assert lowered["plugin_call"]["bindings"] == [
        {"argument": "label", "source": "tag"},
        {"argument": "mass_in", "source": "mass"},
    ]


def test_plugin_call_contract_extends_to_theory_checks_and_custom_likelihoods():
    raw = {
        "metadata": {"name": "plugin-contract"},
        "constants": [
            {"name": "mass", "value": 42.0},
            {"name": "limit", "value": 10.0},
            {"name": "label", "value": "toy", "value_type": "string"},
        ],
        "observables": [
            {"name": "obs", "expression": "mass"}
        ],
        "theory_checks": [
            {
                "name": "backend_check",
                "plugin_call": {
                    "plugin": "toy_backend",
                    "function": "passes_limit",
                    "bindings": {"x": "mass"},
                    "options": {"limit": 50.0},
                },
                "message": "backend veto",
            }
        ],
        "likelihoods": [
            {
                "name": "backend_nll",
                "kind": "custom",
                "plugin_call": {
                    "plugin": "toy_backend",
                    "function": "nll",
                    "bindings": {
                        "x": "obs",
                        "tag": "label",
                    },
                    "options": {"scale": 2.0},
                    "output": "nll",
                },
            }
        ],
        "outputs": {"save": ["obs"]},
    }
    model = ModelDefinition.from_mapping(raw)
    graph = build_model_graph(model)
    compiled = GraphLowerer(model).lower()

    assert graph.nodes["backend_check"].dependencies == {"mass"}
    assert graph.nodes["backend_nll"].dependencies == {"obs", "label"}

    lowered_check = next(node for node in compiled.nodes if node["name"] == "backend_check")
    assert lowered_check["plugin_call"]["plugin"] == "toy_backend"
    assert lowered_check["plugin_call"]["function"] == "passes_limit"
    assert lowered_check["plugin_call"]["options"] == [
        {"name": "limit", "value": {"kind": "real", "value": 50.0}}
    ]

    lowered_constraint = next(node for node in compiled.nodes if node["name"] == "backend_nll")
    assert lowered_constraint["constraint"]["plugin_call"]["plugin"] == "toy_backend"
    assert lowered_constraint["constraint"]["plugin_call"]["function"] == "nll"
    assert lowered_constraint["constraint"]["plugin_call"]["output"] == "nll"
    assert lowered_constraint["constraint"]["plugin_call"]["bindings"] == [
        {"argument": "tag", "source": "label"},
        {"argument": "x", "source": "obs"},
    ]
