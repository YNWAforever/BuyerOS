import psycopg
from tests.lead_fixtures import ACTORS,WORKSPACE,PROJECT,headers,lead_api,lead_case

def test_n21_unassigned_filter_counts_rows_and_totals_consistently(lead_api,lead_case):
    path=f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/lead-workflow"
    response=lead_api.get(path,params={"owner_unassigned":"true"},headers=headers())
    assert response.status_code==200,response.text
    assert response.json()["data"]["total"]==1
    assert response.json()["data"]["items"][0]["owner_user_id"] is None
    with psycopg.connect(lead_case["dsn"],autocommit=True) as db:
        db.execute("UPDATE project_buyers SET owner_user_id=%s WHERE id=%s AND workspace_id=%s AND project_id=%s",
                   (ACTORS["operator"],lead_case["buyer_id"],WORKSPACE,PROJECT))
    empty=lead_api.get(path,params={"owner_unassigned":"true"},headers=headers())
    assert empty.status_code==200,empty.text
    assert empty.json()["data"]["total"]==0
    assert empty.json()["data"]["items"]==[]
    assigned=lead_api.get(path,params={"owner_user_id":str(ACTORS["operator"])},headers=headers())
    assert assigned.status_code==200,assigned.text
    assert assigned.json()["data"]["total"]==1
    ambiguous=lead_api.get(path,params={"owner_user_id":str(ACTORS["operator"]),"owner_unassigned":"true"},headers=headers())
    assert ambiguous.status_code==422,ambiguous.text
