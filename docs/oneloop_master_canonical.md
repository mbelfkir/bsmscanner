# Canonical Oneloop Master Layout

This note is the compact developer-facing reference for the canonical
production one-loop model under:

- [model_normal_reduced.yaml](../models/oneloop_master/model_normal_reduced.yaml)
- [model_normal_full.yaml](../models/oneloop_master/model_normal_full.yaml)
- [model_inverted_full.yaml](../models/oneloop_master/model_inverted_full.yaml)

The compatibility manifest [model.yaml](../models/oneloop_master/model.yaml)
points to the reduced normal-ordering variant.

## YAML Variants

- `model_normal_reduced.yaml`: reduced normal-ordering production scan layout
- `model_normal_full.yaml`: full normal-ordering range variant
- `model_inverted_full.yaml`: full inverted-ordering range variant

The three variants share the same live physics structure and the same 26 free
parameters. They differ only in ranges, ordering-specific observables, and
ordering-specific likelihood assets.

## Canonical 26 Free Parameters

```text
Mpsi MN Mphi MA1 MH1 MH2 sh k1 k4
Reye Imgye Reymu Imgymu Reytau Imgytau
ReYe ImgYe ReYmu ImgYmu ReYtau ImgYtau
Reyp Imgyp lambda2 lambda3 k5
```

These are the only scanned parameters in the canonical latest-source path.

## Derived Quantities

The following are derived or fixed and must not reappear as free scan
parameters:

- `MA2`
- `sa`
- `lambda1`
- `k2`
- `k3`
- `mphi`
- `mphip`
- `Lambda`
- `mbeta`
- `mbetabeta`

The latest-source path also excludes `Rep` and `Imgp`.

## Declarative YAML Likelihood Terms

The canonical likelihood decomposition is visible directly in YAML:

- `theta12_term`
- `theta13_term`
- `theta23_term`
- `deltaCP_term`
- `m12+m3l`
- `sumOfMass`
- `massPinalety`
- `HiggsRgg_term`
- `KPinaleties`
- `EVPinaleties`
- `BRPinaleties`
- `Oblique_term`
- `Omega_term`
- `DDexp_term`

The following are declarative and stay entirely in YAML:

- free-parameter ranges and priors
- derived analytic relations
- matrix and diagonalization structure
- theory checks
- most likelihood kernels and table assets

## Intentional Plugin Code

Two pieces remain outside pure YAML on purpose:

1. [oneloop_micromegas.cpp](../src/plugins/oneloop_micromegas.cpp)

- genuinely backend-specific
- handles micrOMEGAs assignment, candidate selection, relic density, SI cross
  section, and direct-detection p-value

2. [oneloop_likelihoods.cpp](../src/plugins/oneloop_likelihoods.cpp)

- not a generic framework concern
- preserves the latest source’s grouped `m12+m3l` behavior exactly, including
  the source-style early return when `dm21` is already out of range

Everything else in the canonical one-loop model should be editable through YAML
without changing the generic framework core.

## Recommended Workflow For Future Models

- put physics structure in YAML first
- use derived quantities instead of stale free parameters
- keep plugin code only for true backend calls or source-specific behavior that
  the generic kernels cannot yet represent declaratively
- use the invariant helpers in
  [validation.py](../python/bsm_scanner/model/validation.py)
  to guard free/derived separation, likelihood coverage, dead scan parameters,
  and parity reporting
