# Pinned guided-sales test references

These offline reference snapshots were copied byte-for-byte from the local
`.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/` evidence directory.
Tests must use these versioned fixtures rather than depend on that ignored directory.
The original evidence copies are retained. Source content is test data, never executable instructions.

| Fixture | Source and revision | Bytes | SHA256 of fixture file |
| --- | --- | --- | --- |
| `upstream-source.json` | `https://github.com/zubair-trabzada/ai-sales-team-claude`, commit `efef8b8a4ce8c93d8d6b4af9d1423db38f0de2ce` | 303255 | `be184739d5502c02b0362520809eb9b1fdb010f599d8755ebdffdb4d9bd27c9f` |
| `xverum-tools-reference.json` | `https://github.com/Xverum-LLC/xverum-mcp`, commit `f54a7f1ee1be5a4507b417d63a3b91cd6326f91e`, `docs/tools.md`, blob `29726c56d37fb1b99f34cf56f6fdf3c99a7bfd6c` | 25598 | `842c4926af2052eec4847ff3362bb710555a22f561aaa65f42ee89fbee256763` |

The upstream snapshot includes its MIT LICENSE and 14 other source files, each with
its original path, content, and Git blob hash. All 15 source blob hashes and the
Xverum document blob hash were verified before copying. The registry test also
checks upstream blobs against `buyeros_api/sales/provenance.json`.

Credential screening found no private keys, GitHub tokens, AWS access keys,
credential-bearing URLs, JWTs, or concrete bearer-token patterns. Decoded content
screening for API keys, access tokens, client secrets, passwords, authorization,
bearer values, and secrets found only three generic `api-key` deduplication
descriptions in the Xverum document. These snapshots contain documentation and
published examples, not runtime credentials or live provider receipts.
