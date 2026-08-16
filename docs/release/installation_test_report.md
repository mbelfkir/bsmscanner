# Installation Test Report

Date: 2026-06-16

## Artifacts

- Wheel: `dist/bsm_scanner-0.1.0-cp313-cp313-macosx_15_0_arm64.whl`
- Source distribution: `dist/bsm_scanner-0.1.0.tar.gz`

## Build Checks

Commands:

```bash
/tmp/bsmscanner-build-venv/bin/python -m build
/tmp/bsmscanner-build-venv/bin/python -m twine check dist/*
```

Result: build succeeded and `twine check` passed for both artifacts.

Wheel inspection:

- Contains `bsm_scanner/_core.cpython-313-darwin.so`
- Contains `bsm_scanner/examples/quadratic.yaml`
- Does not contain run directories

Source distribution inspection:

- Does not contain generated run directories
- Does not contain source-tree binary extensions

## Wheel Installation

Environment: `/tmp/bsmscanner-wheel-env-final`

Commands passed from `/tmp/bsmscanner-outside-final`:

```bash
python -c "import bsm_scanner; print(bsm_scanner.__version__)"
bsm-scanner --version
python -m bsm_scanner --version
bsm-scanner run --example quadratic --run-dir /tmp/bsmscanner-outside-final/quadratic-wheel-run
```

Result:

- Import version: 0.1.0
- CLI version: 0.1.0
- Example evaluations: 5
- Example valid points: 5
- Example best nLL: 0.006113655744209275

## Source Distribution Installation

Environment: `/tmp/bsmscanner-sdist-env-final`

Commands passed from `/tmp/bsmscanner-outside-final`:

```bash
python -c "import bsm_scanner; print(bsm_scanner.__version__)"
bsm-scanner --version
bsm-scanner run --example quadratic --run-dir /tmp/bsmscanner-outside-final/quadratic-sdist-run
```

Result:

- Import version: 0.1.0
- CLI version: 0.1.0
- Example evaluations: 5
- Example valid points: 5
- Example best nLL: 0.006113655744209275

Final status: clean wheel and source-distribution installation passed.
