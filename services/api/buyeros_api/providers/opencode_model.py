"""OpenCode Go (OpenAI-compatible Chat Completions) transport for the LiveModelAdapter port.

Returns the same shape as ResponsesModelClient.complete: a bounded fit proposal
validated against the frozen basis. No tools. JSON mode is requested and the
proposal is then re-validated deterministically, so a model that ignores the
schema yields 'unknown', never a stored assessment.
"""
from __future__ import annotations
import asyncio,hashlib,json,math,re
from datetime import datetime,timezone
import httpx
from .model import ModelRoute
from .live_model import (PROMPT,PROPOSAL_SCHEMA,MAX_INPUT_BYTES,MAX_RESPONSE_BYTES,ModelResponseUnknown,
                         _basis,_current_source,canonical_json,validate_live_proposal)

ENDPOINT='https://opencode.ai/zen/go/v1/chat/completions'
# Documented Go API endpoint (2026-11-21). The legacy endpoint above remains
# unchanged for existing fit/sales callers.
CONVERSATION_ENDPOINT='https://opencode.ai/inference/go/openai/v1/chat/completions'
ENDPOINTS=frozenset({ENDPOINT,CONVERSATION_ENDPOINT})
DEFAULT_MODEL_ID='kimi-k3'
USER_AGENT='BuyerOS/1.0'
# No token-count endpoint: bound input conservatively at one token per 3 bytes, then recheck reported usage.
BYTES_PER_TOKEN_FLOOR=3


def conversation_session_header(basis:dict)->str:
    """Stable, non-identifying session value for the stored conversation thread."""
    seed=basis.get('thread_id') or basis.get('basis_hash')
    if not isinstance(seed,str) or not seed:
        raise ValueError('stored conversation thread identity required')
    return hashlib.sha256(('buyeros-conversation-session.v1:'+seed).encode()).hexdigest()[:32]


def model_payload(basis:dict,route:ModelRoute,model_id:str)->dict:
    from .conversation_model import prompt_schema
    prompt,schema=prompt_schema(basis)
    if basis.get('schema')=='sales-basis.v1':
        from ..sales.model import wire_basis
        source_data=wire_basis(basis)
    else:
        source_data=basis
    system=(prompt+' Prompt version: '+route.prompt_version+
            ' Reply with one JSON object only, matching this JSON schema: '+json.dumps(schema,separators=(',',':')))
    payload={'model':model_id,'max_tokens':route.max_output_tokens,'stream':False,
            'response_format':{'type':'json_object'},
            'messages':[{'role':'system','content':system},
                        {'role':'user','content':canonical_json({'untrusted_source_data':source_data}).decode()}]}
    if basis.get('schema') in {'conversation-basis.v1','sales-basis.v1'}:
        payload.update(tools=[],tool_choice='none',parallel_tool_calls=False)
    return payload


