# CKM Observables

BSMScanner provides reusable declarative CKM observables in:

```text
core/quark/ckm_observables.yaml
```

The block assumes a CKM matrix node named `V_CKM` already exists. It does not
require access to the original `Mu` or `Md` matrices.

For CKM matrices built directly from SVD rotations whose singular values are
ordered from largest to smallest mass, use:

```text
core/quark/ckm_from_left_rotations_descending_svd.yaml
core/quark/ckm_observables_from_descending_svd.yaml
```

The first block constructs the raw mismatch matrix `V_CKM_descending` from
`U_u_L` and `U_d_L`. The second block reorders `(t,c,u) x (b,s,d)` into
physical `(u,c,t) x (d,s,b)` and then imports the standard
`ckm_observables.yaml` block.

## Construction

For quark-sector models, the recommended construction is:

```yaml
mixing_matrices:
  CKM:
    type: ckm
    up: U_u_L
    down: U_d_L
    output: V_CKM
```

This uses the framework convention:

```text
V_CKM = U_u_L^\dagger U_d_L
```

When `U_u_L` and `U_d_L` come directly from SVD, the generated rows and columns
follow descending singular-value order. In that case write the raw output to
`V_CKM_descending` and import the descending-SVD wrapper:

```yaml
imports:
  - ../../core/quark/ckm_from_left_rotations_descending_svd.yaml
  - ../../core/quark/ckm_observables_from_descending_svd.yaml
```

## Import

```yaml
imports:
  - ../../core/quark/ckm_observables.yaml
```

Adjust the relative path to the model location.

## Matrix Elements

The scalar outputs:

```text
Vud Vus Vub
Vcd Vcs Vcb
Vtd Vts Vtb
```

are absolute values:

```text
Vij = |V_CKM[i,j]|
```

The internal complex matrix-element nodes are named:

```text
Vud_complex, Vus_complex, ...
```

## Angles

The quark mixing angles are:

```text
theta13_q = asin(|Vub|)
theta12_q = atan(|Vus| / |Vud|)
theta23_q = atan(|Vcb| / |Vtb|)
```

Available outputs:

```text
theta12_q theta13_q theta23_q
theta12_q_deg theta13_q_deg theta23_q_deg
t12 t13 t23
s12_q s13_q s23_q
s12_q_sq s13_q_sq s23_q_sq
```

The `asin` input is clipped with `min(max(x, 0), 1)`.
The aliases `t12`, `t13`, and `t23` are degrees, matching the FlavorPy-style
quark-angle output convention.

## CP Phase

The CKM CP phase follows the same invariant structure used by the reference
formula:

```text
deltaCKM in [0, 2*pi)
deltaCKM_deg in [0, 360)
deltaCKM_over_pi = deltaCKM / pi
dq = deltaCKM_deg
```

The phase expression uses epsilon-guarded denominators and a fatal theory check
named `ckm_phase_denominator_valid`. If the phase is undefined, the point is
marked invalid by the evaluator.

## Jarlskog

The direct rephasing-invariant output is:

```text
J_CKM = Im(Vud * Vcs * conj(Vus) * conj(Vcd))
```

Additional outputs:

```text
J_CKM_abs
J_CKM_standard
```

`J_CKM_standard` uses the standard-parameterization expression
`c12*c23*c13^2*s12*s23*s13*sin(deltaCKM)`.

## Wolfenstein Parameters

The outputs are explicitly prefixed to avoid collisions with model parameters:

```text
wolfenstein_lambda
wolfenstein_A
wolfenstein_rhobar
wolfenstein_etabar
```

Definitions:

```text
wolfenstein_lambda = |Vus| / sqrt(|Vud|^2 + |Vus|^2)
wolfenstein_A = (1 / lambda) * |Vcb / Vus|
rhobar + i etabar = -Vud * conj(Vub) / (Vcd * conj(Vcb))
```

A fatal theory check named `ckm_wolfenstein_denominator_valid` marks the point
invalid if the denominator is zero or numerically unsafe.

## Likelihoods

CKM observables are ordinary scalar observables and can be used with generic
likelihood kernels:

```yaml
likelihoods:
  - name: ckm_Vus
    kind: gaussian
    observable: Vus
    mean: 0.22
    sigma: 0.01
```

The repository includes toy CKM likelihoods under:

```text
models/flavor_toy/constraints/ckm_likelihoods_toy.yaml
```

Those numbers are broad placeholders for framework validation only. They are
not production PDG, CKMfitter, or UTfit global-fit inputs.

## Quark Mass Ratios

Quark mass ratios live in a separate reusable block because they require the
ordered SVD mass outputs rather than only `V_CKM`:

```text
core/quark/quark_mass_ratios.yaml
```

Import it after the model has declared diagonalization aliases named
`up_quark_masses` and `down_quark_masses`.

Available outputs:

```text
mu_over_mc
mc_over_mt
md_over_ms
ms_over_mb
```

The current SVD convention returns singular values sorted from largest to
smallest, so the block maps:

```text
up_quark_masses   -> mt, mc, mu
down_quark_masses -> mb, ms, md
```

The slash-style FlavorPy labels map to CSV-safe names:

```text
mu/mc -> mu_over_mc
mc/mt -> mc_over_mt
md/ms -> md_over_ms
ms/mb -> ms_over_mb
```

A fatal theory check named `quark_mass_ratio_denominators_valid` marks the point
invalid if a denominator mass is not positive.
