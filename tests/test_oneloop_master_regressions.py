from pathlib import Path

import pytest

from bsm_scanner import compile_model, load_model
from bsm_scanner.model.schema import ModelDefinition
from bsm_scanner.model.validation import (
    require_free_parameter_set,
    require_likelihood_coverage,
    require_no_dead_scanned_parameters,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "oneloop_master"
MASTER_NORMAL_REDUCED = EXAMPLES / "model_normal_reduced.yaml"
MASTER_NORMAL_FULL = EXAMPLES / "model_normal_full.yaml"
MASTER_INVERTED_FULL = EXAMPLES / "model_inverted_full.yaml"

EXPECTED_FREE_PARAMETERS = {
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

EXPECTED_LIKELIHOODS = {
    "theta12_term",
    "theta13_term",
    "theta23_term",
    "deltaCP_term",
    "m12+m3l",
    "sumOfMass",
    "massPinalety",
    "HiggsRgg_term",
    "KPinaleties",
    "EVPinaleties",
    "BRPinaleties",
    "Oblique_term",
    "Omega_term",
    "DDexp_term",
}


def load_variant(path: Path):
    return load_model(path)


def test_oneloop_master_variants_keep_canonical_parameter_partition():
    for path in (MASTER_NORMAL_REDUCED, MASTER_NORMAL_FULL, MASTER_INVERTED_FULL):
        model = load_variant(path)
        require_free_parameter_set(
            model,
            expected=EXPECTED_FREE_PARAMETERS,
            forbidden={"MA2", "sa", "lambda1", "k2", "k3", "Rep", "Imgp"},
        )
        require_no_dead_scanned_parameters(model)


def test_oneloop_master_variants_keep_expected_likelihood_coverage():
    for path in (MASTER_NORMAL_REDUCED, MASTER_NORMAL_FULL, MASTER_INVERTED_FULL):
        require_likelihood_coverage(load_variant(path), EXPECTED_LIKELIHOODS)


def test_oneloop_master_safe_migration_prep_aligns_constants_and_matrix_metadata():
    normal = load_variant(MASTER_NORMAL_FULL)
    inverted = load_variant(MASTER_INVERTED_FULL)

    normal_constants = {item.name: item.value for item in normal.constants}
    inverted_constants = {item.name: item.value for item in inverted.constants}
    normal_matrices = {item.name: item for item in normal.matrices}
    inverted_matrices = {item.name: item for item in inverted.matrices}

    assert normal_constants["bf_dm21"] == pytest.approx(7.49e-05)
    assert normal_constants["bf_dm3l"] == pytest.approx(0.002513)
    assert inverted_constants["bf_dm21"] == pytest.approx(7.49e-05)
    assert inverted_constants["bf_dm3l"] == pytest.approx(-0.002484)

    for matrices in (normal_matrices, inverted_matrices):
        neutrino = matrices["neutrino_mass_matrix"]
        assert neutrino.matrix_type.value == "majorana_mass"
        assert neutrino.role == "neutrino"
        assert neutrino.diagonalize is True


def test_oneloop_master_table_terms_remain_source_faithful():
    normal = load_variant(MASTER_NORMAL_FULL)
    inverted = load_variant(MASTER_INVERTED_FULL)

    normal_terms = {item.name: item for item in normal.likelihoods}
    inverted_terms = {item.name: item for item in inverted.likelihoods}

    for name in ("theta12_term", "theta13_term", "theta23_term", "deltaCP_term"):
        assert normal_terms[name].interpolation.value == "cubic_spline"
        assert inverted_terms[name].interpolation.value == "cubic_spline"
        assert inverted_terms[name].in_range_offset == pytest.approx(-6.1)

    grouped_normal = normal_terms["m12+m3l"].plugin_call
    grouped_inverted = inverted_terms["m12+m3l"].plugin_call
    assert grouped_normal is not None
    assert grouped_inverted is not None
    assert grouped_normal.options["interpolation"] == "cubic_spline"
    assert grouped_inverted.options["interpolation"] == "cubic_spline"
    assert grouped_inverted.options["in_range_offset"] == pytest.approx(-6.1)

def test_oneloop_master_oblique_term_keeps_source_prefactor():
    for path in (MASTER_NORMAL_REDUCED, MASTER_NORMAL_FULL, MASTER_INVERTED_FULL):
        model = load_variant(path)
        oblique = next(item for item in model.likelihoods if item.name == "Oblique_term")
        assert oblique.quadratic_form_prefactor == pytest.approx(1.0)


def test_grouped_neutrino_mass_term_keeps_source_short_circuit_behavior():
    _core = pytest.importorskip("bsm_scanner._core")
    if not _core.has_plugin_support("oneloop_likelihoods"):
        pytest.skip("optional oneloop_likelihoods plugin is not available in this build")

    dm21_table = ROOT / "models" / "oneloop" / "data" / "Normal" / "dm21.csv"
    dm3l_table = ROOT / "models" / "oneloop" / "data" / "Normal" / "dm3l.csv"

    raw = {
        "metadata": {"name": "oneloop-grouped-term"},
        "constants": [
            {"name": "log10_dm21", "value": -2.0},
            {"name": "dm3l_meV", "value": 2.5},
        ],
        "likelihoods": [
            {
                "name": "m12+m3l",
                "kind": "custom",
                "plugin_call": {
                    "plugin": "oneloop_likelihoods",
                    "function": "neutrino_mass_term",
                    "output": "nll",
                    "bindings": {
                        "log10_dm21": "log10_dm21",
                        "dm3l_meV": "dm3l_meV",
                    },
                    "options": {
                        "dm21_table_file": str(dm21_table),
                        "dm3l_table_file": str(dm3l_table),
                        "interpolation": "cubic_spline",
                        "out_of_range_penalty_scale": 4.0e4,
                        "out_of_range_penalty_cap": 1.0e6,
                        "in_range_offset": 0.0,
                    },
                },
            }
        ],
        "outputs": {"save": []},
    }

    compiled = compile_model(ModelDefinition.from_mapping(raw), build_backend=True)
    result = compiled.evaluate({})

    assert result["status"] == "ok"
    assert result["likelihood_terms"]["m12+m3l"] == pytest.approx(4.0e4)
    assert result["total_nll"] == pytest.approx(4.0e4)


def test_grouped_neutrino_mass_term_keeps_inverted_additive_offset():
    _core = pytest.importorskip("bsm_scanner._core")
    if not _core.has_plugin_support("oneloop_likelihoods"):
        pytest.skip("optional oneloop_likelihoods plugin is not available in this build")

    dm21_table = ROOT / "models" / "oneloop" / "data" / "Inverted" / "dm21.csv"
    dm3l_table = ROOT / "models" / "oneloop" / "data" / "Inverted" / "dm3l.csv"

    def first_row(path: Path) -> tuple[float, float]:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            x_str, y_str, *_ = stripped.replace(",", " ").split()
            return float(x_str), float(y_str)
        raise AssertionError(f"empty table: {path}")

    dm21_x, dm21_y = first_row(dm21_table)
    dm3l_x, dm3l_y = first_row(dm3l_table)

    raw = {
        "metadata": {"name": "oneloop-grouped-term-inverted"},
        "constants": [
            {"name": "log10_dm21", "value": dm21_x},
            {"name": "dm3l_meV", "value": dm3l_x},
        ],
        "likelihoods": [
            {
                "name": "m12+m3l",
                "kind": "custom",
                "plugin_call": {
                    "plugin": "oneloop_likelihoods",
                    "function": "neutrino_mass_term",
                    "output": "nll",
                    "bindings": {
                        "log10_dm21": "log10_dm21",
                        "dm3l_meV": "dm3l_meV",
                    },
                    "options": {
                        "dm21_table_file": str(dm21_table),
                        "dm3l_table_file": str(dm3l_table),
                        "interpolation": "cubic_spline",
                        "out_of_range_penalty_scale": 4.0e4,
                        "out_of_range_penalty_cap": 1.0e6,
                        "in_range_offset": -6.1,
                    },
                },
            }
        ],
        "outputs": {"save": []},
    }

    compiled = compile_model(ModelDefinition.from_mapping(raw), build_backend=True)
    result = compiled.evaluate({})

    assert result["status"] == "ok"
    assert result["likelihood_terms"]["m12+m3l"] == pytest.approx(dm21_y + dm3l_y - 12.2)
