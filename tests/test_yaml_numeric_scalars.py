"""Regression tests for numeric YAML scalars.

PyYAML implements YAML 1.1, in which an exponent without a sign (``1.0e9``)
is *not* a float -- it loads as a string.  Such a value used to travel
silently into numeric fields: a ``table_lookup`` out-of-range penalty became
inert, and the only symptom was an opaque "non-scalar node" failure much
later.  These tests pin the fix.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from bsm_scanner.exceptions import ModelValidationError
from bsm_scanner.model.loader import ScannerYamlLoader
from bsm_scanner.model.schema import _require_number

REPO_ROOT = Path(__file__).resolve().parents[1]
UNSIGNED_EXPONENT = re.compile(r"(?<![\w.])[-+]?[0-9]+(?:\.[0-9]*)?[eE][0-9]+(?![\w.])")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("v: 1.0e9", 1.0e9),
        ("v: 4.0e4", 4.0e4),
        ("v: 1e12", 1.0e12),
        ("v: 1.0e+9", 1.0e9),
        ("v: 1.5e-13", 1.5e-13),
        ("v: -2.5e3", -2.5e3),
    ],
)
def test_unsigned_exponents_load_as_floats(text, expected):
    value = yaml.load(text, Loader=ScannerYamlLoader)["v"]
    assert isinstance(value, float), f"{text!r} loaded as {type(value).__name__}"
    assert value == expected


def test_plain_safe_load_would_have_failed():
    """Documents the defect this loader exists to prevent."""
    assert isinstance(yaml.safe_load("v: 1.0e9")["v"], str)


def test_genuine_strings_are_untouched():
    loaded = yaml.load("a: hello\nb: 1.0e+9x\nc: core:neutrino/x.yaml", Loader=ScannerYamlLoader)
    assert loaded["a"] == "hello"
    assert loaded["b"] == "1.0e+9x"
    assert loaded["c"] == "core:neutrino/x.yaml"


def test_require_number_accepts_numeric_text():
    assert _require_number("1.0e9", "scale", "likelihood 'x'") == 1.0e9
    assert _require_number(3, "scale", "likelihood 'x'") == 3.0


def test_require_number_rejects_text_and_explains_why():
    with pytest.raises(ModelValidationError) as excinfo:
        _require_number("banana", "out_of_range_penalty_scale", "likelihood 'x'")
    message = str(excinfo.value)
    assert "out_of_range_penalty_scale" in message
    assert "1.0e+9" in message, "the error should tell the user how to fix it"


def test_require_number_rejects_booleans():
    with pytest.raises(ModelValidationError):
        _require_number(True, "sigma", "likelihood 'x'")


@pytest.mark.parametrize("directory", ["core", "models"])
def test_shipped_yaml_has_no_unsigned_exponents(directory):
    """Shipped files must stay readable by a plain YAML 1.1 loader too."""
    root = REPO_ROOT / directory
    if not root.is_dir():
        pytest.skip(f"{directory}/ not present")
    offenders = []
    for path in sorted(root.rglob("*.yaml")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if UNSIGNED_EXPONENT.search(code):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, "unsigned exponents found:\n" + "\n".join(offenders[:20])
