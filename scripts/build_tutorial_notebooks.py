#!/usr/bin/env python3
"""Build and execute the tutorial notebooks for the corrected models.

One shared template plus a per-model spec (SPECS below) generates
`notebooks/<model>.ipynb`. Everything numeric in a notebook is read live from
the model YAML (`models/<name>/`) or from the reference best-fit runs stored in
`models/<name>/results/`; only physics context and caveats are static text.

Requires `nbformat`, `nbclient` and `ipykernel` (not dependencies of the
package). Usage, from the repository root:

    python scripts/build_tutorial_notebooks.py                 # all models, executed
    python scripts/build_tutorial_notebooks.py minimal_bl      # one model
    python scripts/build_tutorial_notebooks.py --no-execute    # write unexecuted
"""

from __future__ import annotations

import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"
SKIP_TAG = "skip-execution"


def sub(text: str, **values: str) -> str:
    for key, value in values.items():
        text = text.replace(f"@@{key}@@", value)
    return text


SETUP = '''import json
import pathlib
import sys

REPO_ROOT = pathlib.Path("..").resolve()
sys.path.insert(0, str(REPO_ROOT / "python"))

import bsm_scanner
import pandas as pd
from bsm_scanner import compile_model, load_model, run_scan
from IPython.display import Image, Markdown, display

MODEL_DIR = REPO_ROOT / "models" / "@@NAME@@"

print("bsm_scanner", bsm_scanner.__version__)
print("repo root  :", REPO_ROOT.name)
print("model dir  :", MODEL_DIR.relative_to(REPO_ROOT))'''

LOAD = '''model = load_model(MODEL_DIR / "@@ENTRY@@")
print("model          :", model.metadata.name)
print("scanned params :", len(model.parameters))
print("theory checks  :", len(model.theory_checks))
print("likelihood terms:", len(model.likelihoods))

pd.DataFrame(
    [{"name": p.name, "prior": p.prior.value, "lower": p.lower, "upper": p.upper, "default": p.default}
     for p in model.parameters]
)'''

CONSTRAINTS = '''def describe(term):
    kind = term.kind.value
    obs = term.observable or ", ".join(term.observables)
    if kind in ("gaussian", "asymmetric_gaussian"):
        spec = f"mean {term.mean}, sigma {term.sigma if term.sigma is not None else (term.sigma_down, term.sigma_up)}"
    elif kind == "multivariate_gaussian":
        spec = f"means {term.means}"
    elif kind == "table_lookup":
        spec = f"tabulated Delta chi2 ({len(term.table)} points)"
    elif kind in ("hard_cut", "upper_limit", "lower_limit"):
        spec = f"lower {term.lower}, upper {term.upper}"
    else:
        spec = ""
    return {"term": term.name, "kind": kind, "observable": obs, "constraint": spec}


display(pd.DataFrame([describe(t) for t in model.likelihoods]))
print("\\nFatal theory checks:", [c.name for c in model.theory_checks if c.fatal])'''

PARAMS_YAML = '''lines = (MODEL_DIR / "parameters.yaml").read_text().splitlines()
print("\\n".join(lines[:@@NLINES@@]))
if len(lines) > @@NLINES@@:
    print(f"... ({len(lines) - @@NLINES@@} more lines)")'''

CHANGES = '''display(Markdown((MODEL_DIR / "CHANGES.md").read_text()))'''

LIVE = '''# A small, fast, live demo with a throwaway seed. It is NOT the reference fit below.
model.scan.engine = "serial_random"
model.scan.seed = 1
model.scan.settings["max_evaluations"] = @@NQUICK@@
model.statistics.enabled = False   # the model's DE-weighted statistics need its own engine

compiled = compile_model(model)
demo = run_scan(model, compiled, run_directory="runs/@@NAME@@_demo")

n_eval = demo.summary["evaluations"]
n_valid = demo.summary["valid_points"]
print("evaluations  :", n_eval)
print("valid points :", n_valid, "(%.2f%% of this quick run)" % (100.0 * n_valid / n_eval))
print("best objective in this quick run:", demo.summary["best_metric_value"])

points = pd.read_csv(demo.points_path)
points.head()'''

