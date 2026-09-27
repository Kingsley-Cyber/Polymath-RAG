import { useEffect, useId, useMemo, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { Turn } from "../../lib/chat";
import { clock, liveState, moveWords, plural, presetSeconds, type DeepRunState, type LiveGoal, type LiveSearch } from "../../lib/deep";
import { Icon } from "../../ui/icons";
import "../../styles/deep.css";

/** DEEP-RESEARCH-MODE-V1 §11.2 part 2 (DR7c) — the live research view, in place of the process rail for a research turn: the
 *  goals as a checklist with small coverage meters (findings · books, from `coverage` frames and each frame's `goal_id`), a
 *  collapsible activity feed (each search with its move and what it found), the counters (books, passages, findings) and the
 *  time against the estimate. Finish now asks the run to stop searching and write its report; Stop cancels it. Once the turn
 *  ends it folds into one line that opens again on a click. */

function useNow(on: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!on) return;
    setNow(Date.now());
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [on]);
  return now;
}

/** §11.4's coverage bar: 2 findings from 2 books is "covered". */
function covered(g: LiveGoal): boolean {
  return (g.learnings ?? 0) >= 2 && (g.documents ?? 0) >= 2;
}

function fill(g: LiveGoal): number {
  return Math.round(((Math.min(g.learnings ?? 0, 2) + Math.min(g.documents ?? 0, 2)) / 4) * 100);
}

function found(s: LiveSearch, live: boolean): string {
  if (s.status === "empty") return "nothing in the libraries";
  if (s.status === "failed") return "search failed";
  const bits = [s.rows !== null ? plural(s.rows, "passage") : "",
    s.findings !== null ? (s.findings ? plural(s.findings, "finding") : "no new findings") : ""].filter(Boolean);
  if (s.status === "searching") return live ? (bits.length ? `${bits.join(" · ")} · reading…` : "searching…") : bits.join(" · ");
  return bits.join(" · ") || "read";
}

