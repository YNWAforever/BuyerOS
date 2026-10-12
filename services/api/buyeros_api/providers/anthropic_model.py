"""Claude Messages transport for the existing LiveModelAdapter port.

Returns the same shape as ResponsesModelClient.complete: a bounded fit proposal
validated against the frozen basis. No tools, no prefill; JSON is constrained by
structured output and then re-validated deterministically. SDK retries are off
because a lost response must stay 'unknown' for durable reconciliation, never be
silently resubmitted.
"""
from __future__ import annotations
import asyncio,json,re
from datetime import datetime,timezone
import anthropic
from .model import ModelRoute
from .live_model import (PROMPT,PROPOSAL_SCHEMA,MAX_INPUT_BYTES,MAX_RESPONSE_BYTES,ModelResponseUnknown,
                         _basis,_current_source,canonical_json,validate_live_proposal)

DEFAULT_MODEL_ID='claude-opus-5-5'


class AnthropicModelClient:
    def __init__(self,*,api_key:str,model_id:str=DEFAULT_MODEL_ID,client:anthropic.AsyncAnthropic|None=None,effort:str='low'):
        if not isinstance(api_key,str) or not 1<=len(api_key)<=4096 or any(ord(c)<33 or ord(c)>126 for c in api_key):raise ValueError('server-only model credential required')
        if not isinstance(model_id,str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}',model_id):raise ValueError('explicit model id required')
        if effort not in {'low','medium','high'}:raise ValueError('bounded effort required')
        self._api_key,self.model_id,self.effort=api_key,model_id,effort
        self.client=client or anthropic.AsyncAnthropic(api_key=api_key,max_retries=0)

    def _request(self,basis:dict,route:ModelRoute)->dict:
        return {'model':self.model_id,'system':PROMPT+' Prompt version: '+route.prompt_version,
                'messages':[{'role':'user','content':canonical_json({'untrusted_source_data':basis}).decode()}],
                'output_config':{'effort':self.effort,'format':{'type':'json_schema','schema':PROPOSAL_SCHEMA}}}

    async def complete(self,basis:dict,route:ModelRoute)->dict:
        evidence=_basis(basis);now=datetime.now(timezone.utc)
        if (not isinstance(route,ModelRoute) or route.permitted_tools or not route.route_id or
            not re.fullmatch(r'[A-Za-z0-9._-]{1,80}',route.prompt_version) or
            any(type(v) is not int for v in [route.max_input_tokens,route.max_output_tokens,route.deadline_seconds,route.repair_limit])):raise ValueError('verified code-owned model route required')
        # Do not send private expired/foreign source prose to any provider.
        if any(not _current_source(item,basis,now) for item in evidence.values()):raise ValueError('model input has noncurrent or unverified source')
        request=self._request(basis,route)
        if len(canonical_json(request))>MAX_INPUT_BYTES:raise ValueError('input byte budget exceeded')
        try:
            async with asyncio.timeout(route.deadline_seconds):
                counted=await self.client.messages.count_tokens(**request)
                if type(counted.input_tokens) is not int or not 1<=counted.input_tokens<=route.max_input_tokens:raise ValueError('input token budget exceeded')
                message=await self.client.messages.create(**request,max_tokens=route.max_output_tokens)
            if (message.model!=self.model_id or message.stop_reason!='end_turn' or
                not isinstance(message.id,str) or not re.fullmatch(r'msg_[A-Za-z0-9_-]{1,240}',message.id)):
                raise ModelResponseUnknown('model response incomplete, refused or unverified')
            texts=[]
            for block in message.content:
                if block.type=='thinking':continue # Never persist reasoning.
                if block.type!='text':raise ModelResponseUnknown('model tool or nontext output blocked')
                texts.append(block.text)
            if len(texts)!=1 or self._api_key in texts[0] or len(texts[0].encode())>MAX_RESPONSE_BYTES:raise ModelResponseUnknown('bounded model text unavailable')
            usage=message.usage
            input_tokens,output_tokens=usage.input_tokens,usage.output_tokens
            if type(input_tokens) is not int or type(output_tokens) is not int or input_tokens<0 or output_tokens<0:raise ModelResponseUnknown('typed model usage unavailable')
            if input_tokens>route.max_input_tokens or output_tokens>route.max_output_tokens:raise ModelResponseUnknown('model usage outside admitted bounds')
            parsed=json.loads(texts[0]);assessment=validate_live_proposal(parsed,basis)
            return {'provider_ref':message.id,'proposal':parsed,'assessment':assessment,
                    'usage':{'input_tokens':input_tokens,'output_tokens':output_tokens,'total_tokens':input_tokens+output_tokens},
                    'model_id':self.model_id,'prompt_version':route.prompt_version}
        except ModelResponseUnknown:
            raise
        except (anthropic.APIError,TimeoutError,ValueError,UnicodeError,KeyError,TypeError,AttributeError) as error:
            raise ModelResponseUnknown('model acceptance, result or usage is unknown') from error
