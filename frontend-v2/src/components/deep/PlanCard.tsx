import { useEffect, useId, useRef, useState } from "react";
import {
  confirmPlan, draftFromPlan, isMove, maxPlanItems, MOVE_WORDS, MOVES, moveWords, planProblem, plural, presetLabel, roughly,
  useSkipPlan, words, type DeepGoal, type DeepRunState, type PlanDraftGoal,
} from "../../lib/deep";
import { Icon, IconButton } from "../../ui/icons";
import { Skeleton } from "../../ui/states";
import "../../styles/deep.css";

/** DEEP-RESEARCH-MODE-V1 §11.2 part 1 (DR7a) — the plan card. After Send the research is planned (one model call) and shown
 *  as its parts: each goal as editable text with its move in plain words, removable, plus "Add a part"; the library, the depth
 *  and the estimate. Start runs it; it starts by itself after 10 s unless the person focuses or edits the card; Cancel drops
 *  it. The draft and "touched" live on the turn, so a chat switch neither loses an edit nor restarts an edited plan. */

export const COUNTDOWN_S = 10;

export function PlanCard({ run, onStart, onCancel, onRunPatch }: {
  run: DeepRunState;
  onStart: (goals: DeepGoal[]) => void;
  onCancel: () => void;
  onRunPatch: (patch: Partial<DeepRunState>) => void;
}) {
  if (run.status === "planning") {
    return (
      <section className="plan-card plan-card--loading" aria-busy="true" aria-label="Planning the research">
        <p className="plan-card__title"><span className="spinner" aria-hidden="true" /> Planning the research…</p>
        <Skeleton rows={3} label="Planning the research…" />
        <div className="plan-card__actions"><button type="button" className="btn" onClick={onCancel}>Cancel</button></div>
      </section>
    );
  }
  return <PlanReady run={run} onStart={onStart} onCancel={onCancel} onRunPatch={onRunPatch} />;
}

function PlanReady({ run, onStart, onCancel, onRunPatch }: {
  run: DeepRunState;
  onStart: (goals: DeepGoal[]) => void;
  onCancel: () => void;
  onRunPatch: (patch: Partial<DeepRunState>) => void;
}) {
  const titleId = useId();
  const hintId = useId();
  const [skip, setSkip] = useSkipPlan();
  const draft = run.draft ?? draftFromPlan(run.plan);
  const max = maxPlanItems(run.request.preset);
  const problem = planProblem(draft, max);
  const counting = !run.touched && !problem;
  const [left, setLeft] = useState(COUNTDOWN_S);
  const started = useRef(false);
  const fields = useRef(new Map<string, HTMLTextAreaElement>());
  const focusKey = useRef<string | null>(null);

  function start() {
    if (started.current || planProblem(draft, max)) return;
    started.current = true;
    onStart(confirmPlan(draft, run.plan));
  }
  const startNow = useRef(start);
  startNow.current = start;

  // The countdown: one timer starts the run at 10 s; the other only redraws the number on the button.
  useEffect(() => {
    if (!counting) return;
    const deadline = Date.now() + COUNTDOWN_S * 1000;
    setLeft(COUNTDOWN_S);
    const tick = window.setInterval(() => setLeft(Math.max(1, Math.ceil((deadline - Date.now()) / 1000))), 250);
    const go = window.setTimeout(() => startNow.current(), COUNTDOWN_S * 1000);
    return () => { window.clearInterval(tick); window.clearTimeout(go); };
  }, [counting]);

  useEffect(() => {                                   // a part just added gets the focus
    const key = focusKey.current;
    if (key) { fields.current.get(key)?.focus(); focusKey.current = null; }
  });

  const touch = () => { if (!run.touched) onRunPatch({ touched: true }); };
  const edit = (next: PlanDraftGoal[]) => onRunPatch({ draft: next, touched: true });
  const change = (i: number, patch: Partial<PlanDraftGoal>) => edit(draft.map((d, j) => (j === i ? { ...d, ...patch } : d)));
  function add() {
    const key = `new-${Date.now().toString(36)}-${draft.length}`;
    focusKey.current = key;
    edit([...draft, { key, goal: "", query: "", move: "broad" }]);
  }

  const estimate = run.plan?.estimate;
  const searches = typeof estimate?.searches === "number" ? estimate.searches : null;
  const seconds = typeof estimate?.seconds === "number" ? estimate.seconds : null;
  const n = draft.length;
  return (
    <section className="plan-card" aria-labelledby={titleId}
             onFocusCapture={touch} onPointerDownCapture={touch} onKeyDownCapture={touch}>
      <h3 className="plan-card__title" id={titleId}>I'll research this in {plural(n, "part")}</h3>
      <p className="plan-card__meta">
        <span>Library: <strong>{run.request.corpusId}</strong></span>
        <span>Depth: <strong>{presetLabel(run.request.preset)}</strong></span>
        {(searches !== null || seconds !== null) && (
          <span>Estimate: <strong>{[searches !== null ? plural(searches, "search") : "", seconds !== null ? `about ${roughly(seconds)}` : ""]
            .filter(Boolean).join(", ")}</strong></span>
        )}
        {run.plan?.intent && <span>Question type: <strong>{words(run.plan.intent).toLowerCase()}</strong></span>}
      </p>
      <ol className="plan-card__goals">
        {draft.map((d, i) => (
          <li key={d.key} className="plan-goal">
            <span className="plan-goal__n" aria-hidden="true">{i + 1}</span>
            <div className="plan-goal__body">
              <textarea className="plan-goal__text" rows={2} maxLength={300} value={d.goal} aria-label={`Part ${i + 1}`}
                        placeholder="What should this part find out?"
                        ref={(el) => { if (el) fields.current.set(d.key, el); else fields.current.delete(d.key); }}
                        onChange={(e) => change(i, { goal: e.target.value, query: e.target.value })} />
              <div className="plan-goal__row">
                <label>
                  <span className="sr-only">How part {i + 1} is searched</span>
                  <select value={d.move} onChange={(e) => change(i, { move: e.target.value })}>
                    {MOVES.map((m) => <option key={m} value={m}>{MOVE_WORDS[m]}</option>)}
                    {!isMove(d.move) && <option value={d.move}>{moveWords(d.move)}</option>}
                  </select>
                </label>
                {d.query.trim() && d.query.trim() !== d.goal.trim() && (
                  <span className="plan-goal__query faint">Searches: {d.query}</span>
                )}
                <IconButton icon="x" label={`Remove part ${i + 1}`} className="icon-btn--sm plan-goal__remove"
                            disabled={n <= 1} onClick={() => edit(draft.filter((_, j) => j !== i))} />
              </div>
            </div>
          </li>
        ))}
      </ol>
      {n < max && (
        <button type="button" className="btn plan-card__add" onClick={add}><Icon name="plus" /> Add a part</button>
      )}
      {problem && <p className="plan-card__problem" role="status">{problem}</p>}
      <div className="plan-card__actions">
        <button type="button" className="btn btn--primary" disabled={!!problem} onClick={start} aria-describedby={hintId}>
          <Icon name="play" size={14} /> Start{counting && <span className="plan-card__count" aria-hidden="true"> · {left}</span>}
        </button>
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        <span className="plan-card__hint faint" id={hintId}>
          {counting ? `Starts by itself in ${left} s unless you change the plan.` : "Starts when you press Start."}
        </span>
      </div>
      <label className="plan-card__skip">
        <input type="checkbox" checked={skip} onChange={(e) => setSkip(e.target.checked)} />
        Start deep research without showing the plan
      </label>
    </section>
  );
}
