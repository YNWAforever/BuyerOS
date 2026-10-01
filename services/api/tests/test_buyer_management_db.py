"""T09 durable buyer review, owner/note and list management on disposable PostgreSQL."""
import psycopg
import uuid

from tests.contract_validation import assert_contract_response
from tests.test_buyer_review_db import (
    PROJECT_A, WORKSPACE_A, REVIEWER, OPERATOR, _h, _seed_buyer, api,
)


def _review(api, buyer_id, *, version=1, status="accepted", key="t09-review"):
    return api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "explicit", "buyers": [{"id": buyer_id, "version": version}]},
              "status": status, "reason": "Reviewed source evidence"},
        headers=_h(subject=REVIEWER, key=key),
    )


def test_review_requires_an_assessment_and_never_hides_a_stored_acceptance(api, seeded):
    buyer_id = _seed_buyer(seeded, name="No assessment buyer")
    response = _review(api, buyer_id)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["updated"] == 0
    assert response.json()["data"]["blocked"] == 1
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM human_reviews WHERE project_buyer_id=%s", (buyer_id,)).fetchone()[0] == 0


def test_create_and_read_list_are_durable_contract_responses(api):
    created = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/lists",
        json={"name": "Priority accounts"}, headers=_h(subject=OPERATOR, key="t09-list-create"),
    )
    assert created.status_code == 201, created.text
    assert_contract_response("BuyerListResponse", created.json())
    list_id = created.json()["data"]["id"]
    listed = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/lists", headers=_h())
    assert listed.status_code == 200, listed.text
    assert_contract_response("BuyerListPageResponse", listed.json())
    assert list_id in {row["id"] for row in listed.json()["data"]["items"]}
    one = api.get(f"/v1/workspaces/{WORKSPACE_A}/lists/{list_id}", headers=_h())
    assert one.status_code == 200, one.text
    assert_contract_response("BuyerListResponse", one.json())


def test_buyer_note_accepts_the_contract_limit_and_returns_exact_replay(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Long note buyer")
    note = "N" * 5000
    headers = _h(subject=OPERATOR, key="t09-note", **{"If-Match": '"1"'})
    first = api.patch(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", json={"note": note}, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["note"] == note
    assert_contract_response("BuyerResponse", first.json())
    replay = api.patch(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", json={"note": note}, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"] == first.json()["data"]
    assert replay.headers["ETag"] == first.headers["ETag"]


def test_stale_fit_cannot_be_accepted_as_a_current_review(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Old fit buyer", fit="match")
    with psycopg.connect(seeded, autocommit=True) as conn:
        new_icp = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash,basis_offer_revision) "
            "VALUES (%s,%s,%s,2,'{}'::jsonb,%s,1)",
            (new_icp, WORKSPACE_A, PROJECT_A, "sha256:" + "2" * 64),
        )
        conn.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (new_icp, PROJECT_A))
    response = _review(api, buyer_id, key="t09-stale-fit")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["blocked"] == 1
    assert response.json()["data"]["updated"] == 0
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM human_reviews WHERE project_buyer_id=%s", (buyer_id,)).fetchone()[0] == 0


def test_each_human_review_state_appends_exact_assessment_and_audit(api, seeded):
    for status in ("accepted", "rejected", "needs_information"):
        buyer_id = _seed_buyer(seeded, name=f"Review {status}", fit="match")
        response = _review(api, buyer_id, status=status, key=f"t09-{status}")
        assert response.status_code == 200, response.text
        assert response.json()["data"]["updated"] == 1
        assert_contract_response("BulkResultResponse", response.json())
        detail = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h()).json()["data"]
        assert detail["review"]["status"] == status
        assert detail["review"]["assessment_id"] == detail["fit"]["id"]
        assert detail["review"]["icp_version_id"] == detail["fit"]["icp_version_id"]
    with psycopg.connect(seeded) as conn:
        assert conn.execute(
            "SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='buyer.reviewed'",
            (WORKSPACE_A,),
        ).fetchone()[0] == 3


