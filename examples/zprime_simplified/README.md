# Zprime simplified dark-matter benchmark

This example wraps the corrected implementation in `models/zprime_simplified`
(see its `CHANGES.md`).

Reference:

```text
ATLAS/CMS Dark Matter Forum,
Dark Matter Benchmark Models for Early LHC Run-2 Searches,
arXiv:1507.00966.
```

The model is the leptophobic vector-mediator simplified model with Dirac dark
matter, the DM Forum width with quark thresholds, and the spin-independent
DM-nucleon cross section of Boveia et al., arXiv:1603.04156. The LZ limit
(arXiv:2410.17036) needs a table that is not shipped: `model.yaml` runs without
it, and `model_with_direct_detection.yaml` adds it once the table is in
`models/zprime_simplified/data/` (see its `README.md`).

## Running

Quick demonstration of the mechanics (a few seconds; random sampling, **not** a fit):

```bash
python examples/zprime_simplified/run_scan.py --quick --run-dir examples/zprime_simplified/runs/quick
```

Without `--quick` the model's own `scan.yaml` runs, which is the full best-fit search used for the
reference results in `models/zprime_simplified/results/`: reference run: 1 202 evaluations.

```bash
python examples/zprime_simplified/run_scan.py --run-dir examples/zprime_simplified/runs/best_fit
```
