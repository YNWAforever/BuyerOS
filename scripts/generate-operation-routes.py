"""Generate the browser operation route table from the single OpenAPI contract.

Run from services/api: uv run --frozen python ../../scripts/generate-operation-routes.py [--check]
"""
import json
import sys
from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
contract = root / "docs/buyeros/contracts/openapi.proposed.yaml"
output = root / "services/generated/operation-routes.ts"
spec = yaml.safe_load(contract.read_text(encoding="utf-8"))
entries = {}
for path, routes in spec["paths"].items():
    for method, operation in routes.items():
        if method.lower() not in {"get", "post", "patch", "delete", "put"}:
            continue
        operation_id = operation.get("operationId")
        if not operation_id or operation_id in entries:
            raise SystemExit(f"Missing or duplicate operationId: {operation_id}")
        entries[operation_id] = (method.upper(), path)
if len(entries) < 70:
    raise SystemExit(f"Expected at least 70 operations, found {len(entries)}")
lines = [
    "// Generated from docs/buyeros/contracts/openapi.proposed.yaml; do not edit manually.",
    "import type {operations} from './buyeros-api';",
    "export const operationRoutes = {",
]
for operation_id, (method, path) in entries.items():
    lines.append(f"  {json.dumps(operation_id)}: {{method: {json.dumps(method)}, path: {json.dumps(path)}}},")
lines.extend(["} as const satisfies Record<keyof operations, {method: string; path: string}>;", ""])
rendered = "\n".join(lines)
if "--check" in sys.argv:
    if output.read_text(encoding="utf-8").replace("\r\n", "\n") != rendered:
        raise SystemExit("Operation route map is stale")
    print(f"Operation route map matches OpenAPI: {len(entries)} operations")
else:
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output}: {len(entries)} operations")
