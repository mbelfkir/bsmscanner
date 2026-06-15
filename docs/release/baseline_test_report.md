# Baseline Test Report

Date: 2026-06-16

## Environment

- Python: 3.13.5
- Platform: macOS 15.6.1 arm64
- NumPy in ambient environment: 2.4.3
- PyYAML in ambient environment: 6.0.3
- Missing from ambient environment: SciPy, pandas, pybind11, scikit-build-core, twine, ruff
- micrOMEGAs: not discovered locally
- Diver: not discovered locally

## Initial Baseline

Command:

```bash
pytest -q
```

Result:

- Passed: 128
- Skipped: 11
- Failed: 43
- Runtime: 9.37 s

Failure classification:

- Environment/stale native extension: most native-evaluator failures. The test process loaded `/opt/miniconda3/lib/python3.13/site-packages/bsm_scanner/_core.cpython-313-darwin.so` rather than a freshly built extension from this source tree.
- Missing optional dependency: `de_scipy` smoke test failed in the ambient environment because SciPy was not installed.
- Existing source defect not demonstrated: after rebuilding the current extension, the same suite passed.

## Rebuilt Baseline

Commands:

```bash
/tmp/bsmscanner-build-venv/bin/python -m build
cp /tmp/bsmscanner-build-venv/lib/python3.13/site-packages/bsm_scanner/_core.cpython-313-darwin.so python/bsm_scanner/_core.cpython-313-darwin.so
/tmp/bsmscanner-build-venv/bin/python -m pytest -q
rm -f python/bsm_scanner/_core*.so
```

Result:

- Passed: 176
- Skipped: 6
- Failed: 0
- Runtime: 25.68 s first rebuilt run; 9.87 s after warm build

The temporary copied extension was removed after verification and is excluded from source distributions.
