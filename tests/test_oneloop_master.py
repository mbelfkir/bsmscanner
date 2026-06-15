import json
import math
from pathlib import Path

import pytest

from bsm_scanner import compile_model, load_model, run_scan
from bsm_scanner.scan import evaluate_scan_point


pytest.importorskip("bsm_scanner._core")
from bsm_scanner import _core  # type: ignore[attr-defined]


EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "oneloop_master"
MASTER_EXAMPLE = EXAMPLES / "model.yaml"
MASTER_NORMAL_REDUCED = EXAMPLES / "model_normal_reduced.yaml"
MASTER_NORMAL_FULL = EXAMPLES / "model_normal_full.yaml"
MASTER_INVERTED_FULL = EXAMPLES / "model_inverted_full.yaml"
ONELOOP_CHI_NO_MICROMEGAS = Path(__file__).resolve().parents[1] / "models" / "oneloop" / "model_chi_no_micromegas.yaml"
FIXED_TIMESTAMP = "2026-04-10T00:00:00+00:00"


def load_variant(path: Path):
    return load_model(path)


def make_master_model():
    return load_variant(MASTER_EXAMPLE)


def make_master_serial_random_model():
    model = make_master_model()
    model.scan.engine = "serial_random"
    model.scan.save_every = 1
    model.scan.seed = 20260410
    model.scan.settings = {
        "objective": "nll",
        "max_evaluations": 1,
        "invalid_objective": 1.0e30,
        "save_invalid_points": True,
        "verbose": 0,
    }
    return model


def default_point(model):
    return {parameter.name: parameter.default for parameter in model.parameters}


def test_latest_master_variants_load_with_source_faithful_parameter_set():
    reduced = load_variant(MASTER_NORMAL_REDUCED)
    normal_full = load_variant(MASTER_NORMAL_FULL)
    inverted = load_variant(MASTER_INVERTED_FULL)

    assert reduced.metadata.name == "oneloop_master_normal_reduced"
    assert normal_full.metadata.name == "oneloop_master_normal_full"
    assert inverted.metadata.name == "oneloop_master_inverted_full"

    expected_removed = {"MA2", "sa", "lambda1", "Rep", "Imgp"}
    expected_kept = {
        "Mpsi",
        "MN",
        "Mphi",
        "MA1",
        "MH1",
        "MH2",
        "sh",
        "k1",
        "k4",
        "Reye",
        "Imgye",
        "Reymu",
        "Imgymu",
        "Reytau",
        "Imgytau",
        "ReYe",
        "ImgYe",
        "ReYmu",
        "ImgYmu",
        "ReYtau",
        "ImgYtau",
        "Reyp",
        "Imgyp",
        "lambda2",
        "lambda3",
        "k5",
    }

    for model in (reduced, normal_full, inverted):
        names = {parameter.name for parameter in model.parameters}
        assert len(model.parameters) == 26
        assert expected_kept == names
        assert not (expected_removed & names)


def test_reduced_variant_fixes_invalid_signed_log_priors_from_legacy_config():
    model = load_variant(MASTER_NORMAL_REDUCED)
    parameter_map = {parameter.name: parameter for parameter in model.parameters}

    for name in (
        "k1",
        "k4",
        "Reye",
        "Imgye",
        "Reymu",
        "Imgymu",
        "Reytau",
        "Imgytau",
        "ReYe",
        "ImgYe",
        "ReYmu",
        "ImgYmu",
        "ReYtau",
        "ImgYtau",
        "Reyp",
        "Imgyp",
    ):
        assert parameter_map[name].prior == "flat"


def test_latest_master_model_loads_with_expected_constraints_and_dm_sector():
    model = make_master_model()

    assert model.metadata.name == "oneloop_master_normal_reduced"
    assert len(model.parameters) == 26
    assert len(model.likelihoods) == 14

    names = {observable.name for observable in model.observables}
    for required in (
        "Theta12",
        "HiggsRgg",
        "Lambda",
        "Omega",
        "SIxsec",
        "xsecSI",
        "DD_pvalue",
        "DMCandidateMass",
        "darkMatter",
        "DM_target_match",
    ):
        assert required in names

    likelihood_names = {likelihood.name for likelihood in model.likelihoods}
    for required in (
        "theta12_term",
        "m12+m3l",
        "sumOfMass",
        "massPinalety",
        "KPinaleties",
        "EVPinaleties",
        "BRPinaleties",
        "Oblique_term",
        "Omega_term",
        "DDexp_term",
    ):
        assert required in likelihood_names

    theta12_term = next(likelihood for likelihood in model.likelihoods if likelihood.name == "theta12_term")
    neutrino_mass_term = next(likelihood for likelihood in model.likelihoods if likelihood.name == "m12+m3l")
    oblique_term = next(likelihood for likelihood in model.likelihoods if likelihood.name == "Oblique_term")
    assert theta12_term.interpolation.value == "cubic_spline"
    assert neutrino_mass_term.plugin_call is not None
    assert neutrino_mass_term.plugin_call.plugin == "oneloop_likelihoods"
    assert neutrino_mass_term.plugin_call.function == "neutrino_mass_term"
    assert oblique_term.quadratic_form_prefactor == 1.0


