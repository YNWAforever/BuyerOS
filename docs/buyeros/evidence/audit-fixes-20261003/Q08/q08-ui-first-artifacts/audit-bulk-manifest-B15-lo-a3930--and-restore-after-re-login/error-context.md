# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-bulk-manifest.spec.ts >> B15 lost preview and committed 202 retry one frozen body/key and restore after re-login
- Location: tests\e2e\audit-bulk-manifest.spec.ts:45:1

# Error details

```
Error: Command failed: C:\Users\laich\.codex\worktrees\audit-fixes-20261003\BuyerOS\services\worker\.venv\Scripts\python.exe tests/fixtures/audit_manifests.py seed 101
Traceback (most recent call last):
  File "C:\Users\laich\.codex\worktrees\audit-fixes-20261003\BuyerOS\services\worker\tests\fixtures\audit_manifests.py", line 66, in <module>
    if __name__=='__main__':main()
                            ~~~~^^
  File "C:\Users\laich\.codex\worktrees\audit-fixes-20261003\BuyerOS\services\worker\tests\fixtures\audit_manifests.py", line 30, in main
    db.execute('DELETE FROM project_buyers WHERE workspace_id=%s AND company_id=%s',(WORKSPACE,company))
    ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\laich\.codex\worktrees\audit-fixes-20261003\BuyerOS\services\worker\.venv\Lib\site-packages\psycopg\connection.py", line 300, in execute
    raise ex.with_traceback(None)
psycopg.errors.ForeignKeyViolation: update or delete on table "project_buyers" violates foreign key constraint "fk_buyer_snapshot_items_buyer_project" on table "buyer_snapshot_items"
DETAIL:  Key (workspace_id, project_id, id)=(e0000000-0000-4000-8000-000000000001, e1000000-0000-4000-8000-000000000001, f8e62f75-8e1c-553d-9031-722569281b50) is still referenced from table "buyer_snapshot_items".

```