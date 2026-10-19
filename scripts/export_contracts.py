import json
from pathlib import Path
from contractlens import contracts
from contractlens.api import app

root = Path(__file__).resolve().parents[1] / "docs" / "contracts"
root.mkdir(parents=True, exist_ok=True)
root.joinpath("openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")
for name in [
    "StartRequest",
    "ContractReport",
    "Execution",
    "Event",
    "Evaluation",
    "PlanInput",
    "LedgerEntry",
]:
    root.joinpath(name + ".schema.json").write_text(
        json.dumps(getattr(contracts, name).model_json_schema(), indent=2) + "\n"
    )
