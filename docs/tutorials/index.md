# Tutorials

Seven complete models, each as a pre-executed notebook. Every notebook

1. loads the model from `models/<name>/` and lists its parameters and constraints,
2. shows the model's `CHANGES.md` — every change relative to the original published benchmark,
   with sources,
3. runs a small scan live,
4. loads the reference best-fit run shipped in `models/<name>/results/` and shows the best fit,
   every likelihood term at the best fit, and the figures made from it,
5. lists caveats and shows how to reproduce the full fit.

Nothing numeric is typed into a notebook: values are read from the model YAML or the stored
results, and the test suite checks that the stored results reproduce under the shipped models.

| # | Tutorial | Physics | What it shows about scanning |
|---|---|---|---|
| 1 | [Scotogenic model](notebooks/scotogenic_ma.ipynb) | radiative neutrino mass, inert doublet, Majorana singlets; NuFIT oscillations, LFV, oblique *T*, LEP | a 26-parameter fit with tabulated likelihoods and a Takagi-diagonalised Majorana matrix |
| 2 | [Minimal B−L](notebooks/minimal_bl.ipynb) | gauged U(1)<sub>B−L</sub>, Z′, Higgs mixing | a degenerate plateau: the scan maps an allowed region rather than a point |
| 3 | [Two-Higgs-doublet model](notebooks/two_higgs_doublet.ipynb) | Type II 2HDM; stability, unitarity, *T*, B → X<sub>s</sub>γ | a valid region at 10⁻⁴ of the prior volume: `basin_scan` where random initialisation fails |
| 4 | [SMEFT (Warsaw basis)](notebooks/smeft_wilson.ipynb) | nine dimension-six coefficients; correlated *S*–*T*, Higgs couplings | a quadratic likelihood whose scanned contours match the analytic profile |
| 5 | [Z′ simplified dark matter](notebooks/zprime_simplified.ipynb) | vector mediator, Dirac DM; width, direct detection | a pure exclusion study: no optimum, coverage is the figure of merit |
| 6 | [S1 leptoquark](notebooks/leptoquark_brw.ipynb) | S1 ~ (3̄, 1, 1/3); R(D<sup>(\*)</sup>), B → Kνν̄, B<sub>c</sub> lifetime | measurement-driven fit with a flat direction along the mass |
| 7 | [ALP effective theory](notebooks/alp_effective.ipynb) | axion-like-particle couplings | a narrow target inside a wide prior |

!!! tip "Run them yourself"
    ```bash
    git clone https://github.com/mbelfkir/bsmscanner
    cd bsmscanner
    pip install -e ".[analysis]" jupyterlab
    cd notebooks && jupyter lab
    ```
    Each tutorial page also has a link to download the notebook.