RUNS = '''rows = []
for run in sorted(r for r in (MODEL_DIR / "results").iterdir() if r.is_dir()):
    best = json.loads((run / "best_fit.json").read_text())
    summary = json.loads((run / "summary.json").read_text())
    summary = summary.get("summary", summary)
    meta = json.loads((run / "metadata.json").read_text())
    rows.append({
        "run": run.name,
        "engine": meta.get("engine"),
        "seed": meta.get("seed"),
        "best_objective": best["best_metric_value"],
        "evaluations": summary.get("evaluations"),
        "valid": summary.get("valid_points"),
        "stop": summary.get("engine_details", {}).get("stop_reason"),
    })
runs = pd.DataFrame(rows).sort_values("best_objective").reset_index(drop=True)
runs'''

BESTFIT = '''reference = MODEL_DIR / "results" / runs.loc[0, "run"]
best = json.loads((reference / "best_fit.json").read_text())
print("reference run :", reference.name)
print("best objective:", best["best_metric_value"])

display(pd.DataFrame({"best_fit": best["parameters"]}).rename_axis("parameter"))'''

OBSERVABLES = '''shown = [name for name in @@OBS@@ if name in best["outputs"]]
display(pd.DataFrame({"best_fit": {name: best["outputs"][name] for name in shown}}).rename_axis("observable"))'''

TERMS = '''import numpy as np


def best_value(term):
    names = [term.observable] if term.observable else term.observables
    return [best["outputs"].get(n, "not saved") for n in names]

rows = []
for term in model.likelihoods:
    row = {"term": term.name, "kind": term.kind.value,
           "observable": term.observable or ", ".join(term.observables),
           "best_fit": best_value(term), "term_value": best["likelihood_terms"].get(term.name)}
    if term.kind.value == "table_lookup":
        table = np.asarray(term.table)
        row["measured"] = float(table[np.argmin(table[:, 1]), 0])   # minimum of the tabulated Delta chi2
    elif term.mean is not None:
        row["measured"] = term.mean
    elif term.means:
        row["measured"] = list(term.means)
    rows.append(row)
pd.DataFrame(rows)'''

FIGURE = '''display(Image(filename="figures/@@FILE@@"))'''

REPRO = '''# NOT executed in this notebook: the model's own configured best-fit search
# (engine, budget and seed come from models/@@NAME@@/scan.yaml).
m = load_model(MODEL_DIR / "@@ENTRY@@")
result = run_scan(m, compile_model(m), run_directory="runs/@@NAME@@_best_fit")
print(result.summary)'''


def spec(**kw: object) -> dict:
    return kw


