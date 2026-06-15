# Dependency and Licensing Audit

Date: 2026-06-16

## Status

Publication is blocked.

No repository-level `LICENSE` file is present, and `pyproject.toml` does not declare license metadata. A license must be selected and approved by the repository owner before publishing to TestPyPI or PyPI.

## Python Dependencies

Declared runtime dependencies:

- `numpy>=1.24`
- `PyYAML>=6.0`

Declared optional dependencies:

- `analysis`: `matplotlib>=3.8`, `pandas>=2.0`
- `de`: `scipy>=1.11`
- `posterior`: `emcee>=3.1`
- `dev`: `pytest>=8.0`, `build>=1.2`, `twine>=5.0`, `ruff>=0.5`

External tools not declared as pip dependencies:

- Diver
- micrOMEGAs
- C++ compiler toolchain
- Fortran compiler/runtime where optional Diver builds require it

## Bundled Source

- Python package source under `python/bsm_scanner`
- C++ source and headers under `src` and `include`
- Example Fortran kernel under `fortran/kernels`
- CMake build files under `CMakeLists.txt` and `cmake`

Redistribution status: unresolved until a project license is selected.

## Bundled Data and Documents

Tracked non-code data inspected:

- Neutrino likelihood lookup CSV files under `models/oneloop/data`, `examples/oneloop_full/data`, and `examples/oneloop_minimal/data`
- JSON benchmark diagnostics under `docs/benchmarks`
- Compiled plan JSON files under `examples/leptontest` and `examples/oneloop_full`
- `models/weinberg.zip`
- `HHyybb_Zenodo_Dataset_Variables.docx`
- `docx_quicklook_check/HHyybb_Zenodo_Dataset_Variables.docx.png`

Redistribution status: unresolved. The source/provenance and redistribution rights for these bundled files must be confirmed before public package publication.

## Required Before Publication

- Add an approved repository `LICENSE`.
- Add matching license metadata to `pyproject.toml` and `CITATION.cff`.
- Document provenance and redistribution rights for bundled lookup tables, JSON diagnostics, ZIP archives, and DOCX/PNG artifacts.
- Remove files that are not intended for public redistribution.
