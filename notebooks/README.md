# BSMScanner tutorial notebooks

Seven Jupyter notebooks, one per tutorial model:

| File | Model | Status |
|---|---|---|
| `scotogenic_ma.ipynb` | Scotogenic Ma: radiative neutrino mass + dark matter | corrected |
| `minimal_bl.ipynb` | Minimal gauged B-L with a seesaw and a Z' | corrected |
| `two_higgs_doublet.ipynb` | CP-conserving Type II two-Higgs-doublet model | corrected (interim Higgs data) |
| `smeft_wilson.ipynb` | SMEFT, Warsaw basis, 9 Wilson coefficients | corrected (interim Higgs data) |
| `zprime_simplified.ipynb` | Z' simplified dark matter (DM Forum benchmark) | corrected |
| `leptoquark_brw.ipynb` | S1 scalar leptoquark and the flavour anomalies | replaces the original BRW proxy |
| `alp_effective.ipynb` | Axion-like-particle effective couplings | original benchmark, not yet reviewed |

The six corrected-model notebooks are **generated** by `scripts/build_tutorial_notebooks.py` and
pre-executed. Each one:

1. loads the model from `models/<name>/` and lists its parameters and constraints,
2. shows the model's `CHANGES.md` (every fix relative to the original benchmark, with sources),
3. runs a small scan live,
4. loads the **reference best-fit runs** stored in `models/<name>/results/` and shows the best fit,
   every constraint at the best fit, and the figures made from the reference run,
5. lists caveats, and shows (without running) how to reproduce the fit.

Nothing numeric is typed into a notebook: it is read from the model YAML or the stored results, and
`tests/test_tutorial_reference_results.py` checks that the stored results reproduce under the shipped
models. `alp_effective.ipynb` is the original manuscript notebook and still shows its published
tables. The original (uncorrected) benchmark models of the companion methodology study, and the
engine comparison built on them, are in `benchmarks/manuscript_models/`.

## Running them

```bash
pip install -e ".[analysis]"      # from the repository root
pip install jupyterlab
cd notebooks
jupyter lab
```

The notebooks assume the repository layout (`../models`, `../python`, `figures/`). Some corrected
models use external HEPData tables that are not shipped; their notebooks run the default
`model.yaml`, which excludes those constraints (see each model's `data/README.md`).

## Regenerating

```bash
pip install nbformat nbclient ipykernel
python scripts/build_tutorial_notebooks.py            # all six, executed
python scripts/build_tutorial_notebooks.py minimal_bl # one model
```
