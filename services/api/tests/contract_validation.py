"""Validate an emitted HTTP payload against the checked-in OpenAPI schema."""

from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


@lru_cache(maxsize=1)
def _document() -> dict:
    path = Path(__file__).resolve().parents[3] / "docs/buyeros/contracts/openapi.proposed.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def assert_contract_response(schema_name: str, payload: dict) -> None:
    document = _document()
    schema = {
        "$ref": f"#/components/schemas/{schema_name}",
        "components": document["components"],
    }
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
