"""Deterministic intake planning; no dispatch or invented commercial facts."""
from .contracts import INPUT_MODELS, TaskPlan, PlanStep, ExecutionBounds
from .registry import validate_intake, validate_arguments

from .sections import section_groups

# Children debit one later-admitted parent reservation; no extra reservation here.


def missing_inputs(skill, arguments):
    values = validate_intake(skill, arguments)
    missing = [key for key, field in INPUT_MODELS[skill.id].model_fields.items()
               if field.is_required() and key not in values]
    if skill.id in {'sales-research', 'sales-quick'} and not (values.get('buyer_id') or values.get('research_question')):
        missing.append('buyer_id_or_research_question')
    return tuple(missing)


def plan_task(skill, arguments, context):
    missing = list(missing_inputs(skill, arguments))
    if skill.id in {'sales-outreach','sales-followup','sales-proposal','sales-objections','sales-competitors'} and not context.refs:
        missing.append('selected_offer_facts')
    if missing:
        return TaskPlan(steps=(), missing_inputs=tuple(missing), output_kind=skill.output_kind)
    validate_arguments(skill, arguments)
    steps = tuple(PlanStep(section=section, kind='model') for section in section_groups(skill.output_kind))
    bounds = ExecutionBounds.model_validate(arguments.get('bounds', {}))
    if len(steps) > min(bounds.max_steps, bounds.max_model_calls):
        raise ValueError('section plan exceeds parent bound; request a separately reviewed smaller task')
    return TaskPlan(steps=steps, missing_inputs=(), output_kind=skill.output_kind, bounds=bounds,
        input_token_budget=sum(step.max_input_tokens for step in steps),
        output_token_budget=sum(step.max_output_tokens for step in steps))
