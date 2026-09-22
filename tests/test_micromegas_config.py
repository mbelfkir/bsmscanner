"""Tests for the map-driven micrOMEGAs dark-matter config generator.

``vars1.mdl`` here is copied verbatim from a real compiled CalcHEP model
(1LRNM-1N1P, the model behind the original oneloop_micromegas plugin), used
only to exercise the optional validation path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bsm_scanner.tools.micromegas_config import (
    MicromegasConfigError,
    generate_dm_config,
    load_binding_map,
    parse_vars_mdl,
    render_cmake_cache_script,
    render_constants_yaml,
    render_likelihoods_yaml,
    render_observables_yaml,
    render_theory_checks_yaml,
    validate_bindings_against_vars_mdl,
)

FIXTURE = Path(__file__).parent / "fixtures" / "micromegas" / "vars1.mdl"


def _write_map(tmp_path: Path, content: dict) -> Path:
    path = tmp_path / "map.yaml"
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    return path


def test_load_binding_map_reads_flat_mapping(tmp_path):
    path = _write_map(tmp_path, {"MH01": "MH1", "Y1r1": "g1er"})
    bindings = load_binding_map(path)
    assert bindings == {"MH01": "MH1", "Y1r1": "g1er"}


def test_load_binding_map_rejects_reserved_dm_target_name_key(tmp_path):
    path = _write_map(tmp_path, {"dm_target_name": "~chi"})
    with pytest.raises(MicromegasConfigError, match="dm_target_name"):
        load_binding_map(path)


def test_load_binding_map_rejects_non_string_values(tmp_path):
    path = _write_map(tmp_path, {"MH01": 200.0})
    with pytest.raises(MicromegasConfigError):
        load_binding_map(path)


def test_load_binding_map_rejects_non_mapping_top_level(tmp_path):
    path = tmp_path / "map.yaml"
    path.write_text("- MH01\n- MH2\n", encoding="utf-8")
    with pytest.raises(MicromegasConfigError):
        load_binding_map(path)


def test_parse_vars_mdl_extracts_independent_parameters_only():
    params = parse_vars_mdl(FIXTURE)
    names = {p.name for p in params}
    assert "MH01" in names
    assert "MS" in names  # real hazard: this is the strange-quark mass here
    assert not any(name.startswith("%") for name in names)


def test_validate_bindings_against_vars_mdl_catches_typo():
    params = parse_vars_mdl(FIXTURE)
    with pytest.raises(MicromegasConfigError, match="MH01_TYPO"):
        validate_bindings_against_vars_mdl({"MH01_TYPO": "MH1"}, params)


def test_validate_bindings_against_vars_mdl_accepts_real_names():
    params = parse_vars_mdl(FIXTURE)
    validate_bindings_against_vars_mdl({"MH01": "MH1", "Y1r1": "g1er"}, params)  # no raise


def test_render_observables_yaml_omits_target_match_when_no_target():
    text = render_observables_yaml("micromegas", {"MH01": "MH1"}, dm_target_name=None, dd_pvalue_threshold=0.1)
    assert "DM_target_match" not in text
    assert "dm_target_name" not in text
    assert "MH01: MH1" in text
    assert "&micromegas_bindings" in text
    assert yaml.safe_load(text)  # must still be valid YAML


def test_render_observables_yaml_includes_target_match_when_target_given():
    text = render_observables_yaml("micromegas", {"MH01": "MH1"}, dm_target_name="~chi", dd_pvalue_threshold=0.1)
    assert "DM_target_match" in text
    assert "dm_target_name: dm_target_name" in text
    parsed = yaml.safe_load(text)
    names = {obs["name"] for obs in parsed["observables"]}
    assert "DM_target_match" in names
    assert "DM_candidate_valid" in names


def test_bindings_are_never_rewritten_verbatim_passthrough():
    # The whole point: no auto-matching, no TODO placeholders -- whatever the
    # physicist wrote in the map is exactly what ends up in the YAML.
    text = render_observables_yaml(
        "micromegas", {"MS": "MS", "weird_name": "totally_unrelated_node"}, None, 0.1
    )
    assert "MS: MS" in text
    assert "weird_name: totally_unrelated_node" in text
    assert "TODO" not in text


def test_render_theory_checks_yaml_conditional_on_target():
    without_target = render_theory_checks_yaml(None)
    assert "dm_target_match" not in without_target
    assert "dm_candidate_valid" in without_target
    assert "omega_backend_valid" in without_target

    with_target = render_theory_checks_yaml("~chi")
    assert "dm_target_match" in with_target


def test_render_constants_yaml_embeds_target_name():
    text = render_constants_yaml("~chi")
    parsed = yaml.safe_load(text)
    (entry,) = parsed["constants"]
    assert entry == {"name": "dm_target_name", "value": "~chi", "value_type": "string"}


def test_render_likelihoods_yaml_uses_requested_planck_numbers():
    text = render_likelihoods_yaml(omega_mean=0.12, omega_sigma=0.0012)
    assert "mean: 0.12" in text
    assert "sigma: 0.0012" in text
    assert "DDexp_term" in text


def test_render_cmake_cache_script_sets_expected_cache_vars():
    text = render_cmake_cache_script("/opt/micromegas", "/opt/micromegas/MyModel", "/opt/micromegas/CalcHEP_src")
    assert 'set(BSM_SCANNER_BUILD_MICROMEGAS ON CACHE BOOL "" FORCE)' in text
    assert '"/opt/micromegas"' in text
    assert '"/opt/micromegas/MyModel"' in text
    assert '"/opt/micromegas/CalcHEP_src"' in text


def test_generate_dm_config_without_calchep_paths_skips_cmake_script():
    result = generate_dm_config({"MH01": "MH1"})
    assert result.cmake_cache_script is None
    assert result.constants_yaml is None


def test_generate_dm_config_requires_both_micromegas_and_calchep_paths_together():
    with pytest.raises(MicromegasConfigError):
        generate_dm_config({"MH01": "MH1"}, micromegas_root="/opt/micromegas")


def test_generate_dm_config_with_target_and_calchep_paths_produces_everything():
    result = generate_dm_config(
        {"MH01": "MH1"},
        dm_target_name="~chi",
        micromegas_root="/opt/micromegas",
        calchep_model_root="/opt/micromegas/MyModel",
    )
    assert result.constants_yaml is not None
    assert result.cmake_cache_script is not None
    assert "/opt/micromegas/CalcHEP_src" in result.cmake_cache_script  # derived default


def test_generate_dm_config_runs_validation_when_vars_mdl_given():
    params = parse_vars_mdl(FIXTURE)
    with pytest.raises(MicromegasConfigError):
        generate_dm_config({"NOT_A_REAL_PARAM": "MH1"}, calchep_params_for_validation=params)
