# C61-01 fix integration decision

Recorded 2026-10-07 Asia/Hong_Kong; actual UTC timestamp is in baseline-integrity.json.

Use native isolated worktree based on fetched remote main a78859f. The original
checkout was clean at 671fed7; audit and latest Q13/compatibility checkouts are
clean at 55f8133/e17b699. Neon migration worktree is dirty at a78859f and is
untouched. No on-disk AGENTS.md was found in the root/ancestor paths; the user's
supplied graph-first instructions apply. Code graph BuyerOS-C61 is scoped to
this new worktree; source locations must be checked against its current HEAD.

The outer implementation ZIP hash is
`1287550e1f3b9b6f0ce3f8d6fe96137edfca616502091d40007904d6dfa99d19`.
The nested audit ZIP hash is
`eaa797614dfa6baec8c91d92fe28a9a8c90bcdec9dcd96d0602ef8ec4c85262d`:
75 members, 74 manifest matches. All 114 original case fields are preserved;
16 C61T cases remain not-run. These are evidence integrity checks, not product
acceptance. The 32 source snapshot paths are classified as changed/added/same
against main in baseline-integrity.json.

Fetched main remains a78859f, reviewed Q branch remains bbaf8ec. PR11's recorded
base is codex/n00-native-ipc-isolation; it did not deliver Q fixes to main. The
historical CI tree is preserved from E07. Its ephemeral checkout Git object is
not available locally, so current ci_tree is null rather than inferred.

Adopt Q01-08/Q12/Q14/Q15 plus their necessary existing Q09/revocation/cleanup
and CI-contract followups using the exact commit/path selection JSON. Preserve
public operations and source-generated types. Each group is separately reviewed,
focused tested, and committed. Do not copy historical generated test/build
artifacts into the new branch, and do not merge the Neon spike history into main.
Review peer fa198ae for C61-06 only after C61-02 verification. Q10 tools and Q11
capability guidance remain assigned to their own downstream tasks.

C61-01 produces a release-candidate manifest with all unobserved live fields null.
C61-04 needs driver/SQLSTATE and matching incident context. Historical
OperationalError alone cannot unlock C61-05 or prove pool/cold-start failure.
Production auth, paid provider calls, sending, and deployment remain separate
external gates; none is authorized by an audit fixture or PR merge.

Rollback: discard this branch/worktree if unadopted. Do not reset original
branches, downgrade append-only migrations, delete unknown/accepted intent, or
overwrite audit results.
