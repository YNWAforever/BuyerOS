"""Code-owned child shapes. Assembly into a complete output belongs to Task6."""
from copy import deepcopy
from functools import lru_cache
from pydantic import create_model
from .contracts import Contract, OUTPUT_MODELS

GROUPS = {
    'research_report': {'summary':('summary','unknowns','opportunities','concerns'), 'findings':('findings',)},
    'sales_proposal': {'problem':('summary','unknowns','problem','assumptions'), 'solution':('solution',),
        'terms':('terms',), 'proof_points':('proof_points',), 'followup':('followup',)},
    'outreach_preparation': {'summary':('summary','unknowns','framework'), 'messages':('messages',)},
    'followup_preparation': {'summary':('summary','unknowns','scenario','interaction_ref'), 'messages':('messages',)},
    'meeting_brief': {'cheat_sheet':('summary','unknowns','cheat_sheet','attendees','talking_points','discovery_questions'),
        'agenda':('agenda',), 'next_steps':('next_steps',)},
    'objection_playbook': {'summary':('summary','unknowns'), 'responses':('responses',)},
    'pipeline_report': {'summary':('summary','unknowns','as_of','scope','unavailable_buyer_ids','methodology'), 'rows':('rows',)},
}
SERVER_DEFAULTS = frozenset({'approval_required','review_required','advisory','setup_basis','filters','record_basis','document_basis'})
# These typed output models carry native identities/completion claims whose owners
# are not wired into the selected offer-excerpt resolver. Never trust even empty IDs.
UNRESOLVED_NATIVE_FIELDS = {
    'enrichment_proposal': ('buyer_id','buyer_version','identity_match'),
    'pipeline_report': ('scope','rows','unavailable_buyer_ids'),
    'report_export': ('output_id','output_revision','export_ref'),
    'document_understanding': ('document_ids','extraction_status'),
    'buyer_review': ('proposed_buyer_ids',),
}


def section_groups(kind):
    model = OUTPUT_MODELS[kind]
    return GROUPS.get(kind, {'summary':tuple(key for key in model.model_fields if key not in SERVER_DEFAULTS)})


@lru_cache(maxsize=64)
def section_model(kind, section):
    groups = section_groups(kind)
    if section not in groups:
        raise ValueError('unknown code-owned section')
    model = OUTPUT_MODELS[kind]
    fields = {key:(model.model_fields[key].annotation,deepcopy(model.model_fields[key])) for key in groups[section]}
    return create_model('Section_' + kind + '_' + section, __base__=Contract, **fields)


def require_supported_identity_kind(kind):
    # These names are fields on the registered typed content model, not a raw
    # dictionary-key heuristic. Reject the kind until its resolver owns them.
    if kind in UNRESOLVED_NATIVE_FIELDS:
        assert set(UNRESOLVED_NATIVE_FIELDS[kind]) <= OUTPUT_MODELS[kind].model_fields.keys()
        raise ValueError('native identity/completion fields require their owning authorized resolver')


def projected_arguments(request):
    """Do not repeat unrelated inputs in every child; never truncate supplied facts."""
    arguments = request.arguments
    if request.skill_id == 'sales-proposal':
        keys = {'problem':('language','pain_points'), 'solution':('language','pain_points'),
            'terms':('language','terms'), 'proof_points':('language',),
            'followup':('language','pain_points')}[request.section]
    else:
        # Native IDs are not evidence; selected authorized source references travel separately.
        keys = tuple(key for key in arguments if key not in {'bounds','buyer_id','buyer_ids','profile_id',
            'profile_version','recipient_id','attendee_ids','document_ids','output_id','output_revision','list_id'})
    return {key:arguments[key] for key in keys if key in arguments}
