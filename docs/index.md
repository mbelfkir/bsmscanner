# BSMScanner

**Declarative parameter scans for beyond-the-Standard-Model physics.**

BSMScanner turns a BSM parameter scan from a program into a document. You describe a model in
YAML — parameters and priors, mass matrices and their diagonalisation, observables, theory
checks and likelihood terms — and the framework validates it, compiles it once into a typed
C++ evaluator, and drives it with the scanning engine of your choice.

```bash
pip install bsm-scanner
bsm-scanner new-model mymodel
bsm-scanner run --model mymodel/model.yaml --run-dir mymodel/runs/first
```

<div class="grid cards" markdown>

-   :material-file-document-edit-outline: **A model is a YAML file**

    No code to write and no backend to register. Split a model into small fragments and import
    them from a manifest.

-   :material-library-outline: **Reusable physics library**

    PMNS/CKM construction, Takagi and singular-value diagonalisation, mixing-angle and phase
    conventions, and NuFIT oscillation likelihoods are imported by name with `core:`.

-   :material-speedometer: **Compiled evaluation**

    The model is compiled once into a C++ dependency graph; a point with a full Takagi
    factorisation and PMNS extraction evaluates in microseconds, so 10⁶-point scans are routine.

-   :material-swap-horizontal: **Engines are configuration**

    `serial_random`, `de_scipy`, `adaptive_diver` and the staged `basin_scan` share one
    interface — changing engine is one line of `scan:`.

-   :material-puzzle-outline: **Plugins when you need them**

    Observables or likelihood terms without a closed form (e.g. relic density from micrOMEGAs)
    enter through a C++ or pure-Python plugin call, without leaving the YAML description.

-   :material-chart-scatter-plot: **Reproducible artefacts**

    Every run writes `points.csv`, `best_fit.json`, `summary.json` and `metadata.json` with the
    seed, the fully resolved configuration and the framework version.

</div>

## Where to start

| If you want to… | Go to |
|---|---|
| install the package and run a first scan | [Getting started](getting_started.md) |
| write your own model | [Writing a model](authoring_models.md) |
| see complete worked examples with fits and figures | [Tutorials](tutorials/index.md) |
| choose and configure a scanning engine | [adaptive_diver](adaptive_diver.md), [basin_scan](basin_scan.md) |
| turn a scan into credible intervals | [Statistics](statistics.md), [Posterior sampling](posterior_mcmc.md) |

## Requirements

Prebuilt wheels on [PyPI](https://pypi.org/project/bsm-scanner/) cover macOS arm64 and
Linux x86_64 (manylinux 2.28) for Python 3.10–3.13; nothing else needs to be installed. On other
platforms `pip` builds from source, which needs CMake, a C++17 compiler and Eigen3 — see the
[README](https://github.com/mbelfkir/bsmscanner#prerequisites).

## Author and contact

BSMScanner is developed by **Mohamed Belfkir** (University of Doha for Science and Technology, Doha,
Qatar). Questions, bug reports and suggestions are welcome — by email at
[mohamed.belfkir@udst.edu.qa](mailto:mohamed.belfkir@udst.edu.qa) or through the
[issue tracker](https://github.com/mbelfkir/bsmscanner/issues).
