# BSMScanner

`bsm-scanner` is a framework for fast parameter scans of Beyond-the-Standard-Model
physics models. You describe a model in YAML -- parameters, constants, derived
quantities, matrices, observables, theory checks, likelihoods -- and the framework
compiles it into a dependency graph, evaluates it in a compiled C++ core, and
drives a parameter scan over it.

It is built around a sharp split:

- **Python** owns model definition, validation, graph construction, scan
  orchestration, and result loading.
- **C++** owns hot-loop point evaluation, typed caching, matrix algebra,
  diagonalization, and likelihood accumulation.
- **Optional Fortran** for isolated numerical kernels or external scanner
  bridges.

Your model lives in your own directory, not inside the framework. You write
YAML, optionally import the reusable physics blocks the package ships (shared
constants, neutrino/quark observable definitions, oscillation data tables),
and run.

## Installation

### From a published wheel (recommended)

```bash
pip install bsm-scanner
```

While the package is only published to TestPyPI (a real PyPI release is not out
yet), dependencies have to come from the real index instead, since TestPyPI does
not mirror them:

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ bsm-scanner
```

CI publishes prebuilt wheels via `cibuildwheel` for:

| Platform | Architecture             | Python      |
| -------- | ------------------------ | ----------- |
| macOS    | arm64 (Apple Silicon)    | 3.10 - 3.13 |
| Linux    | x86_64, glibc >= 2.28 (`manylinux_2_28`) | 3.10 - 3.13 |

On a matching machine, installation needs nothing beyond `pip`. Eigen3 -- the
only native dependency besides pybind11 -- is header-only, so it is only needed
while *building* the C++ extension, not at install or runtime; nothing links
against it once compiled. The Linux wheels are also passed through `auditwheel
repair` as part of the build, which fails the build outright (rather than
shipping a broken wheel) if the compiled extension ends up depending on any
shared library outside the `manylinux_2_28` baseline. So on either platform
above, there is nothing to separately install for Eigen3, CMake, or a C++
compiler.

Outside that matrix -- Windows, Linux aarch64, macOS x86_64 (Intel), musllinux
(Alpine), or a Python version other than 3.10-3.13 -- `pip install` silently
falls back to building from the source distribution instead, which needs
everything in [Prerequisites](#prerequisites) below already installed on your
machine, and will fail with a `CMake not found` or `Eigen3 was not found` error
otherwise.

### From source

Clone the repository, install the [Prerequisites](#prerequisites) below, then
see [Build](#build).

## Quickstart

Start from a working template rather than an empty file:

```bash
pip install bsm-scanner
bsm-scanner new-model mymodel
bsm-scanner run --model mymodel/model.yaml --run-dir mymodel/runs/first
```

That creates a small, complete, runnable model you can edit. It runs
immediately, so you always have a working baseline to modify.

### Model syntax

A model is one or more YAML files under a schema with a fixed set of top-level
sections -- `parameters`, `constants`, `functions`, `derived_scalars`,
`derived_complex`, `matrices`, `diagonalizations`, `observables`,
`theory_checks`, `likelihoods`, `outputs`, and `scan`. A trimmed real example
(from `models/minimal_bl/model.yaml`, a gauged B-L benchmark):

```yaml
metadata:
  name: minimal_bl_gauge
  version: 0.1.0

parameters:
- {name: gBL, value_type: real, scan: true, lower: 0.001, upper: 1.0, default: 0.1, prior: log}
- {name: vBL, value_type: real, scan: true, lower: 1000.0, upper: 100000.0, default: 70000.0, prior: log}

constants:
- {name: v_sm, value: 246.22}

derived_scalars:
- {name: MZp, value_type: real, expression: "2.0*gBL*vBL"}

observables:
- {name: MZprime, value_type: real, expression: MZp}

theory_checks:
- {name: positive_masses, condition: "MZp > 0", fatal: true, message: MZp must be positive.}

likelihoods:
- {name: lep_contact_bound, kind: hard_cut, observable: MZprime, lower: 7000.0, upper: 1.0e9}

outputs:
  save: [MZprime]

scan:
  engine: serial_random
  save_every: 100
  seed: 11064462
  settings: {objective: nll, max_evaluations: 2000}
```

The Python layer validates these sections, resolves dependencies, rejects
cycles, expands reusable analytic functions, and lowers the active subgraph
into a compact plan that the C++ core evaluates point by point. Matrices carry
metadata (`type`, `role`, `diagonalize: true`) that triggers automatic
diagonalization -- see `docs/matrix_diagonalization.md` and
`docs/core_model_split.md`.

### Reusable physics blocks

The framework ships a library of model-independent building blocks --
constants, neutrino/quark observable definitions, oscillation data tables.
Reference them with the `core:` prefix, which resolves to wherever the package
is installed, so your model works no matter which directory it lives in:

```yaml
imports:
  - core:constants/physics_constants.yaml
  - core:neutrino/observables_common.yaml
  - core:neutrino/observables_normal.yaml
  - my_parameters.yaml       # your own files stay relative
  - my_matrices.yaml
