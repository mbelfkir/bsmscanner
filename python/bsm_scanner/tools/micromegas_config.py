"""Generate ``plugin_call`` YAML config + a CMake cache script for the generic
``micromegas`` plugin (``src/plugins/micromegas.cpp``), from a binding map the
physicist writes by hand.

Design choice, and why: an earlier version of this tool tried to auto-match
CalcHEP parameter names against model.yaml node names by exact string
equality. That is fragile in a way that matters here -- checked against a
real compiled model (1LRNM-1N1P), its ``vars1.mdl`` uses ``MS`` for the
strange-quark mass, which collides verbatim with a plausible BSM parameter
name (e.g. a doubly-charged scalar mass also called ``MS``). Auto-matching
would silently bind the wrong physical quantity instead of failing loudly.
The physicist already knows the correspondence between their CalcHEP export
and their model.yaml; this tool now only assembles the YAML/CMake
boilerplate around a map they supply, and does no guessing of its own.

``parse_vars_mdl`` is kept only as an *optional* sanity check: if the
physicist also points this at their model's ``vars1.mdl``, every map key is
checked against the real list of CalcHEP-assignable (independent) parameters,
and a typo fails immediately here rather than at the first scan evaluation.
It is never used to fill in a binding on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_RESERVED_MAP_KEY = "dm_target_name"

_PLUGIN_OUTPUTS: tuple[tuple[str, str, str], ...] = (
    ("Omega", "omega", "real"),
    ("SIxsec", "sigma_si", "real"),
    ("DD_pvalue", "dd_pvalue", "real"),
    ("DMCandidateMass", "candidate_mass", "real"),
    ("darkMatter", "candidate_name", "string"),
    ("DM_candidate_valid", "candidate_valid", "bool"),
)
_TARGET_MATCH_OUTPUT = ("DM_target_match", "target_match", "bool")


class MicromegasConfigError(ValueError):
    """Raised for anything wrong with the user-supplied inputs to this tool."""


@dataclass(frozen=True)
class CalcHepParameter:
    """One independent (assignable) CalcHEP parameter from ``vars1.mdl``."""

    name: str
    default: float
    comment: str


def parse_vars_mdl(path: str | Path) -> list[CalcHepParameter]:
    """Parse a CalcHEP ``vars1.mdl`` independent-parameter table.

    Optional validation input only -- see module docstring. Rows whose Name
    starts with ``%`` are SLHA-passthrough/width slots, not parameters
    micrOMEGAs accepts through ``assignValW``, and are excluded.
    """
    text = Path(path).read_text(encoding="utf-8")

    params: list[CalcHepParameter] = []
    in_table = False
    for line in text.splitlines():
        if not in_table:
            if "Name" in line and "Value" in line and "|" in line:
                in_table = True
            continue
        if "|" not in line:
            continue
        fields = line.split("|")
        if len(fields) < 2:
            continue
        name = fields[0].strip()
        value_field = fields[1].strip()
        comment = fields[2].strip().rstrip("|").strip() if len(fields) > 2 else ""
        if not name or name.startswith("%"):
            continue
        try:
            default = float(value_field)
        except ValueError:
            continue
        params.append(CalcHepParameter(name=name, default=default, comment=comment))
    return params


def load_binding_map(path: str | Path) -> dict[str, str]:
    """Load the physicist-authored CalcHEP-name -> model-node-name map.

    A flat mapping (YAML is a superset of JSON, so a .json file works too):

        MH01: MH1
        Y1r1: g1er
        Y1i1: g1ei

    ``dm_target_name`` is reserved -- it comes from --dm-target-name so there
    is exactly one place that sets it, not two that can silently disagree.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise MicromegasConfigError(f"'{path}' must contain a mapping at the top level.")

    bindings: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise MicromegasConfigError(
                f"'{path}': entry {key!r}: {value!r} must be a string key and a string value "
                "(CalcHEP parameter name -> model node name)."
            )
        if key == _RESERVED_MAP_KEY:
            raise MicromegasConfigError(
                f"'{path}' must not set '{_RESERVED_MAP_KEY}' directly -- pass --dm-target-name instead, "
                "so there is one place that decides it."
            )
        bindings[key] = value
    return bindings


def validate_bindings_against_vars_mdl(bindings: dict[str, str], calchep_params: list[CalcHepParameter]) -> None:
    """Fail loudly here if a map key is not a real, independent CalcHEP parameter."""
    valid_names = {p.name for p in calchep_params}
    unknown = sorted(name for name in bindings if name not in valid_names)
    if unknown:
        raise MicromegasConfigError(
            "The following map.yaml keys are not independent parameters in the given "
            f"vars1.mdl (typo, or a dependent/computed CalcHEP quantity that should not "
            f"be bound at all): {', '.join(unknown)}"
        )


def render_observables_yaml(
    plugin_name: str,
    bindings: dict[str, str],
    dm_target_name: str | None,
    dd_pvalue_threshold: float,
) -> str:
    binding_lines = [f"      {name}: {source}" for name, source in sorted(bindings.items())]
    if dm_target_name is not None:
        binding_lines.append(f"      {_RESERVED_MAP_KEY}: {_RESERVED_MAP_KEY}")
    bindings_block = "\n".join(binding_lines)

    outputs = list(_PLUGIN_OUTPUTS)
    if dm_target_name is not None:
        outputs.append(_TARGET_MATCH_OUTPUT)

    observable_blocks = []
    for index, (observable_name, function_name, value_type) in enumerate(outputs):
        bindings_line = (
            f"    bindings: &micromegas_bindings\n{bindings_block}"
            if index == 0
            else "    bindings: *micromegas_bindings"
        )
        observable_blocks.append(
            f"- name: {observable_name}\n"
            f"  value_type: {value_type}\n"
            f"  plugin_call:\n"
            f"    plugin: {plugin_name}\n"
            f"    function: {function_name}\n"
            f"{bindings_line}"
        )

    observable_blocks.append(
        "- name: DDexp_ok\n  value_type: bool\n  expression: DD_pvalue >= " + str(dd_pvalue_threshold)
    )

    header = (
        "# Generated by `bsm-scanner generate-dm-config`.\n"
        "# Bindings come verbatim from your --map file; nothing here was guessed.\n"
    )
    if dm_target_name is None:
        header += (
            "# --dm-target-name was not given: micrOMEGAs' sortOddParticles chooses the\n"
            "# dark-matter candidate on its own, and there is no target-match check.\n"
        )
    return header + "\nobservables:\n" + "\n".join(observable_blocks) + "\n"


