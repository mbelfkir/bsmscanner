# Oneloop Migration Status

The original reference code lives at `oneloop-master2`.

The migrated normal-ordering example now lives at:

- `models/oneloop/model.yaml`

The example wrapper remains available at:

- `examples/oneloop_full/model.yaml`

It is a real compiled model in the framework, not a design stub.

## Migration Checklist

### Completed

- Full `config_nr.yaml` parameter set is ported:
  - masses: `Mpsi`, `MN`, `Mphi`, `MA1`, `MH1`, `MH2`
  - scalar-sector inputs: `sh`, `k1`, `k4`, `k5`, `lambda1`, `lambda2`, `lambda3`
  - Yukawa inputs:
    - `Reye`, `Imgye`, `Reymu`, `Imgymu`, `Reytau`, `Imgytau`
    - `ReYe`, `ImgYe`, `ReYmu`, `ImgYmu`, `ReYtau`, `ImgYtau`
    - `Reyp`, `Imgyp`
- Core scalar relations are ported:
  - `mphi`, `mphip`, `mu_phi`, `MA2`, `sa`, `k2`, `k3`
- Reusable loop/special functions are ported:
  - `I3`, `F`, `F2`, `ft`, `G`, `G2`, `D1`, `D2`, `f`
- Full 3x3 complex neutrino mass matrix is ported.
- Neutrino SVD content is ported:
  - ordered masses
  - PMNS-like matrix elements
  - `Theta12`, `Theta13`, `Theta23`
  - `deltaCP`, `eta1`, `eta2`
  - `dm21`, `dm3l`, `scale`
  - `m1`, `m2`, `m3`, `sum_m`, `mbeta`, `mbetabeta`
- Oscillation likelihood tables are ported for normal ordering:
  - `Theta12`, `Theta13`, `Theta23`, `deltaCP`, `dm21`, `dm3l`
- Full LFV sector is ported:
  - `mu_to_e_gamma`, `tau_to_e_gamma`, `tau_to_mu_gamma`
  - `mu_to_eee`, `tau_to_eee`, `tau_to_mumumu`
- Higgs and electroweak precision sectors are ported:
  - `HiggsMass`
  - `HiggsRgg`
  - `ObliqueS`
  - `ObliqueT`
- Scattering matrices and perturbative unitarity checks are ported:
  - `S_matrix_1` through `S_matrix_6`
  - self-adjoint eigenvalue checks against `8*pi`
- Quartic/vacuum-style theory checks are ported.
- Loop-denominator and mass-ordering theory checks are ported.
- Full machine-readable scan/evaluation output support works for the migrated example.

### Approximated But Explicit

- The fermion dark-matter identity check is implemented analytically as a lightest-odd-state mass ordering condition over the states represented in the graph:
  - `Mpsi < MN, Mphi, MA1, MA2, MH1, MH2`
  - This replaces the original micrOMEGAs particle-name lookup when that backend is not active.
- The Majorana-phase and `mbetabeta` conventions follow the original `nLLConstructor.cxx` algebra literally, including its mixed `pi` and radian conventions.
  - This is the most faithful port of the current source, even though the original formulas are not especially clean dimensionally.
- The example defaults are set to a valid seed point instead of the raw placeholder defaults from `config_nr.yaml`.
  - The original defaults sit on singular LFV loop surfaces such as `Mpsi = Mphi`.

### Intentionally Deferred

- Exact micrOMEGAs-backed dark-matter observables are not yet integrated into the framework hot loop:
  - relic density `Omega`
  - direct-detection cross section / p-value logic
  - exact particle-identity selection through the generated micrOMEGAs model
- Inverted-ordering data tables are copied into the repository, but there is not yet a dedicated inverted-ordering example YAML wired with the original table-normalization offset convention.

## Implemented Mapping

### External Parameters

Directly mapped from the current `config_nr.yaml` parameterization:

- `Mpsi`, `MN`, `Mphi`, `MA1`, `MH1`, `MH2`
- `sh`, `k1`, `k4`, `k5`, `lambda1`, `lambda2`, `lambda3`
- `Reye`, `Imgye`, `Reymu`, `Imgymu`, `Reytau`, `Imgytau`
- `ReYe`, `ImgYe`, `ReYmu`, `ImgYmu`, `ReYtau`, `ImgYtau`
- `Reyp`, `Imgyp`

### Derived Definitions

- `ch`, `sH`, `cH`
- `mphi_sq`, `mphip_sq`
- `MHA22`, `MHA12`, `MA02sq`, `MA2`
- `sa`, `ca`
- `mu_phi`
- `k2`, `k3`
- loop-normalization factor for the neutrino mass matrix

### Matrix Nodes

- `neutrino_mass_matrix`
- `S_matrix_1` through `S_matrix_6`

### Diagonalization Nodes

- `neutrino_svd`
- `S1_eigen` through `S6_eigen`

### Observable Set

- Neutrino sector:
  - `Theta12`, `Theta13`, `Theta23`, `deltaCP`, `eta1`, `eta2`
  - `dm21`, `dm3l`, `m1`, `m2`, `m3`
  - `sum_m`, `scale`, `mbeta`, `mbetabeta`
- LFV:
  - `mu_to_e_gamma`, `tau_to_e_gamma`, `tau_to_mu_gamma`
  - `mu_to_eee`, `tau_to_eee`, `tau_to_mumumu`
- Higgs:
  - `HiggsMass`, `HiggsRgg`
- Electroweak precision:
  - `ObliqueS`, `ObliqueT`

### Theory Checks

- positivity of `mphi_sq`, `mphip_sq`
- validity of `MA02sq`
- dark-matter identity mass-order check
- loop-denominator non-singularity
- I3 mass-order requirement
- quartic stability bounds
- perturbative unitarity bounds from the six scattering matrices
- finite-value checks for neutrino, LFV, and EW/Higgs sectors

### Likelihood Terms

- table-based oscillation likelihoods:
  - `theta12_term`, `theta13_term`, `theta23_term`, `deltaCP_term`
  - `dm21_term`, `dm3l_term`
- cosmological sum-of-masses hard cut:
  - `sum_m_limit`
- Higgs Gaussian terms:
  - `higgs_mass_term`, `higgs_rgg_term`
- LFV hard upper limits:
  - `mu_to_e_gamma_limit`, `tau_to_e_gamma_limit`, `tau_to_mu_gamma_limit`
  - `mu_to_eee_limit`, `tau_to_eee_limit`, `tau_to_mumumu_limit`
- correlated electroweak precision term:
  - `oblique_ST_term`

## External Data

The repository now carries the original oscillation tables under:

- `examples/oneloop_full/data/Normal`
- `examples/oneloop_full/data/Inverted`

## How To Run

Compile and evaluate the default seed point:

```bash
python examples/oneloop_full/run_example.py
```

Launch a scan:

```bash
python examples/oneloop_full/run_scan.py \
  --run-dir examples/oneloop_full/runs/example_scan
```
