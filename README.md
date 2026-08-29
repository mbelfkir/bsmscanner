# BSMScanner

`BSMScanner` is a production-oriented framework skeleton for fast parameter scans of BSM models.

It is intentionally built around a sharp split:

- Python for model definition, validation, graph construction, scan orchestration, result loading, and notebook workflows.
- C++ for hot-loop point evaluation, typed caching, matrix algebra, diagonalization, and likelihood accumulation.
- Optional Fortran for isolated numerical kernels or external scanner bridges.

The framework identity is not backend orchestration. The core abstraction is a user-defined analytic model that is lowered into a compiled dependency graph before the scan starts.

The repository now includes the missing full scan-execution layer: Python builds a deterministic scan request from model metadata, while the native layer drives repeated point evaluation through a scanner-facing callback and writes complete run outputs.

## Architectural Choice

The repository chooses a unified model schema with clear sections instead of requiring users to edit core C++:

- `parameters`
- `constants`
- `functions`
- `derived_scalars`
- `derived_complex`
- `matrices`
- `diagonalizations`
- `observables`
- `theory_checks`
- `likelihoods`
- `outputs`
- `scan`

The Python layer validates these sections, resolves dependencies, rejects cycles, expands reusable analytic functions, and lowers the active subgraph into a compact plan that the C++ core evaluates point by point.

The framework also supports a second layer of reuse through imported YAML blocks
under `core`. This is where genuinely
model-independent building blocks now live, such as shared physics constants and
ordering-aware neutrino observable definitions. Models still own their
likelihood composition and choose which reusable blocks to import.

## Repository Layout

```text
BSMScanner/
├── CMakeLists.txt
├── pyproject.toml
├── README.md
├── docs/
│   ├── architecture.md
│   ├── core_neutrino_blocks.md
│   ├── current_status.md
│   ├── dm_status.md
│   ├── implemented_vs_deferred.md
│   ├── migration_oneloop.md
│   ├── modular_models.md
│   ├── model_schema.md
│   ├── oneloop_full.md
│   ├── oneloop_master.md
│   ├── release_notes_oneloop.md
│   └── scan_runner.md
├── core/
│   ├── constants/
│   │   └── physics_constants.yaml
│   └── neutrino/
│       ├── inverted.yaml
│       ├── normal.yaml
│       ├── observables_common.yaml
│       ├── observables_inverted.yaml
│       └── observables_normal.yaml
├── examples/
│   ├── leptontest/
│   │   ├── model.yaml
│   │   ├── model_inverted.yaml
│   │   └── run_scan.py
│   ├── oneloop_full/
│   │   ├── model.yaml
│   │   ├── run_example.py
│   │   └── run_scan.py
│   ├── oneloop_master/
│   │   ├── model.yaml
│   │   ├── run_example.py
│   │   └── run_scan.py
│   └── oneloop_minimal/
│       ├── model.yaml
│       ├── run_example.py
│       └── run_scan.py
├── models/
│   ├── leptontest/
│   │   ├── model.yaml
│   │   ├── model_inverted.yaml
│   │   ├── parameters.yaml
│   │   ├── functions.yaml
│   │   ├── derived.yaml
│   │   ├── matrices.yaml
│   │   ├── constraints/
│   │   ├── outputs.yaml
│   │   └── scan.yaml
│   ├── oneloop/
│   │   ├── model.yaml
│   │   ├── parameters.yaml
│   │   ├── constants.yaml
│   │   ├── functions.yaml
│   │   ├── derived.yaml
│   │   ├── matrices.yaml
│   │   ├── diagonalizations.yaml
│   │   ├── observables/
│   │   ├── constraints/
│   │   ├── outputs.yaml
│   │   ├── scan.yaml
│   │   └── data/
│   └── oneloop_master/
│       ├── model.yaml
│       ├── parameters.yaml
│       ├── constants.yaml
│       ├── derived_backend.yaml
│       ├── observables/
│       ├── constraints/
│       ├── outputs.yaml
│       └── scan.yaml
├── fortran/
│   └── kernels/
│       └── example_loop_kernel.f90
├── include/
│   └── bsm/
│       └── core/
│           ├── constraints.hpp
│           ├── evaluator.hpp
│           ├── functions.hpp
│           ├── graph.hpp
│           ├── plugins.hpp
│           ├── scan/
│           │   ├── adapter.hpp
│           │   ├── config.hpp
│           │   ├── mapper.hpp
│           │   ├── result_writer.hpp
│           │   └── runner.hpp
│           ├── status.hpp
│           └── types.hpp
├── python/
│   └── bsm_scanner/
│       ├── __init__.py
│       ├── api.py
│       ├── exceptions.py
│       ├── scan.py
│       ├── compiler/
│       │   ├── expressions.py
│       │   └── lowering.py
│       └── model/
│           ├── graph.py
│           └── schema.py
├── src/
│   ├── constraints.cpp
│   ├── evaluator.cpp
│   ├── functions.cpp
│   ├── oneloop_micromegas.cpp
│   ├── status.cpp
│   ├── scan/
│   │   ├── adapter.cpp
│   │   ├── config.cpp
│   │   ├── mapper.cpp
│   │   ├── result_writer.cpp
│   │   └── runner.cpp
│   └── pybind_module.cpp
└── tests/
    ├── test_constraints.py
    ├── test_graph.py
    ├── test_model_loading.py
    ├── test_oneloop_full.py
    └── test_scan_runner.py
```

