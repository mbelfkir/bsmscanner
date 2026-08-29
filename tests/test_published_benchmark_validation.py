from __future__ import annotations

import math
from pathlib import Path

import pytest
from bsm_scanner import compile_model, load_model

pytest.importorskip("bsm_scanner._core")


ROOT = Path(__file__).resolve().parents[1]


def evaluate(model_path: str, overrides: dict[str, float] | None = None):
    model = load_model(ROOT / model_path)
    compiled = compile_model(model, build_backend=True)
    point = {parameter.name: parameter.default for parameter in model.parameters}
    if overrides:
        point.update(overrides)
    result = compiled.evaluate(point)
    assert result["status"] == "ok", result.get("failure_reason")
    return result["outputs"]


@pytest.mark.parametrize(
    "model_path, required_outputs",
    [
        (
            "models/scotogenic_ma/model_no.yaml",
            ["m_eta_R", "m_eta_I", "m1", "m2", "m3", "dm21", "dm3l"],
        ),
        (
            "models/minimal_bl/model.yaml",
            ["MZprime", "contact_scale", "HeavyNeutrino1Mass", "HiggsSignalStrength"],
        ),
        (
            "models/two_higgs_doublet/model.yaml",
            ["HeavyCPEvenMass", "CPoddMass", "ChargedHiggsMass", "HiggsSignalStrength"],
        ),
        (
            "models/smeft_wilson/model.yaml",
            ["SMEFTExpansionParameter", "ObliqueSProxy", "HiggsMuGGFProxy"],
        ),
        (
            "models/zprime_simplified/model.yaml",
            ["MediatorMass", "DarkMatterMass", "WidthFractionProxy"],
        ),
        (
            "models/leptoquark_brw/model.yaml",
            ["LeptoquarkMass", "WidthFractionProxy", "ElectronContactProxy"],
        ),
        (
            "models/alp_effective/model.yaml",
            ["ALPMass", "PhotonCoupling", "LifetimeProxyInvGeV"],
        ),
    ],
)
def test_published_benchmark_defaults_evaluate(model_path, required_outputs):
    outputs = evaluate(model_path)

    for name in required_outputs:
        assert name in outputs
        assert outputs[name] is not None


def test_scotogenic_ma_neutrino_mass_scales_with_lambda5():
    reference = evaluate("models/scotogenic_ma/model_no.yaml", {"lambda5": 1.0e-8})
    suppressed = evaluate("models/scotogenic_ma/model_no.yaml", {"lambda5": 1.0e-12})

    expected_ratio = 1.0e-4
    assert suppressed["inert_neutral_splitting"] / reference["inert_neutral_splitting"] == pytest.approx(
        expected_ratio, rel=1.0e-3
    )
    assert suppressed["loop_N1"] / reference["loop_N1"] == pytest.approx(expected_ratio, rel=1.0e-3)
    assert suppressed["loop_N2"] / reference["loop_N2"] == pytest.approx(expected_ratio, rel=1.0e-3)
    assert suppressed["loop_N3"] / reference["loop_N3"] == pytest.approx(expected_ratio, rel=1.0e-3)
    assert suppressed["m1"] / reference["m1"] == pytest.approx(expected_ratio, rel=1.0e-3)
    assert suppressed["m2"] / reference["m2"] == pytest.approx(expected_ratio, rel=1.0e-3)
    assert suppressed["m3"] / reference["m3"] == pytest.approx(expected_ratio, rel=1.0e-3)


def test_minimal_bl_mass_and_lep_contact_identities():
    outputs = evaluate(
        "models/minimal_bl/model.yaml",
        {"gBL": 0.2, "vBL": 10000.0, "sin_alpha": 0.0},
    )

    assert outputs["MZprime"] == pytest.approx(4000.0)
    assert outputs["contact_scale"] == pytest.approx(20000.0)
    assert outputs["HeavyNeutrino1Mass"] == pytest.approx(math.sqrt(2.0) * 0.01 * 10000.0)
    assert outputs["HiggsSignalStrength"] == pytest.approx(1.0)


def test_two_higgs_doublet_alignment_limit():
    outputs = evaluate(
        "models/two_higgs_doublet/model.yaml",
        {"cos_ba": 0.0, "mH": 300.0, "mA": 500.0, "mHp": 500.0, "m12sq": 10000.0},
    )

    assert outputs["HiggsSignalStrength"] == pytest.approx(1.0)
    assert outputs["ObliqueTProxy"] == pytest.approx(0.0)


def test_smeft_zero_wilson_coefficients_return_sm_limit():
    outputs = evaluate("models/smeft_wilson/model.yaml")

    assert outputs["ObliqueSProxy"] == pytest.approx(0.0)
    assert outputs["ObliqueTProxy"] == pytest.approx(0.0)
    assert outputs["HiggsMuGGFProxy"] == pytest.approx(1.0)
    assert outputs["HiggsMuGammaGammaProxy"] == pytest.approx(1.0)
    assert outputs["KappaBProxy"] == pytest.approx(1.0)
    assert outputs["KappaTauProxy"] == pytest.approx(1.0)


def test_zprime_forum_coupling_benchmark_width_and_rates():
    outputs = evaluate(
        "models/zprime_simplified/model.yaml",
        {"MZp": 1000.0, "mchi": 10.0, "gq": 0.25, "gchi": 1.0, "gl": 0.0},
    )

    expected_monojet_proxy = 0.25**2 * 1.0**2
    assert outputs["ResonantDMOpen"] == pytest.approx(1.0)
    assert outputs["MonojetRateProxy"] == pytest.approx(expected_monojet_proxy)
    assert outputs["DileptonRateProxy"] == pytest.approx(0.0)
    assert outputs["WidthFractionProxy"] == pytest.approx(0.05636737408661791)


def test_leptoquark_zero_couplings_decouple_contact_and_lfv_proxies():
    outputs = evaluate(
        "models/leptoquark_brw/model.yaml",
        {"yeq": 0.0, "ymuq": 0.0, "ytauq": 0.0, "ybnu": 0.0},
    )

    assert outputs["WidthFractionProxy"] == pytest.approx(0.0)
    assert outputs["ElectronContactProxy"] == pytest.approx(0.0)
    assert outputs["MuonContactProxy"] == pytest.approx(0.0)
    assert outputs["MuEFlavorProxy"] == pytest.approx(0.0)


def test_alp_zero_couplings_decouple_visible_proxies():
    outputs = evaluate(
        "models/alp_effective/model.yaml",
        {"cgam": 0.0, "cgg": 0.0, "cee": 0.0, "cmumu": 0.0},
    )

    assert outputs["PhotonCoupling"] == pytest.approx(0.0)
    assert outputs["GluonCoupling"] == pytest.approx(0.0)
    assert outputs["ElectronCoupling"] == pytest.approx(0.0)
    assert outputs["MuonCoupling"] == pytest.approx(0.0)
    assert outputs["GluonColliderProxy"] == pytest.approx(0.0)
    assert outputs["EFTValidityRatio"] == pytest.approx(1.0e-6)
