from pathlib import Path

from bsm_scanner import compile_model, load_model

try:
    from bsm_scanner import _core  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _core = None


ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "model.yaml"


def main() -> None:
    model = load_model(MODEL)
    if _core is None or not _core.has_plugin_support("oneloop_micromegas"):
        raise SystemExit(
            "This latest-master example requires the optional micrOMEGAs-backed "
            "oneloop plugin build. Reinstall with "
            "CMAKE_ARGS='-DBSM_SCANNER_BUILD_ONELOOP_MICROMEGAS=ON "
            "-DBSM_SCANNER_MICROMEGAS_ROOT=/path/to/micromegas "
            "-DBSM_SCANNER_MICROMEGAS_MODEL_ROOT=/path/to/1LRNM-1N1P-New "
            "-DBSM_SCANNER_MICROMEGAS_CALCHEP_ROOT=/path/to/CalcHEP_src'"
        )

    compiled = compile_model(model, build_backend=True)
    plan_path = ROOT / "compiled_plan.json"
    compiled.export_plan(plan_path)

    point = {parameter.name: parameter.default for parameter in model.parameters}
    result = compiled.evaluate(point)

    print(f"Exported lowered plan to {plan_path}")
    print(f"Active evaluation order has {len(compiled.plan.evaluation_order)} nodes")
    print(f"Default-point status: {result['status']}")
    if result["status"] == "ok":
        print(f"Default-point nLL: {result['total_nll']}")
        print(f"Saved outputs: {', '.join(sorted(result['outputs']))}")
    else:
        print(f"Failure reason: {result['failure_reason']}")


if __name__ == "__main__":
    main()
