"""Tests for Python-implemented plugins: direct registration via
`bsm_scanner.register_plugin_function`, and the YAML-declared loading
mechanism (`python_plugins:`) that lets a model.yaml pull in a Python plugin
module the same way a compiled C++ plugin is already linked in -- no CLI
flag, no separate driver script.
"""

from __future__ import annotations

import sys
from pathlib import Path

import bsm_scanner
import pytest
from bsm_scanner import compile_model, load_model
from bsm_scanner.exceptions import ModelValidationError

FIXTURES = Path(__file__).parent / "fixtures" / "python_plugins"


def test_register_plugin_function_roundtrips_through_plugin_call():
    def add_one(args, options):
        return args["x"] + 1.0

    bsm_scanner.register_plugin_function("test_add_one_plugin", "value", add_one)

    from bsm_scanner import _core

    assert _core.has_plugin_support("test_add_one_plugin")

    model_yaml = """
metadata:
  name: direct_registration_test
parameters:
- name: x
  value_type: real
  scan: false
  default: 5.0
observables:
- name: y
  value_type: real
  plugin_call:
    plugin: test_add_one_plugin
    function: value
    bindings: {x: x}
outputs:
  save: [y]
scan:
  engine: serial_random
  seed: 1
  settings: {objective: nll, max_evaluations: 1, invalid_penalty: 1.0e12}
"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        model_path = Path(tmp) / "model.yaml"
        model_path.write_text(model_yaml, encoding="utf-8")
        model = load_model(model_path)
        compiled = compile_model(model)
        result = compiled.evaluate({"x": 5.0})
        assert result["outputs"]["y"] == 6.0


def test_register_plugin_function_receives_options():
    captured = {}

    def record_options(args, options):
        captured.update(options)
        return args["x"] * options.get("factor", 1.0)

    bsm_scanner.register_plugin_function("test_options_plugin", "value", record_options)

    model_yaml = """
metadata:
  name: options_test
parameters:
- name: x
  value_type: real
  scan: false
  default: 2.0
observables:
- name: y
  value_type: real
  plugin_call:
    plugin: test_options_plugin
    function: value
    bindings: {x: x}
    options: {factor: 3.0, label: "scaled"}
outputs:
  save: [y]
scan:
  engine: serial_random
  seed: 1
  settings: {objective: nll, max_evaluations: 1, invalid_penalty: 1.0e12}
"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        model_path = Path(tmp) / "model.yaml"
        model_path.write_text(model_yaml, encoding="utf-8")
        model = load_model(model_path)
        compiled = compile_model(model)
        result = compiled.evaluate({"x": 2.0})
        assert result["outputs"]["y"] == 6.0
        assert captured["factor"] == 3.0
        assert captured["label"] == "scaled"


def test_python_plugins_yaml_key_loads_file_path_plugin(tmp_path):
    plugin_path = FIXTURES / "file_path_plugin.py"
    model_path = tmp_path / "model.yaml"
    model_path.write_text(
        f"""
metadata:
  name: file_path_plugin_test
python_plugins:
  - {plugin_path}
parameters:
- name: value
  value_type: real
  scan: false
  default: 10.0
observables:
- name: tripled
  value_type: real
  plugin_call:
    plugin: fixture_file_path_plugin
    function: triple
    bindings: {{value: value}}
outputs:
  save: [tripled]
scan:
  engine: serial_random
  seed: 1
  settings: {{objective: nll, max_evaluations: 1, invalid_penalty: 1.0e12}}
""",
        encoding="utf-8",
    )
    model = load_model(model_path)
    compiled = compile_model(model)
    result = compiled.evaluate({"value": 10.0})
    assert result["outputs"]["tripled"] == 30.0


def test_python_plugins_yaml_key_loads_dotted_module_plugin(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(FIXTURES))
    sys.modules.pop("dotted_module_plugin", None)

    model_path = tmp_path / "model.yaml"
    model_path.write_text(
        """
metadata:
  name: dotted_module_plugin_test
python_plugins:
  - dotted_module_plugin
parameters:
- name: value
  value_type: real
  scan: false
  default: 2.0
observables:
- name: quadrupled
  value_type: real
  plugin_call:
    plugin: fixture_dotted_module_plugin
    function: quadruple
    bindings: {value: value}
outputs:
  save: [quadrupled]
scan:
  engine: serial_random
  seed: 1
  settings: {objective: nll, max_evaluations: 1, invalid_penalty: 1.0e12}
""",
        encoding="utf-8",
    )
    model = load_model(model_path)
    compiled = compile_model(model)
    result = compiled.evaluate({"value": 2.0})
    assert result["outputs"]["quadrupled"] == 8.0


def test_python_plugins_file_not_found_raises_clearly(tmp_path):
    model_path = tmp_path / "model.yaml"
    model_path.write_text(
        """
metadata:
  name: missing_plugin_test
python_plugins:
  - does_not_exist.py
outputs:
  save: []
scan:
  engine: serial_random
  seed: 1
  settings: {objective: nll, max_evaluations: 1, invalid_penalty: 1.0e12}
""",
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError):
        load_model(model_path)


def test_python_plugins_rejects_non_string_entries(tmp_path):
    model_path = tmp_path / "model.yaml"
    model_path.write_text(
        """
metadata:
  name: bad_python_plugins_test
python_plugins:
  - 42
outputs:
  save: []
scan:
  engine: serial_random
  seed: 1
  settings: {objective: nll, max_evaluations: 1, invalid_penalty: 1.0e12}
""",
        encoding="utf-8",
    )
    with pytest.raises(ModelValidationError):
        load_model(model_path)


def test_python_plugins_same_file_declared_twice_loads_once(tmp_path):
    """Two fragments both declaring the same file-path plugin must not
    re-execute it a second time (sys.modules dedup by resolved path)."""
    plugin_path = FIXTURES / "file_path_plugin.py"

    fragment_a = tmp_path / "fragment_a.yaml"
    fragment_a.write_text(f"python_plugins:\n  - {plugin_path}\n", encoding="utf-8")
    fragment_b = tmp_path / "fragment_b.yaml"
    fragment_b.write_text(f"python_plugins:\n  - {plugin_path}\n", encoding="utf-8")

    root = tmp_path / "model.yaml"
    root.write_text(
        """
metadata:
  name: dedup_test
imports:
  - fragment_a.yaml
  - fragment_b.yaml
outputs:
  save: []
scan:
  engine: serial_random
  seed: 1
  settings: {objective: nll, max_evaluations: 1, invalid_penalty: 1.0e12}
""",
        encoding="utf-8",
    )

    load_model(root)

    module_name = next(name for name in sys.modules if name.startswith("bsm_scanner._yaml_python_plugins."))
    assert sys.modules[module_name].LOAD_COUNT == 1
