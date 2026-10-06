# Minimal B-L gauge benchmark

This example wraps the corrected implementation in `models/minimal_bl`
(see its `CHANGES.md`).

Reference:

```text
L. Basso, S. Moretti, G. M. Pruna,
Phenomenology of the minimal B-L extension of the Standard Model,
arXiv:1106.4462.
```

The model has the Z' of gauged B-L, a complex singlet with h-h' mixing and
three Majorana right-handed neutrinos, with the full Z' width, the Higgs signal
strength including h -> N N and h -> Z'Z', and the LEP contact bound. The ATLAS
dilepton Z' limit needs HEPData tables that are not shipped: `model.yaml` runs
without it, and `model_with_lhc_dilepton.yaml` adds it once the tables are in
`models/minimal_bl/data/` (see its `README.md`).

## Running

Quick demonstration of the mechanics (a few seconds; random sampling, **not** a fit):

```bash
python examples/minimal_bl/run_scan.py --quick --run-dir examples/minimal_bl/runs/quick
```

Without `--quick` the model's own `scan.yaml` runs, which is the full best-fit search used for the
reference results in `models/minimal_bl/results/`: reference run: 6 136 evaluations, about 5 seconds.

```bash
python examples/minimal_bl/run_scan.py --run-dir examples/minimal_bl/runs/best_fit
```
