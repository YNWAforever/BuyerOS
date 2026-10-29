"""Bounded MCP transport contract, fixed read tools, and sanitized failures."""
import json
import httpx
import pytest
from buyeros_api.services import drive_mcp
from buyeros_api.api.errors import ApiError

WS='11111111-1111-4111-8111-111111111111'
PROJECT='a0000000-0000-4000-8000-000000000001'


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setenv('BUYEROS_DRIVE_MCP_URL','https://fimmick-fixture.invalid/mcp')
    monkeypatch.setenv('BUYEROS_DRIVE_MCP_TOKEN','SYNTHETIC_SECRET')
    calls=[];result={'folder_ids':['folder_one']};mode={'value':'json'}
    def handle(request):
        body=json.loads(request.content);calls.append(body)
        assert request.headers['Authorization']=='Bearer SYNTHETIC_SECRET'
        if body['method']=='initialize':
            return httpx.Response(200,json={'jsonrpc':'2.0','id':1,'result':{'protocolVersion':'2025-06-18','capabilities':{'tools':{}}}},headers={'Mcp-Session-Id':'fixture-session'})
        assert request.headers['Mcp-Session-Id']=='fixture-session'
        if body['method']=='notifications/initialized':return httpx.Response(202)
        assert body['method']=='tools/call' and body['params']['name'] in drive_mcp.TOOLS
        args=body['params']['arguments'];assert args['workspace_id']==WS and args['project_id']==PROJECT
        data={'jsonrpc':'2.0','id':2,'result':{'structuredContent':result}}
        if mode['value']=='error':return httpx.Response(401,text='SYNTHETIC_SECRET PRIVATE_BODY')
        if mode['value']=='oversize':return httpx.Response(200,content=b'x'*65537,headers={'content-type':'application/json'})
        if mode['value']=='sse':return httpx.Response(200,content='event: message\ndata: '+json.dumps(data)+'\n\n',headers={'content-type':'text/event-stream'})
        return httpx.Response(200,json=data)
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(handle)))
    return calls,result,mode


@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['json','sse'])
async def test_mcp_initialize_session_and_allowlisted_scoped_read(transport,mode):
    calls,result,options=transport;options['value']=mode
    assert await drive_mcp.adapter().call('buyeros_drive_list_folders',WS,PROJECT)==result
    assert [call['method'] for call in calls]==['initialize','notifications/initialized','tools/call']


@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['error','oversize'])
async def test_failure_never_exposes_upstream_body_or_secret(transport,mode,caplog):
    _,_,options=transport;options['value']=mode
    with pytest.raises(ApiError) as exc:await drive_mcp.adapter().call('buyeros_drive_list_folders',WS,PROJECT)
    assert exc.value.code=='DRIVE_UNAVAILABLE'
    assert 'SYNTHETIC_SECRET' not in str(exc.value) and 'PRIVATE_BODY' not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize('tool',['upload','share','delete','write','connect','list_all_files'])
async def test_unknown_and_write_tools_never_make_network_calls(transport,tool):
    calls,_,_=transport
    with pytest.raises(ApiError):await drive_mcp.adapter().call(tool,WS,PROJECT)
    assert calls==[]


@pytest.mark.asyncio
@pytest.mark.parametrize('url',['http://fimmick.invalid/mcp','https://name:secret@fimmick.invalid/mcp','https://fimmick.invalid/mcp?token=secret',''])
async def test_untrusted_endpoint_configuration_fails_closed(transport,monkeypatch,url):
    calls,_,_=transport;monkeypatch.setenv('BUYEROS_DRIVE_MCP_URL',url)
    with pytest.raises(ApiError):await drive_mcp.adapter().call('buyeros_drive_status',WS,PROJECT)
    assert calls==[]


@pytest.mark.asyncio
@pytest.mark.parametrize('bad',[{'folder_ids':['one','one']},{'folder_ids':['https://public']},{'folder_ids':['one'],'filename':'private'}, {'items':[{'id':'one','folder_id':'unapproved'}]}])
async def test_unverified_gateway_metadata_rejected(transport,monkeypatch,bad):
    async def status(*args):pass
    gateway=drive_mcp.adapter();monkeypatch.setattr(gateway,'status',status)
    _,result,_=transport;result.clear();result.update(bad)
    with pytest.raises(ApiError):
        if 'items' in bad:await gateway.items(WS,PROJECT,['approved'])
        else:await gateway.folders(WS,PROJECT)


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation',['owner','scope','workspace','project','residency','retention','secret','connected'])
async def test_status_requires_fimmick_readonly_scoped_hk_zero_retention(monkeypatch,mutation):
    value={'workspace_id':WS,'project_id':PROJECT,'oauth_owner':'fimmick',
        'scope':'https://www.googleapis.com/auth/drive.readonly','connected':True,
        'residency_preference':'HK','retention_seconds':0}
    key={'owner':'oauth_owner','workspace':'workspace_id','project':'project_id','residency':'residency_preference','retention':'retention_seconds'}.get(mutation,mutation)
    value[key]=False if mutation=='retention' else 1 if mutation=='connected' else 'unapproved'
    gateway=drive_mcp.adapter()
    async def call(*args,**kwargs):return value
    monkeypatch.setattr(gateway,'call',call)
    with pytest.raises(ApiError):await gateway.status(WS,PROJECT)
