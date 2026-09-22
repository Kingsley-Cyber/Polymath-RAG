import { useEffect, useRef, useState } from "react";
import type { Phase } from "../lib/chat";

/** PROCESS-RAIL-V2 — the Agent-Zero-style reasoning trail as a compact process
 *  rail (ported from the original Polymath UI). Live: "Working · N steps" with a
 *  spinner on the active row and the model's thinking streaming in a pane. When
 *  the turn ends it lingers, then collapses to "Worked for Ns · N steps". */
const COLLAPSE_DELAY_MS = 1800;

export function ProcessRail({
  phases, live, reasoning,
}: { phases: Phase[]; live: boolean; reasoning?: string }) {
  const [open, setOpen] = useState(true);
  const [manual, setManual] = useState(false);
  const paneRef = useRef<HTMLDivElement | null>(null);
  const startedAt = useRef<number | null>(null);
  const finishedAt = useRef<number | null>(null);

  useEffect(() => {
    if (live && startedAt.current === null) startedAt.current = Date.now();
    if (!live && startedAt.current !== null && finishedAt.current === null) finishedAt.current = Date.now();
  }, [live]);

  useEffect(() => {
    if (live) { setOpen(true); setManual(false); return; }
    if (manual) return;
    const timer = window.setTimeout(() => setOpen(false), COLLAPSE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [live, manual]);

  useEffect(() => {
    if (live && paneRef.current) paneRef.current.scrollTop = paneRef.current.scrollHeight;
  }, [live, reasoning]);

  if (phases.length === 0 && !live && !reasoning) return null;

  const steps = phases.length;
  const stepWord = `${steps} step${steps === 1 ? "" : "s"}`;
  const toggle = () => { setManual(true); setOpen((o) => !o); };

  return (
    <div className={`phases${live ? " live" : ""}${open ? " open" : ""}`}>
      <div
        className="phases-summary"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={toggle}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } }}
      >
        <span className={`disclosure${open ? " open" : ""}`} aria-hidden>▸</span>
        {live ? (
          <span className="thinking-label">Working{steps ? ` · ${stepWord}` : "…"}</span>
        ) : (
          <span className="worked-label">
            Worked for {formatDuration(startedAt.current, finishedAt.current)} · {stepWord}
          </span>
        )}
        {live && steps > 0 && <span className="phase-current">{phases[steps - 1]?.label ?? ""}</span>}
      </div>
      {(live || open) && reasoning && (
        <div className="reasoning-pane" ref={paneRef}>
          {reasoning}
          {live && <span className="cursor">▍</span>}
        </div>
      )}
      {open && steps > 0 && (
        <div className="phase-rows">
          {phases.map((p, i) => {
            const isActive = live && i === steps - 1;
            return (
              <div key={`${p.stage}-${i}`} className={`phase-line${isActive ? " active" : ""}`}>
                <span className="phase-icon">{isActive ? <span className="spinner" /> : "✓"}</span>
                <span className="phase-label">{p.label ?? (p as unknown as { name?: string }).name ?? p.stage}</span>
                <span className="phase-detail">{detail(p)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function formatDuration(startedAt: number | null, finishedAt: number | null): string {
  if (startedAt !== null && finishedAt !== null && finishedAt > startedAt) {
    const s = (finishedAt - startedAt) / 1000;
    return s >= 10 ? `${Math.round(s)}s` : `${s.toFixed(1)}s`;
  }
  return "a moment";
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** The most reader-useful facts a given step carries, right-aligned in the rail. */
function detail(p: Phase): string {
  const d = p.data ?? {};
  const bits: string[] = [];
  const ec = num(d.evidence_count); if (ec !== null) bits.push(`${ec} chunk${ec === 1 ? "" : "s"}`);
  const gf = num(d.graph_fact_count); if (gf !== null && gf > 0) bits.push(`${gf} relationship${gf === 1 ? "" : "s"}`);
  const it = num(d.items); if (it !== null) bits.push(`${it} items`);
  const q = num(d.queries); if (q !== null) bits.push(`${q} quer${q === 1 ? "y" : "ies"}`);
  const tt = num(d.titles); if (tt !== null) bits.push(`${tt} titles`);
  const asp = num(d.aspects); if (asp !== null) bits.push(`${asp} aspect${asp === 1 ? "" : "s"}`);
  if (Array.isArray(d.corpora)) bits.push((d.corpora as string[]).join(", "));
  if (typeof d.model === "string") bits.push(d.model.split("/").pop() as string);
  return bits.join(" · ");
}