SPECS: dict[str, dict] = {
    "scotogenic_ma": spec(
        number=1,
        title="Scotogenic Ma: radiative neutrino mass with dark matter",
        cite="E. Ma, *Phys. Rev. D* **73**, 077301 (2006), hep-ph/0601225. Loop normalisation as in "
        "Merle and Platscher, arXiv:1507.06314.",
        entry="model_no.yaml",
        nquick=4000,
        nlines=40,
        context=(
            "The scotogenic model generates neutrino masses **radiatively**, at one loop, instead of at tree level. "
            "An inert scalar doublet and three right-handed neutrinos are added, all odd under an exactly conserved "
            "$Z_2$ symmetry. That symmetry forbids a tree-level neutrino mass, forces the mass to appear first at one "
            "loop through the new Yukawa couplings and scalar quartics, and simultaneously stabilizes the lightest "
            "$Z_2$-odd state as a dark matter candidate -- neutrino mass and dark matter share a common origin."
        ),
        corrected=(
            "This is the **corrected** implementation: the loop kernel carries the $1/(32\\pi^2)$ normalisation, the "
            "complex-symmetric Majorana matrix is diagonalized by a Takagi factorization (so $\\delta_{CP}$ and the "
            "Majorana phases are meaningful), $\\delta_{CP}$ is scored against the NuFIT table on its own "
            "$[-180^\\circ,180^\\circ]$ domain, and the fit includes $\\mu\\to e\\gamma$, $\\tau\\to e\\gamma$, "
            "$\\tau\\to\\mu\\gamma$, the oblique $T$ parameter and LEP constraints."
        ),
        observables=["s12", "s13", "s23", "deltaCP_deg_m180_180", "dm21_scaled", "dm3l_scaled", "sum_m_scaled", "mbetabeta_scaled",
                     "br_mu_e_gamma", "br_tau_e_gamma", "br_tau_mu_gamma", "oblique_T",
                     "m_eta_charged", "m_eta_R", "m_eta_I", "yukawa_norm_sq"],
        result_text=(
            "The six short runs (15k-130k evaluations) end at very different objective values -- a single short run "
            "is not a robust result for a 26-dimensional landscape with a thin viable sheet. Only the long runs "
            "(0.6M and 1.0M evaluations, `g4000_*`) reach $\\Delta\\chi^2\\approx1$ or below (1.09 and 0.64). The best fit has "
            "$\\theta_{12}$, $\\theta_{13}$ and $\\Delta m^2_{3\\ell}$ on the NuFIT values, $\\theta_{23}$ in the upper "
            "octant (the largest remaining term), and degenerate neutral inert scalars ($\\lambda_5\\to 0$)."
        ),
        figures=[
            ("scotogenic_ma_nufit_s12_s13.png", "Reference-run points in the $(\\sin^2\\theta_{12},\\sin^2\\theta_{13})$ plane against the NuFIT region."),
            ("scotogenic_ma_nufit_s23_dcp.png", "The $(\\sin^2\\theta_{23},\\delta_{CP})$ plane."),
            ("scotogenic_ma_nufit_dm21_dm31.png", "The mass-squared splittings."),
            ("scotogenic_ma_oblique_T.png", "The oblique $T$ parameter of the sampled points."),
        ],
        caveats=(
            "- **Mass scale.** The core anchors the overall neutrino mass scale to the NuFIT best fit, so `dm21_scaled`, "
            "`dm3l_scaled`, `sum_m_scaled` and `mbetabeta_scaled` are anchored values; the fit constrains the mixing and the ratio "
            "$\\Delta m^2_{21}/\\Delta m^2_{3\\ell}$, not the absolute scale (see the *Mass-scale convention* in the "
            "changes above).\n"
            "- **Objective units.** Every term is a $\\Delta\\chi^2$; Gaussian `sigma` values in the YAML are "
            "$\\sigma/\\sqrt2$ because BSMScanner's `gaussian` returns $z^2/2$.\n"
            "- **Not included.** Relic density and direct detection (they need a dark-matter backend), the inert-doublet "
            "$S$ parameter, $\\mu\\to 3e$ and $\\mu$-$e$ conversion. NuFIT tables are normal-ordering only.\n"
            "- LFV and LEP bounds are hard cuts, so they are walls in the objective."
        ),
    ),
    "minimal_bl": spec(
        number=2,
        title="Minimal B-L: a gauged U(1) with a seesaw and a Z'",
        cite="L. Basso, S. Moretti, G. M. Pruna, arXiv:1106.4462.",
        entry="model.yaml",
        nquick=4000,
        nlines=60,
        context=(
            "The minimal gauged $B-L$ model extends the Standard Model gauge group by $U(1)_{B-L}$, broken "
            "spontaneously by a new singlet scalar. That scalar's vacuum expectation value also generates Majorana "
            "masses for three right-handed neutrinos via the type-I seesaw, so gauge symmetry breaking and neutrino "
            "mass share a single new scale $v_{BL}$. The new $Z'$ and the extra scalar mix with their Standard Model "
            "counterparts, subjecting the model to LEP contact-interaction bounds, a $Z'$ narrow-width requirement, "
            "and Higgs signal-strength measurements."
        ),
        corrected=(
            "This is the **corrected** implementation: the full $Z'$ width including the Majorana neutrinos and "
            "thresholds, the Higgs signal strength including $h\\to NN$ and $h\\to Z'Z'$, and an LHC dilepton limit. "
            "The ATLAS dilepton limit needs HEPData tables that are not shipped, so `model.yaml` runs without it; "
            "`model_with_lhc_dilepton.yaml` adds it once the tables are in `models/minimal_bl/data/`."
        ),
        observables=["MZprime", "ZprimeWidthOverMass", "BRZprimeToEE", "BRZprimeToNN", "contact_scale",
                     "HeavyScalarMass", "HeavyNeutrino1Mass", "HeavyNeutrino2Mass", "HeavyNeutrino3Mass",
                     "HiggsSignalStrength", "HiggsExoticBR", "sin_alpha"],
        result_text=(
            "The best fit sits on the **edge** of the allowed ranges: $v_{BL}$ and $m_{H_2}$ at their upper bounds "
            "and $\\sin\\alpha\\approx0$, i.e. the decoupling limit, where the model is indistinguishable from the "
            "Standard Model Higgs. The only non-zero term is the Higgs signal strength. The minimum is therefore a "
            "flat region rather than a point: this model maps an allowed region, as the changes note."
        ),
        figures=[
            ("minimal_bl_allowed_MZp_gBL.png", "Allowed region in $(M_{Z'},g_{BL})$."),
            ("minimal_bl_allowed_mH2_sinalpha.png", "Allowed region in $(m_{H_2},\\sin\\alpha)$."),
            ("minimal_bl_zp_width_vs_g.png", "The $Z'$ width against $g_{BL}$."),
        ],
        caveats=(
            "- The LHC dilepton limit is **not applied** in the default model (tables not shipped).\n"
            "- The LHC Run-2 Higgs signal strength is an input, not a global fit.\n"
            "- See `models/minimal_bl/CHANGES.md` for the width and mixing conventions."
        ),
    ),
    "two_higgs_doublet": spec(
        number=3,
        title="Two-Higgs-Doublet Model: custodial and alignment limits",
        cite="G. C. Branco et al., *Phys. Rept.* **516** (2012), arXiv:1106.0034.",
        entry="model.yaml",
        nquick=200000,
        nlines=60,
        context=(
            "The CP-conserving, softly broken $Z_2$-symmetric two-Higgs-doublet model adds a second scalar doublet "
            "to the Standard Model, producing two neutral scalars, one pseudoscalar, and a charged scalar pair. Its "
            "low-energy phenomenology is set by the mixing angle $\\beta-\\alpha$ -- whether the light Higgs looks "
            "Standard-Model-like, the *alignment limit* -- and by mass splittings among the new states, which the "
            "electroweak oblique parameter $T$ constrains strongly, favoring the *custodial-symmetry limit*."
        ),
        corrected=(
            "This is the **corrected Type II** model: the quartics are obtained by the full inversion from the physical "
            "masses, $\\tan\\beta$ and the alignment angle; stability and tree-level perturbative unitarity use the "
            "complete conditions; $T$ is the full one-loop expression; the Yukawa sector is Type II; and "
            "$B\\to X_s\\gamma$ gives $m_{H^\\pm}>800$ GeV. The Higgs-coupling constraint is **interim** ($\\kappa_V$ "
            "only)."
        ),
        observables=["HeavyCPEvenMass", "CPoddMass", "ChargedHiggsMass", "tanb", "cos_ba", "KappaV", "KappaU",
                     "KappaD", "ObliqueT", "UnitarityMaxEigenvalue", "lambda1", "lambda2", "lambda3", "lambda4",
                     "lambda5"],
        result_text=(
            "Only about $1.4\\times10^{-4}$ of random points are valid (the live demo above needs 200 000 draws to find "
            "a few dozen), which is why the model is scanned with `basin_scan`. The best fit is the custodial, aligned "
            "point: $m_H\\simeq m_A\\simeq m_{H^\\pm}\\simeq 860$ GeV, $\\cos(\\beta-\\alpha)=0$, all $\\kappa=1$. "
            "The only non-zero term is the interim $\\kappa_V$ measurement ($1.035\\pm0.031$): a Type II model has "
            "$\\kappa_V=\\sin(\\beta-\\alpha)\\le1$, so the minimum sits on the alignment boundary $\\kappa_V=1$."
        ),
        figures=[
            ("two_higgs_doublet_mH_vs_mHp.png", "The $(m_H,m_{H^\\pm})$ plane of the valid points."),
            ("two_higgs_doublet_tanb_vs_cosba.png", "The $(\\tan\\beta,\\cos(\\beta-\\alpha))$ plane."),
        ],
        caveats=(
            "- **Interim data.** $\\kappa_V=1.035\\pm0.031$ is taken from the text of ATLAS Nature 607 (2022) 52; the "
            "resolved $\\kappa$ fit with correlations (HEPData) is pending.\n"
            "- **Not included.** $S$ and $U$, direct $H/A/H^\\pm$ searches, $B_s\\to\\mu\\mu$, $B\\to\\tau\\nu$, global "
            "vacuum stability and RGE running.\n"
            "- The soft-mass parameter is replaced by `delta_soft`, which changes the prior (not the best fit)."
        ),
    ),
    "smeft_wilson": spec(
        number=4,
        title="SMEFT Warsaw basis: a smooth fit and an exposed degeneracy",
        cite="B. Grzadkowski, M. Iskrzynski, M. Misiak, J. Rosiek, *JHEP* **10** (2010), arXiv:1008.4884.",
        entry="model.yaml",
        nquick=4000,
        nlines=60,
        context=(
            "The Standard Model Effective Field Theory parameterizes new physics too heavy to produce directly as a "
            "tower of higher-dimensional operators built from Standard Model fields, and the Warsaw basis is the "
            "standard dimension-six operator basis used in LEP/LHC precision fits. This benchmark scans nine Wilson "
            "coefficients touching the Higgs, the electroweak oblique parameters $S$ and $T$, and the gluon/photon "
            "Higgs couplings, at a fixed cutoff scale $\\Lambda=1$ TeV."
        ),
        corrected=(
            "This is the **corrected** implementation: $S$ carries the Han-Skiba normalisation, $\\kappa_g$ and "
            "$\\kappa_\\gamma$ are derived from the effective Lagrangian, $C_H$ is replaced by the Warsaw "
            "$C_{H\\Box}$ with its field normalisation, $\\Lambda$ is no longer a scan parameter (it is an exact flat "
            "direction), and $S$, $T$ use the PDG fit with their correlation."
        ),
        observables=["ObliqueS", "ObliqueT", "KappaV", "KappaG", "KappaGamma", "KappaT", "KappaB", "KappaTau",
                     "SMEFTExpansionParameter"],
        result_text=(
            "The fit is exact ($\\chi^2\\approx0$): $S$ and $T$ sit on the PDG values and $\\kappa_V$ on the interim "
            "measurement. But with only $\\kappa_V$ and $S,T$ as data, several coefficients ($C_{HG}$, $C_{HW}$, "
            "$C_{HB}$, $C_{fH}$) are bounded only by the linear-EFT guard -- a large exposed degeneracy rather than a "
            "determination."
        ),
        figures=[
            ("smeft_wilson_C_HWB_vs_C_HD.png", "The $(C_{HWB},C_{HD})$ plane of the valid points."),
            ("smeft_wilson_C_Hbox_vs_C_HD.png", "The $(C_{H\\Box},C_{HD})$ plane."),
        ],
        caveats=(
            "- **Interim data.** Only $\\kappa_V$ is used for Higgs data; the resolved $\\kappa$ fit is pending.\n"
            "- **Approximations.** Tree level, linear in $C/\\Lambda^2$, no RG running; $\\kappa_W=\\kappa_Z=\\kappa_V$; "
            "$\\kappa_g$ from the top loop only; $h\\to\\gamma\\gamma$ from $W$ and top loops only.\n"
            "- The linear-EFT guard $|\\delta\\kappa|<0.5$ is a validity condition, not a measurement."
        ),
    ),
    "zprime_simplified": spec(
        number=5,
        title="Z' simplified dark matter: an exclusion study",
        cite="ATLAS/CMS Dark Matter Forum, arXiv:1507.00966.",
        entry="model.yaml",
        nquick=4000,
        nlines=60,
        context=(
            "Simplified $Z'$-mediator models couple a new massive vector boson to quarks and a dark-matter fermion. "
            "They are the standard benchmark the LHC Dark Matter Forum uses for translating collider searches into "
            "$(M_{Z'},m_\\chi)$ exclusion limits, and are deliberately built so there is nothing to *fit* -- only a "
            "region to map."
        ),
        corrected=(
            "This is the **corrected** implementation: the mediator is leptophobic as in the Forum benchmark, the "
            "width includes all quark thresholds (Forum Eq. 2.3), and the old dimensionless proxy cuts are replaced by "
            "the spin-independent DM-nucleon cross section against the LZ limit. The LZ table is not shipped, so "
            "`model.yaml` runs without it; `model_with_direct_detection.yaml` adds it once it is in "
            "`models/zprime_simplified/data/`."
        ),
        observables=["MediatorMass", "DarkMatterMass", "gq", "gchi", "SigmaSI_cm2", "WidthFraction", "InvisibleBR"],
        result_text=(
            "Without the direct-detection limit the objective is flat zero: every valid point is equally good, so the "
            "'best fit' is an arbitrary one of the equally good valid points. The useful output is the allowed region shown "
            "below. Once the LZ table is supplied the spin-independent cross section becomes the discriminating "
            "constraint."
        ),
        figures=[
            ("zprime_simplified_allowed_mzp_mchi.png", "Allowed region in $(M_{Z'},m_\\chi)$."),
            ("zprime_simplified_sigmaSI_vs_mchi.png", "The spin-independent cross section against $m_\\chi$."),
            ("zprime_simplified_gq_vs_gchi.png", "The $(g_q,g_\\chi)$ plane."),
        ],
        caveats=(
            "- The **LZ direct-detection limit is not applied** in the default model (table not shipped), so the "
            "plotted region is not yet an exclusion.\n"
            "- Leptophobic benchmark only; no collider-search recasting is included.\n"
            "- The reference run used the variant without the direct-detection term."
        ),
    ),
    "leptoquark_brw": spec(
        number=6,
        title="S1 leptoquark: R(D(*)), B -> K nu nu and the B_c lifetime",
        cite="I. Dorsner et al., *Phys. Rept.* **641** (2016), arXiv:1603.04993; A. Angelescu et al., arXiv:1808.08179.",
        entry="model.yaml",
        nquick=4000,
        nlines=60,
        context=(
            "Scalar leptoquarks carry both baryon and lepton number and couple a quark to a lepton, making them a "
            "natural target for explaining flavor anomalies such as the $R(D^{(*)})$ excess in $b\\to c\\tau\\nu$ "
            "transitions, which needs an enhanced third-generation coupling while respecting bounds from "
            "$B\\to K\\nu\\bar\\nu$ and the $B_c$ lifetime."
        ),
        corrected=(
            "This model **replaces** the original BRW proxy benchmark, which specified no leptoquark representation "
            "and had no computable flavour observable. It is the $S_1\\sim(\\bar3,1,1/3)$ leptoquark with real "
            "couplings to the third lepton generation, and computes $R(D)$, $R(D^*)$, $B^+\\to K^+\\nu\\bar\\nu$, "
            "the $B_c$ lifetime bound and the $S_1$ widths. The LHC pair-production limits need HEPData tables that "
            "are not shipped, so `model.yaml` runs without them; `model_with_lhc_pair.yaml` adds them."
        ),
        observables=["LeptoquarkMass", "RD", "RDst", "BR_BKnunu", "R_nunu_obs", "gP_mb_obs", "WidthFraction",
                     "BR_ttau_obs", "BR_bnu_obs", "BR_ctau_obs", "BR_snu_obs"],
        result_text=(
            "The fit is exact: $R(D)$ and $R(D^*)$ sit on the HFLAV averages and $B^+\\to K^+\\nu\\bar\\nu$ is within "
            "its Belle II interval. The best point has $M_{S_1}\\approx 830$ GeV and a large third-generation coupling "
            "$|y_L^{33}|\\approx1.3$, with branching ratios split between $t\\tau$ and $b\\nu$. Because the "
            "pair-production limits are not applied, it must be treated as a candidate pending those limits."
        ),
        figures=[
            ("leptoquark_brw_rd_rdst.png", "The $(R(D),R(D^*))$ plane against the HFLAV average."),
            ("leptoquark_brw_bknunu_vs_mass.png", "$B^+\\to K^+\\nu\\bar\\nu$ against $M_{S_1}$."),
            ("leptoquark_brw_coupling_plane.png", "The coupling plane."),
        ],
        caveats=(
            "- **Pending data.** The LHC pair-production limits ($t\\tau$, $b\\nu$, $c\\tau$, $s\\nu$) are not applied.\n"
            "- **Approximations.** Real couplings only (no CP phases); the running matrix from 1 TeV is applied at "
            "$M_{S_1}$; CKM $\\approx1$ in decays; only same-channel pair limits.\n"
            "- $R(D^{(*)})$ uses the HFLAV 2024 average with SM uncertainties added in quadrature."
        ),
    ),
}