def _new_list(api, key="t09-new-list"):
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/lists",
        json={"name": "Priority accounts"}, headers=_h(key=key),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_list_add_duplicate_remove_keeps_buyer_company_and_evidence(api, seeded):
    from tests.test_buyer_review_db import _seed_evidence
    buyer_id = _seed_buyer(seeded, name="Durable list buyer", fit="match")
    with psycopg.connect(seeded) as conn:
        company_id = conn.execute("SELECT company_id FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0]
    evidence_id = _seed_evidence(seeded, buyer_id, company_id)
    list_id = _new_list(api, key="t09-members-list")
    path = f"/v1/workspaces/{WORKSPACE_A}/lists/{list_id}/memberships"
    selection = {"kind": "explicit", "buyers": [{"id": buyer_id, "version": 1}]}
    first = api.post(path, json={"selection": selection, "operation": "add"}, headers=_h(key="t09-add-once", **{"If-Match": '"1"'}))
    assert first.status_code == 200, first.text
    assert_contract_response("BulkResultResponse", first.json())
    assert first.json()["data"]["updated"] == 1
    again = api.post(path, json={"selection": selection, "operation": "add"}, headers=_h(key="t09-add-again", **{"If-Match": '"2"'}))
    assert again.status_code == 200 and again.json()["data"]["updated"] == 0
    assert again.json()["data"]["results"][0]["status"] == "unchanged"
    assert api.get(f"/v1/workspaces/{WORKSPACE_A}/lists/{list_id}", headers=_h()).json()["data"]["member_count"] == 1
    removed = api.post(path, json={"selection": selection, "operation": "remove"}, headers=_h(key="t09-remove-once", **{"If-Match": '"2"'}))
    assert removed.status_code == 200 and removed.json()["data"]["updated"] == 1
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM list_memberships WHERE list_id=%s", (list_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM companies WHERE id=%s", (company_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM evidence WHERE id=%s", (evidence_id,)).fetchone()[0] == 1


def test_list_rejects_foreign_project_buyer_and_stale_rename(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Own project buyer")
    list_id = _new_list(api, key="t09-scope-list")
    with psycopg.connect(seeded, autocommit=True) as conn:
        other_project = str(uuid.uuid4())
        other_buyer = str(uuid.uuid4())
        company_id = conn.execute("SELECT company_id FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0]
        conn.execute(
            "INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) "
            "VALUES (%s,%s,'Other','Other','offer','{US}','{en}',1)",
            (other_project, WORKSPACE_A),
        )
        conn.execute(
            "INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",
            (other_buyer, WORKSPACE_A, other_project, company_id),
        )
    changed = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/lists/{list_id}/memberships",
        json={"selection": {"kind": "explicit", "buyers": [{"id": other_buyer, "version": 1}]}, "operation": "add"},
        headers=_h(key="t09-cross-project", **{"If-Match": '"1"'}),
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["blocked"] == 1 and changed.json()["data"]["updated"] == 0
    rename_path = f"/v1/workspaces/{WORKSPACE_A}/lists/{list_id}"
    renamed = api.patch(rename_path, json={"name": "Renamed"}, headers=_h(key="t09-list-rename", **{"If-Match": '"1"'}))
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["version"] == 2
    assert_contract_response("BuyerListResponse", renamed.json())
    stale = api.patch(rename_path, json={"name": "Overwrite"}, headers=_h(key="t09-list-stale", **{"If-Match": '"1"'}))
    assert stale.status_code == 412
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM project_buyers WHERE id=%s", (other_buyer,))
        conn.execute("DELETE FROM projects WHERE id=%s", (other_project,))


def test_filter_presets_are_actor_scoped_and_reject_unsupported_filters(api):
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/filter-presets"
    body = {"name": "Matches", "filters": {"fit": ["match"], "q": "Sensors"}, "sort": "best_fit"}
    saved = api.post(path, json=body, headers=_h(subject=OPERATOR, key="t09-preset-save"))
    assert saved.status_code == 201, saved.text
    assert_contract_response("FilterPresetResponse", saved.json())
    own = api.get(path, headers=_h(subject=OPERATOR))
    assert own.status_code == 200 and own.json()["data"]["total"] == 1
    assert_contract_response("FilterPresetPageResponse", own.json())
    other = api.get(path, headers=_h(subject=REVIEWER))
    assert other.status_code == 200 and other.json()["data"]["total"] == 0
    unsupported = api.post(
        path, json={"name": "Unsupported", "filters": {"markets": ["US"]}, "sort": "best_fit"},
        headers=_h(subject=OPERATOR, key="t09-preset-reject"),
    )
    assert unsupported.status_code == 422


def test_buyer_update_replay_returns_first_version_after_later_edit(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Replay context buyer")
    path = f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}"
    first_headers = _h(key="t09-first-edit", **{"If-Match": '"1"'})
    first = api.patch(path, json={"note": "first"}, headers=first_headers)
    assert first.status_code == 200, first.text
    second = api.patch(path, json={"note": "second"}, headers=_h(key="t09-second-edit", **{"If-Match": '"2"'}))
    assert second.status_code == 200, second.text
    replay = api.patch(path, json={"note": "first"}, headers=first_headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"] == first.json()["data"]
    assert replay.headers["ETag"] == first.headers["ETag"]


def test_note_does_not_revise_draft_and_material_review_invalidates_approval(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Approval context buyer", fit="match")
    draft_id, approval_id = str(uuid.uuid4()), str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) "
            "VALUES (%s,%s,%s,%s,1,'approved')",
            (draft_id, WORKSPACE_A, PROJECT_A, buyer_id),
        )
        conn.execute(
            "INSERT INTO approvals(id,workspace_id,draft_id,revision_number,content_hash,context_fingerprint,approver_id) "
            "VALUES (%s,%s,%s,1,%s,%s,%s)",
            (approval_id, WORKSPACE_A, draft_id, "sha256:" + "a" * 64, "sha256:" + "b" * 64, str(uuid.uuid4())),
        )
    note = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "Internal note"}, headers=_h(key="t09-note-draft", **{"If-Match": '"1"'}),
    )
    assert note.status_code == 200, note.text
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT current_revision FROM outreach_drafts WHERE id=%s", (draft_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT invalidated_reason FROM approvals WHERE id=%s", (approval_id,)).fetchone()[0] is None
    reviewed = _review(api, buyer_id, version=2, key="t09-review-invalidates")
    assert reviewed.status_code == 200 and reviewed.json()["data"]["updated"] == 1
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT invalidated_reason FROM approvals WHERE id=%s", (approval_id,)).fetchone()[0] == "buyer_review_changed"
        assert conn.execute("SELECT current_revision FROM outreach_drafts WHERE id=%s", (draft_id,)).fetchone()[0] == 1
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM approvals WHERE id=%s", (approval_id,))
        conn.execute("DELETE FROM outreach_drafts WHERE id=%s", (draft_id,))


def test_0014_migration_owns_preset_rls_and_disposable_rollback(migrated, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from tests.test_buyer_review_db import ALEMBIC_INI, SERVICE_ROOT

    monkeypatch.setenv("BUYEROS_DATABASE_URL", migrated)
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    with psycopg.connect(migrated) as conn:
        before = conn.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='filter_presets'"
        ).fetchone()
        assert before == (True, True)
        assert conn.execute(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name='project_buyers' AND column_name='note'"
        ).fetchone()[0] == 20000
    command.downgrade(config, "0013_project_link_constraints")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT to_regclass('filter_presets')").fetchone()[0] is None
        assert conn.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name='buyer_lists' AND column_name='version'"
        ).fetchone()[0] == 0
    command.upgrade(config, "0014_buyer_management")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT to_regclass('filter_presets')").fetchone()[0] == "filter_presets"
        assert conn.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0] == "0014_buyer_management"
    command.upgrade(config, "head")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0035_worker_recovery_probe"


