# Increment 2.3 contract — composer attachments via the existing ingest path

Status: implementation contract. UI-only; the upload client and the thread-sources
API already exist.

## What exists (verified)

- `services/live/document-upload.ts` `createDocumentUpload(client, storage).upload(
  file, ctx, onProgress)` — resumable, idempotent, hashed chunked upload of
  pdf/txt/md (5 MiB) and pptx (20 MiB), returning the ingested `Document`; the
  native offer-documents screen already uses it.
- `ConversationThreads.sources(thread, sources)` — `PUT …/conversation-threads/
  {id}/sources` with the thread version as If-Match, storing `{id,label}` refs.
- Grounding already resolves thread sources; the context panel already renders
  document sources with their ingestion status.
- Turn requests do not carry per-turn documents; attachments are thread sources.

## Contract

- In an existing discussion, the composer gains an **Attach** control (file input,
  no new modality) available only when the surface is live, the viewer has edit
  access (owner/editor), a thread exists, and no upload is in flight. It is hidden
  on `/new` (a discussion must exist before a source can be attached; this is a
  documented limitation, not a workaround).
- Selecting a file reuses the existing uploader unchanged: the same accepted
  formats, the same size limits, the same resumable/idempotent behaviour, and its
  own honest messages on rejection. Do not duplicate or re-word those limits.
- Progress is shown without adding secondary prose: a determinate progress
  indicator with an accessible value, and nothing else.
- On successful ingestion, the document is added to the thread sources as
  `document:<id>` with the existing allowlisted label, using the current thread
  version. An already-attached document is not duplicated. A stale-version
  conflict refetches the thread and retries once; a second failure is an honest
  error, never a silently dropped attachment.
- The uploaded document must appear in the context panel with its ingestion status
  (the existing source presentation), and a turn sent afterwards grounds on it.
- Failures are honest and recoverable: rejected file (uploader message), upload
  failure (retry), attach failure (retry), no access (control absent). No
  optimistic "attached" state that is not persisted.
- Viewer or archived threads: the control is absent, and no request is issued.
- EN + zh-HK for every new string; keyboard operable; the file input is labelled.

## Non-goals

- No server change: no new endpoint, no part type, no schema change.
- No per-message attachments, no drag-and-drop redesign, no image uploads.
- No change to upload limits or to the native uploader.

## Tests

- Unit: attachment state machine (idle → uploading(progress) → attaching → attached;
  failure branches; duplicate suppression; retry-once-on-stale; abort on unmount).
- Browser gate: in a persisted thread, attach a fixture file → the upload endpoints
  receive exactly the expected calls, the thread sources PUT carries
  `document:<id>` and the current version, the context panel shows the source, and
  the composer returns to idle; a viewer sees no attach control and issues no
  request; a failed attach shows the honest notice; zh-HK label. Keep the existing
  23 cases' strength and five original screenshots.
- Report the new core count (currently 154).
