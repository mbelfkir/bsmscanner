# Core Neutrino Blocks

## Purpose

`/Users/mbelfkir/HEP/BSMScanner/core` contains declarative YAML that is owned by
the framework rather than by a specific model. These blocks are still loaded
through the normal model import mechanism, so they remain inspectable and
editable instead of being hidden inside evaluator code.

The current prototype centralizes:

- shared physics constants
- automatic-diagonalization-friendly neutrino observable wiring
- ordering-aware normal and inverted neutrino observable mappings

Likelihood composition stays model-side on purpose.

## Current Layout

```text
core/
  constants/
    physics_constants.yaml
  neutrino/
    normal.yaml
    inverted.yaml
    constants_normal.yaml
    constants_inverted.yaml
    observables_common.yaml
    observables_normal.yaml
    observables_inverted.yaml
  quark/
    ckm_from_left_rotations_descending_svd.yaml
    ckm_observables.yaml
    ckm_observables_from_descending_svd.yaml
    quark_mass_ratios.yaml
```

## Intended Split

Framework-owned blocks should contain only calculations that are genuinely
model-independent. For the current neutrino prototype this means:

- charged-lepton and neutrino rotation bookkeeping
- PMNS construction
- ordering-aware mass mapping
- `s12`, `s13`, `s23`
- `deltaCP`, `eta1`, `eta2`, `alpha21`, `alpha31`
- `mbeta`, `mbetabeta`
- `sum_mnu`, `dm21`, `dm3l`, and related aliases

The same boundary applies to the quark sector: CKM construction from generic
left-handed rotations belongs in reusable core flavor blocks, while model YAML
declares only `Mu` and `Md` plus their metadata.

Model-owned YAML should still contain:

- parameters
- analytic matrix definitions
- scan settings
- likelihood blocks
- model-specific datasets and numerical targets
- plugin-backed or custom terms that are not generic

## Automatic Diagonalization Contract

The reusable neutrino blocks assume that the model declares matrices with
metadata instead of hardcoded names in the core:

```yaml
matrices:
  - name: lepton_mass_matrix
    value_type: complex_matrix
    type: dirac_mass
    role: charged_lepton
    diagonalize: true
    rows:
      - ["me_over_mtau", "0.0", "0.0"]
      - ["0.0", "mmu_over_mtau", "0.0"]
      - ["0.0", "0.0", "1.0"]

  - name: neutrino_mass_matrix
    value_type: complex_matrix
    type: majorana_mass
    role: neutrino
    diagonalize: true
    rows:
      ...
```

From that metadata the loader creates role-based diagonalization nodes such as:

- `diag__charged_lepton`
- `diag__neutrino`

The core neutrino blocks then project from those generated nodes without knowing
the model’s original matrix names.

For complex `majorana_mass` matrices the automatic method is Takagi
factorization. The conventions are:

```text
U_l_L^\dagger M_l U_l_R = D_l
U_nu^T M_nu U_nu = D_nu
U_PMNS = U_l_L^\dagger U_nu
```

Normal and inverted ordering blocks only permute the neutrino mass columns.
They do not change the PMNS multiplication convention.

The official oscillation observables use:

```text
s13 = |Ue3|^2
s12 = |Ue2|^2 / (1 - |Ue3|^2)
s23 = |Umu3|^2 / (1 - |Ue3|^2)
deltaCP = wrap_0_2pi(atan2(sin_delta, cos_delta))
```

Here `sin_delta` is obtained from the Jarlskog invariant and `cos_delta` from
the standard PDG parameterization. `mbeta` and `mbetabeta` are evaluated
directly as:

```text
mbeta     = sqrt(sum_i |Uei|^2 mi^2)
mbetabeta = |sum_i Uei^2 mi|
```

Python callers with an already constructed PMNS matrix can use the same
convention directly:

```python
from bsm_scanner import pmns_observables_from_matrix

pmns = U_charged_lepton_left.conj().T @ U_neutrino
observables = pmns_observables_from_matrix(pmns)

print(observables["s12"])
print(observables["delta_cp_deg"])
```

The utility returns squared mixing sines, angles in radians and degrees, the
wrapped Dirac phase, its sine and cosine, and the Jarlskog invariant. Use
`delta_deg_signed` when a likelihood table expects `[-180, 180)` instead of
the core `[0, 360)` phase convention.

## Leptontest Prototype

`/Users/mbelfkir/HEP/BSMScanner/models/leptontest` is the first model using this
layout.

Normal ordering:

```yaml
imports:
  - parameters.yaml
  - functions.yaml
  - derived.yaml
  - matrices.yaml
  - ../../core/neutrino/normal.yaml
  - constraints/likelihood.yaml
  - outputs.yaml
  - scan.yaml
```

Inverted ordering swaps only the imported core neutrino block and the local
likelihood file.

## Why Likelihoods Stay Out Of Core

The framework core provides kernels such as:

- `gaussian`
- `hard_cut`
- `table_lookup`
- `multivariate_gaussian`

but it does not choose datasets or decide which terms are active. That remains
the model’s job so users can:

- swap a Gaussian term for a table term
- disable a block for a scan variant
- change numerical targets without touching framework code

## Ready For Later Migration

This split is intentionally generic enough for later migration of
`oneloop_master`, but this refactor does not force that model onto the new
layout yet. The prototype goal is:

- reusable core neutrino infrastructure
- model-side likelihood ownership
- no hardcoded matrix names in the framework core
