import type { ReadyState, Verdict } from "../lib/readiness";

/** The readiness pill. Renders the backend's own verdict word — never a paraphrase. */
export function Pill({ v, title }: { v: Verdict; title?: string }) {
  return (
    <span className={`pill pill--${v.state}`} title={title ?? v.detail ?? v.label}>
      <span className="pill__dot" />
      {v.label}
    </span>
  );
}

export function StatePill({ state, label }: { state: ReadyState; label: string }) {
  return <Pill v={{ state, label }} />;
}
