"""Fixed, bounded, no-retry MCP transport. Provider text is untrusted data.

No credential discovery, logging, response persistence or OAuth provisioning.
The server connection owner supplies an ephemeral SecretHandle after authority
checks. Task9 owns paid admission and reconciliation, not this transport.
"""
import asyncio
import json
import re
from typing import get_args, get_origin, Annotated

import httpx
from pydantic import BaseModel
from ..sales import contracts as c

ENDPOINT = 'https://mcp.xverum.com/mcp'
PROTOCOL = '2025-06-18'
PROJECTIONS = {
    'search_company_xverum': c.XverumCompanySearch,
    'search_people_xverum': c.XverumPeopleSearch,
    'enrich_company_xverum': c.XverumCompanyDetail,
    'enrich_person_xverum': c.XverumPersonDetail,
    'get_email_xverum': c.XverumBusinessEmail,
}


class XverumTransportError(Exception):
    """No upstream text. Nonacceptance concerns only the billable tool call.

    Any failure once tools/call begins is unknown, including HTTP/RPC errors;
    those alone are not authoritative billing/nonacceptance evidence.
    """
    def __init__(self, phase='validation', *, code='XVERUM_PROTOCOL_ERROR'):
        self.phase = phase
        self.code = code
        self.definitely_nonaccepted = phase != 'tools/call'
        self.outcome = 'definitely_nonaccepted' if self.definitely_nonaccepted else 'unknown'
        super().__init__(code)


def validate_arguments(tool, arguments):
    if tool not in c.CONTACT_ALLOWLIST or not isinstance(arguments, dict):
        raise XverumTransportError()
    try:
        parsed = c.ACTION_MODELS[tool].model_validate(arguments)
        value = parsed.model_dump(mode='json')
        if tool not in ('search_company_xverum', 'search_people_xverum'):
            ident = value.get('company_id', value.get('id'))
            if not re.fullmatch(r'[0-9]{1,128}', ident):
                raise ValueError()
        return value
    except (ValueError, TypeError):
        raise XverumTransportError() from None


def _project(model, value):
    """Recursively select known fields before strict validation; no raw extras."""
    if not isinstance(value, dict):
        raise ValueError()
    def pick(annotation, item):
        origin = get_origin(annotation)
        if origin is Annotated:
            return pick(get_args(annotation)[0], item)
        if origin in (tuple, list) and isinstance(item, list):
            return [pick(get_args(annotation)[0], v) for v in item]
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return _project(annotation, item)
        return item
    return {name: pick(field.annotation, value[name]) for name, field in model.model_fields.items() if name in value}


def projection(tool, value, arguments):
    if not isinstance(value, dict):
        raise ValueError()
    data = PROJECTIONS[tool].model_validate(_project(PROJECTIONS[tool], value))
    if tool.startswith('search_') and (data.page != arguments['page']
            or data.page_size != arguments['page_size'] or len(data.results) > data.page_size):
        raise ValueError()
    result = c.XverumResult(tool=tool, projection=data, request_id=value.get('request_id'),
        credits_used=value.get('credits_used'), credits_remaining=value.get('credits_remaining'))
    if tool == 'get_email_xverum' and not data.has_email and result.credits_used != 0:
        raise ValueError()
    return result


def validate_advertised_tools(value):
    """Activation guard against actual tools/list input schemas, never prose.

    Reject unknown schema constraints rather than guessing their semantics.
    Extra tools are ignored, never granted. Optional additions are harmless
    only when they do not alter the known argument contract.
    """
    if not isinstance(value, dict) or value.get('nextCursor') or not isinstance(value.get('tools'), list):
        raise ValueError('incomplete advertised tool schemas')
    found = {}
    for item in value['tools']:
        if not isinstance(item, dict):raise ValueError('invalid tool schema')
        name = item.get('name')
        if name not in c.CONTACT_ALLOWLIST:continue
        if name in found:raise ValueError('duplicate tool schema')
        schema = item.get('inputSchema')
        allowed_root = {'type','properties','required','additionalProperties','title','description','$schema'}
        if not isinstance(schema, dict) or schema.get('type') != 'object' or set(schema) - allowed_root:
            raise ValueError('unsupported input schema')
        properties, required = schema.get('properties'), schema.get('required', [])
        search = name.startswith('search_')
        expected = {'query':'string','page':'integer','page_size':'integer'} if search else {
            'company_id' if name == 'enrich_company_xverum' else 'id':'string'}
        mandatory = {'query'} if search else set(expected)
        if (not isinstance(properties, dict) or not isinstance(required, list)
                or not all(isinstance(x,str) for x in required) or set(required) != mandatory):
            raise ValueError('required field drift')
        limits = {'query':{'minLength':1,'maxLength':500}, 'page':{'minimum':1,'default':1},
                  'page_size':{'minimum':1,'maximum':100,'default':10}}
        for field, kind in expected.items():
            spec = properties.get(field)
            if not isinstance(spec, dict) or spec.get('type') != kind:
                raise ValueError('field type drift')
            known = {'type','title','description'} | set(limits.get(field, {}))
            if set(spec) - known:raise ValueError('unsupported field constraint')
            for key, expected_value in limits.get(field, {}).items():
                if key in spec and spec[key] != expected_value:raise ValueError('field constraint drift')
        found[name] = schema
    if set(found) != set(c.CONTACT_ALLOWLIST):raise ValueError('missing allowlisted tool')
    return found


