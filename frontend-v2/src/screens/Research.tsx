import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { Qualification, RunSummary, RunView } from "../lib/contracts";
import { useAsync } from "../lib/useAsync";
import { useConfirm } from "../ui/Dialog";
import { Icon } from "../ui/icons";
import { EmptyState, ErrorState, Skeleton } from "../ui/states";

/** TRAIL-INTERFACE-V1 — watch and read governed research runs. It only observes: agents submit the reasoning and the score is
 *  TrailSignal's alone, so this screen labels who decided what and never computes a verdict. Field text renders as text. */

const POLL_MS = 5000;
const REFUSAL_WORDS: Record<string, string> = {
  HARD_GATE_UNMET: "A required check wasn't met",
  NO_ADMITTED_EVIDENCE: "No evidence passed admission",
};
const STATE_WORDS: Record<string, string> = {
  done: "Done", current: "Running", waiting_agent: "Waiting for your agent", waiting_harness: "Waiting for web research",
  failed: "Failed", skipped: "Skipped", pending: "Not reached",
};

/** "current_price_checks" → "Current price checks" (TrailSignal's own names, formatted, never paraphrased). */
function words(id: string | null | undefined): string {
  if (!id) return "—";
  const s = id.replace(/[_.]/g, " ").trim().toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** T5: the dossier is a page the server renders under its own CSP — a plain link, never fetched into this app. */
function reportHref(runId: string): string {
  return `/adapter/${encodeURIComponent(runId)}/report`;
}

function when(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function tone(status: string, outcome = ""): "ready" | "degraded" | "blocked" | "unknown" {
  if (status === "completed") return outcome.includes("refused") && !outcome.includes("scored") ? "degraded" : "ready";
  if (["created", "running", "awaiting_agent", "awaiting_harness"].includes(status)) return "degraded";
  if (["failed", "terminal_gap", "cancelled"].includes(status)) return "blocked";
  return "unknown";
}

export function Research() {
  const [open, setOpen] = useState<string | null>(null);
  return open ? <RunPage runId={open} onBack={() => setOpen(null)} /> : <RunList onOpen={setOpen} />;
}

function RunList({ onOpen }: { onOpen: (id: string) => void }) {
  const [nonce, setNonce] = useState(0);
  const runs = useAsync((s) => api.adapterRuns(50, s), [nonce]);
  return (
    <div className="screen screen--wide">
      <div className="screen__head files__head">
        <div>
          <h1 className="screen__title">Research</h1>
          <p className="screen__sub">Governed product-research runs, with TrailSignal's decisions. Your agent drives a run; this page watches it.</p>
        </div>
        <button type="button" className="btn" onClick={() => setNonce((n) => n + 1)}><Icon name="refresh" /> Refresh</button>
      </div>
      {runs.data == null && !runs.error ? (
        <div className="card"><Skeleton rows={4} label="Loading runs…" /></div>
      ) : runs.error && runs.data == null ? (
        <div className="card"><ErrorState message={runs.error} onRetry={() => setNonce((n) => n + 1)} /></div>
      ) : !(runs.data ?? []).length ? (
        <div className="card"><EmptyState title="No research runs yet">Ask your connected agent to start one with the research adapter.</EmptyState></div>
      ) : (
        <div className="stack">
          {(runs.data ?? []).map((r: RunSummary) => (
            <button key={r.run_id} type="button" className="card run-row" onClick={() => onOpen(r.run_id)}>
              <span className="run-row__title">{r.title}</span>
              <span className="run-row__meta">
                <span className={`pill pill--${tone(r.status, r.outcome)}`}><span className="pill__dot" />{r.outcome}</span>
                <span className="faint">{words(r.adapter_id.split(".").pop())} · started {when(r.started_at)} · {r.steps_accepted} steps</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function RunPage({ runId, onBack }: { runId: string; onBack: () => void }) {
  const [nonce, setNonce] = useState(0);
  const [error, setError] = useState("");
  const [confirm, confirmDialog] = useConfirm();
  const view = useAsync((s) => api.adapterView(runId, s), [runId, nonce]);
  const v = view.data;
  const live = v != null && !v.run.terminal;
  useEffect(() => {                               // follow a live run; stop once it ends
    if (!live) return;
    const t = setTimeout(() => setNonce((n) => n + 1), POLL_MS);
    return () => clearTimeout(t);
  }, [live, nonce]);

  async function cancel() {
    if (!(await confirm({ title: "Cancel this run?", action: "Cancel run", danger: true,
      body: "The run stops where it is. Its steps and evidence so far stay on record." }))) return;
    try { await api.adapterCancel(runId); setNonce((n) => n + 1); } catch (e) { setError(e instanceof ApiError ? e.detailMessage : String(e)); }
  }

  return (
    <div className="screen screen--wide">
      {confirmDialog}
      <button type="button" className="linklike back-link" onClick={onBack}>← All runs</button>
      {v == null && !view.error ? <div className="card"><Skeleton rows={6} label="Loading the run…" /></div>
        : view.error && v == null ? <div className="card"><ErrorState message={view.error} onRetry={() => setNonce((n) => n + 1)} /></div>
        : v && <RunBody v={v} onCancel={() => void cancel()} error={error} />}
    </div>
  );
}

function RunBody({ v, onCancel, error }: { v: RunView; onCancel: () => void; error: string }) {
  const s = v.sections;
  const statement = useMemo(() => {
    const m = new Map<string, string>();
    for (const h of s.hypothesis_semantics ?? []) {
      if (h.hypothesis?.hypothesis_id) m.set(h.hypothesis.hypothesis_id, h.hypothesis.statement ?? h.hypothesis.hypothesis_id);
    }
    return (id?: string) => (id ? m.get(id) ?? id : "—");
  }, [s.hypothesis_semantics]);
  const admitted = (s.evidence_admissions ?? []).flatMap((a) => a.admitted ?? []);
  const rejected = (s.evidence_admissions ?? []).flatMap((a) => a.rejected ?? []);
  const count = (xs: (string | undefined)[]) => Object.entries(xs.reduce<Record<string, number>>((m, x) => ({ ...m, [x ?? "—"]: (m[x ?? "—"] ?? 0) + 1 }), {}))
    .sort((a, b) => b[1] - a[1]);
  const platforms = new Set(admitted.map((a) => a.independence_group).filter(Boolean)).size;

  return (
    <div className="stack">
      <div className="screen__head" style={{ marginBottom: 0 }}>
        <h1 className="screen__title">{v.run.title}</h1>
        <p className="screen__sub row" style={{ gap: 8 }}>
          <span className={`pill pill--${tone(v.run.status)}`}><span className="pill__dot" />{words(v.run.status)}</span>
          <span>{words(v.run.adapter_id.split(".").pop())} {v.run.adapter_version ?? ""} · started {when(v.run.started_at)}
            {v.run.finished_at ? ` · finished ${when(v.run.finished_at)}` : ""}{v.run.agent_identity ? ` · agent ${v.run.agent_identity}` : ""}</span>
          {v.report?.available && <>
            <a className="btn" href={reportHref(v.run.run_id)} target="_blank" rel="noopener noreferrer" title="The full dossier, in a new tab">
              <Icon name="external" /> Dossier</a>
            <a className="btn" href={`${reportHref(v.run.run_id)}?download=1`} rel="noopener noreferrer" title="The dossier as an HTML file">
              <Icon name="download" /> Download</a>
          </>}
          {!v.run.terminal && <button type="button" className="btn btn--danger" onClick={onCancel}>Cancel run</button>}
        </p>
        {v.run.gap?.code && <div className="banner banner--bad" style={{ marginTop: 10 }}>Stopped: {v.run.gap.code}{v.run.gap.message ? ` — ${v.run.gap.message}` : ""}</div>}
        {error && <div className="banner banner--bad" style={{ marginTop: 10 }}>{error}</div>}
        {v.stored_result_shadowed && (
          <div className="banner banner--info" style={{ marginTop: 10 }}>
            This run's saved result lost its gate results (a fixed bug); they are rebuilt here from the run's own steps.
          </div>
        )}
      </div>

      <section className="card stack" aria-labelledby="outcome-h">
        <h2 className="settings__title" id="outcome-h">Outcome <span className="authority authority--trail">Trail decided</span></h2>
        {(s.trail_scores ?? []).length > 0 && <p className="dim" style={{ margin: 0 }}>{(s.trail_scores ?? []).length} hypothesis(es) scored by TrailSignal.</p>}
        {(s.score_refusals ?? []).length === 0 && (s.trail_scores ?? []).length === 0 && <p className="dim" style={{ margin: 0 }}>No score or refusal yet.</p>}
        {(s.score_refusals ?? []).map((r, i) => (
          <div key={r.record_id ?? i} className="outcome-row">
            <span className="pill pill--blocked"><span className="pill__dot" />{REFUSAL_WORDS[r.reason_code ?? ""] ?? words(r.reason_code)}</span>
            <span>{statement(r.hypothesis_id)}</span>
          </div>
        ))}
      </section>

      {(s.qualifications ?? []).length > 0 && (
        <section className="card stack" aria-labelledby="gates-h">
          <h2 className="settings__title" id="gates-h">Gates <span className="authority authority--trail">Trail decided</span></h2>
          <p className="dim" style={{ margin: 0 }}>Each gate counts independent platforms, not posts. "1 of 3" means one platform where three are required.</p>
          <div className="table-wrap">
            <table className="t">
              <thead><tr><th>Hypothesis</th><th>Stage</th><th>State</th><th>Gates</th></tr></thead>
              <tbody>
                {(s.qualifications ?? []).map((q: Qualification, i) => (
                  <tr key={q.record_id ?? i}>
                    <td>{statement(q.hypothesis_ids?.[0])}</td>
                    <td>{words(q.stage)}</td>
                    <td><span className={`pill pill--${q.state === "PROMOTED" ? "ready" : q.state === "REJECTED" ? "blocked" : "degraded"}`}><span className="pill__dot" />{words(q.state)}</span></td>
                    <td>
                      <div className="gates">
                        {(q.gate_results ?? []).map((g, j) => (
                          <span key={g.gate_id ?? j} className={`gate ${g.passed ? "gate--pass" : "gate--fail"}`} title={g.gate_id ?? ""}>
                            {words(g.name ?? g.gate_id)}: {g.observed ?? 0} of {g.minimum ?? 0}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {(admitted.length > 0 || rejected.length > 0) && (
        <section className="card stack" aria-labelledby="evidence-h">
          <h2 className="settings__title" id="evidence-h">Evidence <span className="authority authority--field">Field evidence</span></h2>
          <p style={{ margin: 0 }}><strong>{admitted.length}</strong> admitted from <strong>{platforms}</strong> independent platform(s) · <strong>{rejected.length}</strong> rejected</p>
          <div className="grid grid--2">
            <div><div className="label">Admitted, by role</div>
              <ul className="plain-list">{count(admitted.map((a) => a.evidence_role)).map(([k, n]) => <li key={k}>{words(k)} <span className="faint">× {n}</span></li>)}</ul></div>
            <div><div className="label">Rejected, by reason</div>
              <ul className="plain-list">{rejected.length ? count(rejected.map((r) => r.reason_code)).map(([k, n]) => <li key={k}>{words(k)} <span className="faint">× {n}</span></li>) : <li className="faint">None</li>}</ul></div>
          </div>
        </section>
      )}

      {(s.lived_clusters ?? []).length > 0 && (
        <section className="card stack" aria-labelledby="lived-h">
          <h2 className="settings__title" id="lived-h">Lived world</h2>
          <div className="grid grid--3">
            {(s.lived_clusters ?? []).map((c, i) => (
              <div key={c.id ?? i} className="mini-card">
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <strong>{c.community ?? "—"}</strong>
                  <span className={`pill pill--${c.authority === "ANCHOR" ? "ready" : "unknown"}`}><span className="pill__dot" />{words(c.authority)}</span>
                </div>
                <div className="dim">{c.friction_family}</div>
                <div className="faint">{c.record_count ?? 0} of {c.threshold?.min_records ?? "?"} records · {c.thread_count ?? 0} of {c.threshold?.min_threads ?? "?"} threads</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {(s.product_concepts ?? []).length > 0 && (
        <section className="card stack" aria-labelledby="concepts-h">
          <h2 className="settings__title" id="concepts-h">Concepts <span className="authority">Agent's reasoning</span></h2>
          <ul className="plain-list">
            {(s.product_concepts ?? []).map((c, i) => {
              const reality = (s.concept_reality ?? []).find((r) => r.concept_id === c.id);
              return (
                <li key={c.id ?? i}>
                  <strong>{c.name ?? c.id}</strong>{c.buyer ? <span className="dim"> · for {c.buyer}</span> : null}
                  {reality && <> · <span className={`pill pill--${reality.status?.includes("CONTESTS") ? "blocked" : "degraded"}`}><span className="pill__dot" />{words(reality.status)}</span>
                    <span className="faint"> ({reality.existing_products ?? 0} existing products)</span></>}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {(s.unresolved_research_gaps ?? []).length > 0 && (
        <details className="card">
          <summary className="label" style={{ cursor: "pointer" }}>Unresolved questions ({(s.unresolved_research_gaps ?? []).length})</summary>
          <ul className="plain-list" style={{ marginTop: 10 }}>
            {(s.unresolved_research_gaps ?? []).map((g, i) => <li key={g.gap_id ?? i}>{g.question} <span className="faint">({words(g.evidence_role)})</span></li>)}
          </ul>
        </details>
      )}

      {v.registry && (
        <section className="card stack" aria-labelledby="registry-h">
          <h2 className="settings__title" id="registry-h">Registry <span className="authority authority--trail">Trail registry</span></h2>
          <p className="dim" style={{ margin: 0 }}>The registry snapshot TrailSignal decided this run against, and the coordinates it placed the hypotheses on. Coordinates are never evidence.</p>
          <p style={{ margin: 0 }}>Snapshot <span className="mono">{v.registry.snapshot?.snapshot_id ?? "—"}</span>
            {v.registry.snapshot?.content_hash && <span className="mono faint" style={{ overflowWrap: "anywhere" }}> · {v.registry.snapshot.content_hash}</span>}</p>
          {v.registry.snapshot_ids.length > 1 && (
            <p className="faint" style={{ margin: 0 }}>This run met {v.registry.snapshot_ids.length} snapshots: {v.registry.snapshot_ids.join(" · ")}</p>
          )}
          {v.registry.priors.length > 0 && (
            <div className="table-wrap">
              <table className="t">
                <thead><tr><th>Prior</th><th>Role</th><th>Hypotheses</th></tr></thead>
                <tbody>
                  {v.registry.priors.map((p, i) => (
                    <tr key={`${p.registry_record_id ?? ""}-${i}`}>
                      <td>{p.label ?? p.registry_record_id ?? "—"}{p.label && p.registry_record_id ? <span className="faint mono"> {p.registry_record_id}</span> : null}</td>
                      <td>{words(p.prior_role)}</td><td>{p.hypothesis_ids?.length ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {v.registry.territories.length > 0 && (
            <div className="table-wrap">
              <table className="t">
                <thead><tr><th>Territory</th><th>Role</th><th>Hypotheses</th></tr></thead>
                <tbody>
                  {v.registry.territories.map((t, i) => (
                    <tr key={`${t.territory_id ?? ""}-${i}`}>
                      <td>{t.territory_name ?? t.territory_id ?? "—"}{t.territory_name && t.territory_id ? <span className="faint mono"> {t.territory_id}</span> : null}</td>
                      <td>{words(t.territory)}</td><td>{t.hypothesis_ids?.length ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <details className="card" open={!v.run.terminal}>
        <summary className="label" style={{ cursor: "pointer" }}>Progress ({v.progress.filter((p) => p.state === "done").length} of {v.progress.length} steps)</summary>
        <ol className="timeline">
          {v.progress.map((p) => (
            <li key={p.step_id} className={`timeline__step timeline__step--${p.state}`}>
              <span className="timeline__dot" aria-hidden="true" />
              <span>{p.title}{p.visits > 1 ? <span className="faint"> · round {p.visits}</span> : null}</span>
              <span className="faint">{STATE_WORDS[p.state] ?? words(p.state)}</span>
            </li>
          ))}
        </ol>
      </details>

      {v.other_output_keys.length > 0 && (
        <details className="card">
          <summary className="label" style={{ cursor: "pointer" }}>Other records in this run</summary>
          <p className="dim mono" style={{ marginTop: 10 }}>{v.other_output_keys.join(" · ")}</p>
        </details>
      )}
    </div>
  );
}
