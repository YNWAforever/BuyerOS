"""Fictional draft buffers/jobs in the owned disposable browser database only."""
import hashlib
import json
import sys
import uuid
import psycopg
from tests.fixtures.run_browser_research import owner_dsn,WORKSPACE
PROJECT='e1000000-0000-4000-8000-000000000001'
BASE='ec000000-0000-4000-8000-000000000001'
ACTOR='e0000000-0000-4000-8000-000000000002'
with psycopg.connect(owner_dsn()) as db:
    if db.execute('SELECT company_name FROM projects WHERE id=%s AND workspace_id=%s',(PROJECT,WORKSPACE)).fetchone()!=('Fictional Seller',):raise RuntimeError('unknown fictional project')
    if sys.argv[1:] == ['create']:
        base=db.execute('SELECT r.content,r.evidence_ids,r.offer_fact_ids,d.buyer_id FROM draft_revisions r JOIN outreach_drafts d ON d.id=r.draft_id AND d.workspace_id=r.workspace_id WHERE d.id=%s AND d.workspace_id=%s AND r.revision_number=1',(BASE,WORKSPACE)).fetchone()
        db.execute('DELETE FROM api_rate_windows WHERE workspace_id=%s AND actor_id=%s',(WORKSPACE,ACTOR))
        ids=[];subjects=[]
        for index in [1,2]:
            draft,revision=uuid.uuid4(),uuid.uuid4();content=dict(base[0]);content['subject']=f'Audit fixture {index} {str(draft)[:8]}';subjects.append(content['subject']);content['body']=f'Fictional draft {index} content';ids.append(str(draft))
            digest=hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            db.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) VALUES (%s,%s,%s,%s,1,'draft')",(draft,WORKSPACE,PROJECT,base[3]))
            db.execute('INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,content,content_hash,evidence_ids,offer_fact_ids) VALUES (%s,%s,%s,1,%s::jsonb,%s,%s::jsonb,%s::jsonb)',(revision,WORKSPACE,draft,json.dumps(content),digest,json.dumps(base[1]),json.dumps(base[2])))
        job=uuid.uuid4()
        db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested) VALUES (%s,%s,%s,%s,'draft_generation','generateDraft',%s::jsonb,'queued',1)",(job,WORKSPACE,PROJECT,ACTOR,json.dumps({'draft_id':ids[1]})))
        print(json.dumps({'draft':ids[0],'other':ids[1],'subject':subjects[0],'other_subject':subjects[1],'job':str(job),'fixture_only':True}))
    elif len(sys.argv)==3 and sys.argv[1]=='complete':
        changed=db.execute("UPDATE async_jobs SET status='completed',processed=1,updated=1,command=jsonb_set(command,'{result_draft_id}',command->'draft_id') WHERE id=%s AND workspace_id=%s AND project_id=%s AND actor_user_id=%s AND kind='draft_generation' RETURNING id",(uuid.UUID(sys.argv[2]),WORKSPACE,PROJECT,ACTOR)).fetchone()
        if not changed:raise RuntimeError('unknown fixture job')
        print(json.dumps({'fixture_only':True,'completed':str(changed[0])}))
    else:raise ValueError('bounded fixture command required')
