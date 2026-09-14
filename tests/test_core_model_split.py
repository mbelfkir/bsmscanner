from pathlib import Path

import pytest
from bsm_scanner import compile_model, load_model
from bsm_scanner.compiler.lowering import GraphLowerer
from bsm_scanner.model.schema import MatrixKind, ModelDefinition

ROOT = Path(__file__).resolve().parents[1]


def test_matrix_metadata_parses_and_propagates_through_lowering():
    raw = {
        "metadata": {"name": "matrix-metadata"},
        "matrices": [
            {
                "name": "sector_matrix",
                "value_type": "complex_matrix",
                "type": "hermitian",
                "role": "sample_sector",
                "diagonalize": True,
                "rows": [["1.0", "0.0"], ["0.0", "2.0"]],
            }
        ],
        "observables": [
            {
                "name": "lowest_eval",
                "value_type": "real",
                "projection": {
                    "from": "diag__sample_sector",
                    "quantity": "eigenvalues",
                    "index": 0,
                },
            }
        ],
        "outputs": {"save": ["lowest_eval"]},
    }

    model = ModelDefinition.from_mapping(raw)
    matrix = model.matrices[0]
    assert matrix.matrix_type == MatrixKind.HERMITIAN
    assert matrix.role == "sample_sector"
    assert matrix.diagonalize is True

    resolved = {item.name: item for item in model.resolved_diagonalizations()}
    assert resolved["diag__sample_sector"].input == "sector_matrix"
    assert resolved["diag__sample_sector"].method == "hermitian_eigh"

    lowered = GraphLowerer(model).lower()
    matrix_node = next(node for node in lowered.nodes if node["name"] == "sector_matrix")
    diag_node = next(node for node in lowered.nodes if node["name"] == "diag__sample_sector")

    assert matrix_node["metadata"] == {
        "matrix_type": "hermitian",
        "role": "sample_sector",
        "diagonalize": True,
    }
    assert diag_node["diagonalization"] == {
        "input": "sector_matrix",
        "method": "hermitian_eigh",
    }


def test_non_diagonalized_matrices_are_not_auto_processed():
    raw = {
        "metadata": {"name": "no-auto-diag"},
        "constants": [{"name": "x", "value": 1.0}],
        "matrices": [
            {
                "name": "plain_matrix",
                "value_type": "real_matrix",
                "rows": [["1.0", "0.0"], ["0.0", "1.0"]],
            }
        ],
        "observables": [{"name": "obs", "expression": "x"}],
        "outputs": {"save": ["obs"]},
    }

    model = ModelDefinition.from_mapping(raw)
    assert model.resolved_diagonalizations() == []

    lowered = GraphLowerer(model).lower()
    assert not any(node["kind"] == "diagonalization" for node in lowered.nodes)


def test_imported_model_side_likelihood_blocks_work_with_generic_kernels(tmp_path):
    pytest.importorskip("bsm_scanner._core")

    (tmp_path / "constraints").mkdir()
    (tmp_path / "model.yaml").write_text(
        "metadata:\n"
        "  name: imported-likelihoods\n"
        "imports:\n"
        "  - observables.yaml\n"
        "  - constraints/likelihoods.yaml\n"
        "  - outputs.yaml\n"
        "constants:\n"
        "  - name: x\n"
        "    value: 0.5\n",
        encoding="utf-8",
    )
    (tmp_path / "observables.yaml").write_text(
        "observables:\n"
        "  - name: obs\n"
        "    expression: x\n"
        "  - name: pass_cut\n"
        "    value_type: bool\n"
        "    expression: x < 1.0\n",
        encoding="utf-8",
    )
    (tmp_path / "constraints" / "likelihoods.yaml").write_text(
        "likelihoods:\n"
        "  - name: gauss_term\n"
        "    kind: gaussian\n"
        "    observable: obs\n"
        "    mean: 0.0\n"
        "    sigma: 1.0\n"
        "  - name: cut_term\n"
        "    kind: hard_cut\n"
        "    observable: pass_cut\n"
        "  - name: table_term\n"
        "    kind: table_lookup\n"
        "    observable: obs\n"
        "    interpolation: linear\n"
        "    table:\n"
        "      - [0.0, 0.0]\n"
        "      - [1.0, 1.0]\n"
        "      - [2.0, 0.0]\n",
        encoding="utf-8",
    )
    (tmp_path / "outputs.yaml").write_text(
        "outputs:\n"
        "  save:\n"
        "    - obs\n",
        encoding="utf-8",
    )

    model = load_model(tmp_path / "model.yaml")
    compiled = compile_model(model, build_backend=True)
    result = compiled.evaluate({})

    assert result["status"] == "ok"
    assert result["likelihood_terms"]["gauss_term"] == pytest.approx(0.125)
    assert result["likelihood_terms"]["cut_term"] == pytest.approx(0.0)
    assert result["likelihood_terms"]["table_term"] == pytest.approx(0.5)
