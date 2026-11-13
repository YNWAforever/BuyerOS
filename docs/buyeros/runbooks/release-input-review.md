# Private release-input review

This owner-only review path helps reconstruct the reviewed configuration when the original local contract files are unavailable. It does not change protected inputs, rebind a source, collect acceptance, deploy or promote.

## Preconditions

The helper must be merged to main and invoked through `buyeros-release-input-review.yml`. Only a fresh manual dispatch by the repository owner (actor ID `201698560`) on main is allowed. The job uses `buyeros-runtime-readonly` and its normal branch/review restrictions, with read-only repository permissions. A rerun must be replaced by a new owner dispatch.

Generate an ephemeral RSA recipient key (2048–4096 bits) on the backend host. Keep its private key outside the checkout and outside any preview server's filesystem root. Only the public PEM is provided as workflow input `recipient_public_key`; no private key or credential is an input.

## What the job reads and returns

The job validates the existing API seed with the closed API/account validator and the four distinct protected credential/hash bindings. It validates the existing schema seed with `SchemaContract`. It uses the protected schema-check DSN only to compute credential-free database and endpoint fingerprints; it makes no database or network calls.

The private review payload contains only the validated API/schema metadata, their original source fields, current-source match flags and database-target fingerprints. It explicitly carries `promotable=false`, `acceptance=false` and `deployment_binding_verified=false`. Stale source fields are retained for review. Tokens, DSNs, cookie secrets and arbitrary environment values are never included. A known injected credential accidentally appearing in metadata causes a refusal.

No plaintext payload file is written. The job uploads only `buyeros-private-release-input-review-encrypted`, retained for one day. Safe logs include status, the dispatch source SHA and recipient public-key fingerprint; failures use a fixed diagnostic.

## Encryption protocol

The envelope schema is `buyeros.private-release-input-review-envelope.v1`, algorithm `RSA-OAEP-SHA256+A256GCM`. It contains a recipient SHA256 fingerprint of DER SubjectPublicKeyInfo, a base64 RSA-wrapped AES-256 key, a base64 12-byte nonce and a base64 ciphertext including the GCM tag.

RSA uses OAEP SHA256 with MGF1 SHA256 and label `buyeros.release-input-review.v1`. AES-GCM authenticated data is canonical UTF-8 JSON of exactly `schema`, `algorithm` and `recipient_key_sha256`, with sorted keys, compact separators and non-ASCII preservation. Compare the recipient fingerprint before decryption and reject any authenticated-data/tag failure. Decrypt only on the backend host into a private location outside the preview root; never paste the result into chat or commit it.

## After review

Compare the actual protected seed fingerprints and account scopes with independently verified provider/identity/membership/revocation records. Reconfirm final main and exact-source CI. Build fresh reviewed records only after resolving mismatches; do not merely replace a source hash in a stale packet. Fresh credentials must be independently bound to the intended principals.

This artifact is configuration review material. It cannot replace the staged runtime/database binding, real G0 controls, authenticated candidate and rollback acceptance, attestations, protected approvals or promotion intent controls.
