"""A fatal theory check that is cheap to evaluate must run before an expensive
plugin_call whenever the dependency graph allows it, so a point that fails the
cheap check never pays for the plugin (e.g. a micrOMEGAs relic-density solve).
"""

from __future__ import annotations

import bsm_scanner
from bsm_scanner import compile_model, load_model

MODEL_YAML = """
metadata:
  name: plugin_order_test
parameters:
- name: x
  value_type: real
  scan: false
  default: 1.0
observables:
- name: expensive
  value_type: real
  plugin_call:
    plugin: test_order_plugin
    function: value
    bindings: {x: x}
theory_checks:
- name: cheap_positive_x
  condition: x > 0.0
  fatal: true
  message: x must be positive.
- name: after_plugin
  condition: expensive < 100.0
  fatal: true
  message: plugin output too large.
outputs:
  save: [expensive]
scan:
  engine: serial_random
  seed: 1
  settings: {objective: nll, max_evaluations: 1, invalid_penalty: 1.0e12}
"""


def _compiled(tmp_path):
    calls: list[float] = []

    def expensive(args, options):
        calls.append(args["x"])
        return args["x"] * 2.0

    bsm_scanner.register_plugin_function("test_order_plugin", "value", expensive)
    path = tmp_path / "model.yaml"
    path.write_text(MODEL_YAML, encoding="utf-8")
    return compile_model(load_model(path)), calls


def test_failing_cheap_check_skips_expensive_plugin(tmp_path):
    compiled, calls = _compiled(tmp_path)

    result = compiled.evaluate({"x": -1.0})

    assert result["valid"] is False
    assert "x must be positive" in result["failure_reason"]
    assert calls == []


def test_passing_cheap_check_still_runs_plugin_and_dependent_check(tmp_path):
    compiled, calls = _compiled(tmp_path)

    ok = compiled.evaluate({"x": 3.0})
    assert ok["valid"] is True
    assert ok["outputs"]["expensive"] == 6.0
    assert calls == [3.0]

    # A check that depends on the plugin output must still see it.
    bad = compiled.evaluate({"x": 80.0})
    assert bad["valid"] is False
    assert "plugin output too large" in bad["failure_reason"]
