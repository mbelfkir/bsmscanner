# Release Ready

## Snapshot

This repository was prepared as a milestone freeze on April 10, 2026.

Current baseline:

- framework package version: `0.1.0`
- modular oneloop model version: `0.2.0`
- canonical full model manifest: `models/oneloop/model.yaml`
- main remaining gap: exact micrOMEGAs-backed dark-matter observables and likelihoods

## Release Audit

Recommended audit command:

```bash
python scripts/release_audit.py
```

The audit verifies:

- the local test suite passes
- the full oneloop model loads successfully
- the full oneloop model compiles to the native backend
- one default-point evaluation returns `status == ok`
- one serial-random smoke scan completes and writes outputs

Audit note:

- the smoke scan intentionally uses a tiny deterministic box around the known-good default point so it exercises the scan runner and output path without pretending to be a physics search

## Local Cleanup State

Local generated run output was removed from:

- `examples/oneloop_minimal/runs/serial_random_2026-04-08`

Generated or environment-specific paths that should not be treated as release source:

- `build/`
- `.venv/`
- `.pytest_cache/`
- `examples/**/runs/`

The ignore rules were tightened so source data tables are no longer hidden behind a blanket `*.csv` or `*.json` ignore.

## Tagging Plan

No git tag was created automatically during this audit because the current workspace does not expose a usable `.git` repository.

Suggested annotated milestone tag once the repository is inside its real git checkout:

- `oneloop-milestone-2026-04-10`

Suggested manual sequence:

```bash
git status
python scripts/release_audit.py
git add .
git commit -m "Freeze oneloop milestone state"
git tag -a oneloop-milestone-2026-04-10 -m "Stable oneloop milestone after table-lookup fix"
```

## Required Reading Before Production Scans

- `docs/current_status.md`
- `docs/implemented_vs_deferred.md`
- `docs/dm_status.md`
- `docs/release_notes_oneloop.md`

## Milestone Claim

What is frozen as working:

- compiled point evaluation
- native scan execution
- Diver integration on the server
- modular oneloop normal-ordering model
- oscillation tables with corrected in-range table likelihood evaluation
- Higgs, LFV, electroweak, and analytic theory-check sectors used by the migrated model

What is explicitly not claimed as complete:

- exact micrOMEGAs-backed relic density
- exact micrOMEGAs-backed direct detection
- exact backend-selected odd-particle identity and DM naming
