# Two-Higgs-doublet benchmark

This example wraps the corrected implementation in `models/two_higgs_doublet`
(see its `CHANGES.md`).

Reference:

```text
G. C. Branco et al.,
Theory and phenomenology of two-Higgs-doublet models,
Phys. Rept. 516, 1-102 (2012), arXiv:1106.0034.
```

The model is the CP-conserving Type II 2HDM with the full quartic inversion from
physical masses, tan beta and the alignment angle; boundedness from below and
tree-level perturbative unitarity; the oblique T parameter; B -> X_s gamma;
and Type II Higgs couplings. The Higgs-coupling constraint is INTERIM (kappa_V
only) pending the resolved HEPData fit. Its small valid fraction is handled by
the `delta_soft` parametrization and the `basin_scan` engine, so a full scan
takes longer than the other examples.

## Running

Quick demonstration of the mechanics (a few seconds; random sampling, **not** a fit):

```bash
python examples/two_higgs_doublet/run_scan.py --quick --run-dir examples/two_higgs_doublet/runs/quick
```

Without `--quick` the model's own `scan.yaml` runs, which is the full best-fit search used for the
reference results in `models/two_higgs_doublet/results/`: a `basin_scan` (4x10^5-point exploration, then focused searches); the reference run used 0.4 million evaluations.

```bash
python examples/two_higgs_doublet/run_scan.py --run-dir examples/two_higgs_doublet/runs/best_fit
```
