# Increment 2.5 contract — inline output preview in the transcript

Status: implementation contract. UI-only; the server already renders the preview.

## What exists (verified)

- `GET /v1/workspaces/{ws}/projects/{pj}/sales-outputs/{output_id}/preview?revision=N`
  (`api/routes/sales_outputs.py:138`) returns server-rendered **HTML** with
  `Content-Security-Policy: default-src 'none'; sandbox`, `Referrer-Policy:
  no-referrer`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`.
- Access is the same `access(..., sales=True, admission=False, locks=False)` path as
  the output read: owner/editor/viewer rules already apply.
- The transcript already renders an `output_link` card (`inline-parts.tsx`
  `OutputLink`) with title, status pill, revision and "Open saved output".

So this increment adds no endpoint, no migration, no authority — only the inline
preview surface and its client.

## Contract

- The output link card gains a collapsed-by-default disclosure **Preview**
  (zh-HK: 預覽).
- Expanding it fetches the preview HTML **once** (no polling), with the output's
  own revision, through the authenticated same-origin client. It must not fetch
  before expansion and must refetch only when the output id or revision changes.
- The HTML is rendered in a strictly sandboxed frame: `sandbox` with no tokens, no
  `allow-scripts`, `referrerpolicy="no-referrer"`, a bounded height, and an
  accessible title that names the output. `srcDoc` is used so the client can see
  the HTTP status before rendering.
- Bounds: response capped (e.g. 64 KiB); beyond the cap show the first part with an
  honest "preview truncated" notice instead of buffering unbounded HTML.
- Failure states are honest and non-retrying automatically: 401/403 → "You no
  longer have access to this output"; 404 → "This output is no longer available";
  other/network → "Preview unavailable" with a manual retry. The card's
  "Open saved output" action is unchanged in every state.
- No internal ids, revision hashes or API paths rendered in the ordinary UI; the
  frame's src/content is not exposed in tooltips or text.
- EN + zh-HK for every new string; the disclosure is keyboard operable and its
  state is announced.

## Non-goals

- No editing, exporting or approving from the preview; those stay on the native
  output screen.
- No second rendering path: the server remains the only author of preview HTML.
- No change to the output link part schema or the preview endpoint.

## Tests

- Unit: preview URL builder (workspace/project/output/revision encoding), size cap,
  sandbox attribute set, error-to-notice mapping.
- Browser gate: expand a preview from a persisted thread → exactly one preview
  request containing the right output id and revision, rendered in a sandboxed
  frame; no request before expand; a denied response shows the honest notice and
  no frame; "Open saved output" still present; zh-HK label.
- Existing 23 gate cases keep their strength; no new screenshots unless a stable
  visual is worth asserting.
