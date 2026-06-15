# Weinberg Multi-Island Scan

This directory is a fresh scan-strategy validation wrapper for the Weinberg-operator modular S4 model of arXiv:2006.03058.

The physics implementation is imported from the canonical BSMScanner Weinberg fragments in `models/arxiv2006_03058_weinberg`, while this directory adds a new multi-island scan strategy:

- progressive exploration
- balanced likelihood-term selection
- near-miss preservation
- guided prior-profile sampling
- seed refinement
- manifold refocus
- ML focus
- adaptive-diver focused optimization with local refinement

The scanner remains model-agnostic: the strategy uses parameter coordinates, objective values, validity, and generic likelihood-term columns.

## Files

- `model_no.yaml`: normal-ordering scan manifest.
- `model_io.yaml`: inverted-ordering scan manifest.
- `guided_sampling.yaml`: generic prior-profile proposal stages for Weinberg parameters.
- `scan_strategy_smoke.yaml`: smoke-sized full strategy config.
- `run_scan.py`: model-local scan runner.

## Smoke Run

```bash
.venv/bin/python models/weinberg_multi_island/run_scan.py --model models/weinberg_multi_island/model_no.yaml --run-dir models/weinberg_multi_island/runs/no_multi_island_smoke
```

The smoke config is intended to validate that all strategy stages run and write artifacts. It is not a production minimization budget.
