from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app.main import app  # noqa: E402


def _is_exempt(path: str) -> bool:
    return path.startswith("/health") or path == "/metrics"


def main() -> None:
    spec = app.openapi()
    if "paths" not in spec or not spec["paths"]:
        raise SystemExit("OpenAPI gate failed: no paths defined")
    failures: list[str] = []
    operation_ids: set[str] = set()
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if _is_exempt(path):
                continue
            op_ref = f"{method.upper()} {path}"
            summary = operation.get("summary")
            description = operation.get("description")
            tags = operation.get("tags")
            operation_id = operation.get("operationId")
            responses = operation.get("responses", {})
            if not summary:
                failures.append(f"{op_ref}: missing summary")
            if not description:
                failures.append(f"{op_ref}: missing description")
            if not tags:
                failures.append(f"{op_ref}: missing tags")
            if not operation_id:
                failures.append(f"{op_ref}: missing operationId")
            elif operation_id in operation_ids:
                failures.append(f"{op_ref}: duplicate operationId {operation_id}")
            else:
                operation_ids.add(operation_id)
            if not any(code.startswith("2") for code in responses):
                failures.append(f"{op_ref}: missing 2xx response")
            if not any(code.startswith("4") or code.startswith("5") for code in responses):
                failures.append(f"{op_ref}: missing error response")
    if failures:
        raise SystemExit("OpenAPI gate failed:\n- " + "\n- ".join(failures))
    print("OpenAPI gate passed")


if __name__ == "__main__":
    main()
