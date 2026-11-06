"""Read-only versioned catalogue. Never resolve user input to a filesystem path."""
import json
from pathlib import Path
from types import MappingProxyType

from .contracts import (
    ACTION_MODELS, CONTACT_ALLOWLIST, INPUT_MODELS, OUTPUT_MODELS, OutputCandidate,
    SkillDefinition, contract_schemas,
)

_ROOT = Path(__file__).resolve().parent
_DATA = json.loads((_ROOT / "catalogue.json").read_text(encoding="utf-8"))
TEMPLATE_SKILLS = MappingProxyType(_DATA["template_skills"])
_SCHEMAS = contract_schemas()


def _definitions() -> tuple[SkillDefinition, ...]:
    definitions = []
    seen = set()
    for row in _DATA["skills"]:
        key = (row["id"], row["version"])
        if key in seen or row["id"] not in INPUT_MODELS or row["output_kind"] not in OUTPUT_MODELS:
            raise ValueError("invalid or duplicate code-owned catalogue entry")
        seen.add(key)
        definitions.append(SkillDefinition(
            **{name: row[name] for name in SkillDefinition.model_fields if name != "inputs_schema"},
            inputs_schema=_SCHEMAS[INPUT_MODELS[row["id"]].__name__],
        ))
    if {item.id for item in definitions} != set(INPUT_MODELS):
        raise ValueError("incomplete catalogue")
    return tuple(definitions)


_CATALOGUE = _definitions()
_INDEX = MappingProxyType({(skill.id, skill.version): skill for skill in _CATALOGUE})


def catalogue() -> tuple[SkillDefinition, ...]:
    return _CATALOGUE


def load_skill(skill_id: str, version: str) -> SkillDefinition:
    if not isinstance(skill_id, str) or not isinstance(version, str):
        raise ValueError("skill ID and version must be strings")
    try:
        return _INDEX[(skill_id, version)]
    except KeyError:
        raise ValueError("unknown skill or version") from None


def _registered(skill: SkillDefinition) -> SkillDefinition:
    canonical = load_skill(skill.id, skill.version)
    if skill != canonical:
        raise ValueError("skill differs from code-owned immutable definition")
    return canonical


def validate_arguments(skill: SkillDefinition, arguments: dict) -> dict:
    canonical = _registered(skill)
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    return INPUT_MODELS[canonical.id].model_validate(arguments).model_dump(mode="json")


def validate_action(skill: SkillDefinition, capability: str, arguments: dict) -> dict:
    canonical = _registered(skill)
    if capability not in canonical.allowed_actions:
        raise ValueError("capability is disabled for this skill")
    return ACTION_MODELS[capability].model_validate(arguments).model_dump(mode="json")


def output_schema(kind: str) -> dict:
    if kind not in OUTPUT_MODELS:
        raise ValueError("unknown output kind")
    return OUTPUT_MODELS[kind].model_json_schema(ref_template="#/components/schemas/{model}")


def validate_output(skill: SkillDefinition, candidate: dict) -> OutputCandidate:
    canonical = _registered(skill)
    result = OutputCandidate.model_validate(candidate)
    if result.kind != canonical.output_kind:
        raise ValueError("output kind does not match skill")
    return result


def playbook(skill: SkillDefinition) -> str:
    canonical = _registered(skill)
    row = next(row for row in _DATA["skills"] if row["id"] == canonical.id and row["version"] == canonical.version)
    return (_ROOT / "playbooks" / row["playbook"]).read_text(encoding="utf-8")



def validate_intake(skill: SkillDefinition, arguments: dict) -> dict:
    """Missing top-level fields are permitted; every supplied value keeps its type."""
    from pydantic import TypeAdapter
    canonical = _registered(skill)
    model = INPUT_MODELS[canonical.id]
    if not isinstance(arguments, dict) or set(arguments) - set(model.model_fields):
        raise ValueError("unknown intake fields")
    result = {}
    for key, value in arguments.items():
        adapter = TypeAdapter(model.model_fields[key].rebuild_annotation())
        result[key] = adapter.dump_python(adapter.validate_python(value), mode="json")
    # Full model/cross-field validation is mandatory as soon as intake is complete.
    required = {key for key, field in model.model_fields.items() if field.is_required()}
    target_missing = canonical.id in {"sales-research", "sales-quick"} and not (result.get("buyer_id") or result.get("research_question"))
    if required <= result.keys() and not target_missing:
        validate_arguments(canonical, result)
    return result
