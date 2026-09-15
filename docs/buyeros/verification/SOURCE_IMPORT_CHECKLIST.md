# Source import and identity verification checklist

**Status: PROPOSED / EXECUTED (Option A).** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Option A was executed with owner authorization: the audited commit `b804ba8d1514a1049b7202c861278dd72c473a75` was pushed as branch `import-b804ba8d` and merged into `main` via `72fef7da785624a35bb6701f1451ebcf0184a089`. Options B/C below remain unexecuted.

Goal: place the audited application source into canonical repository `YNWAforever/BuyerOS` so a specific commit carries tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`, then re-verify the BO-000/BO-001 identity baseline.

## Why a plain copy is not enough

An `export`/copy of the files followed by a commit produces a commit whose tree equals the content of that commit. If `docs/buyeros/**` is already present (it is — see the planning commit `1512d4c`), the tree will include both docs and source and therefore will **not** equal `b4c6b538…`. To satisfy "exact import, same tree", bring in the **actual commit** `b804ba8d1514a1049b7202c861278dd72c473a75`, whose tree is `b4c6b538…`.

## Option A (recommended): import the audited commit as a branch, then integrate

```bash
# 1. Fetch the audited source history (read-only on buyerosgpt)
git clone https://github.com/YNWAforever/buyerosgpt.git buyerosgpt-src
cd buyerosgpt-src
git rev-parse HEAD^{tree}        # expect b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1

# 2. Push that exact commit into BuyerOS on a dedicated branch (mutates remote)
git remote add buyer https://github.com/YNWAforever/BuyerOS.git
git push buyer b804ba8d1514a1049b7202c861278dd72c473a75:refs/heads/import-b804ba8d
```

Then verify the imported commit's tree equals `b4c6b538…`, and decide how `main` should relate to it (see Option C for integration). The import branch preserves the exact tree evidence; `main` may later merge it.

## Option B: orphan commit with the exact tree (no shared history)

Create an orphan branch, check out the audited tree, and commit it; the resulting commit's tree equals `b4c6b538…` because docs are not part of it. Useful if the owner wants no history from `buyerosgpt`.

```bash
git clone https://github.com/YNWAforever/BuyerOS.git buyer
cd buyer
git checkout --orphan source-import
git rm -rf . 2>/dev/null || true
git --git-dir=../buyerosgpt-src/.git --work-tree=. checkout b804ba8d1514a1049b7202c861278dd72c473a75 -- .
git add -A
git commit -m "Import audited BuyerOS source (tree b4c6b538)"
git rev-parse HEAD^{tree}        # verify b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1
git push origin source-import
```

## Verification (run after either option)

```bash
# Local (in the BuyerOS clone)
git log --oneline -5
git rev-parse HEAD^{tree}
git status --short                    # must be clean; preserve any unrelated local edits

# Remote (GitHub API)
# GET /repos/YNWAforever/BuyerOS/commits/<import-sha>    → commit.tree.sha == b4c6b538...
# GET /repos/YNWAforever/BuyerOS/git/trees/<tree>?recursive=1  → 200, truncated=false
```

Expected: the import commit's tree is `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`; `main` and `docs/buyeros/**` remain intact.

## Integration options for `main`

| Option | Result | Trade-off |
|---|---|---|
| Merge `import-b804ba8d` into `main` | single history with docs + source | merge commit's tree is a combined tree, not `b4c6b538…` (expected) |
| Keep import on its own branch; `main` holds docs until a reviewed merge | import evidence isolated | `main` is not yet the app |
| Rebase docs onto the import commit, force-update `main` | linear history, import commit intact underneath | rewrites the docs commits; do only if the owner approves a history rewrite |

## After import

1. Follow `docs/buyeros/tasks/BO-000-...md` to re-record identity: repository, HEAD, tree, working-tree state, applicable instructions (recheck for `AGENTS.md`).
2. Update `HANDOFF_INDEX.md`, `PROGRESS.md`, and the affected identity statements to reference the actual import SHA instead of "not yet imported".
3. Only then select and approve one task (recommended `BO-005`) per `decisions/BUILD_APPROVAL_RECORD.template.md`.

## Boundaries

- Mutating the remote (pushes) requires explicit owner authorization covering the exact branch and action.
- Do not force-push `main`, rewrite history, or delete branches without a named approval.
- No application code, installs, migrations, provisioning, or provider calls occur during import.
