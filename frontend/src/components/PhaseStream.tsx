import { useEffect, useState } from "react";
import type { Phase } from "../types";

/** Agent-zero-style reasoning trail: phase lines fade in as the engine
 * reports them; the active line carries a spinner; the trail
 * auto-collapses when the answer lands but stays reviewable. */
export default function PhaseStream({
  phases,
  live,
}: {
  phases: Phase[];
  live: boolean;
}) {
  const [open, setOpen] = useState(true);

  // Mirror the old chat behavior: collapse once the answer starts.
  useEffect(() => {
    if (!live) setOpen(false);
  }, [live]);

  if (phases.length === 0 && !live) return null;

  return (
    <div className="phases">
      <div className="phases-summary" onClick={() => setOpen((o) => !o)}>
        {live ? (
          <>
            <span className="spinner" />
            <span className="thinking-label">
              {phases.length ? phases[phases.length - 1].label : "Thinking…"}
            </span>
          </>
        ) : (
          <>
            <span className="phase-icon">✓</span>
            <span>
              reasoning · {phases.length} step{phases.length === 1 ? "" : "s"}
            </span>
            <span style={{ marginLeft: "auto" }}>{open ? "▾" : "▸"}</span>
          </>
        )}
      </div>
      {open && (
        <div>
          {phases.map((p, i) => {
            const isActive = live && i === phases.length - 1;
            return (
              <div
                key={`${p.stage}-${i}`}
                className={`phase-line${isActive ? " active" : ""}`}
              >
                <span className="phase-icon">
                  {isActive ? <span className="spinner" /> : "✓"}
                </span>
                <span>{p.label}</span>
                <span className="phase-detail">{detail(p)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function detail(p: Phase): string {
  const bits: string[] = [];
  if (typeof p.evidence_count === "number")
    bits.push(`${p.evidence_count} chunks`);
  if (typeof p.graph_fact_count === "number")
    bits.push(`${p.graph_fact_count} relationships`);
  if (typeof p.items === "number") bits.push(`${p.items} items`);
  if (Array.isArray(p.corpora)) bits.push((p.corpora as string[]).join(", "));
  if (p.counts && typeof p.counts === "object")
    bits.push(
      Object.entries(p.counts as Record<string, number>)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => `${v} ${k}`)
        .join(" · "),
    );
  return bits.join(" · ");
}
