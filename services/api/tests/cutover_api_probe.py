"""Cold subprocess imports only the pinned archive; no Principal override."""
import json,sys
# Match the existing owned API test harness; psycopg async does not support
# the Windows Proactor loop. Linux production needs no platform adjustment.
if sys.platform=='win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from pathlib import Path
from fastapi.testclient import TestClient
from buyeros_api.api import auth,verifier
from buyeros_api.api.app import create_app
data=json.load(sys.stdin)
assert Path(auth.__file__).resolve().parent.parent==Path(data['expected_package']).resolve()
fetched=[]
async def fetch(url):
    assert url==data['issuer']+'/jwks','Unexpected provider URL in offline rollback probe'
    fetched.append(url);return {'keys':[data['jwk']]}
verifier.fetch_jwks_document=fetch
result={'statuses':{},'codes':{},'canonical_project_ids':{},'ready':None,'auth_package_from_archive':True,'exception_metadata':{}}
with TestClient(create_app(),raise_server_exceptions=True) as api:
    for name,token in data['tokens'].items():
        try:
            response=api.get(f"/v1/workspaces/{data['workspace']}/projects/{data['project']}",headers={'Authorization':'Bearer '+token})
        except Exception as error:
            chain=[];current=error
            for _ in range(5):
                if current is None:break
                chain.append({'type':type(current).__name__,'sqlstate':getattr(current,'sqlstate',None)})
                current=current.__cause__ or current.__context__
            result['exception_metadata'][name]=chain
            result['statuses'][name]=500;result['codes'][name]='INTERNAL_ERROR'
            continue
        result['statuses'][name]=response.status_code;result['codes'][name]=response.json().get('code')
        if response.status_code==200:result['canonical_project_ids'][name]=response.json()['data']['id']
    if result['statuses']['migrated']==200:
        response=api.get(f"/v1/workspaces/{data['workspace']}/readiness",headers={'Authorization':'Bearer '+data['tokens']['migrated']})
        assert response.status_code==200,response.text
        result['ready']=response.json()['data']['ready']
result['approved_JWKS_fetches']=len(fetched)
print(json.dumps(result))