export function LiveResearch({ t, onStop, onRunPatch }: {
  t: Turn;
  onStop: () => void;
  onRunPatch: (patch: Partial<DeepRunState>) => void;
}) {
  const s = useMemo(() => liveState(t), [t]);
  const live = !t.done;
  const run = t.deepRun ?? null;
  const now = useNow(live);
  const [open, setOpen] = useState(live);
  const [feedOpen, setFeedOpen] = useState(true);
  const [manual, setManual] = useState(false);
  const feedId = useId();
  const bodyId = useId();

  useEffect(() => {                                     // fold away once the turn ends, unless the person opened it
    if (live) { setOpen(true); return; }
    if (!manual) { setOpen(false); setFeedOpen(false); }
  }, [live, manual]);

  if (!live && t.phases.length === 0 && !run?.goals?.length) return null;

  const startedAt = run?.startedAt ?? null;
  const lastAt = t.phases[t.phases.length - 1]?.at ?? null;
  const elapsed = live ? (startedAt ? (now - startedAt) / 1000 : null)
    : t.latencyMs != null ? t.latencyMs / 1000 : lastAt !== null ? lastAt / 1000 : null;
  const estimate = run?.estimateS ?? presetSeconds(run?.request?.preset);
  const counters = [
    s.books !== null ? plural(s.books, "book") : "",
    s.passages !== null ? plural(s.passages, "passage") : "",
    s.findings !== null ? plural(s.findings, "finding") : "",
  ].filter(Boolean).join(" · ");
  const finishing = !!run?.finishing;
  const status = live
    ? (s.writing ? "Writing the report" : finishing ? "Finishing: writing the report from what was found" : "Researching")
    : t.error ? "Research stopped" : "Research done";

  async function finish() {
    onRunPatch({ finishing: true, note: null });
    try {
      await api.deepResearchFinish();
    } catch (e) {
      if (e instanceof SyntaxError) return;                 // a 202 with no JSON body: accepted
      onRunPatch({
        finishing: false,
        note: e instanceof ApiError && e.status === 404 ? "Nothing to finish: this research has already stopped searching."
          : `Finish now did not go through: ${e instanceof ApiError ? e.detailMessage : String(e)}`,
      });
    }
  }

  const toggle = () => { setManual(true); setOpen((o) => !o); };
  return (
    <section className={`research-live${live ? " research-live--live" : ""}`} aria-label="Deep research progress">
      <div className="research-live__head">
        <button type="button" className="research-live__toggle" aria-expanded={open} aria-controls={open ? bodyId : undefined} onClick={toggle}>
          <span className={`disclosure${open ? " open" : ""}`} aria-hidden="true">▸</span>
          {live && <span className="spinner" aria-hidden="true" />}
          <span className="research-live__status">{status}</span>
        </button>
        {counters && <span className="research-live__counters">{counters}</span>}
        {elapsed !== null && (
          <span className="research-live__time" title="Time so far, against the estimate">
            {clock(elapsed)}{estimate ? ` of about ${clock(estimate)}` : ""}
          </span>
        )}
        {live && (
          <span className="research-live__actions">
            {!s.writing && (
              <button type="button" className="btn" disabled={finishing} onClick={() => void finish()}
                      title="Stop searching and write the report from what has been found">
                {finishing ? "Finishing…" : "Finish now"}
              </button>
            )}
            <button type="button" className="btn btn--danger" onClick={onStop} title="Cancel the research">
              <Icon name="stop" size={12} /> Stop
            </button>
          </span>
        )}
      </div>
      {live && s.step && s.step !== status && <p className="research-live__step">{s.step}</p>}
      {open && (
        <div id={bodyId} className="stack" style={{ gap: 8 }}>
          {s.goals.length > 0 && (
            <ol className="research-goals" aria-label="Parts of the research">
              {s.goals.map((g) => (
                <li key={g.id} className={`research-goal${covered(g) ? " research-goal--covered" : ""}`}>
                  <span className="research-goal__icon" aria-hidden="true">
                    {g.active ? <span className="spinner" /> : covered(g) ? <Icon name="check" size={14} /> : <span className="research-goal__dot" />}
                  </span>
                  <span className="research-goal__text">
                    {g.text}
                    {g.move && <span className="research-goal__move"> · {moveWords(g.move)}</span>}
                    <span className="sr-only">{g.active ? " (searching now)" : covered(g) ? " (well covered)" : ""}</span>
                  </span>
                  <span className="research-goal__cov">
                    <span className="meter" aria-hidden="true"><span className="meter__fill" style={{ width: `${fill(g)}%` }} /></span>
                    <span className="research-goal__counts">
                      {g.learnings === null ? (g.searches ? plural(g.searches, "search") : "not searched yet")
                        : `${plural(g.learnings, "finding")} · ${plural(g.documents ?? 0, "book")}`}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          )}
          {s.feed.length > 0 && (
            <div className="research-feed">
              <button type="button" className="linklike research-feed__toggle" aria-expanded={feedOpen} aria-controls={feedOpen ? feedId : undefined}
                      onClick={() => setFeedOpen((o) => !o)}>
                {feedOpen ? "Hide" : "Show"} activity ({plural(s.searches, "search")})
              </button>
              {feedOpen && (
                <ol className="research-feed__list" id={feedId}>
                  {s.feed.map((x) => x.kind === "note" ? (
                    <li key={x.key} className="research-feed__note">{x.text}</li>
                  ) : (
                    <li key={x.key} className={`research-feed__item research-feed__item--${x.status}`}>
                      <span className="research-feed__icon" aria-hidden="true">
                        {x.status === "searching" && live ? <span className="spinner" /> : x.status === "read" ? "✓" : "–"}
                      </span>
                      <span className="research-feed__what">
                        <span className="research-feed__move">{moveWords(x.move) || "Search"}</span> · {x.query}
                      </span>
                      <span className="research-feed__found">{found(x, live)}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}
        </div>
      )}
      {run?.note && <p className="research-live__note" role="status">{run.note}</p>}
    </section>
  );
}
