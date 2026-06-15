# Core / Model Split

## Scope

The framework architecture is now explicitly split between reusable core YAML
and model-owned YAML.

This is not a hidden convention. It is the intended pattern for future models.

## What Belongs In The Core

The core may provide declarative, reusable building blocks only when they are
genuinely model-independent.

Current examples:

- shared physics constants
- automatic diagonalization infrastructure
- generic flavor mixing-matrix construction from declared rotations
- ordering-aware neutrino observable logic
- reusable neutrino observable blocks under
  `/Users/mbelfkir/HEP/BSMScanner/core/neutrino`
- generic likelihood kernels implemented in the evaluator:
  - `gaussian`
  - `asymmetric_gaussian`
  - `upper_limit`
  - `lower_limit`
  - `interval`
  - `hard_cut`
  - `table_lookup`
  - `multivariate_gaussian`

The core does not own model datasets, scan composition, or model-specific
backend semantics.

## What Belongs In A Model

Each model remains responsible for:

- parameters
- analytic matrix definitions
- matrix metadata
- mixing-matrix declarations
- ordering selection
- outputs
- scan settings
- imported likelihood blocks
- model-specific datasets and numerical choices
- plugin-backed observables or custom likelihoods when they are not generic

This keeps the core reusable and keeps model intent visible in YAML.

## Matrix Metadata

Matrices can now declare:

- `type`
  - `complex_general`
  - `complex_symmetric`
  - `dirac_mass`
  - `majorana_mass`
  - `hermitian`
  - `real_symmetric`
- `role`
  - a model-defined sector label such as `neutrino` or `charged_lepton`
- `diagonalize`
  - whether the framework should create a diagonalization node automatically

Optional overrides:

- `diagonalization_name`
- `diagonalization_method`

## Automatic Diagonalization

Automatic diagonalization is opt-in.

The framework does not diagonalize every matrix blindly. A matrix is only
auto-processed when `diagonalize: true` is declared.

Default dispatch is inferred from matrix type:

- `complex_general` -> `svd`
- `complex_symmetric` -> `takagi`
- `hermitian` -> `hermitian_eigh`
- `dirac_mass` -> `svd_complex`
- complex `majorana_mass` -> `takagi`
- `real_symmetric` -> `self_adjoint_eigen`

Generated node naming is deterministic:

- `diag__<role>` when `role` is present
- otherwise `diag__<matrix_name>`

Explicit `diagonalizations:` blocks remain supported for models that still need
manual naming or older layouts.

## Flavor Mixing

The core can construct generic mismatch matrices from named rotations. The
default convention is:

```text
U_left_dagger_U_right: output = dagger(left) @ right
```

This covers the standard flavor matrices:

```text
U_PMNS = U_l_L^\dagger U_nu
V_CKM  = U_u_L^\dagger U_d_L
```

Models choose active sectors by declaring the relevant matrices and requested
mixing matrices. Neutrino-only, lepton-sector, quark-only, full flavor-sector,
and custom partial-sector models are all valid. CKM requests require both up-
and down-sector rotations. PMNS requests require a neutrino rotation and may use
the documented identity charged-lepton fallback for old neutrino-only models.

## Neutrino Ordering

Ordering is selected at the model level through:

- `metadata.ordering: normal`
- or `metadata.ordering: inverted`

The current reusable neutrino blocks are:

- `/Users/mbelfkir/HEP/BSMScanner/core/neutrino/normal.yaml`
- `/Users/mbelfkir/HEP/BSMScanner/core/neutrino/inverted.yaml`

These blocks centralize the standard ordering-aware neutrino observable mapping
without moving model-specific likelihood composition into the core.

## CKM Observables

The reusable CKM observable block is:

- `/Users/mbelfkir/HEP/BSMScanner/core/quark/ckm_observables.yaml`

CKM construction from standard SVD left rotations is provided by:

- `/Users/mbelfkir/HEP/BSMScanner/core/quark/ckm_from_left_rotations_descending_svd.yaml`

That construction uses:

```text
V_CKM = U_u_L^\dagger U_d_L
```

with the raw descending-SVD matrix named `V_CKM_descending`. The companion
`ckm_observables_from_descending_svd.yaml` block reorders it into physical CKM
order and then provides scalar absolute CKM elements, quark mixing angles,
`deltaCKM`, `J_CKM`, and Wolfenstein parameters. These core blocks do not own
production experimental likelihood numbers. Model-side YAML remains responsible
for choosing and documenting CKM likelihood inputs.

## Likelihood Blocks Stay Model-Side

Likelihood definitions remain under the model because users must be able to:

- choose which terms are active
- swap datasets
- replace a Gaussian term with a table term
- remove or modify a constraint without editing framework code

The framework provides kernels; the model composes them.

Typical pattern:

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

## Why `leptontest` Is The Reference Example

`/Users/mbelfkir/HEP/BSMScanner/models/leptontest` is now the clean reference
example because it shows the intended split without one-loop-specific baggage:

- model-owned parameters and analytic matrices
- matrix metadata with automatic diagonalization
- imported core neutrino logic
- imported model-side likelihood blocks
- normal and inverted manifests with minimal duplication

It is the preferred example to follow when adding a new model.

## Migration Direction

`oneloop_master` remains the canonical physics model and must preserve its
current behavior. Its migration to this split should therefore be incremental:

- align constants and matrix metadata where safe
- keep model-side likelihood blocks model-side
- keep one-loop-specific plugins and grouped likelihood behavior out of the core
- only replace duplicated generic neutrino pieces when parity risk is low
