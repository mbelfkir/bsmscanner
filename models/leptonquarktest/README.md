# leptonquarktest

`leptonquarktest` is the full lepton+quark reference model for the generic
flavor-sector architecture. Its parameter set and analytic mass matrices follow
the detailed modular-flavor example in the FlavorPy documentation:

```text
https://flavorpy.github.io/FlavorPy/examples/detailedexample_modelfitting.html
```

It demonstrates:

- Majorana-like neutrino matrix declaration through YAML
- charged-lepton matrix declaration through YAML
- up- and down-quark matrix declaration through YAML
- framework-managed diagonalization
- CKM construction from `U_u_L^\dagger U_d_L`, followed by the reusable
  descending-SVD reorder block so CKM observables use `(u,c,t) x (d,s,b)`
- reusable core neutrino observables imported from `core/neutrino`
- reusable CKM and quark mass-ratio observables imported from `core/quark`
- combined lepton and quark likelihood terms

The model-side parameters are:

```text
Retau, Imtau, n_scale, alpha, beta, gamma
```

The active scan parameters are:

```text
Retau, Imtau, alpha, beta, gamma
```

`n_scale` is kept fixed by default.

The model files define parameters, helper functions, derived matrix inputs, mass
matrices, likelihood composition, outputs, and scan settings. They do not define
physical PMNS, neutrino, CKM, Wolfenstein, Jarlskog, or quark-ratio observable
formulas manually.

The lepton and quark likelihood values are illustrative reference inputs from
the FlavorPy example page. They are not production global-fit inputs.

Run a small scan from the repository root:

```bash
python examples/leptonquarktest/run_scan.py \
  --model examples/leptonquarktest/model.yaml \
  --run-dir examples/leptonquarktest/runs/smoke
```

Run the native adaptive Differential Evolution engine:

```bash
python examples/leptonquarktest/run_scan.py \
  --model examples/leptonquarktest/model_adaptive_diver.yaml \
  --run-dir examples/leptonquarktest/runs/adaptive_diver
```

The adaptive run also writes `history.json`, `final_population.csv`,
`elite_points.csv`, and population-summary JSON artifacts.

Expected `points.csv` columns include:

- `valid`
- `output::s12`, `output::s13`, `output::deltaCP`
- `output::Vus`, `output::Vcb`, `output::deltaCKM`
- `output::mu_over_mc`, `output::ms_over_mb`
- `likelihood::lepton_s12_term`
- `likelihood::quark_t12_term`