## Core Concepts

- `ModelDefinition`: validated user-facing representation of a model.
- `ModelGraph`: named dependency graph over parameters, derived quantities, matrices, diagonalizations, observables, theory checks, likelihoods, and outputs.
- `CompiledModelSpec`: Python-lowered plan that contains bytecode-like expression programs plus typed node metadata.
- `CompiledModel`: immutable C++ evaluation object safe to reuse across many scan points and threads.
- `PointResult`: structured result for one point, including outputs, likelihood terms, total likelihood, flags, and invalid-point diagnostics.

## Current State

This repository is a serious scaffold, not a monolithic finished physics package. It already contains:

- a concrete schema,
- dependency analysis,
- cycle detection,
- expression lowering to bytecode,
- a C++ typed evaluator skeleton,
- likelihood machinery interfaces,
- diagonalization and matrix hooks,
- an `oneloop_minimal` smoke-test example model,
- a substantially migrated `oneloop_full` example covering the original neutrino, LFV, Higgs, EW, and theory-check sectors,
- an optional `oneloop_master` variant that matches the latest `oneloop-master` constraint structure and exact micrOMEGAs-backed DM observables when that backend is enabled,
- a native scan runner with Diver integration and deterministic output writing,
- modular multi-file model manifests with relative imports and duplicate protection,
- a generic plugin-call path for backend-backed observables without model-specific core hacks,
- migration notes from the reference code,
- seven published benchmark models (see Benchmark Models below) plus a
  `basin_scan` engine (broad exploration, clustering, focused refinement)
  alongside `serial_random`, `de_scipy`, and `adaptive_diver`,
- a YAML loader with YAML-1.2-compliant float resolution, so numeric scalars
  such as `1.0e9` are never silently read as text (YAML 1.1's default
  behaviour, since it requires a signed exponent for a bare token to parse as
  a float),
- tests for the Python frontend.

## Prerequisites

- Python >= 3.10
- A C++20 compiler (tested with GCC >= 11 and Apple Clang)
- CMake >= 3.20
- **Eigen3 >= 3.4** -- a system dependency, not vendored. Install it first:

  ```bash
  brew install eigen              # macOS
  sudo apt-get install libeigen3-dev   # Debian/Ubuntu
  conda install -c conda-forge eigen   # conda
  ```

  `CMakeLists.txt` also looks under `/usr/include`, `/usr/local/include`, and
  `/opt/homebrew/include` directly, or you can point it at a specific install
  with `-DEigen3_DIR=/path/to/eigen/share/eigen3/cmake`.

## Build

Python packaging is driven by `scikit-build-core`, with CMake building the C++ extension.
The root build now discovers plugin sources under `src/plugins/*.cpp`
automatically and includes any plugin-local CMake fragments under
`cmake/plugins/*.cmake`, so new backend integrations do not require editing the
framework `CMakeLists.txt`.

```bash
pip install -e .
```

To configure without the optional Diver or Fortran layers:

```bash
cmake -S . -B build
cmake --build build -j
```

To build the native Diver bridge:

```bash
CMAKE_ARGS="-DBSM_SCANNER_BUILD_DIVER=ON -DBSM_SCANNER_DIVER_ROOT=/path/to/Diver" \
pip install -e .[dev]
```

To enable the SciPy differential-evolution reference backend:

```bash
python -m pip install -e '.[de]'
```

## Command Line

The installable package exposes a small CLI:

```bash
bsm-scanner --help
bsm-scanner --version
python -m bsm_scanner --help
```

A lightweight installed smoke example is available without micrOMEGAs or Diver:

```bash
bsm-scanner run --example quadratic --run-dir runs/quadratic-smoke
```

Full physics scans should use model-local YAML files, for example:

```bash
bsm-scanner run --model models/oneloop_master/model_normal_full.yaml --run-dir runs/normal-full
```

Models that request the external `diver` engine still require a Diver-enabled native build.

To build the exact latest-master oneloop DM backend against micrOMEGAs:

```bash
CMAKE_ARGS="-DBSM_SCANNER_BUILD_ONELOOP_MICROMEGAS=ON \
            -DBSM_SCANNER_MICROMEGAS_ROOT=/path/to/micromegas \
            -DBSM_SCANNER_MICROMEGAS_MODEL_ROOT=/path/to/1LRNM-1N1P-New \
            -DBSM_SCANNER_MICROMEGAS_CALCHEP_ROOT=/path/to/CalcHEP_src" \
pip install -e .[dev]
```

## Run A Scan

The high-level API now supports full scan execution:

```python
from pathlib import Path

from bsm_scanner import compile_model, load_model, run_scan

model = load_model("models/oneloop/model.yaml")
compiled = compile_model(model, build_backend=False)
results = run_scan(model, compiled, run_directory=Path("runs/oneloop_example"))
print(results.summary)
```

