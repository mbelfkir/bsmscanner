# Architecture

## Overview

The framework is split into three layers:

1. Python frontend
   - reads model files,
   - validates schema,
   - expands reusable analytic functions,
   - builds a typed dependency graph,
   - detects cycles,
   - computes the active subgraph from requested outputs and likelihood terms,
   - lowers expressions to a compact execution plan,
   - constructs the C++ backend object.

2. C++ core
   - owns the immutable compiled model plan,
   - performs point evaluation without calling back into Python,
   - caches node values within a point,
   - supports matrices and diagonalization workflows,
   - separates theory checks from observable and likelihood evaluation,
   - returns structured point results,
   - exposes a native scan runner that keeps the scanner callback in compiled code.

3. Optional Fortran layer
   - isolated kernels only,
   - no global framework dependence,
   - intended for numerically sensitive loop functions or external scanner interfaces.

## Core Class Design

### Python

- `ModelDefinition`
  - validated model input.
- `GraphNode`
  - one logical node in the model graph.
- `ModelGraph`
  - node registry, adjacency, topological sorting, active-closure selection.
- `ExpressionCompiler`
  - compiles restricted analytic expressions to a stack program.
- `GraphLowerer`
  - converts graph nodes into a C++-friendly `CompiledModelSpec`.
- `CompiledModel`
  - Python wrapper around the C++ backend.
- `ScanSession`
  - orchestrates plan export, run-directory setup, result loading, and scanner launch hooks.
- `ScanRequest`
  - validated native-runner configuration built from `scan:` metadata.
- `ScanResults`
  - scan output paths plus summary payload.

### C++

- `NodePlan`
  - one lowered node with kind, value type, dependencies, and payload.
- `CompiledModelPlan`
  - immutable collection of lowered nodes plus evaluation order.
- `CompiledModel`
  - the point evaluator.
- `PointResult`
  - outputs, likelihood terms, status flags, failure reason, total likelihood.
- `ConstraintSpec`
  - typed likelihood metadata.
- `DiagonalizationValue`
  - cached SVD/eigensystem payload.
- `ScanConfig`
  - native scan settings, parameter ordering, selected outputs, and reproducibility metadata.
- `ParameterMapper`
  - scanner index to evaluator-input translation and prior contribution handling.
- `CompiledEvaluatorAdapter`
  - native bridge from scanner vector to `CompiledModel::evaluate`.
- `RunController`
  - evaluation counting, interruption, diagnostics, and best-fit tracking.
- `ResultWriter`
  - machine-readable CSV/JSON scan output writer.
- `DiverRunner`
  - compiled target-function wrapper for Diver.

## Node Data Model

Supported logical node kinds:

- `ExternalParameterNode`
- `ConstantNode`
- `FunctionNode`
- `DerivedScalarNode`
- `DerivedComplexNode`
- `DerivedVectorNode`
- `DerivedMatrixNode`
- `DiagonalizationNode`
- `ObservableNode`
- `TheoryCheckNode`
- `ConstraintNode`
- `OutputNode`

The lowering step maps these onto `NodePlan` objects with payloads:

- scalar/complex expression program,
- matrix cell programs,
- diagonalization descriptor,
- projection descriptor,
- likelihood descriptor,
- output alias descriptor,
- literal value descriptor.

## Point-Evaluation Lifecycle

1. Receive external parameter values.
2. Populate parameter nodes.
3. Evaluate active derived nodes in topological order.
4. Evaluate theory checks as soon as their dependencies are available.
5. Abort early on fatal theory-check failure with a deterministic invalid-point reason.
6. Evaluate observables.
7. Evaluate constraints and accumulate per-term `nll`.
8. Materialize requested outputs only.
9. Return `PointResult`.

## Scan Lifecycle

1. Python validates the `scan:` section and builds a deterministic `ScanRequest`.
2. The native layer validates parameter ordering and bounds through `ParameterMapper`.
3. The selected scan engine samples a scanner vector.
4. `CompiledEvaluatorAdapter` maps the vector to named inputs and calls the compiled evaluator.
5. Native invalid-point policy converts non-usable points into a scanner-safe objective value.
6. `RunController` updates counters, tracks the best point, and streams outputs through `ResultWriter`.
7. Final CSV/JSON artifacts are flushed together with a best-fit summary and failure diagnostics.

## Error Handling Strategy

Failure classes are explicit:

- `missing_input`
- `invalid_point`
- `numerical_error`
- `evaluation_error`

Early exits are preferred over silent NaNs. A theory rejection and a numerical failure are distinct outcomes and are reported differently.

## Performance Strategy

- Expressions are lowered once in Python.
- The C++ core executes only compiled node programs.
- Per-point values are cached.
- Only the active subgraph is evaluated.
- Matrix cell programs are precompiled.
- Reusable analytic functions are expanded before entering the C++ hot loop.
- Immutable compiled plans make thread-local evaluation straightforward.
- The plan shape is deterministic, which is useful for MPI runs and scanner reproducibility.

## Build and Packaging Recommendation

- CMake for the compiled core.
- `scikit-build-core` to package the Python interface and native extension together.
- `pybind11` for the Python bridge.
- `Eigen` for matrix algebra.

This keeps the stack lightweight and portable across clusters.
