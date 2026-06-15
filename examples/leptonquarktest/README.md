# leptonquarktest Example

This example wraps `models/leptonquarktest`.

Run:

```bash
python examples/leptonquarktest/run_scan.py \
  --model examples/leptonquarktest/model.yaml \
  --run-dir examples/leptonquarktest/runs/smoke
```

Run with the native adaptive DE engine:

```bash
python examples/leptonquarktest/run_scan.py \
  --model examples/leptonquarktest/model_adaptive_diver.yaml \
  --run-dir examples/leptonquarktest/runs/adaptive_diver
```

The model combines lepton and quark sectors while importing physical
observables from reusable core YAML blocks. Its parameters and analytic mass
matrices follow the FlavorPy detailed modular-flavor example. The active scan
parameters are `Retau`, `Imtau`, `alpha`, `beta`, and `gamma`; `n_scale` is
fixed by default.
