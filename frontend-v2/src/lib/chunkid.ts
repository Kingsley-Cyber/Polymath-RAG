/**
 * One way to get a chunk's id out of a receipt row.
 *
 * The receipt names a chunk THREE ways depending on which section it came from:
 *   `final_detail[]` and `legend[]` carry a bare `chunk_id`
 *   `chunks[]` carries only `locator` — "chunk:<id>@<start>:<end>" — and NO chunk_id
 *
 * Joining those sections on `chunk_id` therefore silently produced ZERO matches, which
 * is how the Answer Review came to judge a well-cited answer against "0 cited passages"
 * and return 0/5 UNSUPPORTED (caught in F12, 2026-09-11). The Evidence Inspector had
 * the same latent bug: chunk rows keyed by locator never merged with scored rows keyed
 * by chunk_id, so one chunk could appear as two rows.
 */
export function chunkIdOf(row: Record<string, unknown> | null | undefined): string {
  if (!row) return "";
  const direct = row.chunk_id;
  if (typeof direct === "string" && direct) return direct;
  const loc = row.locator;
  if (typeof loc === "string" && loc) {
    // "chunk:chunk_abc123@365:564" -> "chunk_abc123"
    const body = loc.startsWith("chunk:") ? loc.slice("chunk:".length) : loc;
    const at = body.indexOf("@");
    return at === -1 ? body : body.slice(0, at);
  }
  return "";
}
