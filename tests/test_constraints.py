import pytest

from bsm_scanner import compile_model
from bsm_scanner.compiler.lowering import GraphLowerer
from bsm_scanner.model.schema import ModelDefinition


def test_multivariate_constraint_payload_is_preserved():
    raw = {
        "metadata": {"name": "mv"},
        "constants": [{"name": "x", "value": 1.0}, {"name": "y", "value": 2.0}],
        "observables": [
            {"name": "obs_x", "expression": "x"},
            {"name": "obs_y", "expression": "y"},
        ],
        "likelihoods": [
            {
                "name": "st_like",
                "kind": "multivariate_gaussian",
                "observables": ["obs_x", "obs_y"],
                "means": [0.0, 0.0],
                "covariance": [[1.0, 0.5], [0.5, 2.0]],
                "quadratic_form_prefactor": 1.0,
            }
        ],
        "outputs": {"save": ["obs_x"]},
    }
    model = ModelDefinition.from_mapping(raw)
    spec = GraphLowerer(model).lower()
    payload = next(node["constraint"] for node in spec.nodes if node["name"] == "st_like")

    assert payload["kind"] == "multivariate_gaussian"
    assert payload["observables"] == ["obs_x", "obs_y"]
    assert payload["covariance"][0][1] == 0.5
    assert payload["quadratic_form_prefactor"] == 1.0


def test_upper_limit_constraint_depends_on_observable():
    raw = {
        "metadata": {"name": "limit"},
        "constants": [{"name": "a", "value": 3.0}],
        "observables": [{"name": "obs", "expression": "a"}],
        "likelihoods": [
            {
                "name": "obs_limit",
                "kind": "upper_limit",
                "observable": "obs",
                "upper": 4.0,
                "sigma": 0.5,
            }
        ],
        "outputs": {"save": ["obs"]},
    }
    model = ModelDefinition.from_mapping(raw)
    spec = GraphLowerer(model).lower()
    node = next(node for node in spec.nodes if node["name"] == "obs_limit")

    assert node["dependencies"] == ["obs"]


def test_table_lookup_constraint_payload_is_preserved():
    raw = {
        "metadata": {"name": "table"},
        "constants": [{"name": "x", "value": 1.0}],
        "observables": [{"name": "obs", "expression": "x"}],
        "likelihoods": [
            {
                "name": "obs_table",
                "kind": "table_lookup",
                "observable": "obs",
                "table": [[0.0, 4.0], [1.0, 0.0], [2.0, 9.0]],
                "interpolation": "cubic_spline",
                "in_range_offset": -6.1,
                "out_of_range_penalty_scale": 4.0e4,
                "out_of_range_penalty_cap": 1.0e6,
            }
        ],
        "outputs": {"save": ["obs"]},
    }
    model = ModelDefinition.from_mapping(raw)
    spec = GraphLowerer(model).lower()
    payload = next(node["constraint"] for node in spec.nodes if node["name"] == "obs_table")

    assert payload["kind"] == "table_lookup"
    assert payload["table"][1] == [1.0, 0.0]
    assert payload["interpolation"] == "cubic_spline"
    assert payload["in_range_offset"] == -6.1
    assert payload["out_of_range_penalty_scale"] == 4.0e4
    assert payload["out_of_range_penalty_cap"] == 1.0e6


def test_table_lookup_uses_interpolated_value_in_range():
    pytest.importorskip("bsm_scanner._core")

    raw = {
        "metadata": {"name": "table-eval"},
        "constants": [{"name": "x", "value": 0.5}],
        "observables": [{"name": "obs", "expression": "x"}],
        "likelihoods": [
            {
                "name": "obs_table",
                "kind": "table_lookup",
                "observable": "obs",
                "table": [[0.0, 4.0], [1.0, 0.0], [2.0, 9.0]],
                "out_of_range_penalty_scale": 4.0,
                "out_of_range_penalty_cap": 1.0e6,
            }
        ],
        "outputs": {"save": ["obs"]},
    }

    compiled = compile_model(ModelDefinition.from_mapping(raw), build_backend=True)
    result = compiled.evaluate({})

    assert result["status"] == "ok"
    assert result["likelihood_terms"]["obs_table"] == pytest.approx(2.0)
    assert result["total_nll"] == pytest.approx(2.0)


