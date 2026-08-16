# Code Audit

Date: 2026-06-16

## Scope

Inspected repository structure and searched Python, C++, headers, YAML, tests, scripts, examples, and docs.

Approximate file counts:

- Files under source/docs/models/examples/tests/scripts/core/cmake/fortran: 2327
- Python package files: 27
- C++ source/header files: 28
- YAML model/core/example files: 214

## Findings

### Retain

- YAML-driven model loading, imports, graph lowering, scan orchestration, and C++ evaluator boundaries are retained.
- Existing model directories and examples are retained.
- `bsm_scanner.api` re-exports are retained for compatibility.

### Replace

- Package version access now prefers installed package metadata with a source-tree fallback.
- CLI access is standardized through `bsm-scanner` and `python -m bsm_scanner`.

### Remove

- Removed small verified unused imports in docs helper, posterior runner, and tests.
- Removed no physics code and no scan-engine behavior.

### Exclude From Distributions

- Source distributions now exclude generated runs, archives, build outputs, caches, binary extensions, and large result directories.
- Wheels contain only the Python package, the compiled extension, and the package-owned lightweight example.

## Static Analysis

Command:

```bash
/tmp/bsmscanner-build-venv/bin/python -m ruff check .
```

Result: passed.

## Remaining Audit Items

- Absolute local paths and server-specific names in docs/scripts were a publication-readiness issue at the time of this audit. They have since been rewritten to repository-relative paths; upstream provenance references were kept but stripped of the personal directory prefix.
- No broad dead-code removal was performed because baseline protection and packaging were higher priority, and static-analysis-only removals would be unsafe for YAML/dynamic references.
