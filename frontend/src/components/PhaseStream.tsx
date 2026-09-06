import { useEffect, useRef, useState } from "react";
import type { Phase } from "../types";

/** PROCESS-RAIL-V1 (surgical UI pass, 2026-09-06): the Agent-Zero-style
 * reasoning trail as a compact, visually subordinate process rail.
 *
 * - live      → open; the header reads "Working · N steps" behind a
 *               rotating disclosure triangle; the active row carries a
 *               spinner, finished rows a check, details right-aligned.
 * - finished  → stays open briefly (COLLAPSE_DELAY_MS), then collapses to
 *               "Worked for 7.4s · N steps"; a click reopens it, and a
 *               click during the grace window keeps it open.
 * - reasoning → the model's thinking streams into a pane under the header
 *               while live; it collapses with the rail.
 *
 * Nothing about the streaming contract changes: the same Phase objects,
 * the same `live` flag, the same reasoning string. Duration is read from
 * the phases' own timestamps (`t`) and falls back to a client clock. */
const COLLAPSE_DELAY_MS = 1800;

export default function PhaseStream({
  phases,
  live,
  reasoning,
}: {
  phases: Phase[];
  live: boolean;
  reasoning?: string;
}) {
  const [open, setOpen] = useState(true);
  const [manual, setManual] = useState(false);
  const paneRef = useRef<HTMLDivElement | null>(null);
  const startedAt = useRef<number | null>(null);
  const finishedAt = useRef<number | null>(null);

  // Client clock as the fallback duration source.
  useEffect(() => {
    if (live && startedAt.current === null) startedAt.current = Date.now();
    if (!live && startedAt.current !== null && finishedAt.current === null)
      finishedAt.current = Date.now();
  }, [live]);

  // Delayed collapse: the finished work stays readable for a moment, then
  // folds away unless the user has taken over (manual toggle).
  useEffect(() => {
    if (live) {
      setOpen(true);
      setManual(false);
      return;
    }
    if (manual) return;
    const timer = window.setTimeout(() => setOpen(false), COLLAPSE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [live, manual]);

  // Follow the thinking stream while live.
  useEffect(() => {
    if (live && paneRef.current)
      paneRef.current.scrollTop = paneRef.current.scrollHeight;
  }, [live, reasoning]);

  if (phases.length === 0 && !live && !reasoning) return null;

  const steps = phases.length;
  const stepWord = `${steps} step${steps === 1 ? "" : "s"}`;
  const toggle = () => {
    setManual(true);
    setOpen((o) => !o);
  };

  return (
    <div className={`phases${live ? " live" : ""}${open ? " open" : ""}`}>
      <div
        className="phases-summary"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
          }
        }}
      >
        <span className={`disclosure${open ? " open" : ""}`} aria-hidden>▸</span>
        {live ? (
          <span className="thinking-label">
            Working{steps ? ` · ${stepWord}` : "…"}
          </span>
        ) : (
          <span className="worked-label">
            Worked for {formatDuration(phases, startedAt.current, finishedAt.current)} · {stepWord}
          </span>
        )}
        {live && steps > 0 && (
          <span className="phase-current">{phases[steps - 1].label}</span>
        )}
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
              <div
                key={`${p.stage}-${i}`}
                className={`phase-line${isActive ? " active" : ""}`}
              >
                <span className="phase-icon">
                  {isActive ? <span className="spinner" /> : "✓"}
                </span>
                <span className="phase-label">{p.label}</span>
                <span className="phase-detail">{detail(p)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Wall time of the whole turn as the reader experienced it: the client
 * clock from the moment the rail went live to the moment the stream ended
 * (this covers generation, which has no phase stamp of its own). A chat
 * restored from storage has no client clock, so the span between the first
 * and last phase stamp (`t`, epoch seconds or milliseconds) stands in. */
function formatDuration(phases: Phase[], startedAt: number | null, finishedAt: number | null): string {
  let seconds: number | null = null;
  if (startedAt !== null && finishedAt !== null && finishedAt > startedAt)
    seconds = (finishedAt - startedAt) / 1000;
  if (seconds === null) {
    const stamps = phases.map((p) => p.t).filter((t): t is number => typeof t === "number" && Number.isFinite(t));
    if (stamps.length >= 2) {
      const span = Math.max(...stamps) - Math.min(...stamps);
      seconds = span > 1000 ? span / 1000 : span;      // ms vs s stamps
      if (seconds <= 0) seconds = null;
    }
  }
  if (seconds === null) return "a moment";
  return seconds >= 10 ? `${Math.round(seconds)}s` : `${seconds.toFixed(1)}s`;
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
