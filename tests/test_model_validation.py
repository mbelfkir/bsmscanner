from pathlib import Path

from bsm_scanner.api import load_model
from bsm_scanner.exceptions import ModelValidationError
from bsm_scanner.model.schema import ParameterSpec, PriorKind
from bsm_scanner.model.validation import (
    build_parity_section,
    dead_scanned_parameters,
    plugin_term_accounting,
    require_free_parameter_set,
    require_likelihood_coverage,
    require_no_dead_scanned_parameters,
    summarize_model_invariants,
)

ROOT = Path(__file__).resolve().parents[1]
MASTER_REDUCED = ROOT / "examples" / "oneloop_master" / "model_normal_reduced.yaml"


def test_model_invariant_summary_reports_plugin_and_scan_state():
    model = load_model(MASTER_REDUCED)
    summary = summarize_model_invariants(model)

    assert summary.model_name == "oneloop_master_normal_reduced"
    assert summary.dead_scanned_parameters == ()
    assert "m12+m3l" in summary.plugin_terms.likelihoods
    assert "Omega" in summary.plugin_terms.observables


def test_validation_helpers_reject_forbidden_or_dead_scan_parameters():
    model = load_model(MASTER_REDUCED)

    require_no_dead_scanned_parameters(model)
    require_free_parameter_set(model, forbidden={"MA2", "sa", "lambda1", "k2", "k3", "Rep", "Imgp"})

    broken = load_model(MASTER_REDUCED)
    broken.parameters.append(
        ParameterSpec(
            name="unused_parameter",
            scan=True,
            lower=0.0,
            upper=1.0,
            default=0.5,
            prior=PriorKind.FLAT,
        )
    )

    try:
        require_no_dead_scanned_parameters(broken)
    except ModelValidationError as exc:
        assert "unused_parameter" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected dead scanned parameter failure")


def test_validation_helpers_check_likelihood_coverage():
    model = load_model(MASTER_REDUCED)

    require_likelihood_coverage(
        model,
        {
            "theta12_term",
            "theta13_term",
            "theta23_term",
            "deltaCP_term",
            "m12+m3l",
            "sumOfMass",
            "massPinalety",
            "HiggsRgg_term",
            "KPinaleties",
            "EVPinaleties",
            "BRPinaleties",
            "Oblique_term",
            "Omega_term",
            "DDexp_term",
        },
    )


def test_build_parity_section_supports_alias_mapping_and_summed_terms():
    report = build_parity_section(
        {"grouped": 3.0, "direct": 1.5},
        {"part_a": 1.0, "part_b": 2.0, "direct": 1.5},
        mapping={"grouped": ["part_a", "part_b"], "direct": "direct"},
    )

    assert report["grouped"].match is True
    assert report["grouped"].mapped_to == ("part_a", "part_b")
    assert report["direct"].match is True


def test_dead_scanned_parameters_returns_empty_for_canonical_reduced_model():
    model = load_model(MASTER_REDUCED)
    assert dead_scanned_parameters(model) == ()
    accounting = plugin_term_accounting(model)
    assert accounting.likelihoods == ("m12+m3l",)
