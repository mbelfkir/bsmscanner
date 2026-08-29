from pathlib import Path

from bsm_scanner import compile_model, load_model

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "model.yaml"


def main() -> None:
    model = load_model(MODEL)
    if "micromegas_pending" in model.metadata.tags:
        print(
            "Warning: the exact micrOMEGAs-backed DM sector is still deferred in this "
            "milestone. See docs/dm_status.md"
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