def test_latest_master_variants_compile_without_native_dm_backend():
    for path in (MASTER_NORMAL_REDUCED, MASTER_NORMAL_FULL, MASTER_INVERTED_FULL):
        model = load_variant(path)
        compiled = compile_model(model, build_backend=False)

        assert len(compiled.plan.evaluation_order) > 0
        assert "Omega" in compiled.plan.saved_outputs
        assert "xsecSI" in compiled.plan.saved_outputs
        assert "darkMatter" in compiled.plan.saved_outputs
        omega_node = next(node for node in compiled.plan.nodes if node["name"] == "Omega")
        assert omega_node["plugin_call"]["plugin"] == "oneloop_micromegas"
        assert omega_node["plugin_call"]["function"] == "omega"


def test_latest_master_backend_capability_is_exposed():
    assert isinstance(_core.has_plugin_support("oneloop_micromegas"), bool)


@pytest.mark.skipif(
    not _core.has_plugin_support("oneloop_micromegas"),
    reason="optional oneloop micrOMEGAs backend is not available in this build",
)
def test_latest_master_default_point_evaluates_with_dm_outputs():
    model = make_master_model()
    model.theory_checks = []
    model.likelihoods = []
    compiled = compile_model(model, build_backend=True)

    result = compiled.evaluate(default_point(model))

    assert result["status"] == "ok"
    for required in ("Omega", "SIxsec", "xsecSI", "DD_pvalue", "DMCandidateMass", "darkMatter", "Lambda"):
        assert required in result["outputs"]


@pytest.mark.skipif(
    not _core.has_plugin_support("oneloop_micromegas"),
    reason="optional oneloop micrOMEGAs backend is not available in this build",
)
def test_latest_master_serial_random_smoke_scan_writes_outputs(tmp_path):
    model = make_master_serial_random_model()
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "scan",
        run_id="oneloop-master-smoke",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert results.points_path.exists()
    assert results.metadata_path.exists()
    assert results.summary_path.exists()
    metadata = json.loads(results.metadata_path.read_text(encoding="utf-8"))
    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))

    assert metadata["model_name"] == "oneloop_master_normal_reduced"
    assert "Omega" in metadata["selected_outputs"]
    assert "darkMatter" in metadata["selected_outputs"]
    assert summary["evaluations"] == 1


@pytest.mark.skipif(
    not _core.has_plugin_support("oneloop_micromegas"),
    reason="optional oneloop micrOMEGAs backend is not available in this build",
)
def test_oneloop_chi_no_micromegas_relic_density_dd_and_si_evaluate(tmp_path):
    model = load_model(ONELOOP_CHI_NO_MICROMEGAS)
    compiled = compile_model(model, build_backend=True)
    point = {
        "Mdm": 6.850298193896e02,
        "gap_charged": 7.950395280889e01,
        "gap_H01": 3.626313695421e01,
        "gap_H02": 6.647781478029e00,
        "gap_A01": 2.708964264372e01,
        "MN": 1.169219004969e03,
        "sh": 1.083313865470e-01,
        "l2": 3.035793131227e-04,
        "l3": 1.731115300762e00,
        "k1": 3.567481173699e00,
        "k4": 4.354320051702e-01,
        "k5": 4.876562044884e-01,
        "ypr11": 5.363831808236e-06,
        "ypi11": 0.0,
        "Y1r1": 1.608676133379e-03,
        "Y1i1": -2.450875758750e-03,
        "Y1r2": -3.543940723969e-03,
        "Y1i2": 4.431658781404e-04,
        "Y1r3": -6.012512737118e-03,
        "Y1i3": 3.632232814744e-03,
        "ynr1": 8.748562858429e-03,
        "yni1": -8.142091822126e-03,
        "ynr2": 1.198560905959e-01,
        "yni2": -7.218269773237e-02,
        "ynr3": 8.243418422035e-02,
        "yni3": -1.469958211852e-02,
    }
    vector = [point[parameter.name] for parameter in model.parameters if parameter.scan]

    record = evaluate_scan_point(model, compiled, vector, run_directory=tmp_path / "oneloop-plugin-point")
    result = record["point_result"]
    outputs = result["outputs"]

    assert result["status"] == "ok"
    assert record["valid"] is True
    assert outputs["darkMatter"] == "~chi"
    assert outputs["DM_target_match"] is True
    assert outputs["DM_candidate_valid"] is True
    for name in ("Omega", "SIxsec", "xsecSI", "DD_pvalue"):
        assert math.isfinite(float(outputs[name]))
    assert outputs["Omega"] == pytest.approx(0.12017404419416185)
    assert outputs["SIxsec"] == pytest.approx(1.0046473817881528e-14)
    assert outputs["xsecSI"] == pytest.approx(outputs["SIxsec"])
    assert outputs["DD_pvalue"] == pytest.approx(0.5)
    assert result["likelihood_terms"]["relic_density"] == pytest.approx(0.010517840806058422)
