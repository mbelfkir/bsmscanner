from pathlib import Path

import pytest
from bsm_scanner import compile_model, load_model, run_scan

pytest.importorskip("bsm_scanner._core")


ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models" / "oneloop"
FIXED_TIMESTAMP = "2026-06-08T00:00:00+00:00"


REFERENCE = {
    "model_chi_no.yaml": {
        "metadata": "oneloop_chi_normal",
        "outputs": {
            "Mchi": 685.0298193896,
            "mphich": 764.5337721985,
            "MH01": 721.2929563438,
            "MH02": 727.9407378219,
            "MA01": 712.1194620333,
            "s12": 0.3079612152794,
            "s13": 0.02267532311526,
            "s23": 0.4727613084648,
            "delta_cp_deg": 217.1347650646,
            "dm21": 7.370115454528e-05,
            "dm3l": 0.002499717559,
            "sum_mnu_eV": 0.05858211316552,
            "ObliqueS": -0.003411240200368,
            "ObliqueT": 0.04079180145361,
            "R_gammagamma": 0.9811632464403,
            "BR_mu_to_e_gamma": 5.762847515245e-14,
        },
    },
    "model_chi_io.yaml": {
        "metadata": "oneloop_chi_inverted",
        "outputs": {
            "Mchi": 546.8042889321,
            "mphich": 565.9525735533,
            "MH01": 560.2873528161,
            "MH02": 626.7812689443,
            "MA01": 612.3441831496,
            "s12": 0.3037638588871,
            "s13": 0.02244612588537,
            "s23": 0.5571855061149,
            "delta_cp_deg": 282.1346091033,
            "dm21": 7.376236761061e-05,
            "dm3l": -0.002501074559053,
            "sum_mnu_eV": 0.09927850459873,
            "ObliqueS": 0.003927113043189,
            "ObliqueT": 0.03383733292528,
            "R_gammagamma": 0.9953901651541,
            "BR_mu_to_e_gamma": 3.983515895746e-23,
        },
    },
    "model_h01_no.yaml": {
        "metadata": "oneloop_h01_normal",
        "outputs": {
            "Mchi": 231.6640210736,
            "mphich": 100.6806422054,
            "MH01": 73.11204181893,
            "MH02": 104.2487915294,
            "MA01": 78.2647930913,
            "s12": 0.3018149121735,
            "s13": 0.02239627503383,
            "s23": 0.5503303387339,
            "delta_cp_deg": 216.6839313665,
            "dm21": 7.563949765257e-05,
            "dm3l": 0.002516572273594,
            "sum_mnu_eV": 0.05886254608415,
            "ObliqueS": -0.01107542247639,
            "ObliqueT": 0.004112878570315,
            "R_gammagamma": 0.9737774291661,
            "BR_mu_to_e_gamma": 4.208657381444e-16,
        },
    },
    "model_h01_io.yaml": {
        "metadata": "oneloop_h01_inverted",
        "outputs": {
            "Mchi": 220.6188077718,
            "mphich": 77.07756191292,
            "MH01": 70.00325295911,
            "MH02": 152.6832945892,
            "MA01": 87.46126101692,
            "s12": 0.3132967789027,
            "s13": 0.02210064712839,
            "s23": 0.5494128833574,
            "delta_cp_deg": 269.2838361651,
            "dm21": 7.488403046589e-05,
            "dm3l": -0.002494257916045,
            "sum_mnu_eV": 0.09912967745158,
            "ObliqueS": 0.03410224063151,
            "ObliqueT": 0.07150924614255,
            "R_gammagamma": 1.046636059902,
            "BR_mu_to_e_gamma": 1.161920419221e-14,
        },
    },
}


def _load(name: str):
    return load_model(MODEL_DIR / name)


def _default_point(model):
    return {parameter.name: parameter.default for parameter in model.parameters}


@pytest.mark.parametrize("manifest", sorted(REFERENCE))
def test_oneloop_reference_variants_load_and_compile(manifest):
    model = _load(manifest)
    compiled = compile_model(model, build_backend=False)

    assert model.metadata.name == REFERENCE[manifest]["metadata"]
    assert len(model.parameters) == 26
    assert len(compiled.plan.evaluation_order) > 0
    assert {parameter.name for parameter in model.parameters} >= {
        "Mdm",
        "MN",
        "sh",
        "ypr11",
        "ypi11",
        "Y1r1",
        "Y1i1",
        "ynr1",
        "yni1",
    }


