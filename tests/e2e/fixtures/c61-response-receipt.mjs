/** Metadata receipt for an owned fixture response; no product or live acceptance. */
export async function responseReceipt(response) {
  const path = new URL(response.url()).pathname;
  const headers = response.headers();
  let request_id = headers['x-request-id'] ?? null;
  if (request_id === null && headers['content-type']?.includes('json')) {
    const body = await response.json().catch(() => ({}));
    request_id = body.request_id ?? null;
  }
  return {path, method: response.request().method(), status: response.status(), request_id};
}
