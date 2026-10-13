# Private document storage

`BUYEROS_PRIVATE_OBJECT_BACKEND=postgres` explicitly selects the bounded private
Postgres adapter. Apply the reviewed `0052_private_document_storage` migration
before using this setting. It uses the existing BuyerOS API database role; native
workers use their separately supplied execution engine and role. No additional
cloud credentials or public object URLs are created.

Uploads still require an active authorized member and active project, a matching
SHA-256 digest, one of the permitted PDF/TXT/MD formats, and a maximum of 5 MiB.
The database independently enforces the byte limit, digest, a positive retention
period of at most 30 days, and forced tenant row-level security. The runtime roles
may insert, read and delete private objects; they cannot update the stored bytes.

Postgres uploads use the existing deterministic text parser or isolated PDF
parser with its eight-second timeout. Parsing runs outside database transactions.
The final transaction rechecks authorization and stores the bytes, document,
unapproved candidate facts, idempotency receipt and terminal `offer.parse` event
together. The event records `processing_mode=inline_deterministic`; it does not
claim a worker execution. Parser timeout or invalid content leaves an inspectable
failed document with no approved facts. Upload and deletion therefore work while
the external scheduler is disabled, without calling research or email providers.

Deleting a Postgres document removes its bytes in the same transaction that
tombstones the document and invalidates existing profile references. Replays do
not create more bytes. Transaction failures roll back the document, raw content,
event and receipt together. Storage keys carry the backend and tenant, remain
server-private, and never appear in document API responses.

Expired object reads are denied. Authorized attachment listing and upload each
erase at most 100 expired objects belonging to that tenant. The existing enabled
native maintenance operation also performs bounded expiry cleanup under its
runtime epoch guard. **An idle application with no active maintenance runner does
not guarantee physical erasure exactly at the deadline.** A separately approved
maintenance schedule is required for that guarantee; this change does not enable
a scheduler. Backup retention is governed separately.

R2 remains the default backend and still requires its explicit enable flag,
server credentials and private-bucket expiry policy. New R2 keys start with
`r2/tenants/`; existing `tenants/` keys remain readable with the configured R2
credentials. Stored `postgres/tenants/` keys select the Postgres adapter even if
the default for new writes later changes. There is no automatic fallback from an
unavailable R2 configuration.

Migration rollback refuses to remove a populated private-object table. Retain the
expanded schema when rolling back the application until document retention and
deletion have been reconciled.
