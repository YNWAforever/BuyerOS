"""Code-owned new contact quote/claim authority; original receipt decoding stays separate."""
from ..providers import registry


def current_contact_configuration(capability, *, market: str, language: str, role: str, environment: str) -> dict:
    config=registry.DEFAULT_REGISTRY.contact_lookup_configuration(
        market=market,language=language,role=role,environment=environment)
    if config is None or capability!=config['capability']:
        raise ValueError('current contact reviewed registry configuration unavailable')
    scope=config['scope']
    return {'registry_contract_hash':config['registry_contract_hash'],
            'receipt_contract_hash':config['receipt_contract_hash'],
            'account_reference':scope.account_reference,'market':market,'language':language,
            'contact_type':scope.contact_type,'limit':scope.max_contacts}
