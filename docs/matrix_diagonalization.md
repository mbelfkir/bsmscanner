# Matrix Diagonalization And Flavor Mixing

BSMScanner supports generic flavor-sector diagonalization through matrix
metadata. The framework does not require every model to define every flavor
matrix. A model activates only the sectors it declares and the mixing matrices
it requests.

## Supported Sectors

Standard flavor matrices can be declared with roles such as:

- `neutrino_mass`
- `charged_lepton_mass`
- `up_quark_mass`
- `down_quark_mass`

The role is metadata for model organization. The numerical routine is selected
from the declared `type` and `diagonalize.method`.

## Majorana Neutrinos

For a complex symmetric Majorana matrix, use:

```yaml
type: complex_symmetric
diagonalize:
  method: takagi
```

The convention is:

```text
U_nu^T Mnu U_nu = diag(m1, m2, m3)
```

The masses are non-negative. The generated unitary is the Takagi unitary
`U_nu`.

Complex matrices declared with the semantic type `majorana_mass` also default
to `takagi`. In the evaluator, `u_complex[row, column]` is the flavor-row,
mass-column unitary satisfying:

```text
U_nu^T Mnu U_nu = D_nu
```

## Dirac Fermions

For charged leptons and quarks, use:

```yaml
type: complex_general
diagonalize:
  method: svd
```

The framework convention is:

```text
U_L^\dagger M U_R = diag(m1, m2, m3)
```

The generated outputs are:

- `masses`
- `left_unitary`
- `right_unitary`

## Hermitian Matrices

For explicit Hermitian matrices, use:

```yaml
type: hermitian
diagonalize:
  method: hermitian_eigh
```

The convention is:

```text
U^\dagger H U = diag(eigenvalues)
```

## Output Aliases

Diagonalization outputs can be named directly in YAML:

```yaml
matrices:
  Ml:
    value_type: complex_matrix
    type: complex_general
    role: charged_lepton_mass
    diagonalize:
      method: svd
      output:
        masses: charged_lepton_masses
        left_unitary: U_l_L
        right_unitary: U_l_R
    rows: ...
```

The aliases are ordinary graph nodes and can be used by observables, theory
checks, likelihoods, outputs, and mixing matrices.

## Mixing Matrices

Mixing matrices are constructed from already-declared rotation matrices.

```yaml
mixing_matrices:
  PMNS:
    type: left_mismatch
    convention: U_left_dagger_U_right
    left: U_l_L
    right: U_nu
    output: U_PMNS

  CKM:
    type: left_mismatch
    convention: U_left_dagger_U_right
    left: U_u_L
    right: U_d_L
    output: V_CKM
```

The default convention is:

```text
output = dagger(left) @ right
```

Thus:

```text
U_PMNS = U_l_L^\dagger U_nu
V_CKM  = U_u_L^\dagger U_d_L
```

The reusable neutrino core applies this same convention when it extracts
ordering-aware scalar PMNS entries:

```text
U_PMNS[alpha, i] = sum_k conj(U_l_L[k, alpha]) * U_nu[k, i]
```

The alternate convention is:

```text
U_left_U_right_dagger
```

which computes:

```text
output = left @ dagger(right)
```

## Optional Sectors

The framework does not require all four standard matrices.

- Neutrino-only models may define only `Mnu`.
- Lepton-sector models may define `Mnu` and `Ml`.
- Quark-only models may define `Mu` and `Md`.
- Full flavor models may define all four.
- Custom BSM matrices may be diagonalized without requesting PMNS or CKM.

If `type: pmns` is requested with no charged-lepton rotation, the default
compatibility behavior is to use an identity charged-lepton rotation:

```text
U_PMNS = U_nu
```

Disable this fallback with:

```yaml
charged_lepton_identity_fallback: false
```

CKM has no identity fallback. A CKM request requires both up- and down-sector
left-handed rotations.

## CKM Observables

After `V_CKM` is constructed, models can import reusable CKM scalar
observables:

```yaml
imports:
  - ../../core/quark/ckm_observables.yaml
```

The block exposes absolute CKM elements (`Vud` through `Vtb`), quark mixing
angles (`theta12_q`, `theta13_q`, `theta23_q` and degree variants),
`deltaCKM`, `deltaCKM_deg`, `J_CKM`, and prefixed Wolfenstein parameters:

```text
wolfenstein_lambda
wolfenstein_A
wolfenstein_rhobar
wolfenstein_etabar
```

See `docs/ckm_observables.md` for formulas and likelihood usage.

## Neutrino Observable Convention

The reusable core follows the PDG matrix-element extraction:

```text
s13 = |Ue3|^2
s12 = |Ue2|^2 / (1 - |Ue3|^2)
s23 = |Umu3|^2 / (1 - |Ue3|^2)
```

The Dirac phase is reconstructed from the rephasing-invariant Jarlskog
combination and an `atan2(sin_delta, cos_delta)` quadrant choice. `deltaCP` is
wrapped to `[0, 2*pi)` and `deltaCP_deg` to `[0, 360)`.

If the mixing-angle denominator needed to define the phase vanishes, the core
returns a non-finite phase. Standard evaluator validity handling then marks the
point invalid instead of assigning an arbitrary phase.
