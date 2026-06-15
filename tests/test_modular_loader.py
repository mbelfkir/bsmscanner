from pathlib import Path

import pytest

from bsm_scanner import compile_model, load_model
from bsm_scanner.exceptions import ModelValidationError


ROOT = Path(__file__).resolve().parents[1]
MODULAR_ONeloop = ROOT / "models" / "oneloop" / "model.yaml"
WRAPPER_ONeloop = ROOT / "examples" / "oneloop_full" / "model.yaml"
LEGACY_ONeloop = ROOT / "tests" / "fixtures" / "oneloop_full_single_file.yaml"


def test_modular_oneloop_model_matches_single_file_fixture():
    modular = load_model(MODULAR_ONeloop)
    wrapper = load_model(WRAPPER_ONeloop)
    legacy = load_model(LEGACY_ONeloop)

    assert wrapper == modular

    assert modular.metadata == legacy.metadata
    assert modular.parameters == legacy.parameters
    assert modular.likelihoods == legacy.likelihoods
    assert modular.outputs == legacy.outputs

    modular_constants = {item.name: item.value for item in modular.constants}
    legacy_constants = {item.name: item.value for item in legacy.constants}
    for name, value in legacy_constants.items():
        assert modular_constants[name] == value

    modular_matrices = {item.name: item for item in modular.matrices}
    legacy_matrices = {item.name: item for item in legacy.matrices}
    assert modular_matrices["neutrino_mass_matrix"].rows == legacy_matrices["neutrino_mass_matrix"].rows
    assert modular_matrices["neutrino_mass_matrix"].matrix_type is not None
    assert modular_matrices["neutrino_mass_matrix"].role == "neutrino"
    assert modular_matrices["neutrino_mass_matrix"].diagonalize is True


def test_modular_oneloop_model_compiles_successfully():
    compiled = compile_model(MODULAR_ONeloop, build_backend=False)

    assert compiled.model.metadata.name == "oneloop_full_normal"
    assert len(compiled.plan.nodes) == 253
    assert len(compiled.plan.evaluation_order) == 253


def test_missing_import_file_raises_clear_error(tmp_path):
    model_path = tmp_path / "model.yaml"
    model_path.write_text(
        "metadata:\n  name: missing-import\nimports:\n  - missing.yaml\n",
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="missing.yaml"):
        load_model(model_path)


def test_duplicate_named_entries_raise_clear_error(tmp_path):
    root = tmp_path
    (root / "model.yaml").write_text(
        "metadata:\n  name: duplicate-entries\nimports:\n  - a.yaml\n  - b.yaml\n",
        encoding="utf-8",
    )
    parameter_fragment = (
        "parameters:\n"
        "  - name: x\n"
        "    value_type: real\n"
        "    scan: false\n"
        "    default: 1.0\n"
        "    prior: fixed\n"
    )
    (root / "a.yaml").write_text(parameter_fragment, encoding="utf-8")
    (root / "b.yaml").write_text(parameter_fragment, encoding="utf-8")

    with pytest.raises(ModelValidationError, match="Duplicate entry 'x' in section 'parameters'"):
        load_model(root / "model.yaml")


def test_nested_relative_imports_and_table_paths_resolve_correctly(tmp_path):
    root = tmp_path
    (root / "blocks" / "constraints").mkdir(parents=True)
    (root / "blocks" / "data").mkdir(parents=True)

    (root / "model.yaml").write_text(
        "metadata:\n"
        "  name: nested-relative-model\n"
        "imports:\n"
        "  - blocks/core.yaml\n"
        "  - outputs.yaml\n",
        encoding="utf-8",
    )
    (root / "blocks" / "core.yaml").write_text(
        "imports:\n"
        "  - ../parameters.yaml\n"
        "  - ../observables.yaml\n"
        "  - constraints/likelihoods.yaml\n",
        encoding="utf-8",
    )
    (root / "parameters.yaml").write_text(
        "parameters:\n"
        "  - name: x\n"
        "    value_type: real\n"
        "    scan: false\n"
        "    default: 1.0\n"
        "    prior: fixed\n",
        encoding="utf-8",
    )
    (root / "observables.yaml").write_text(
        "observables:\n"
        "  - name: x_obs\n"
        "    value_type: real\n"
        "    expression: x\n",
        encoding="utf-8",
    )
    (root / "outputs.yaml").write_text(
        "outputs:\n"
        "  save:\n"
        "    - x_obs\n",
        encoding="utf-8",
    )
    (root / "blocks" / "constraints" / "likelihoods.yaml").write_text(
        "likelihoods:\n"
        "  - name: x_term\n"
        "    kind: table_lookup\n"
        "    observable: x_obs\n"
        "    table_file: ../data/x_table.csv\n",
        encoding="utf-8",
    )
    (root / "blocks" / "data" / "x_table.csv").write_text(
        "0.0, 4.0\n1.0, 0.0\n2.0, 4.0\n",
        encoding="utf-8",
    )

    model = load_model(root / "model.yaml")
    likelihood = next(item for item in model.likelihoods if item.name == "x_term")

    assert model.metadata.name == "nested-relative-model"
    assert len(likelihood.table) == 3

    compiled = compile_model(model, build_backend=False)
    assert compiled.plan.saved_outputs == ["x_obs"]
