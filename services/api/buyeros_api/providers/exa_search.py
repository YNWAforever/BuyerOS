"""Exa company-search transport for the existing LiveSearchAdapter port.

Same contract as BraveSearchClient: one bounded request, a bounded streamed body,
and SearchResult rows whose snippets are untrusted source data. Exa has a market
filter (userLocation) but no language filter, so the registry only admits
explicitly reviewed market/language pairs (see providers/activation.py).
"""
from __future__ import annotations
import asyncio,json,re
import httpx
from .search import SearchResult
from .live_search import SearchResponseUnknown
from ..services.safe_fetch import _safe_https_url

ENDPOINT='https://api.exa.ai/search'
MAX_RESPONSE_BYTES=262144
SNIPPET_CHARACTERS=1000


class ExaSearchClient:
    def __init__(self,*,api_key:str,http:httpx.AsyncClient,search_type:str='auto'):
        if not isinstance(api_key,str) or not 1<=len(api_key)<=4096 or any(ord(c)<33 or ord(c)>126 for c in api_key):raise ValueError('server-only Exa API key required')
        if search_type not in {'instant','fast','auto'}:raise ValueError('bounded Exa search type required')
        self._api_key,self.http,self.search_type=api_key,http,search_type

    async def search(self,query:str,market:str,language:str,limit:int)->list[SearchResult]:
        if (type(limit) is not int or not 1<=limit<=20 or not isinstance(query,str) or not query.strip() or len(query)>600
                or len(query.split())>75 or not re.fullmatch(r'[A-Z]{2}',market) or not isinstance(language,str) or not 1<=len(language)<=32):
            raise ValueError('unsupported or unbounded search scope')
        body={'query':query,'type':self.search_type,'numResults':limit,'category':'company','userLocation':market,
              'contents':{'text':{'maxCharacters':SNIPPET_CHARACTERS}}}
        headers={'x-api-key':self._api_key,'Accept':'application/json','Content-Type':'application/json'}
        try:
            async with asyncio.timeout(15):
                async with self.http.stream('POST',ENDPOINT,json=body,headers=headers,follow_redirects=False,timeout=15) as response:
                    if response.status_code!=200:raise SearchResponseUnknown('vendor result unavailable')
                    raw=bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw)+len(chunk)>MAX_RESPONSE_BYTES:raise SearchResponseUnknown('vendor result exceeds limit')
                        raw.extend(chunk)
            parsed=json.loads(raw)
            if not isinstance(parsed,dict) or not isinstance(parsed.get('results'),list):raise SearchResponseUnknown('vendor result schema unavailable')
            items=parsed['results']
            if len(items)>limit:raise SearchResponseUnknown('vendor result count exceeds scope')
            results=[]
            for item in items:
                if not isinstance(item,dict) or not isinstance(item.get('url'),str) or not 1<=len(item['url'])<=2000:raise SearchResponseUnknown('vendor item schema unavailable')
                title=item.get('title') if isinstance(item.get('title'),str) and item.get('title').strip() else item['url']
                text=item.get('text') if isinstance(item.get('text'),str) else ''
                title,snippet=title[:512],' '.join(text.split())[:4000]
                if any(self._api_key in value for value in (item['url'],title,snippet)):raise SearchResponseUnknown('credential echoed in vendor data')
                checked=_safe_https_url(item['url'])
                if checked is None:raise SearchResponseUnknown('unsafe source URL')
                results.append(SearchResult(checked[0],title,snippet))
            return results
        except SearchResponseUnknown:
            raise
        except (httpx.HTTPError,TimeoutError,ValueError,UnicodeError) as error:
            raise SearchResponseUnknown('search acceptance or result is unknown') from error