def render_likelihoods_yaml(omega_mean: float, omega_sigma: float) -> str:
    return (
        "# Generated by `bsm-scanner generate-dm-config`.\n"
        "# omega_mean/omega_sigma default to Planck 2018 TT,TE,EE+lowE+lensing\n"
        "# Omega_c h^2 (arXiv:1807.06209 Table 2), assuming this candidate saturates\n"
        "# 100% of the relic abundance -- confirm that assumption for your model.\n\n"
        "likelihoods:\n"
        "- name: Omega_term\n"
        "  kind: gaussian\n"
        "  observable: Omega\n"
        f"  mean: {omega_mean}\n"
        f"  sigma: {omega_sigma}\n"
        "- name: DDexp_term\n"
        "  kind: hard_cut\n"
        "  observable: DDexp_ok\n"
    )


def render_theory_checks_yaml(dm_target_name: str | None) -> str:
    checks = [
        "- name: dm_candidate_valid\n"
        "  condition: DM_candidate_valid\n"
        "  fatal: true\n"
        "  message: micrOMEGAs could not identify a valid odd-particle dark matter candidate.",
    ]
    if dm_target_name is not None:
        checks.append(
            "- name: dm_target_match\n"
            "  condition: DM_target_match\n"
            "  fatal: true\n"
            "  message: The micrOMEGAs-selected dark matter candidate does not match the intended source-level scan target."
        )
    checks.append(
        "- name: omega_backend_valid\n"
        "  condition: Omega >= 0 and Omega <= 10 and isfinite(Omega)\n"
        "  fatal: true\n"
        "  message: The micrOMEGAs relic-density backend returned an invalid Omega value."
    )
    return "# Generated by `bsm-scanner generate-dm-config`.\n\ntheory_checks:\n" + "\n".join(checks) + "\n"


def render_constants_yaml(dm_target_name: str) -> str:
    return (
        "# Generated by `bsm-scanner generate-dm-config`.\n\n"
        "constants:\n"
        "- name: dm_target_name\n"
        f'  value: "{dm_target_name}"\n'
        "  value_type: string\n"
    )


def render_cmake_cache_script(micromegas_root: str, calchep_model_root: str, calchep_src_root: str) -> str:
    return (
        "# Generated by `bsm-scanner generate-dm-config`.\n"
        "# Use as a CMake initial-cache script:\n"
        "#     cmake -S . -B build -C <this file>\n"
        "# Only one micrOMEGAs-backed CalcHEP model can be linked into a given\n"
        "# BSMScanner build at a time -- reconfigure+rebuild to switch models.\n"
        'set(BSM_SCANNER_BUILD_MICROMEGAS ON CACHE BOOL "" FORCE)\n'
        f'set(BSM_SCANNER_MICROMEGAS_ROOT "{micromegas_root}" CACHE PATH "" FORCE)\n'
        f'set(BSM_SCANNER_MICROMEGAS_MODEL_ROOT "{calchep_model_root}" CACHE PATH "" FORCE)\n'
        f'set(BSM_SCANNER_MICROMEGAS_CALCHEP_ROOT "{calchep_src_root}" CACHE PATH "" FORCE)\n'
    )


@dataclass(frozen=True)
class DmConfigResult:
    observables_yaml: str
    likelihoods_yaml: str
    theory_checks_yaml: str
    constants_yaml: str | None
    cmake_cache_script: str | None


def generate_dm_config(
    bindings: dict[str, str],
    dm_target_name: str | None = None,
    plugin_name: str = "micromegas",
    dd_pvalue_threshold: float = 0.1,
    omega_mean: float = 0.12,
    omega_sigma: float = 0.0012,
    calchep_params_for_validation: list[CalcHepParameter] | None = None,
    micromegas_root: str | None = None,
    calchep_model_root: str | None = None,
    calchep_src_root: str | None = None,
) -> DmConfigResult:
    if calchep_params_for_validation is not None:
        validate_bindings_against_vars_mdl(bindings, calchep_params_for_validation)

    if bool(micromegas_root) != bool(calchep_model_root):
        raise MicromegasConfigError(
            "--micromegas-root and --calchep-model-root must be given together (or both omitted)."
        )

    cmake_cache_script = None
    if micromegas_root and calchep_model_root:
        resolved_calchep_src_root = calchep_src_root or str(Path(micromegas_root) / "CalcHEP_src")
        cmake_cache_script = render_cmake_cache_script(micromegas_root, calchep_model_root, resolved_calchep_src_root)

    return DmConfigResult(
        observables_yaml=render_observables_yaml(plugin_name, bindings, dm_target_name, dd_pvalue_threshold),
        likelihoods_yaml=render_likelihoods_yaml(omega_mean, omega_sigma),
        theory_checks_yaml=render_theory_checks_yaml(dm_target_name),
        constants_yaml=render_constants_yaml(dm_target_name) if dm_target_name is not None else None,
        cmake_cache_script=cmake_cache_script,
    )
