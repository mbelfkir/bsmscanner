# BSMScanner

Graph-compiled scanner for BSM (Beyond the Standard Model) physics models. Python
owns model definition, validation, graph construction, scan orchestration, and
result loading; a C++ extension (built via `pybind11` + CMake + `scikit-build-core`)
owns hot-loop point evaluation, matrix algebra/diagonalization, and likelihood
accumulation. The core abstraction is a user-defined analytic model (YAML) that
gets lowered into a compiled dependency graph before a scan starts. See
`README.md` for the full repository layout and `docs/architecture.md` for the
architectural rationale.

## Setup / build

```bash
pip install -e ".[dev,de,analysis]"
```

This compiles the C++ extension in place via `scikit-build-core`/CMake. Eigen3
(header-only) and a C++20-capable compiler must be available on the machine —
see `README.md`'s Prerequisites section. To iterate on the CMake side directly:

```bash
cmake -S . -B build
cmake --build build -j
```

## Test & lint

Exactly what CI runs (`.github/workflows/release.yml`, `validate` job):

```bash
pytest -q
ruff check .
```

`pyproject.toml`'s `[tool.pytest.ini_options]` sets `testpaths = ["tests"]` and
`pythonpath = ["python"]`. Ruff is scoped to `select = ["E4", "E7", "E9", "F", "I"]`
(pyflakes, a few pycodestyle error classes, import sorting) — deliberately not
the full default rule set.

## Repository layout

- `python/bsm_scanner/` — the Python package (model loading/validation/graph in
  `model/`, YAML→plan lowering in `compiler/`, scan orchestration in `scan.py`,
  the public API in `api.py`, the `bsm-scanner` CLI in `cli.py`).
- `src/`, `include/bsm/` — the C++ evaluation core and its pybind11 bindings.
- `core/` — reusable, model-independent YAML building blocks shipped with the
  package (constants, neutrino/quark observable definitions, oscillation data
  tables). Referenced from model YAML via the `core:` prefix, e.g.
  `core:neutrino/observables_common.yaml` — never `../../core/...` (that only
  works inside this checkout; the `core:` prefix resolves correctly wherever
  the package is installed). See `docs/authoring_models.md` for the full
  authoring guide, including `bsm-scanner core list/show/path`.
- `models/` — the framework's own example/benchmark models, each with
  `model.yaml`, `parameters.yaml`, `outputs.yaml`, etc. following the schema
  documented in `docs/model_schema.md`.
- `examples/` — small runnable end-to-end examples paired with some of the
  models above.
- `notebooks/` — pre-executed Jupyter tutorial notebooks, one per published
  benchmark model, loading `../models/...` and `../python` by relative path.
  Re-run cells write scratch output to `notebooks/**/runs/` (gitignored); a
  cell explicitly marked as not executed in the original notebook (the
  full matched-budget, ~30k-evaluation reproduction) should stay that way
  when refreshing outputs.
- `tests/` — pytest suite; `tests/fixtures/` for shared fixtures.
- `docs/` — one Markdown file per subsystem (architecture, scan runner, basin
  scan, adaptive Diver engine, posterior MCMC, statistics layer, matrix
  diagonalization, etc.) plus `docs/current_status.md` for the current
  implemented/deferred milestone state — check that file before assuming
  something is or isn't implemented.

## Versioning & release process

The version string is duplicated in two places and must be bumped together:

- `pyproject.toml` → `[project] version`
- `python/bsm_scanner/__init__.py` → the `__version__` fallback string (used
  when the package metadata lookup via `importlib.metadata.version` fails,
  e.g. running from a source checkout without an install)

Add a matching `## X.Y.Z` section at the top of `CHANGELOG.md` (above the
previous version's section, below any `## Unreleased` section).

CI (`.github/workflows/release.yml`) builds real installable wheels via
`cibuildwheel` (config in `pyproject.toml`'s `[tool.cibuildwheel]` table) for:

| Platform | Architecture | Python |
|---|---|---|
| macOS | arm64 (Apple Silicon) | 3.10-3.13 |
| Linux | x86_64, manylinux_2_28 | 3.10-3.13 |

macOS x86_64 is intentionally not built — cross-compiling this project's CMake/
scikit-build-core extension for x86_64 from GitHub's arm64 `macos-14` runners
failed, and GitHub has no free Intel macOS runner to build it natively.
Windows is also not built (unvalidated). Both are a known, documented gap —
see the Installation section of `README.md`.

**PyPI/TestPyPI immutability**: a given `(package, version)` filename can never
be re-uploaded once published, even with different content. A release that
needs to change after publishing requires a version bump, not a re-upload —
this is why CI/release work often needs its own version bump even for
infrastructure-only changes (e.g. 0.1.1 → 0.1.2 for the `cibuildwheel` CI
overhaul, with no Python-facing API change).

Releases are dispatched against `release-target: testpypi` or `pypi` (workflow
`inputs.target` in `release.yml`) — only publish to real PyPI when explicitly
asked to; TestPyPI is the default/safe target for verifying a release.

## Known gotchas

- **`nscale`/`Lambda` were renamed to `scale`** in the neutrino core blocks and
  several models' `outputs.yaml` (0.1.1). If you see `KeyError: 'nscale'` or
  `KeyError: 'Lambda'` in tests or scan output, it's almost always a leftover
  reference to the old name in a model's `outputs.yaml`/`constraints`, not a
  framework bug — grep the model directory before assuming otherwise.
- **Eigen3 is header-only** — it's a build-time-only dependency of the C++
  extension. Nothing links against it at runtime once compiled, so it must
  never appear as a runtime/install-time requirement in `pyproject.toml`.
- On Linux, wheels are passed through `auditwheel repair` (cibuildwheel's
  default) — this fails the CI build outright, rather than shipping a broken
  wheel, if the compiled extension depends on a shared library outside the
  `manylinux_2_28` policy baseline.
- The `release/0.1.0` branch and `main` are kept in sync for release/doc work
  in this repo's current workflow — check whether a change needs to land on
  both before assuming a single-branch push is complete.
