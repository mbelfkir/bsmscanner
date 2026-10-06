# SMEFT Wilson-coefficient benchmark

This example wraps the corrected implementation in `models/smeft_wilson`
(see its `CHANGES.md`).

Reference:

```text
B. Grzadkowski, M. Iskrzynski, M. Misiak, J. Rosiek,
Dimension-Six Terms in the Standard Model Lagrangian,
JHEP 10, 085 (2010), arXiv:1008.4884.
```

The model is a tree-level, linear Warsaw-basis scan over nine Wilson
coefficients at fixed Lambda = 1 TeV, with S and T from the PDG STU fit and the
Higgs data entering as kappa factors. The Higgs-coupling constraint is INTERIM
(kappa_V only) pending the resolved HEPData fit, so several coefficients are
bounded only by the linear-EFT guard.

## Running

Quick demonstration of the mechanics (a few seconds; random sampling, **not** a fit):

```bash
python examples/smeft_wilson/run_scan.py --quick --run-dir examples/smeft_wilson/runs/quick
```

Without `--quick` the model's own `scan.yaml` runs, which is the full best-fit search used for the
reference results in `models/smeft_wilson/results/`: reference run: 15 051 evaluations.

```bash
python examples/smeft_wilson/run_scan.py --run-dir examples/smeft_wilson/runs/best_fit
```
