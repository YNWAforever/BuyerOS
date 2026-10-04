# Diff hygiene

Full staged diff --check returns2 for captured producer trailing whitespace and raw source.patch blank context lines. Preserve original bytes; do not trim evidence or patch. Authored code commit2f14645 passed diff check, and authored checkpoint/RESULTS/COMMANDS/RULINGS/SUMMARY paths pass targeted --check exit0. This is a formatting scope distinction, not a test/DB skip suppression. Actual acceptance still has two callback failures. Raw full output retained; exact byte hashes verified against Git index.