The example launcher uses the same path:

```bash
python examples/oneloop_full/run_scan.py --run-dir examples/oneloop_full/runs/example_scan
```

Available scan engines now include:

- `serial_random`
- `diver`
- `de_scipy`
- `adaptive_diver`
- `basin_scan`

`de_scipy` is a temporary reference backend built on
`scipy.optimize.differential_evolution`. It exists to validate the framework’s
DE engine contract and to provide a comparison baseline before a native DE
implementation is added.

`adaptive_diver` is the native model-agnostic adaptive Differential Evolution
engine. It uses the same evaluator/objective pipeline as the other engines,
supports final-population diagnostics, and can optionally refine elite points
with SciPy local minimizers.

`basin_scan` explores broadly first, clusters the surviving valid points,
builds a focused sub-box around each cluster, and runs `adaptive_diver` inside
each box. It is the strongest strategy on benchmarks with a sparse, clustered
valid region (see `docs/published_benchmark_validation.md`), and the weakest
on benchmarks where the valid region is a broad, degenerate plateau -- engine
choice should follow the shape of the likelihood, not a fixed default.

An optional statistics layer can also post-process completed scan outputs into
plot-ready CSV and JSON artifacts. It is configured through a top-level
`statistics:` block, writes under `run_directory/statistics`, and intentionally
does not generate plots inside the framework.

The example path remains as a compatibility wrapper, but the real modular model now lives in:

```text
models/oneloop/model.yaml
```

The latest-master-faithful variant lives in:

```text
models/oneloop_master/model.yaml
```

`scan.settings` is reserved for actual runner controls such as `maxgen`,
`population_size`, and `objective`. Unknown keys are rejected instead of being
silently echoed into metadata.

## Core Reusable YAML

The `core` tree is for framework-owned YAML that
is still declarative rather than hardcoded into the evaluator. The current
prototype centralizes:

- shared physics constants
- ordering-aware neutrino observable blocks
- core/common observable wiring that depends only on declared matrix roles and
  automatic diagonalization

Models are expected to keep their own:

- parameters
- analytic matrix definitions
- scan settings
- likelihood blocks and dataset choices
- plugins or custom likelihood terms when they are genuinely model-specific

`models/leptontest` is the first clean example of this split.

## Remote Sync And Build

To sync this workspace to a remote build host and build it there, set the
destination first:

```bash
export REMOTE_HOST=user@host
export REMOTE_DIR=/path/on/remote/BSMScanner

./scripts/sync_to_remote.sh
./scripts/build_on_remote.sh
```

Both variables are required; the scripts exit with a message if either is unset.

## Benchmark Models

`models/` includes seven published benchmark models used in a companion
methodology study comparing the four scan engines at matched budget, in
addition to the framework's own development models (`oneloop`,
`oneloop_master`, `leptontest`, ...):

- `scotogenic_ma` -- radiative (one-loop) neutrino mass with dark matter
- `minimal_bl` -- gauged U(1)_B-L with a seesaw and a Z'
- `two_higgs_doublet` -- CP-conserving two-Higgs-doublet model
- `smeft_wilson` -- SMEFT, Warsaw basis, 10 Wilson coefficients
- `zprime_simplified` -- Z' simplified dark matter (LHC DM Forum benchmark)
- `leptoquark_brw` -- Buchmuller-Ruckl-Wyler scalar leptoquark
- `alp_effective` -- axion-like-particle effective couplings

Each ships as a standalone model directory under `models/<name>/` with a
matching runnable example under `examples/<name>/`. See
`docs/published_benchmark_validation.md` for what is validated
formula-by-formula against the cited reference versus what remains a
simplified analytic proxy for each benchmark.

## Documentation

- [Architecture](docs/architecture.md)
- [Core / model split](docs/core_model_split.md)
- [Core and plugin boundaries](docs/core_plugin_boundaries.md)
- [Core neutrino blocks](docs/core_neutrino_blocks.md)
- [Current status](docs/current_status.md)
- [Implemented vs deferred](docs/implemented_vs_deferred.md)
- [DM status](docs/dm_status.md)
- [Modular models](docs/modular_models.md)
- [Model schema](docs/model_schema.md)
- [Scan runner](docs/scan_runner.md)
- [Oneloop migration and mapping](docs/migration_oneloop.md)
- [Full oneloop example](docs/oneloop_full.md)
- [Latest-master oneloop example](docs/oneloop_master.md)
- [Oneloop release notes](docs/release_notes_oneloop.md)
- [Basin scan engine](docs/basin_scan.md)
- [Adaptive Diver engine](docs/adaptive_diver.md)
- [Guided sampling](docs/guided_sampling.md)
- [Matrix diagonalization](docs/matrix_diagonalization.md)
- [Posterior MCMC](docs/posterior_mcmc.md)
- [Statistics post-processing](docs/statistics.md)
- [Published benchmark validation](docs/published_benchmark_validation.md)
- [Release readiness snapshot](RELEASE_READY.md)