@pytest.mark.parametrize("manifest", sorted(REFERENCE))
def test_oneloop_reference_default_matches_supplied_scanner_row(manifest):
    model = _load(manifest)
    compiled = compile_model(model, build_backend=True)

    result = compiled.evaluate(_default_point(model))

    assert result["status"] == "ok"
    assert result["valid"] is True
    for name, expected in REFERENCE[manifest]["outputs"].items():
        assert result["outputs"][name] == pytest.approx(expected, rel=2.0e-8, abs=1.0e-12)


@pytest.mark.parametrize(
    ("manifest", "expected"),
    [
        ("model_chi_no.yaml", {"Mchi": "Mdm", "MH01": "Mdm + gap_H01"}),
        ("model_h01_no.yaml", {"MH01": "Mdm", "Mchi": "Mdm + gap_chi"}),
    ],
)
def test_oneloop_reference_mass_basis_identities(manifest, expected):
    model = _load(manifest)
    result = compile_model(model, build_backend=True).evaluate(_default_point(model))
    point = _default_point(model)
    outputs = result["outputs"]

    if expected["Mchi"] == "Mdm":
        assert outputs["Mchi"] == pytest.approx(point["Mdm"])
        assert outputs["MH01"] == pytest.approx(point["Mdm"] + point["gap_H01"])
    else:
        assert outputs["MH01"] == pytest.approx(point["Mdm"])
        assert outputs["Mchi"] == pytest.approx(point["Mdm"] + point["gap_chi"])


@pytest.mark.parametrize(
    "manifest",
    [
        "model_chi_no_micromegas.yaml",
        "model_chi_io_micromegas.yaml",
        "model_h01_no_micromegas.yaml",
        "model_h01_io_micromegas.yaml",
    ],
)
def test_oneloop_reference_optional_micromegas_manifests_compile_without_backend(manifest):
    model = _load(manifest)
    compiled = compile_model(model, build_backend=False)

    assert "Omega" in compiled.plan.saved_outputs
    assert "DD_pvalue" in compiled.plan.saved_outputs
    omega_node = next(node for node in compiled.plan.nodes if node["name"] == "Omega")
    assert omega_node["plugin_call"]["plugin"] == "oneloop_micromegas"
    bindings = {
        binding["argument"]: binding["source"]
        for binding in omega_node["plugin_call"]["bindings"]
    }
    assert bindings["MA02"] == "MA2"
    assert bindings["thetaa"] == "thetaa_backend"


@pytest.mark.parametrize(
    "manifest",
    [
        "model_chi_no_mcmc.yaml",
        "model_chi_io_mcmc.yaml",
        "model_h01_no_mcmc.yaml",
        "model_h01_io_mcmc.yaml",
        "model_chi_no_micromegas_mcmc.yaml",
        "model_chi_io_micromegas_mcmc.yaml",
        "model_h01_no_micromegas_mcmc.yaml",
        "model_h01_io_micromegas_mcmc.yaml",
    ],
)
def test_oneloop_reference_mcmc_manifests_enable_posterior(manifest):
    model = _load(manifest)
    compiled = compile_model(model, build_backend=False)

    assert compiled.plan.scan["posterior"]["enabled"] is True
    assert compiled.plan.scan["posterior"]["method"] == "emcee"
    assert model.scan.posterior["start_from"]["initialization"] == "elite_covariance"


def test_oneloop_reference_one_point_scan_writes_outputs(tmp_path):
    model = _load("model_chi_no.yaml")
    model.scan.engine = "serial_random"
    model.scan.save_every = 1
    model.scan.settings = {
        "objective": "nll",
        "max_evaluations": 1,
        "invalid_penalty": 1.0e12,
        "save_invalid_points": True,
        "verbose": 0,
    }
    compiled = compile_model(model, build_backend=False)

    result = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "scan",
        run_id="oneloop-reference-smoke",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert result.points_path.exists()
    text = result.points_path.read_text(encoding="utf-8")
    assert "valid" in text.splitlines()[0]
    assert "output::s12" in text.splitlines()[0]
    assert "likelihood::s12_nufit" in text.splitlines()[0]
