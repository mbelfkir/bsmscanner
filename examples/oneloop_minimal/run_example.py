from pathlib import Path

from bsm_scanner import compile_model

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "model.yaml"


def main() -> None:
    compiled = compile_model(MODEL, build_backend=False)
    plan_path = ROOT / "compiled_plan.json"
    compiled.export_plan(plan_path)
    print(f"Exported lowered plan to {plan_path}")
    print(f"Active evaluation order has {len(compiled.plan.evaluation_order)} nodes")


if __name__ == "__main__":
    main()

