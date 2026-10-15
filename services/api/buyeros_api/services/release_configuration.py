"""Effective runtime settings and activation proof without provider execution."""
import asyncio
import hashlib
import json

from sqlalchemy import text
from ..settings import Settings
from .release_binding import runtime_identity

CONFIG_FIELDS=('auth_mode','auth0_issuer','auth0_audience','neon_issuer','neon_audience','neon_jwks_url',
               'neon_expected_issuer','neon_expected_audience','neon_expected_jwks_url',
               'paid_admission_enabled','delivery_admission_enabled','cloudflare_execution_enabled',
               'live_read_enabled','reconciliation_enabled','r2_enabled','private_object_backend','environment')


def configuration_sha256(settings: Settings) -> str:
    projected={name:getattr(settings,name) for name in CONFIG_FIELDS}
    return hashlib.sha256(json.dumps(projected,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def pulled_configuration_sha256(values: dict) -> str:
    class PulledSettings(Settings):
        @classmethod
        def settings_customise_sources(cls,settings_cls,init_settings,env_settings,dotenv_settings,file_secret_settings):
            return (init_settings,)
    selected={name:values['BUYEROS_'+name.upper()] for name in CONFIG_FIELDS if 'BUYEROS_'+name.upper() in values}
    return configuration_sha256(PulledSettings(**selected))


async def read_runtime_configuration(engine,settings: Settings) -> dict:
    from ..providers.registry import provider_readiness
    source,deployment=runtime_identity(settings)
    # Provider readiness is passive; never resolve an adapter or call a provider.
    contact=provider_readiness('contact',environment='production')
    contact_state='unconfigured' if contact.get('reason_codes')==['PROVIDER_UNSELECTED'] else contact.get('status')
    async with asyncio.timeout(8):
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text('SET TRANSACTION READ ONLY'))
                await connection.execute(text("SET LOCAL statement_timeout = '3000ms'"))
                worker=(await connection.execute(text('SELECT enabled FROM public.worker_runtime_control LIMIT 2'))).scalar_one()
    return {'schema':'buyeros.runtime-configuration.v1','source_sha':source,'deployment_id':deployment,
            'configuration_sha256':configuration_sha256(settings),
            'activation':{'providers':'active' if settings.paid_admission_enabled else 'disabled',
                          'delivery':'active' if settings.delivery_admission_enabled else 'disabled',
                          'worker':'active' if worker or settings.cloudflare_execution_enabled else 'disabled',
                          'contact_enrichment':contact_state}}
