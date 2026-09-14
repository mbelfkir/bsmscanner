# BSMScanner tutorial notebooks

Seven Jupyter notebooks, one per benchmark model from the companion paper's methodology
study (models 1-7):

| File | Model |
|---|---|
| `scotogenic_ma.ipynb` | Scotogenic Ma: radiative neutrino mass + dark matter |
| `minimal_bl.ipynb` | Minimal gauged B-L with a seesaw and a Z' |
| `two_higgs_doublet.ipynb` | CP-conserving two-Higgs-doublet model |
| `smeft_wilson.ipynb` | SMEFT, Warsaw basis, 10 Wilson coefficients |
| `zprime_simplified.ipynb` | Z' simplified dark matter (DM Forum benchmark) |
| `leptoquark_brw.ipynb` | Buchmuller-Ruckl-Wyler scalar leptoquark |
| `alp_effective.ipynb` | Axion-like-particle effective couplings |

Each notebook is pre-executed (the outputs you see were produced by literally running the
code in each cell) and follows the same structure: physics context, the model's YAML
specification loaded and inspected live, a small fast scan run live, the published
matched-budget four-engine comparison and best-fit / allowed-region result loaded and
displayed, the relevant study figure, caveats, and a (not-executed, for time reasons) cell
showing exactly how to reproduce the full matched-budget study yourself.

## Where these go

Drop this whole `notebooks/` directory into the repository root, alongside the existing
`models/` and `python/` directories -- the notebooks reference both via relative paths
(`../models/...`, `../python`) and assume that layout. `figures/` here holds only the
pedagogical PNGs these notebooks display; it is separate from the paper's own `figures/`
directory.

## Running them

```
pip install -e .        # from the repo root, or `pip install bsmscanner` once released
cd notebooks
jupyter lab
```

Requires `pandas` and `matplotlib` in addition to BSMScanner's own dependencies (both are
already optional extras of the package -- see `pyproject.toml`'s `analysis` extra).
