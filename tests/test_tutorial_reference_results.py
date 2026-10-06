"""The reference best-fit runs stored under models/<name>/results/ must reproduce.

Each `best_fit.json` records the parameters and objective of a finished scan.
Re-evaluating that point through the shipped model must return the same
objective, so the notebooks' reference results and the models cannot drift apart.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from bsm_scanner import compile_model, load_model

pytest.importorskip("bsm_scanner._core")

ROOT = Path(__file__).resolve().parents[1]
ENTRY = {"scotogenic_ma": "model_no.yaml"}
RUNS = sorted((ROOT / "models").glob("*/results/*/best_fit.json"))


def test_reference_results_are_present():
    models = {path.parts[-4] for path in RUNS}
    assert models == {
        "scotogenic_ma",
        "minimal_bl",
        "two_higgs_doublet",
        "smeft_wilson",
        "zprime_simplified",
        "leptoquark_brw",
    }


@pytest.mark.parametrize("best_fit_path", RUNS, ids=lambda p: f"{p.parts[-4]}/{p.parts[-2]}")
def test_reference_best_fit_reproduces(best_fit_path: Path):
    name = best_fit_path.parts[-4]
    model = load_model(ROOT / "models" / name / ENTRY.get(name, "model.yaml"))
    compiled = compile_model(model, build_backend=True)

    best = json.loads(best_fit_path.read_text())
    point = {parameter.name: parameter.default for parameter in model.parameters}
    point.update(best["parameters"])
    result = compiled.evaluate(point)

    assert result["valid"], result.get("failure_reason")
    assert result["total_nll"] == pytest.approx(best["best_metric_value"], rel=1.0e-6, abs=1.0e-9)
