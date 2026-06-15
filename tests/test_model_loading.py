from pathlib import Path

from bsm_scanner.api import load_model


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "oneloop_minimal" / "model.yaml"


def test_example_model_loads():
    model = load_model(EXAMPLE)

    assert model.metadata.name == "oneloop_minimal"
    assert len(model.parameters) >= 10
    assert len(model.matrices) == 1
    assert len(model.diagonalizations) == 1
    assert model.outputs.save[0] == "Mpsi"
    dm21_term = next(item for item in model.likelihoods if item.name == "dm21_term")
    assert dm21_term.kind.value == "table_lookup"
    assert len(dm21_term.table) > 100
