# Dark Matter Status

## Purpose

This document is the precise gap analysis for the dark-matter sector of the migrated oneloop model.

The short version is:

- the frozen milestone model under `/Users/mbelfkir/HEP/BSMScanner/models/oneloop` does not provide exact micrOMEGAs-backed DM observables
- the new latest-master variant under `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master` does provide exact micrOMEGAs-backed DM observables when built with the optional backend
- the baseline and latest-master variants now have intentionally different DM status

## Original Oneloop Workflow

Reference implementation:

- `/Users/mbelfkir/Downloads/oneloop-master2/src/nLLConstructor.cxx`
- `/Users/mbelfkir/Downloads/oneloop-master2/config/config_nr.yaml`

### Candidate Identity In The Original Code

The original code calls:

- `sortOddParticles(cdmName)`

It then loops over the micrOMEGAs-provided odd states, records their names and masses, and stores the selected candidate in `darkMatter`.

Relevant source region:

- `/Users/mbelfkir/Downloads/oneloop-master2/src/nLLConstructor.cxx:1149`

In the main FCN, the original code hard-rejects the point if:

- `darkMatter->get_name() != DMtarget`

Relevant source region:

- `/Users/mbelfkir/Downloads/oneloop-master2/src/nLLConstructor.cxx:1582`

### Relic Density In The Original Code

The original code computes relic density through micrOMEGAs:

- `darkOmega(&Xf, fast, Beps, &errDM)`

with:

- `fast = 1`
- `Beps = 1e-3`

It returns an invalid marker if the backend errors out or produces a non-finite or negative value.

Relevant source region:

- `/Users/mbelfkir/Downloads/oneloop-master2/src/nLLConstructor.cxx:1160`

The original likelihood contribution is a Gaussian built from the configured `Omega` interval:

- observable in config: `/Users/mbelfkir/Downloads/oneloop-master2/config/config_nr.yaml:345`
- likelihood implementation: `/Users/mbelfkir/Downloads/oneloop-master2/src/nLLConstructor.cxx:1430`

### Direct Detection In The Original Code

The original code computes a nucleon cross section using micrOMEGAs amplitudes:

- `nucleonAmplitudes(...)`

and stores a spin-independent nucleon cross section for the selected candidate.

Relevant source region:

- `/Users/mbelfkir/Downloads/oneloop-master2/src/nLLConstructor.cxx:1181`

The original direct-detection likelihood is backend-driven:

- `DD_pval(AllDDexp, Maxwell, &expName)`

It returns:

- `0` if `pval > 0.1`
- `std::numeric_limits<double>::max()` otherwise

Relevant source region:

- `/Users/mbelfkir/Downloads/oneloop-master2/src/nLLConstructor.cxx:1440`

### DM Outputs In The Original Code

The original output CSV includes:

- `Omega`
- `darkMatter`
- `SIxsec`

Reference:

- `/Users/mbelfkir/Downloads/oneloop-master2/output/output.rank0.csv`

## Current Framework State

Current modular model:

- `/Users/mbelfkir/HEP/BSMScanner/models/oneloop/model.yaml`

Latest-master-faithful variant:

- `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model.yaml`

### What Is Present Now

- analytic DM identity check:
  - `/Users/mbelfkir/HEP/BSMScanner/models/oneloop/constraints/theory_checks.yaml`
  - implemented as `Mpsi < MN, Mphi, MA1, MA2, MH1, MH2`
- metadata tag documenting the backend gap:
  - `micromegas_pending`
- explicit DM observable fragment:
  - `/Users/mbelfkir/HEP/BSMScanner/models/oneloop/observables/dm.yaml`
  - currently empty on purpose

### What Is Not Present Now

- no `Omega` observable
- no `SIxsec` observable
- no `darkMatter` string output
- no relic-density likelihood term
- no direct-detection likelihood term
- no micrOMEGAs backend wrapper inside the current framework build

## Latest-Master Variant Status

The repository now also contains an exact-path DM implementation for the latest
`oneloop-master` logic.

That path consists of:

- model-specific plugin:
  - `/Users/mbelfkir/HEP/BSMScanner/src/plugins/oneloop_micromegas.cpp`
- latest-master model:
  - `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model.yaml`
- declarative backend bindings:
  - `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/observables/dm.yaml`

### What Is Present In `models/oneloop_master`

- exact micrOMEGAs candidate selection through `sortOddParticles`
- exact `~chi` target match check
- exact relic density observable `Omega`
- exact spin-independent cross section observable `SIxsec`
- exact direct-detection p-value observable `DD_pvalue`
- dark-matter candidate mass output
- active DM likelihood terms:
  - `Omega_term`
  - `DDexp_term`
- generic runtime capability check through `has_plugin_support("oneloop_micromegas")`

### What Is Still Not Present

- string-valued dark-matter candidate output
  - the framework currently exposes numeric DM outputs and boolean target-match state, not the raw candidate-name string
- a guarantee that randomly chosen seed points are frequently valid
  - the exact latest-master DM path is intentionally strict and can reject a large fraction of points early

## Exact Status Classification

### Relic Density

- frozen baseline status: absent
- latest-master plugin status: exact micrOMEGAs-backed observable is implemented
- fidelity relative to original: exact on the optional `models/oneloop_master` path
- production-ready: only after model-specific scan validation on the plugin-enabled build

### Direct Detection

- frozen baseline status: absent
- latest-master plugin status: exact micrOMEGAs-backed `SIxsec` and `DD_pvalue` are implemented
- fidelity relative to original: exact on the optional `models/oneloop_master` path
- production-ready: only after model-specific scan validation on the plugin-enabled build

### DM Candidate Identity

- frozen baseline status: simplified analytic proxy
- latest-master plugin status: exact candidate sorting and target matching through micrOMEGAs
- fidelity relative to original: approximate in the frozen baseline, exact in the optional plugin path
- production-ready: exact only on the plugin-enabled latest-master path

### Backend Interface Preservation

- current status: generic plugin interface implemented
- fidelity relative to original: connected for the oneloop micrOMEGAs path through the plugin layer
- production-ready: the interface is production-usable; the physics validation remains model-specific

## Recommended Completion Plan

To reach full ergonomic parity with the original DM workflow, the framework still benefits from:

1. exposing the raw dark-matter candidate name as a first-class output type
2. adding a validated production scan configuration with known viable seed regions
3. benchmarking scan efficiency once the exact DM terms are active
4. deciding whether the frozen baseline model should ever gain an exact DM companion profile or remain DM-deferred by design

## Production Guidance Right Now

Current recommendation:

- do not include DM likelihood terms in production scans using the current milestone
- do not claim relic-density or direct-detection coverage in papers based on the current milestone alone
- if DM is essential to the analysis, finish and validate the micrOMEGAs backend integration first

Updated recommendation:

- for the frozen baseline model under `models/oneloop`, continue to exclude DM likelihood claims
- for exact latest-master DM studies, use `models/oneloop_master` on a build with `has_plugin_support("oneloop_micromegas") == True`

Acceptable current use:

- scans that explicitly focus on oscillation, LFV, Higgs, electroweak, and analytic theory-check sectors
- scans that document the DM sector as deferred