class XverumTransport:
    def __init__(self, *, endpoint=ENDPOINT, before_dispatch=None):
        if endpoint != ENDPOINT:
            raise XverumTransportError()
        self.before_dispatch = before_dispatch

    async def call(self, tool: c.XverumTool, arguments: dict, credential: c.SecretHandle) -> c.XverumResult:
        args = validate_arguments(tool, arguments)
        return await self._session(credential, tool=tool, arguments=args)

    async def activate(self, credential: c.SecretHandle):
        return await self._session(credential)

    async def _session(self, credential, *, tool=None, arguments=None):
        if not isinstance(credential, c.SecretHandle):raise XverumTransportError()
        headers = {'Authorization':credential._authorization(), 'Accept':'application/json, text/event-stream'}
        phase = 'initialize'
        consumed = 0

        def fail():
            raise XverumTransportError(phase)

        def decode(raw, ident):
            if credential._authorization()[7:].encode() in raw:fail()
            value = json.loads(raw)
            def has_secret(item):
                if isinstance(item,str):return credential._authorization()[7:] in item
                if isinstance(item,list):return any(has_secret(v) for v in item)
                if isinstance(item,dict):return any(has_secret(k) or has_secret(v) for k,v in item.items())
                return False
            if has_secret(value):fail()
            if not isinstance(value, dict) or value.get('jsonrpc') != '2.0':fail()
            if 'id' not in value:
                if not isinstance(value.get('method'), str):fail()
                return None  # bounded notifications are data, never executed
            if type(value['id']) is not int or value['id'] != ident:fail()
            if 'error' in value or not isinstance(value.get('result'), dict):fail()
            return value['result']

        async def rpc(client, method, params=None, ident=None):
            nonlocal consumed
            message = {'jsonrpc':'2.0','method':method}
            if params is not None:message['params'] = params
            if ident is not None:message['id'] = ident
            async with client.stream('POST', ENDPOINT, json=message, headers=headers) as response:
                if response.status_code != (202 if ident is None else 200):fail()
                session_id = response.headers.get('Mcp-Session-Id')
                if session_id is not None:
                    if not re.fullmatch(r'[!-~]{1,200}', session_id):fail()
                    if phase != 'initialize' and session_id != headers.get('Mcp-Session-Id'):fail()
                    headers['Mcp-Session-Id'] = session_id
                content_type = response.headers.get('content-type','').split(';')[0].strip().lower()
                if ident is not None and content_type not in {'application/json','text/event-stream'}:fail()
                raw = bytearray()
                line, event_data, after_cr = bytearray(), [], False
                async for chunk in response.aiter_bytes():
                    consumed += len(chunk)
                    if consumed > 65536:fail()
                    raw.extend(chunk)
                    if content_type == 'text/event-stream':
                        # Stateful CR/LF parser: a split CRLF is one line ending,
                        # never a false blank event. UTF-8 is decoded only by JSON
                        # after the complete, byte-bounded event has arrived.
                        raw.clear()
                        for byte in chunk:
                            if after_cr:
                                after_cr = False
                                if byte == 10:continue
                            if byte not in (10,13):
                                line.append(byte)
                                continue
                            after_cr = byte == 13
                            if not line:
                                if event_data:
                                    result = decode(b'\n'.join(event_data),ident)
                                    event_data.clear()
                                    if result is not None:return result
                            elif line.startswith(b'data:'):
                                event_data.append(bytes(line[5:]).removeprefix(b' '))
                            line.clear()
                if ident is None:
                    if raw:fail()
                    return None
                if content_type != 'application/json':fail()
                result = decode(raw, ident)
                if result is None:fail()
                return result

        try:
            async with asyncio.timeout(12), httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False) as client:
                init = await rpc(client,'initialize',{'protocolVersion':PROTOCOL,'capabilities':{},
                    'clientInfo':{'name':'buyeros-xverum','version':'1'}},1)
                if init.get('protocolVersion') != PROTOCOL or not isinstance(init.get('capabilities'),dict) or not isinstance(init['capabilities'].get('tools'),dict):fail()
                headers['MCP-Protocol-Version'] = PROTOCOL
                phase = 'initialized'
                await rpc(client,'notifications/initialized')
                if tool is None:
                    phase = 'tools/list'
                    result = await rpc(client,'tools/list',{},2)
                    return validate_advertised_tools(result)
                phase = 'pre_dispatch'
                if self.before_dispatch is not None:
                    try:await self.before_dispatch()
                    except Exception:raise XverumTransportError(phase,code='XVERUM_AUTHORITY_CHANGED') from None
                phase = 'tools/call'
                result = await rpc(client,'tools/call',{'name':tool,'arguments':arguments},2)
                if result.get('isError',False) is not False:fail()
                return projection(tool, result.get('structuredContent'), arguments)
        except XverumTransportError:
            raise
        except (httpx.HTTPError, TimeoutError, ValueError, TypeError, AttributeError, KeyError, RecursionError):
            raise XverumTransportError(phase) from None
