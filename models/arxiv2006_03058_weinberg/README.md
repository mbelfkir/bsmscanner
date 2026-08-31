# arxiv2006_03058_weinberg

This model implements the Weinberg-operator example from FlavorPy's
`arxiv2006.03058` documentation:

```text
https://flavorpy.github.io/FlavorPy/examples/arxiv2006dot03058.html
```

It is based on section 6.1 of "Double Cover of Modular S4 for Flavour Model
Building" and defines the charged-lepton matrix `Me` and neutrino Weinberg
operator matrix `Mn`.

The scanned parameters are:

```text
Retau, Imtau, a2t, a3t, g2t, g3t
```

`n_scale` is fixed to `1.0` as a constant for formula compatibility and is not
a scanned parameter. The reusable core neutrino block computes the physical
mass scale through `scale`.

Available manifests:

```text
model_no.yaml  normal ordering
model_io.yaml  inverted ordering
```

Both manifests import reusable core neutrino observables. PMNS-related
observables are therefore computed from the model-declared charged-lepton and
neutrino diagonalizations, not hard-coded in this model.

The default likelihood follows the FlavorPy example's fitted observable list:

```text
me_over_mu
mu_over_tau
s12_sq
s13_sq
s23_sq
dm21
dm3l
```

The CP phase `deltaCP_over_pi` is saved as an output but intentionally excluded
from the default likelihood.

Run a small reference scan from the repository root:

```bash
python examples/arxiv2006_03058_weinberg/run_scan.py \
  --model examples/arxiv2006_03058_weinberg/model_no.yaml \
  --run-dir examples/arxiv2006_03058_weinberg/runs/no_smoke
```