```

```bash
bsm-scanner core list                                    # every shipped block
bsm-scanner core show core:quark/quark_mass_ratios.yaml   # what a block defines
bsm-scanner core path                                     # where they live
```

See `docs/authoring_models.md` for the full authoring guide, including what
each shipped block provides and the division between what belongs in the
reusable core versus in your own model.

### Python API

```python
from pathlib import Path

from bsm_scanner import compile_model, load_model, run_scan

model = load_model("models/minimal_bl/model.yaml")
compiled = compile_model(model, build_backend=True)
results = run_scan(model, compiled, run_directory=Path("runs/minimal_bl_example"))
print(results.summary)
```

The example launcher uses the same path:

```bash
python examples/minimal_bl/run_scan.py --run-dir examples/minimal_bl/runs/example_scan
```

## Core Concepts

- `ModelDefinition`: validated user-facing representation of a model.
- `ModelGraph`: named dependency graph over parameters, derived quantities, matrices, diagonalizations, observables, theory checks, likelihoods, and outputs.
- `CompiledModelSpec`: Python-lowered plan that contains bytecode-like expression programs plus typed node metadata.
- `CompiledModel`: immutable C++ evaluation object safe to reuse across many scan points and threads.
- `PointResult`: structured result for one point, including outputs, likelihood terms, total likelihood, flags, and invalid-point diagnostics.

## Prerequisites

These are only needed for a from-source build -- i.e. cloning this repository,
or installing on a platform/Python version outside the prebuilt-wheel matrix
above.

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
The root build discovers plugin sources under `src/plugins/*.cpp`
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
bsm-scanner new-model mymodel
bsm-scanner core list
```

A lightweight installed smoke example is available without any model file:

```bash
bsm-scanner run --example quadratic --run-dir runs/quadratic-smoke
```

Full physics scans use model-local YAML files, for example:

```bash
bsm-scanner run --model models/scotogenic_ma/model_no.yaml --run-dir runs/scotogenic-no
```

Models that request the external `diver` engine still require a Diver-enabled native build.

Available scan engines:

- `serial_random`
- `diver`
- `de_scipy`
- `adaptive_diver`
- `basin_scan`

`de_scipy` is a reference backend built on
`scipy.optimize.differential_evolution`. It exists to validate the framework's
DE engine contract and to provide a comparison baseline.

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

`scan.settings` is reserved for actual runner controls such as `maxgen`,
`population_size`, and `objective`. Unknown keys are rejected instead of being
silently echoed into metadata.

## Core Reusable YAML

The `core` tree is for framework-owned YAML that
is still declarative rather than hardcoded into the evaluator. It centralizes:

- shared physics constants
- ordering-aware neutrino observable blocks
- CKM observable and construction blocks
- core/common observable wiring that depends only on declared matrix roles and
  automatic diagonalization

Models are expected to keep their own:

- parameters
- analytic matrix definitions
- scan settings
- likelihood blocks and dataset choices
- plugins or custom likelihood terms when they are genuinely model-specific

`models/leptontest` is a clean, minimal example of this split. See
`docs/core_model_split.md` for the full rationale.

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
methodology study comparing the four scan engines at matched budget, plus a
handful of smaller internal reference/test models (`leptontest`, `t43i_b1`,
`weinberg`, ...):

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

Tutorial notebooks (one per published benchmark model, pre-executed) are under
`notebooks/` -- see `notebooks/README.md`.

## Repository Layout

```text
BSMScanner/
├── CMakeLists.txt
├── pyproject.toml
├── CHANGELOG.md
├── README.md
├── docs/                    # one file per subsystem -- see Documentation below
├── core/                    # reusable, model-independent YAML (core: prefix)
│   ├── constants/
│   └── neutrino/
├── examples/                # small runnable end-to-end examples, one per model
│   └── <name>/
│       ├── model.yaml
│       └── run_scan.py
├── models/                  # standalone model directories (see Benchmark Models)
│   └── <name>/
│       ├── model.yaml
│       ├── parameters.yaml
│       ├── constraints/
│       └── outputs.yaml
├── fortran/
│   └── kernels/
├── include/
│   └── bsm/core/            # C++ evaluation core headers
├── python/
│   └── bsm_scanner/         # Python package: api, compiler, model, scan
├── src/
│   ├── constraints.cpp
│   ├── evaluator.cpp
│   ├── plugins/             # backend plugins, auto-discovered at build time
│   └── scan/
├── notebooks/                # pre-executed tutorial notebooks
│   └── README.md
└── tests/                    # pytest suite
    └── fixtures/
```

## Documentation

- [Core / model split](docs/core_model_split.md)
- [Authoring your own model](docs/authoring_models.md)
- [Basin scan engine](docs/basin_scan.md)
- [Adaptive Diver engine](docs/adaptive_diver.md)
- [Guided sampling](docs/guided_sampling.md)
- [Matrix diagonalization](docs/matrix_diagonalization.md)
- [CKM observables](docs/ckm_observables.md)
- [Posterior MCMC](docs/posterior_mcmc.md)
- [Statistics post-processing](docs/statistics.md)
- [Published benchmark validation](docs/published_benchmark_validation.md)
- [Tutorial notebooks](notebooks/README.md)
