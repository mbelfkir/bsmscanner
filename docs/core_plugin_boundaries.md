# Core And Plugin Boundaries

## Refactor Goal

The framework core must stay model-agnostic. A new physics model should normally
require only YAML edits. If an external backend is unavoidable, the imperative
bridge belongs in a plugin layer rather than in the generic evaluator or generic
expression compiler.

## Audit Summary

### Kept In The Generic Core

- typed values and node plans
- dependency graph construction and lowering
- generic scalar and complex math builtins
- matrix construction and diagonalization
- generic likelihood kernels
- table interpolation
- scan execution and Diver integration
- generic plugin dispatch

### Moved Out Of The Generic Core

- oneloop-specific micrOMEGAs builtins
- oneloop-specific backend capability checks
- oneloop-specific backend assignment logic
- oneloop-specific DM observable dispatch

### Kept Model-Specific By Design

- the `oneloop_micromegas` plugin implementation under
  `/Users/mbelfkir/HEP/BSMScanner/src/plugins/oneloop_micromegas.cpp`
- the backend variable mapping declared in
  `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/observables/dm.yaml`

## What Belongs Where

### YAML Model Definitions

Use YAML for:

- parameters
- constants
- reusable analytic functions
- derived quantities
- matrices
- diagonalizations
- observables
- theory checks
- likelihoods
- saved outputs
- plugin call declarations
- runtime scan controls only

### Generic Core

The generic core may know only about:

- node execution
- typed values
- generic math
- generic linear algebra
- generic likelihood evaluation
- generic scan infrastructure
- generic plugin invocation

It must not know oneloop parameter names, oneloop backend variable names, or
oneloop-specific observables.

### Plugin Layer

Use plugins only for external or non-generic backends. A plugin may contain:

- backend API calls
- backend-specific assignment logic
- backend-specific caching
- backend-specific post-processing
- source-specific grouped logic that is still not representable through the
  current generic declarative kernels

It should receive typed named inputs from the framework and return typed outputs
back to the evaluator.

## Generic Plugin Call Contract

Derived nodes, observables, theory checks, and custom likelihoods may use the
same `plugin_call` contract instead of adding backend-specific framework code:

```yaml
observables:
  - name: backend_mass
    value_type: real
    plugin_call:
      plugin: my_backend
      function: mass
      bindings:
        input_mass: Mphi
        tag: backend_label
      options:
        scale: 2.0
      output: mass
```

The binding keys are plugin argument names. The binding values are source node
names already known to the model graph.

The option keys are literal plugin options supplied directly from YAML. The
framework forwards them unchanged as typed scalar values.

For backend-assignment plugins, the binding keys are also the backend variable
names. The plugin should consume those keys directly from YAML rather than
carrying a second hard-coded assignment list in C++.

## Build-Time Plugin Discovery

The root CMake file now discovers plugin source files and plugin-local CMake
fragments generically:

- `src/plugins/*.cpp` are added to the native module automatically
- `cmake/plugins/*.cmake` are included automatically

That means adding a new backend should not require editing the framework
`CMakeLists.txt`. If a plugin needs special link flags or headers, those belong
in its own plugin-local CMake fragment rather than in the core build file.

## Scan Settings

`scan.settings` is now reserved for execution controls that the runner actually
consumes. Unknown keys are rejected during scan-request construction instead of
being silently copied into metadata. Model-specific backend choices should live
in constants, plugin bindings, or model metadata, not in dead runtime knobs.

## Oneloop After The Refactor

The stable oneloop baseline remains plugin-free.

The latest-master exact path now uses:

- generic `plugin_call` nodes in
  `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/observables/dm.yaml`
- a model-specific plugin in
  `/Users/mbelfkir/HEP/BSMScanner/src/plugins/oneloop_micromegas.cpp`
- a source-specific likelihood helper in
  `/Users/mbelfkir/HEP/BSMScanner/src/plugins/oneloop_likelihoods.cpp`
- generic runtime capability checks through
  `has_plugin_support("oneloop_micromegas")`

This keeps the framework core reusable for non-oneloop models.

### Oneloop Plugin Roles

`oneloop_micromegas.cpp` is backend-specific. It owns:

- micrOMEGAs assignment
- DM candidate discovery
- relic density
- SI cross section
- DD p-value

`oneloop_likelihoods.cpp` is not a backend bridge. It exists only to preserve a
source-specific likelihood behavior that is not yet expressible as a single
generic declarative kernel:

- the grouped `m12+m3l` neutrino-mass term with source-style early return when
  `dm21` is already outside the table domain

If a future model needs similar grouped source logic, it should use its own
small plugin helper rather than teaching the generic core about one specific
physics decomposition.
