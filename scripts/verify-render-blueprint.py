"""Validate the review artifact against Render's official schema; no provisioning."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import jsonschema
import yaml


SCHEMA_URL = "https://render.com/schema/render.yaml.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, help="use a previously downloaded official schema")
    args = parser.parse_args()
    if args.schema:
        schema_bytes = args.schema.read_bytes()
    else:
        with urlopen(SCHEMA_URL, timeout=30) as response:
            schema_bytes = response.read(1_000_001)
        if len(schema_bytes) > 1_000_000:
            raise ValueError("Render schema exceeds the bounded download size")
    schema = json.loads(schema_bytes)
    if schema.get("$id") != SCHEMA_URL:
        raise ValueError("Unexpected Render schema identity")
    blueprint = Path(__file__).resolve().parents[1] / "render.yaml"
    validator = jsonschema.validators.validator_for(schema)
    validator.check_schema(schema)
    validator(schema).validate(yaml.safe_load(blueprint.read_text(encoding="utf-8")))
    print(json.dumps({"valid": True, "schema_url": SCHEMA_URL,
                      "schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
                      "blueprint_sha256": hashlib.sha256(blueprint.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
