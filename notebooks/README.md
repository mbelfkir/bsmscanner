# BSMScanner tutorial notebooks

Eight Jupyter notebooks, one per benchmark model from the companion paper's methodology
study (models 1-7) plus the T4-3-i-B1 worked example added afterwards (model 8):

| File | Model |
|---|---|
| `scotogenic_ma.ipynb` | Scotogenic Ma: radiative neutrino mass + dark matter |
| `minimal_bl.ipynb` | Minimal gauged B-L with a seesaw and a Z' |
| `two_higgs_doublet.ipynb` | CP-conserving two-Higgs-doublet model |
| `smeft_wilson.ipynb` | SMEFT, Warsaw basis, 10 Wilson coefficients |
| `zprime_simplified.ipynb` | Z' simplified dark matter (DM Forum benchmark) |
| `leptoquark_brw.ipynb` | Buchmuller-Ruckl-Wyler scalar leptoquark |
| `alp_effective.ipynb` | Axion-like-particle effective couplings |
| `t43i_b1.ipynb` | T4-3-i-B1: one-loop neutrino mass + dark matter (arXiv:2608.12646) |

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

## A note on notebook 8 (T4-3-i-B1)

This model's viable region is only ~0.1-0.2% of its 26-dimensional prior box, so all four
cold-start engines struggle badly (documented honestly in section 4 of that notebook). The
quoted best fit (nLL = 0.1052) was found by a hand-run, seeded local refinement -- explicitly
*not* a fifth engine -- and section 5 explains in detail why it should not be read as
comparable to the four engines in section 4, including a direct comparison to `basin_scan`'s
actual algorithm (which this procedure superficially resembles but mechanistically is not).
