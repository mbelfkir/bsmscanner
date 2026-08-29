# Changelog

## Unreleased

- Added the `basin_scan` engine (broad exploration, clustering, focused
  per-cluster refinement) alongside `serial_random`, `de_scipy`, and
  `adaptive_diver`.
- Added seven published benchmark models (Scotogenic Ma, minimal B-L,
  two-Higgs-doublet, SMEFT Warsaw basis, Z' simplified dark matter, BRW
  scalar leptoquark, ALP effective couplings) used in a companion
  methodology study comparing all four engines at matched budget; see
  `docs/published_benchmark_validation.md`.
- Fixed the YAML loader to resolve floats per YAML 1.2 instead of YAML 1.1.
  Previously a scalar such as `1.0e9` (an exponent with no explicit sign)
  silently loaded as the *string* `"1.0e9"` rather than a float -- this could
  poison any numeric constant, parameter bound, or `table_lookup` penalty
  written that way. `ConstantSpec.value`, `ParameterSpec` bounds, and
  `table_lookup` penalty fields now also validate and coerce numeric text
  independently of the loader, with an error message that names the field and
  explains the fix.
- Fixed `evaluate_table_lookup`'s out-of-range branch, which previously
  returned the quadratic penalty alone and discarded the table's boundary
  value, creating a discontinuity at the edge of a tabulated likelihood's
  domain.
- Documented the Eigen3 >= 3.4 system prerequisite (not vendored) and added
  it to CI.
- Added a CI workflow that runs the test suite on Linux and macOS, in
  addition to the existing manual release/publish workflow.

## 0.1.0 - Release Candidate

- Added standard `bsm-scanner` CLI entry point.
- Added `python -m bsm_scanner` support.
- Added installed package version lookup through Python package metadata.
- Added a lightweight package-owned quadratic example for clean-install smoke tests.
- Tightened source-distribution exclusions so generated runs, archives, caches, and binary build artifacts are not packaged.
- Verified wheel and source-distribution installation from outside the source checkout.

This release candidate does not include a completed full normal-ordering production scan.
