# S1 leptoquark benchmark

This example wraps `models/leptoquark_brw`, which replaces the original BRW proxy
benchmark with an explicit S1 leptoquark (see its `CHANGES.md`).

Reference:

```text
I. Dorsner et al., Physics of leptoquarks in precision experiments and at
particle colliders, Phys. Rept. 641, 1 (2016), arXiv:1603.04993;
A. Angelescu et al., arXiv:1808.08179.
```

The model has real couplings to the third lepton generation and the mass
M_S1, and computes R(D), R(D*), B -> K nu nu, the B_c lifetime bound and the
S1 widths. The LHC pair-production limits need HEPData tables that are not
shipped: `model.yaml` runs without them, and `model_with_lhc_pair.yaml` adds
them once the tables are in `models/leptoquark_brw/data/` (see its `README.md`).

## Running

Quick demonstration of the mechanics (a few seconds; random sampling, **not** a fit):

```bash
python examples/leptoquark_brw/run_scan.py --quick --run-dir examples/leptoquark_brw/runs/quick
```

Without `--quick` the model's own `scan.yaml` runs, which is the full best-fit search used for the
reference results in `models/leptoquark_brw/results/`: reference run: 51 698 evaluations.

```bash
python examples/leptoquark_brw/run_scan.py --run-dir examples/leptoquark_brw/runs/best_fit
```
