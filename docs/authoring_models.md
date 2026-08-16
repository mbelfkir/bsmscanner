# Writing Your Own Model

BSMScanner is installable from PyPI and designed so that **your model lives in
your own directory**, not inside the framework. You write YAML, import the
reusable physics blocks that ship with the package, and run.

```bash
pip install bsm-scanner
```

## Start from a working template

```bash
bsm-scanner new-model mymodel
bsm-scanner run --model mymodel/model.yaml --run-dir mymodel/runs/first
```

That creates a small, complete, runnable model you can edit. It runs
immediately, so you always have a working baseline to modify.

## Using the shipped physics blocks

The framework ships a library of model-independent building blocks. Reference
them with the `core:` prefix, which resolves to wherever the package is
installed — so your model works no matter which directory it lives in:

```yaml
imports:
  - core:constants/physics_constants.yaml
  - core:neutrino/observables_common.yaml
  - core:neutrino/observables_normal.yaml
  - my_parameters.yaml       # your own files stay relative
  - my_matrices.yaml
```

Never write `../../core/...` — that only works inside the source checkout and
will break for anyone who installs your model elsewhere.

### Discovering what is available

```bash
bsm-scanner core list                                    # every shipped block
bsm-scanner core show core:quark/quark_mass_ratios.yaml  # what a block defines
bsm-scanner core path                                    # where they live
```

`core show` prints the constants, functions, observables and theory checks a
block contributes, so you can see what names become available before importing.

### What is currently shipped

| Block | Provides |
|---|---|
| `core:constants/physics_constants.yaml` | shared charged-lepton mass ratios |
| `core:neutrino/observables_common.yaml` | PMNS extraction, mixing angles, `deltaCP`, masses, `mbeta`, `mbetabeta`, `sum_m` |
| `core:neutrino/observables_normal.yaml` / `_inverted.yaml` | ordering-aware mass mapping |
| `core:neutrino/constants_normal.yaml` / `_inverted.yaml` | best-fit splittings used for mass normalization |
| `core:quark/ckm_observables.yaml` | CKM elements, angles, `deltaCKM`, Jarlskog, Wolfenstein parameters |
| `core:quark/quark_mass_ratios.yaml` | `mu_over_mc`, `mc_over_mt`, `md_over_ms`, `ms_over_mb` |
| `core:modular/level4_s4.yaml` | level-4 (Γ₄ / S4) modular forms |
| `core:data/nufit/{Normal,Inverted}/*.csv` | oscillation likelihood tables |

Experimental data tables are referenced the same way:

```yaml
likelihoods:
  - name: theta12_term
    kind: table_lookup
    observable: Theta12
    table_file: core:data/nufit/Normal/Theta12.csv
```

## What your model owns

The division is deliberate. The library owns **mathematics and measurements of
nature**; your model owns **its own physics**:

- `parameters` — what you scan, with ranges and priors
- `matrices` — your mass matrices and their metadata (`type`, `role`,
  `diagonalize`), which drive the automatic diagonalization
- `derived_scalars` / `derived_complex` / `functions` — your model's relations
- `likelihoods` — which constraints you apply and to what
- `scan` — engine and settings

If you declare a matrix with the right metadata, the shipped neutrino and quark
blocks pick it up automatically without knowing your matrix names:

```yaml
matrices:
  - name: neutrino_mass_matrix
    value_type: complex_matrix
    type: majorana_mass       # -> Takagi factorization
    role: neutrino
    diagonalize: true
    rows: [...]
```

## Using the Python API instead

```python
from pathlib import Path
from bsm_scanner import compile_model, load_model, list_core_blocks

print(list_core_blocks())

model = load_model(Path("mymodel/model.yaml"))
compiled = compile_model(model, build_backend=True)

result = compiled.evaluate({"x": 1.0, "y": -1.0})
print(result["status"], result["total_nll"], result["outputs"])
```

## Overriding the library location

For development against a source checkout, or to pin a modified copy of the
blocks, set:

```bash
export BSM_SCANNER_CORE_LIBRARY=/path/to/core
```

`core:` references then resolve against that directory instead of the installed
package data.

## Optional extras

```bash
pip install 'bsm-scanner[de]'         # SciPy differential evolution engine
pip install 'bsm-scanner[posterior]'  # emcee posterior refinement
pip install 'bsm-scanner[analysis]'   # pandas/matplotlib helpers
```

Native Diver and micrOMEGAs backends require building from source with the
corresponding CMake options; see the README.

## Before publishing results

- Record which NuFIT release the bundled tables correspond to, and cite it.
- Check the mass-scale normalization convention in
  `core:neutrino/observables_common.yaml` (`nscale`) matches the one your
  reference uses — normalizing to Δm²₃ₗ alone and to the average of both
  splittings differ at the sub-percent level in every mass output.
