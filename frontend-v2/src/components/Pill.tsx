import type { ReadyState, Verdict } from "../lib/readiness";

/** The backend's own verdict word, formatted for reading: "SEMANTIC_INCOMPLETE" → "Semantic incomplete", "VNEXT READY" →
 *  "vNext ready". The words are the backend's, never a paraphrase (FRONTEND-V2-PLAN §7); the exact code stays in the tooltip. */
export function readable(label: string | null | undefined): string {
  if (!label) return "Unknown";                // a verdict the backend did not send
  const words = String(label).replace(/_/g, " ").trim().toLowerCase();
  const s = words.charAt(0).toUpperCase() + words.slice(1);
  return s.replace(/\bvnext\b/gi, "vNext").replace(/\bpmap\b/gi, "pMAP");
}

export function Pill({ v, title }: { v: Verdict; title?: string }) {
  return (
    <span className={`pill pill--${v.state}`} title={title ?? (v.detail ? `${v.label} — ${v.detail}` : v.label)} data-verdict={v.label}>
      <span className="pill__dot" />
      {readable(v.label)}
    </span>
  );
}

export function StatePill({ state, label }: { state: ReadyState; label: string }) {
  return <Pill v={{ state, label }} />;
}
