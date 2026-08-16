# Pre-PyPI Archive

Date: 2026-06-16 00:06 +04

## Repository State

- Repository root: `the repository root`
- Git repository: not available in this working tree (`git status` reports `fatal: not a git repository`)
- Archive branch: not created because `.git` is absent
- Archive tag: not created because `.git` is absent
- Commit hash: unavailable because `.git` is absent
- Python: 3.13.5, Anaconda build
- Platform: macOS 15.6.1 arm64

## Archive

- Archive file: `archives/BSMScanner_pre_pypi_20260616_000644.tar.gz`
- Archive size: 888 KiB
- Verification: `tar -tzf` completed successfully
- Excluded generated/reproducible heavy paths: `.venv`, `build`, `dist`, `archives`, `artifacts`, `results`, `examples/*/runs`, `models/*/runs`, `benchmarks/runs`, caches, `__pycache__`, `.DS_Store`

## Baseline Test Status

Initial baseline with the ambient Python environment failed because it imported a stale globally installed native extension from `/opt/miniconda3/lib/python3.13/site-packages/bsm_scanner/_core.cpython-313-darwin.so`.

After rebuilding the current source extension in an isolated environment, the suite passed with `176 passed, 6 skipped`.