def build(name: str) -> nbformat.NotebookNode:
    s = SPECS[name]
    v = dict(NAME=name, ENTRY=s["entry"], NQUICK=str(s["nquick"]), NLINES=str(s["nlines"]),
             OBS=repr(s["observables"]))
    cells = [
        new_markdown_cell(f"# Model {s['number']} -- {s['title']}\n\n{s['cite']}"),
        new_markdown_cell(s["context"]),
        new_markdown_cell(
            "**What this notebook does.** BSMScanner separates *what a model is* (a declarative YAML specification: "
            "parameters, priors, derived quantities, observables, validity conditions, likelihoods) from *how it is "
            "scanned* (one of several interchangeable engines). This notebook loads the model below, lists everything "
            "that was corrected relative to the original benchmark, runs a small scan live, and then loads the "
            "**reference best-fit runs** stored with the model (`models/" + name + "/results/`) and shows what they "
            "found. The live demo uses a small budget and an illustrative seed; it is not the reference fit."
        ),
        new_markdown_cell(s["corrected"]),
        new_markdown_cell("## 1. Load the framework and the model"),
        new_code_cell(sub(SETUP, **v)),
        new_markdown_cell(f"## 2. The model specification\n\nEverything below comes from the YAML under "
                          f"`models/{name}/`; nothing is hand-written Python."),
        new_code_cell(sub(LOAD, **v)),
        new_markdown_cell("Constraints declared on the model:"),
        new_code_cell(CONSTRAINTS),
        new_markdown_cell("The parameter block exactly as written in the YAML:"),
        new_code_cell(sub(PARAMS_YAML, **v)),
        new_markdown_cell("## 3. What was corrected\n\nThe model's own change log, relative to the original "
                          "benchmark. Every fix lists its source and how it was verified."),
        new_code_cell(CHANGES),
        new_markdown_cell("## 4. A quick, live scan\n\nThis runs `serial_random` for " + f"`{s['nquick']}`" +
                          " evaluations at a throwaway seed, right here, so you can see the mechanics end to end. "
                          "It is deliberately small."),
        new_code_cell(sub(LIVE, **v)),
        new_markdown_cell("## 5. Reference best-fit scans\n\nThe runs below were produced with the model's "
                          "`run_best_fit.py` and are stored under `results/` (best point, run summary and scan "
                          "metadata). The table is read from those files."),
        new_code_cell(RUNS),
        new_markdown_cell("### The best fit\n\nParameters of the best run above:"),
        new_code_cell(BESTFIT),
        new_markdown_cell("Key observables at the best fit:"),
        new_code_cell(sub(OBSERVABLES, **v)),
        new_markdown_cell("Every constraint at the best fit. `measured` is the central value in the YAML, or the "
                          "minimum of the tabulated $\\Delta\\chi^2$ for table-lookup terms; `term_value` is the term's "
                          "contribution to the objective."),
        new_code_cell(TERMS),
        new_markdown_cell(s["result_text"]),
        new_markdown_cell("## 6. Figures from the reference run"),
    ]
    for filename, caption in s["figures"]:
        cells.append(new_code_cell(sub(FIGURE, FILE=filename)))
        cells.append(new_markdown_cell(caption))
    cells += [
        new_markdown_cell("## 7. Caveats\n\n" + s["caveats"]),
        new_markdown_cell("## 8. Reproducing the reference fit\n\nThe cell below is the pattern the reference runs "
                          "use, shown but not executed (a full search takes anywhere from seconds to well over half an hour depending on the model; compare the evaluation counts in the table above). From a shell:\n\n"
                          "```bash\npython models/" + name + "/run_best_fit.py --seeds <seed>\n```"),
    ]
    repro = new_code_cell(sub(REPRO, **v))
    repro.metadata["tags"] = [SKIP_TAG]
    cells.append(repro)
    cells.append(new_markdown_cell(
        "---\nBSMScanner: a declarative parameter-scanning framework for BSM physics. The original (uncorrected) "
        "benchmark models of the companion methodology study are kept in `benchmarks/manuscript_models/`."))
    nb = new_notebook(cells=cells)
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
        "title": f"Model {s['number']} -- {s['title']}",
    }
    return nb


def execute(nb: nbformat.NotebookNode) -> nbformat.NotebookNode:
    skipped = {}
    for index, cell in enumerate(nb.cells):
        if cell.cell_type == "code" and SKIP_TAG in cell.metadata.get("tags", []):
            skipped[index] = cell.source
            cell.source = "pass"
    NotebookClient(nb, timeout=900, kernel_name="python3",
                   resources={"metadata": {"path": str(NB_DIR)}}).execute()
    for index, source in skipped.items():
        nb.cells[index].source = source
        nb.cells[index].outputs = []
        nb.cells[index].execution_count = None
    return nb


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="*", default=list(SPECS), help="model names (default: all)")
    parser.add_argument("--no-execute", action="store_true", help="write the notebooks without running them")
    args = parser.parse_args()
    for name in args.models:
        if name not in SPECS:
            raise SystemExit(f"unknown model {name!r}; choose from {', '.join(SPECS)}")
        nb = build(name)
        if not args.no_execute:
            nb = execute(nb)
        nbformat.write(nb, NB_DIR / f"{name}.ipynb")
        print("wrote", (NB_DIR / f"{name}.ipynb").relative_to(ROOT))


if __name__ == "__main__":
    main()
