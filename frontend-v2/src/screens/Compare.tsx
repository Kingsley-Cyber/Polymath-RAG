import { useState } from "react";
import { api } from "../lib/api";
import { PUBLIC_MODES } from "../lib/contracts";
import type { CompareResponse } from "../lib/contracts";

/**
 * F6 — Compare Retrieval (FRONTEND-V2-PLAN §5), on COMPARE-RETRIEVAL-V1.
 *
 * User-triggered only. One question, several modes, RETRIEVAL ONLY — the backend runs
 * the arms inside one request so they share the question and the engine, and no arm
 * pays a synthesis. The naive alternative (N chat calls) confounds "the mode changed"
 * with "the run varied"; that is GAP-2, and this contract is the answer to it.
 */
export function Compare({ corpusId }: { corpusId: string }) {
  const [q, setQ] = useState("");
  const [modes, setModes] = useState<string[]>([...PUBLIC_MODES]);
  const [res, setRes] = useState<CompareResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    if (!q.trim() || !modes.length) return;
    setBusy(true); setErr(null); setRes(null);
    try {
      setRes(await api.compare({ message: q.trim(), corpus_id: corpusId, modes }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  const arms = res?.arms ?? [];
  const docSets = arms.map((a) => new Set(a.retrieval?.documents ?? []));
  const shared = docSets.length
    ? [...docSets[0]!].filter((d) => docSets.every((s) => s.has(d)))
    : [];

  return (
    <div className="screen screen--wide">
      <div className="screen__head">
        <h1 className="screen__title">Compare retrieval</h1>
        <p className="screen__sub">
          One question across modes on <span className="mono">{corpusId}</span> — retrieval only, no synthesis
        </p>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="row" style={{ marginBottom: 10 }}>
          <input type="text" style={{ flex: 1, minWidth: 300 }}
                 placeholder="Question to compare…" value={q}
                 onChange={(e) => setQ(e.target.value)}
                 onKeyDown={(e) => { if (e.key === "Enter") void run(); }} />
          <button className="btn btn--primary" onClick={() => void run()} disabled={busy || !q.trim()}>
            {busy ? "Running…" : "Compare"}
          </button>
        </div>
        <div className="row" style={{ gap: 14 }}>
          {PUBLIC_MODES.map((m) => (
            <label key={m} className="row" style={{ gap: 6, cursor: "pointer" }}>
              <input type="checkbox" checked={modes.includes(m)}
                     onChange={(e) => setModes((cur) =>
                       e.target.checked ? [...cur, m] : cur.filter((x) => x !== m))} />
              <span className="mono">{m}</span>
            </label>
          ))}
          <span className="faint" style={{ fontSize: 12 }}>
            arms run sequentially — the reranker is one shared GPU lane, so parallel arms
            would make the latencies meaningless
          </span>
        </div>
      </div>

      {err && <div className="banner banner--bad">{err}</div>}
      {!res && !busy && <div className="empty">Ask a question to compare modes.</div>}

      {arms.length > 0 && (
        <>
          <div className="card" style={{ marginBottom: 14, overflowX: "auto" }}>
            <table className="t">
              <thead>
                <tr><th>Mode</th><th>Latency</th><th>Union</th><th>Evidence</th>
                    <th>Documents</th><th>Sections</th><th>Degraded</th><th>Lanes fired</th></tr>
              </thead>
              <tbody>
                {arms.map((a) => {
                  const r = a.retrieval ?? {};
                  const fired = Object.entries(r.lane_sizes ?? {})
                    .filter(([k, v]) => v > 0 && k !== "union" && k !== "union_uncapped");
                  return (
                    <tr key={a.mode}>
                      <td className="mono"><b>{a.mode}</b></td>
                      <td className="mono">{a.latency_ms} ms</td>
                      <td className="mono">{r.union_size ?? "—"}</td>
                      <td className="mono">{r.evidence_count ?? "—"}</td>
                      <td className="mono">{r.selected_documents ?? "—"}</td>
                      <td className="mono">{r.selected_sections ?? "—"}</td>
                      <td className="mono">{r.degraded?.length ? r.degraded.join(",") : <span className="faint">none</span>}</td>
                      <td className="mono faint">{fired.map(([k, v]) => `${k}:${v}`).join(" · ") || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!arms.every((a) => a.ok) && (
              <div className="banner banner--bad" style={{ marginTop: 10 }}>
                {arms.filter((a) => !a.ok).map((a) => <div key={a.mode}>{a.mode}: {a.error}</div>)}
              </div>
            )}
          </div>

          <div className="card" style={{ marginBottom: 14 }}>
            <div className="label" style={{ marginBottom: 6 }}>Document overlap</div>
            <div className="mono" style={{ fontSize: 12.5 }}>
              {shared.length} document(s) selected by EVERY arm
              {arms.map((a) => {
                const only = (a.retrieval?.documents ?? []).filter((d) => !shared.includes(d));
                return (
                  <div key={a.mode} className="faint" style={{ marginTop: 4 }}>
                    {a.mode}: {only.length ? `${only.length} unique — ${only.map((d) => d.slice(0, 14)).join(", ")}` : "nothing unique"}
                  </div>
                );
              })}
            </div>
            {shared.length === (arms[0]?.retrieval?.documents?.length ?? -1) && arms.length > 1 && (
              <div className="banner" style={{ marginTop: 10 }}>
                Every arm selected the same documents. On a small homogeneous corpus the modes
                genuinely converge — that is a result, not a bug.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
