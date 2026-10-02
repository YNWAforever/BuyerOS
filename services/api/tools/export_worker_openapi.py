"""Export the five internal operations separately from the public78 contract."""
import argparse
import json
from pathlib import Path

from buyeros_api.api.app import create_app
from buyeros_api.api.worker_auth import INTERNAL_PATHS


def internal_spec() -> dict:
    full = create_app().openapi()
    paths = {path: routes for path, routes in full["paths"].items() if path in INTERNAL_PATHS}
    assert len(paths) == 5
    spec = {"openapi": full["openapi"], "info": {"title": "BuyerOS internal worker protocol", "version": "1"},
            "paths": paths, "components": {"schemas": {}}}
    schemas = full["components"]["schemas"]
    queue = [paths]
    while queue:
        node = queue.pop()
        if isinstance(node, dict):
            ref = node.get("$ref", "")
            if ref.startswith("#/components/schemas/"):
                name = ref.rsplit("/", 1)[1]
                if name not in spec["components"]["schemas"]:
                    spec["components"]["schemas"][name] = schemas[name]
                    queue.append(schemas[name])
            queue.extend(node.values())
        elif isinstance(node, list):
            queue.extend(node)
    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = Path(__file__).resolve().parents[1] / "contracts/worker.openapi.json"
    value = json.dumps(internal_spec(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != value:
            raise SystemExit("Internal worker OpenAPI is stale")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8")
    print("Internal worker contract: 5 operations")


if __name__ == "__main__":
    main()