def test_list_filter_freezes_membership_and_refreezes_after_remove(api, seeded):
    first_id = _seed_buyer(seeded, name="In list")
    _seed_buyer(seeded, name="Outside list")
    list_id = _new_list(api, key="t09-list-filter")
    membership_path = f"/v1/workspaces/{WORKSPACE_A}/lists/{list_id}/memberships"
    selection = {"kind": "explicit", "buyers": [{"id": first_id, "version": 1}]}
    added = api.post(membership_path, json={"selection": selection, "operation": "add"},
                     headers=_h(key="t09-list-filter-add", **{"If-Match": '"1"'}))
    assert added.status_code == 200 and added.json()["data"]["updated"] == 1
    snapshot_path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots"
    body = {"filters": {"list_id": list_id}, "sort": "name_asc", "requested_limit": 10}
    frozen = api.post(snapshot_path, json=body, headers=_h(key="t09-list-filter-frozen"))
    assert frozen.status_code == 201, frozen.text
    assert frozen.json()["data"]["total"] == 1
    removed = api.post(membership_path, json={"selection": selection, "operation": "remove"},
                       headers=_h(key="t09-list-filter-remove", **{"If-Match": '"2"'}))
    assert removed.status_code == 200 and removed.json()["data"]["updated"] == 1
    page_path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers"
    old_page = api.get(page_path, params={"snapshot_id": frozen.json()["data"]["id"]}, headers=_h())
    assert old_page.status_code == 200 and [row["id"] for row in old_page.json()["data"]["items"]] == [first_id]
    refreshed = api.post(snapshot_path, json=body, headers=_h(key="t09-list-filter-refrozen"))
    assert refreshed.status_code == 201 and refreshed.json()["data"]["total"] == 0


