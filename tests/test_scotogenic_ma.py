from pathlib import Path

import pytest
from bsm_scanner import compile_model, load_model

pytest.importorskip("bsm_scanner._core")


MODEL = Path(__file__).resolve().parents[1] / "models" / "scotogenic_ma" / "model_no.yaml"


def default_point(model):
    return {parameter.name: parameter.default for parameter in model.parameters}


def test_scotogenic_ma_model_loads_with_published_reference_metadata():
    model = load_model(MODEL)

    assert model.metadata.name == "scotogenic_ma_normal"
    assert "ma_2006" in model.metadata.tags
    assert len(model.parameters) == 26
    assert len(model.likelihoods) == 7

    names = {observable.name for observable in model.observables}
    for required in (
        "m_eta_R",
        "m_eta_I",
        "m_eta_charged",
        "dm_mass_analytic",
        "m1",
        "m2",
        "m3",
        "dm21",
        "dm3l",
        "s12",
        "s13",
        "s23",
        "deltaCP",
        "mbetabeta",
    ):
        assert required in names


def test_scotogenic_ma_default_point_evaluates():
    model = load_model(MODEL)
    compiled = compile_model(model, build_backend=True)

    result = compiled.evaluate(default_point(model))

    assert result["status"] == "ok"
    assert result["total_nll"] > 0
    assert result["outputs"]["m_eta_R"] > 0
    assert result["outputs"]["m_eta_I"] > 0
    assert result["outputs"]["dm_mass_analytic"] > 0
    assert result["outputs"]["sum_m"] < 0.12
