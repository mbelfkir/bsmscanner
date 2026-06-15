# One-loop radiative neutrino and dark-matter model

This directory contains two generations of the one-loop model:

- `model.yaml` is the preserved legacy BSMScanner migration.
- `model_chi_*.yaml` and `model_h01_*.yaml` reproduce the parameterization and
  analytic formulas of the supplied `Model_Onelopp/scanner_common` scanner.

No framework code is required by the reference manifests.

## Variants

| Manifest | Dark-matter branch | Neutrino ordering | Backend |
| --- | --- | --- | --- |
| `model_chi_no.yaml` | fermion `chi` | normal | analytic |
| `model_chi_io.yaml` | fermion `chi` | inverted | analytic |
| `model_h01_no.yaml` | scalar `H01` | normal | analytic |
| `model_h01_io.yaml` | scalar `H01` | inverted | analytic |
| `model_*_micromegas.yaml` | corresponding branch | corresponding ordering | optional `oneloop_micromegas` plugin |
| `model_*_mcmc.yaml` | corresponding branch | corresponding ordering | analytic scan plus posterior MCMC |
| `model_*_micromegas_mcmc.yaml` | corresponding branch | corresponding ordering | micrOMEGAs scan plus posterior MCMC |

The analytic manifests include the scalar reconstruction, one-loop Majorana
neutrino mass matrix, oscillation observables, LFV decays, oblique parameters,
Higgs diphoton rate, bounded-from-below constraints, perturbativity, and scalar
unitarity.

## Parameter basis

The scanner uses the same mass-gap basis as the standalone implementation.
For the `chi` branch:

```text
Mchi   = Mdm
mphich = Mdm + gap_charged
MH01   = Mdm + gap_H01
MH02   = MH01 + gap_H02
MA01   = Mdm + gap_A01
```

For the `H01` branch:

```text
MH01   = Mdm
Mchi   = Mdm + gap_chi
mphich = Mdm + gap_charged
MH02   = Mdm + gap_H02
MA01   = Mdm + gap_A01
```

The complex Yukawas are scanned as Cartesian components:

```text
y_alpha = ynr_alpha + i yni_alpha
Y_alpha = Y1r_alpha + i Y1i_alpha
yprime  = ypr11 + i ypi11
```

## Neutrino mass

The matrix implemented in `matrices.yaml` is

```text
(m_nu)_ab = Lambda * (Y_a y_b + y_a Y_b)
Lambda = -(mu_phi v^2 Mchi / MN) I3(mphi, mphip, Mchi) yprime
```

The singular values are converted from GeV to eV without automatic NuFit
rescaling. Normal ordering uses columns `[2, 1, 0]`; inverted ordering uses
`[1, 0, 2]`. Mixing angles and the CP phase use the PDG matrix-element and
Jarlskog/`atan2` extraction.

## Running

Compile and evaluate the default accepted reference point:

```bash
.venv/bin/python - <<'PY'
from bsm_scanner import compile_model, load_model

model = load_model("models/oneloop/model_chi_no.yaml")
compiled = compile_model(model, build_backend=True)
point = {parameter.name: parameter.default for parameter in model.parameters}
print(compiled.evaluate(point))
PY
```

Run the configured `basin_scan`:

```bash
.venv/bin/python - <<'PY'
from bsm_scanner import compile_model, load_model, run_scan
from pathlib import Path

model = load_model("models/oneloop/model_chi_no.yaml")
compiled = compile_model(model, build_backend=False)
result = run_scan(model, compiled, run_directory=Path("runs/oneloop_chi_no"))
print(result.summary)
PY
```

Run a scan followed by posterior MCMC around the best/elite points:

```bash
.venv/bin/python examples/oneloop_full/run_scan.py \
  --model examples/oneloop_full/model_chi_no_mcmc.yaml \
  --run-dir examples/oneloop_full/runs/chi_no_mcmc
```

For the micrOMEGAs-backed chi-DM normal-ordering model:

```bash
.venv/bin/python examples/oneloop_full/run_scan.py \
  --model examples/oneloop_full/model_chi_no_micromegas_mcmc.yaml \
  --run-dir examples/oneloop_full/runs/chi_no_micromegas_mcmc
```

The posterior-enabled manifests use `scan_reference_mcmc.yaml`. They first run
the usual `basin_scan`; if a best-fit/elite set is available, they initialize
`emcee` walkers with `elite_covariance` and save MCMC artifacts such as:

```text
mcmc_samples.csv
mcmc_summary.json
mcmc_diagnostics.json
mcmc_best_posterior.json
mcmc_best_likelihood.json
mcmc_valid_points_delta_nll.csv
mcmc_valid_points_delta_chi2.csv
```

Use a `model_*_micromegas.yaml` manifest only when the optional
`oneloop_micromegas` backend is built and configured. The analytic manifests
remain portable and do not require micrOMEGAs.

The default points are accepted rows taken from the supplied standalone scan
outputs. They are regression references, not guaranteed global best fits.
