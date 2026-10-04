# Exact diff hygiene outcomes

Source4file staging checked0 before ef0b437. Current authored metadata/docs check0. Full staged diff check2: four whitespace-only producer lines in red.log (58/60/105/107). Keep raw Node RED bytes and SHA rather than stripping original diagnostic output. This is capture formatting, not a test pass or permission to weaken tests. Full command output retained in diff-check-full.log.gz; no all-files-zero claim.

Commands: git diff --cached --check; git diff --cached --check -- :(exclude)docs/buyeros/evidence/audit-fixes-20261003/N00_REAL_PREFLIGHT/**
