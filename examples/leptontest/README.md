# Leptontest Reference Example

This example is the reference layout for the current `BSMScanner`
core/model split.

It demonstrates:

- model-owned parameters, functions, and analytic matrix definitions
- matrix metadata (`type`, `role`, `diagonalize`)
- automatic diagonalization driven by that metadata
- ordering selection through separate normal and inverted manifests
- imported core neutrino observable blocks
- imported model-side likelihood blocks

Files:

- `/Users/mbelfkir/HEP/BSMScanner/examples/leptontest/model.yaml`
  - normal-order wrapper
- `/Users/mbelfkir/HEP/BSMScanner/examples/leptontest/model_inverted.yaml`
  - inverted-order wrapper
- `/Users/mbelfkir/HEP/BSMScanner/examples/leptontest/model_de_scipy.yaml`
  - normal-order wrapper configured for the SciPy DE reference engine
- `/Users/mbelfkir/HEP/BSMScanner/examples/leptontest/model_inverted_de_scipy.yaml`
  - inverted-order wrapper configured for the SciPy DE reference engine
- `/Users/mbelfkir/HEP/BSMScanner/models/leptontest`
  - the actual model implementation

What this example is meant to teach:

- keep generic neutrino-sector observable logic in reusable core YAML
- keep likelihood composition in the model
- declare matrix roles and types explicitly instead of relying on hardcoded
  matrix names in the framework

This is the preferred pattern for future models unless a sector is genuinely
backend-specific or otherwise not yet representable in declarative YAML.

The two `*_de_scipy.yaml` wrappers also enable the additive statistics layer, so
their runs write both the usual scan artifacts and the machine-readable
`statistics/` summaries used for later external plotting.