class OpenCodeGoModelClient:
    def __init__(self,*,api_key:str,http:httpx.AsyncClient,model_id:str=DEFAULT_MODEL_ID,endpoint:str=ENDPOINT):
        if not isinstance(api_key,str) or not 1<=len(api_key)<=4096 or any(ord(c)<33 or ord(c)>126 for c in api_key):raise ValueError('server-only model credential required')
        if not isinstance(model_id,str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}',model_id):raise ValueError('explicit model id required')
        if endpoint not in ENDPOINTS:raise ValueError('approved HTTPS model endpoint required')
        self._api_key,self.http,self.model_id,self.endpoint=api_key,http,model_id,endpoint

    def _payload(self,basis:dict,route:ModelRoute)->dict:
        return model_payload(basis,route,self.model_id)

    async def complete(self,basis:dict,route:ModelRoute)->dict:
        evidence=_basis(basis);now=datetime.now(timezone.utc)
        if (not isinstance(route,ModelRoute) or route.permitted_tools or not route.route_id or
            not re.fullmatch(r'[A-Za-z0-9._-]{1,80}',route.prompt_version) or
            any(type(v) is not int for v in [route.max_input_tokens,route.max_output_tokens,route.deadline_seconds,route.repair_limit])):raise ValueError('verified code-owned model route required')
        if basis.get('schema')=='conversation-basis.v1' and self.endpoint!=CONVERSATION_ENDPOINT:
            raise ValueError('conversation schema requires the current documented HTTPS endpoint')
        # Do not send private expired/foreign source prose to any provider.
        if any(not _current_source(item,basis,now) for item in evidence.values()):raise ValueError('model input has noncurrent or unverified source')
        if basis.get('schema')=='sales-basis.v1':
            from ..sales.model import ROUTE
            from dataclasses import replace
            if route != replace(ROUTE,route_id=ROUTE.prompt_version) or basis['request']['model_id'] != self.model_id:
                raise ValueError('exact bounded sales route/model required')
        payload=self._payload(basis,route);size=len(canonical_json(payload))
        if size>MAX_INPUT_BYTES or math.ceil(size/(1 if basis.get('schema') in {'conversation-basis.v1','sales-basis.v1'} else BYTES_PER_TOKEN_FLOOR))>route.max_input_tokens:raise ValueError('input token/byte budget exceeded')
        stage='http'
        try:
            async with asyncio.timeout(route.deadline_seconds):
                headers={'Authorization':'Bearer '+self._api_key,'Accept':'application/json',
                         'User-Agent':USER_AGENT}
                if basis.get('schema')=='conversation-basis.v1':
                    headers['x-opencode-session']=conversation_session_header(basis)
                async with self.http.stream('POST',self.endpoint,json=payload,headers=headers,
                                            follow_redirects=False,timeout=route.deadline_seconds) as response:
                    if response.status_code!=200:raise ModelResponseUnknown('model response unavailable')
                    raw=bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw)+len(chunk)>MAX_RESPONSE_BYTES:raise ModelResponseUnknown('model response exceeds byte budget')
                        raw.extend(chunk)
            stage='response_json'
            body=json.loads(raw)
            stage='model_identity'
            if basis.get('schema') in {'conversation-basis.v1','sales-basis.v1'} and (not isinstance(body,dict) or body.get('model')!=self.model_id):raise ModelResponseUnknown('frozen conversation model changed')
            stage='completion'
            choices=body.get('choices') if isinstance(body,dict) else None
            if isinstance(choices,list) and len(choices)==1 and isinstance(choices[0],dict) and choices[0].get('finish_reason')=='length':
                stage='completion_length'
            if (not isinstance(body.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,240}',body['id'])
                or not isinstance(choices,list) or len(choices)!=1 or not isinstance(choices[0],dict)
                or choices[0].get('finish_reason')!='stop'):raise ModelResponseUnknown('model response incomplete or unverified')
            stage='assistant_message'
            message=choices[0].get('message')
            if (not isinstance(message,dict) or message.get('role')!='assistant' or message.get('tool_calls') or message.get('function_call') or message.get('refusal')
                or not isinstance(message.get('content'),str)):raise ModelResponseUnknown('model tool/foreign role output blocked')
            text=message['content'].strip()
            if text.startswith('```'):text=re.sub(r'^```(?:json)?\s*|\s*```$','',text)
            if self._api_key in text:raise ModelResponseUnknown('bounded model text unavailable')
            stage='usage'
            usage=body.get('usage')
            if not isinstance(usage,dict) or any(type(usage.get(k)) is not int or usage[k]<0 for k in ['prompt_tokens','completion_tokens']):raise ModelResponseUnknown('typed model usage unavailable')
            if basis.get('schema')=='conversation-basis.v1':
                stage='go_billing'
                opencode=usage.get('opencode')
                if (not isinstance(opencode,dict) or opencode.get('billing_source') not in {'go','go-plus'}
                    or type(usage.get('cost')) not in {int,float} or usage['cost']!=0):
                    raise ModelResponseUnknown('reviewed Go billing not confirmed')
            stage='token_limits'
            input_tokens,output_tokens=usage['prompt_tokens'],usage['completion_tokens']
            if input_tokens>route.max_input_tokens or output_tokens>route.max_output_tokens:raise ModelResponseUnknown('model usage outside admitted bounds')
            stage='proposal_json'
            parsed=json.loads(text)
            stage='proposal_policy'
            assessment=validate_live_proposal(parsed,basis)
            return {'provider_ref':body['id'],'proposal':parsed,'assessment':assessment,
                    'usage':{'input_tokens':input_tokens,'output_tokens':output_tokens,'total_tokens':input_tokens+output_tokens},
                    'model_id':self.model_id,'prompt_version':route.prompt_version}
        except (ModelResponseUnknown,httpx.HTTPError,TimeoutError,ValueError,UnicodeError,KeyError,TypeError,AttributeError) as error:
            if basis.get('schema')=='conversation-basis.v1':
                # Vercel's Python runtime captures stdout for request logs.
                print(f'discussion_model_response_unverified stage={stage}',flush=True)
            if isinstance(error,ModelResponseUnknown):
                raise
            raise ModelResponseUnknown('model acceptance, result or usage is unknown') from error