def test_preset_same_name_upserts_one_versioned_actor_record(api):
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/filter-presets"
    initial = {"name": "Focus", "filters": {"q": "First"}, "sort": "name_asc"}
    replacement = {"name": "Focus", "filters": {"q": "Second"}, "sort": "best_fit"}
    first = api.post(path, json=initial, headers=_h(subject=OPERATOR, key="t09-preset-upsert-first"))
    assert first.status_code == 201, first.text
    second = api.post(path, json=replacement, headers=_h(subject=OPERATOR, key="t09-preset-upsert-second"))
    assert second.status_code == 201, second.text
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert second.json()["data"]["version"] == 2
    assert second.json()["data"]["filters"] == {"q": "Second"}
    own = api.get(path, headers=_h(subject=OPERATOR))
    assert own.status_code == 200 and own.json()["data"]["total"] == 1
    assert_contract_response("FilterPresetPageResponse", own.json())
    replay = api.post(path, json=initial, headers=_h(subject=OPERATOR, key="t09-preset-upsert-first"))
    assert replay.status_code == 201 and replay.json()["data"] == first.json()["data"]
    other = api.get(path, headers=_h(subject=REVIEWER))
    assert other.status_code == 200 and other.json()["data"]["total"] == 0


def test_membership_change_requires_current_list_version(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Versioned list member")
    list_id = _new_list(api, key="t09-list-version")
    path = f"/v1/workspaces/{WORKSPACE_A}/lists/{list_id}/memberships"
    body = {"selection": {"kind": "explicit", "buyers": [{"id": buyer_id, "version": 1}]}, "operation": "add"}
    missing = api.post(path, json=body, headers=_h(key="t09-members-no-version"))
    assert missing.status_code == 400
    good = api.post(path, json=body, headers=_h(key="t09-members-current", **{"If-Match": '"1"'}))
    assert good.status_code == 200 and good.json()["data"]["updated"] == 1
    stale = api.post(path, json=body, headers=_h(key="t09-members-stale", **{"If-Match": '"1"'}))
    assert stale.status_code == 412
    replay = api.post(path, json=body, headers=_h(key="t09-members-current", **{"If-Match": '"1"'}))
    assert replay.status_code == 200 and replay.json()["data"] == good.json()["data"]


def test_preset_rejects_nonexistent_list_filter_before_persisting(api):
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/filter-presets"
    body = {"name": "Invalid list", "filters": {"list_id": str(uuid.uuid4())}, "sort": "name_asc"}
    missing = api.post(path, json=body, headers=_h(key="t09-preset-missing-list"))
    assert missing.status_code == 404, missing.text
    body["filters"]["list_id"] = "not-a-uuid"
    malformed = api.post(path, json=body, headers=_h(key="t09-preset-malformed-list"))
    assert malformed.status_code == 422, malformed.text
    own = api.get(path, headers=_h())
    assert own.status_code == 200 and own.json()["data"]["total"] == 0