def test_table_lookup_supports_cubic_spline_interpolation():
    pytest.importorskip("bsm_scanner._core")

    raw = {
        "metadata": {"name": "table-eval-spline"},
        "constants": [{"name": "x", "value": 0.5}],
        "observables": [{"name": "obs", "expression": "x"}],
        "likelihoods": [
            {
                "name": "obs_table",
                "kind": "table_lookup",
                "observable": "obs",
                "interpolation": "cubic_spline",
                "table": [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]],
            }
        ],
        "outputs": {"save": ["obs"]},
    }

    compiled = compile_model(ModelDefinition.from_mapping(raw), build_backend=True)
    result = compiled.evaluate({})

    assert result["status"] == "ok"
    assert result["likelihood_terms"]["obs_table"] == pytest.approx(0.6875)
    assert result["total_nll"] == pytest.approx(0.6875)


def test_table_lookup_applies_in_range_offset_only_to_interpolated_values():
    pytest.importorskip("bsm_scanner._core")

    raw = {
        "metadata": {"name": "table-eval-offset"},
        "constants": [{"name": "x", "value": 0.5}],
        "observables": [{"name": "obs", "expression": "x"}],
        "likelihoods": [
            {
                "name": "obs_table",
                "kind": "table_lookup",
                "observable": "obs",
                "interpolation": "cubic_spline",
                "in_range_offset": -6.1,
                "table": [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]],
            }
        ],
        "outputs": {"save": ["obs"]},
    }

    compiled = compile_model(ModelDefinition.from_mapping(raw), build_backend=True)
    result = compiled.evaluate({})

    assert result["status"] == "ok"
    assert result["likelihood_terms"]["obs_table"] == pytest.approx(0.6875 - 6.1)
    assert result["total_nll"] == pytest.approx(0.6875 - 6.1)


def test_table_lookup_uses_quadratic_penalty_out_of_range():
    pytest.importorskip("bsm_scanner._core")

    raw = {
        "metadata": {"name": "table-eval-oob"},
        "constants": [{"name": "x", "value": 3.0}],
        "observables": [{"name": "obs", "expression": "x"}],
        "likelihoods": [
            {
                "name": "obs_table",
                "kind": "table_lookup",
                "observable": "obs",
                "table": [[0.0, 4.0], [1.0, 0.0], [2.0, 9.0]],
                "out_of_range_penalty_scale": 4.0,
                "out_of_range_penalty_cap": 1.0e6,
            }
        ],
        "outputs": {"save": ["obs"]},
    }

    compiled = compile_model(ModelDefinition.from_mapping(raw), build_backend=True)
    result = compiled.evaluate({})

    assert result["status"] == "ok"
    assert result["likelihood_terms"]["obs_table"] == pytest.approx(4.0)
    assert result["total_nll"] == pytest.approx(4.0)


def test_multivariate_constraint_supports_full_quadratic_form_prefactor():
    pytest.importorskip("bsm_scanner._core")

    raw = {
        "metadata": {"name": "mv-eval"},
        "constants": [{"name": "x", "value": 1.0}, {"name": "y", "value": 2.0}],
        "observables": [
            {"name": "obs_x", "expression": "x"},
            {"name": "obs_y", "expression": "y"},
        ],
        "likelihoods": [
            {
                "name": "st_like",
                "kind": "multivariate_gaussian",
                "observables": ["obs_x", "obs_y"],
                "means": [0.0, 0.0],
                "covariance": [[1.0, 0.0], [0.0, 1.0]],
                "quadratic_form_prefactor": 1.0,
            }
        ],
        "outputs": {"save": ["obs_x"]},
    }

    compiled = compile_model(ModelDefinition.from_mapping(raw), build_backend=True)
    result = compiled.evaluate({})

    assert result["status"] == "ok"
    assert result["likelihood_terms"]["st_like"] == pytest.approx(5.0)
    assert result["total_nll"] == pytest.approx(5.0)
