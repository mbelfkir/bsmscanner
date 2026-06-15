# Oneloop Release Notes

## Milestone

Milestone freeze date:

- April 10, 2026

Relevant versions:

- framework package: `0.1.0`
- modular oneloop model: `0.2.0`

## Included In This Milestone

- modular oneloop normal-ordering model
- working compiled evaluator
- working native scan runner
- Diver support on the server
- oscillation table likelihoods
- LFV, Higgs, electroweak, scalar-theory-check, and perturbative-unitarity sectors
- milestone documentation separating implemented scope from deferred scope

## Major Scientific Fix Before Freeze

### Fixed `table_lookup` Likelihood Bug

Bug description:

- in-range `table_lookup` points incorrectly returned zero penalty instead of the interpolated table value

Fix location:

- `/Users/mbelfkir/HEP/BSMScanner/src/constraints.cpp`

Fix date:

- April 9, 2026

Impact:

- all earlier scans using `table_lookup` terms are invalid for physics use

Known obsolete results include:

- the earlier oscillation-only Diver run with an apparent `nLL = 0` minimum
- any earlier `dm21`-table scans produced before the fix

Corrected superseding run:

- `/home/mohamed/HEP/BSMScanner/examples/oneloop_full/runs/diver_oscillation_only_fixed_2026-04-09`
- corrected best minimum: `152.56087916897076`

## Remaining Scientific Limitation

The frozen milestone model under `/Users/mbelfkir/HEP/BSMScanner/models/oneloop`
does not claim exact parity with the original DM backend path.

Still deferred in that baseline model:

- micrOMEGAs relic density `Omega`
- micrOMEGAs direct-detection likelihood
- exact backend-based DM candidate identity and naming

New optional exact-path implementation:

- `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model.yaml`
- requires a build with the optional micrOMEGAs backend enabled

See:

- `/Users/mbelfkir/HEP/BSMScanner/docs/dm_status.md`

## Recommended Citation / Usage Language

Suggested scientifically honest description for this milestone:

- the framework provides a compiled scan implementation of the modularized normal-ordering oneloop model with validated oscillation, LFV, Higgs, electroweak, and analytic theory-check sectors
- the frozen baseline dark-matter sector remains explicitly deferred pending micrOMEGAs backend integration
- exact latest-master DM parity is available only through the separate `models/oneloop_master` variant on supported builds
- only scans produced after the April 9, 2026 `table_lookup` fix should be used for analyses involving tabulated oscillation likelihoods
