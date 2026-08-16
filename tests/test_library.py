"""Regression tests for the shipped ``core:`` YAML library.

These guard the two defects that made the published package unusable for
third-party models:

1. the reusable ``core/`` blocks were not shipped inside the wheel at all, and
2. fragment imports resolved only relative to the importing file, so a model
   living outside the source checkout could never reference them.

Both are covered here, including a model written into a throwaway directory
that reaches the library purely through ``core:`` references.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from bsm_scanner.exceptions import ModelValidationError
from bsm_scanner.library import (
    LIBRARY_ENV_VAR,
    LIBRARY_PREFIX,
    core_library_path,
    describe_core_block,
    is_library_reference,
    list_core_blocks,
    resolve_library_reference,
)
from bsm_scanner.model.loader import ModelFragmentLoader

REPO_ROOT = Path(__file__).resolve().parents[1]

# Blocks that models are documented to rely on. If one of these disappears from
# the shipped library, downstream user models break.
EXPECTED_BLOCKS = [
    "core:constants/physics_constants.yaml",
    "core:neutrino/observables_common.yaml",
    "core:neutrino/observables_normal.yaml",
    "core:neutrino/observables_inverted.yaml",
    "core:neutrino/constants_normal.yaml",
    "core:quark/ckm_observables.yaml",
    "core:quark/quark_mass_ratios.yaml",
]


# --------------------------------------------------------------------------
# library discovery
# --------------------------------------------------------------------------

def test_core_library_path_exists():
    root = core_library_path()
    assert root.is_dir(), f"core library path {root} is not a directory"


def test_list_core_blocks_is_non_empty_and_well_formed():
    blocks = list_core_blocks()
    assert blocks, "the shipped core library is empty"
    for block in blocks:
        assert block.startswith(LIBRARY_PREFIX)
        assert resolve_library_reference(block).is_file()


@pytest.mark.parametrize("block", EXPECTED_BLOCKS)
def test_expected_blocks_are_shipped(block):
    assert block in list_core_blocks()
    assert resolve_library_reference(block).is_file()


def test_oscillation_tables_are_shipped():
    """table_lookup models need the data files, not just the YAML blocks."""
    root = core_library_path()
    tables = sorted(p.name for p in (root / "data" / "nufit" / "Normal").glob("*.csv"))
    assert tables, "no normal-ordering oscillation tables shipped"
    for expected in ("Theta12.csv", "Theta13.csv", "Theta23.csv", "dm21.csv", "dm3l.csv"):
        assert expected in tables


# --------------------------------------------------------------------------
# reference parsing / resolution
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "reference,expected",
    [
        ("core:neutrino/normal.yaml", True),
        ("core:", True),
        ("../../core/neutrino/normal.yaml", False),
        ("parameters.yaml", False),
        ("/absolute/path.yaml", False),
    ],
)
def test_is_library_reference(reference, expected):
    assert is_library_reference(reference) is expected


def test_resolve_rejects_non_library_reference():
    with pytest.raises(ModelValidationError):
        resolve_library_reference("parameters.yaml")


def test_resolve_rejects_empty_reference():
    with pytest.raises(ModelValidationError, match="Empty core library reference"):
        resolve_library_reference("core:")


def test_missing_block_error_lists_available_blocks():
    with pytest.raises(ModelValidationError) as excinfo:
        resolve_library_reference("core:neutrino/does_not_exist.yaml")
    message = str(excinfo.value)
    assert "does not exist" in message
    # the error should be actionable, i.e. tell the user what they *can* use
    assert "core:neutrino/observables_common.yaml" in message


def test_reference_cannot_escape_the_library_directory():
    with pytest.raises(ModelValidationError):
        resolve_library_reference("core:../../../etc/passwd")


def test_describe_core_block_reports_named_entries():
    summary = describe_core_block("core:quark/quark_mass_ratios.yaml")
    assert "observables" in summary
    assert "mu_over_mc" in summary["observables"]


def test_describe_core_block_accepts_bare_reference():
    assert describe_core_block("quark/quark_mass_ratios.yaml") == describe_core_block(
        "core:quark/quark_mass_ratios.yaml"
    )


def test_env_var_overrides_library_location(tmp_path, monkeypatch):
    fake = tmp_path / "mycore"
    (fake / "neutrino").mkdir(parents=True)
    (fake / "neutrino" / "custom.yaml").write_text("constants: []\n", encoding="utf-8")

    monkeypatch.setenv(LIBRARY_ENV_VAR, str(fake))
    core_library_path.cache_clear()
    try:
        assert core_library_path() == fake.resolve()
        assert list_core_blocks() == ["core:neutrino/custom.yaml"]
    finally:
        monkeypatch.delenv(LIBRARY_ENV_VAR, raising=False)
        core_library_path.cache_clear()


def test_env_var_pointing_at_missing_directory_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv(LIBRARY_ENV_VAR, str(tmp_path / "nope"))
    core_library_path.cache_clear()
    try:
        with pytest.raises(ModelValidationError):
            core_library_path()
    finally:
        monkeypatch.delenv(LIBRARY_ENV_VAR, raising=False)
        core_library_path.cache_clear()


# --------------------------------------------------------------------------
# the actual regression: an out-of-tree model using core: imports
# --------------------------------------------------------------------------

def _write_out_of_tree_model(directory: Path) -> Path:
    """A model that lives nowhere near the repository and uses only core:."""
    (directory / "my_parameters.yaml").write_text(
        textwrap.dedent(
            """\
            parameters:
            - name: x
              value_type: real
              scan: true
              lower: -1.0
              upper: 1.0
              default: 0.5
              prior: flat
            """
        ),
        encoding="utf-8",
    )
    model = directory / "model.yaml"
    model.write_text(
        textwrap.dedent(
            """\
            metadata:
              name: out_of_tree_model
              version: 0.1.0

            imports:
              - core:constants/physics_constants.yaml
              - my_parameters.yaml
            """
        ),
        encoding="utf-8",
    )
    return model


def test_model_outside_the_repository_can_import_core_blocks(tmp_path):
    model_path = _write_out_of_tree_model(tmp_path)
    assert REPO_ROOT not in model_path.parents, "fixture must live outside the repo"

    merged = ModelFragmentLoader().load(model_path)

    names = {entry["name"] for entry in merged["constants"]}
    assert "me_over_mtau" in names, "core constants block was not merged in"
    assert {entry["name"] for entry in merged["parameters"]} == {"x"}


def test_core_table_file_reference_resolves(tmp_path):
    """`table_file: core:data/...` must work for models with no local data copy."""
    model = tmp_path / "model.yaml"
    model.write_text(
        textwrap.dedent(
            """\
            metadata: {name: table_ref, version: 0.1.0}
            parameters:
            - {name: Theta12, value_type: real, scan: true, lower: 0.0, upper: 1.0,
               default: 0.31, prior: flat}
            observables:
            - {name: Theta12_obs, value_type: real, expression: Theta12}
            likelihoods:
            - name: theta12_term
              kind: table_lookup
              observable: Theta12_obs
              table_file: core:data/nufit/Normal/Theta12.csv
            """
        ),
        encoding="utf-8",
    )
    merged = ModelFragmentLoader().load(model)
    table = merged["likelihoods"][0]["table"]
    assert len(table) > 1
    assert all(len(row) == 2 for row in table)


def test_relative_imports_still_work(tmp_path):
    """Backward compatibility: existing models use relative paths, not core:."""
    (tmp_path / "frag.yaml").write_text(
        "constants:\n- {name: some_constant, value: 1.5}\n", encoding="utf-8"
    )
    model = tmp_path / "model.yaml"
    model.write_text(
        "metadata: {name: rel, version: 0.1.0}\nimports:\n  - frag.yaml\n",
        encoding="utf-8",
    )
    merged = ModelFragmentLoader().load(model)
    assert merged["constants"][0]["name"] == "some_constant"


def test_core_and_relative_imports_can_be_mixed(tmp_path):
    model_path = _write_out_of_tree_model(tmp_path)
    merged = ModelFragmentLoader().load(model_path)
    assert merged["constants"] and merged["parameters"]


# --------------------------------------------------------------------------
# packaging guard
# --------------------------------------------------------------------------

def test_cmake_installs_the_core_library_into_the_wheel():
    """Guards the packaging fix itself.

    Without this install rule the wheel ships no physics blocks, which is
    exactly the defect this module exists to prevent from recurring.
    """
    cmake = REPO_ROOT / "CMakeLists.txt"
    if not cmake.is_file():  # installed-only environment, nothing to check
        pytest.skip("CMakeLists.txt not present (running against an installed package)")
    text = cmake.read_text(encoding="utf-8")
    assert "bsm_scanner/library/core" in text, (
        "CMakeLists.txt no longer installs core/ into the wheel; "
        "pip-installed users would get no reusable blocks"
    )
