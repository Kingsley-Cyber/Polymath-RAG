import { useState } from "react";
import { api } from "../lib/api";
import { chunkIdOf } from "../lib/chunkid";
import type { RetrievalReceipt, ReviewResponse, Synthesizer } from "../lib/contracts";

/**
 * F7 — Answer Review (FRONTEND-V2-PLAN §6), on ANSWER-REVIEW-V1.
 *
 * Evaluation only. The reviewer judges an EXISTING answer against the evidence that
 * answer actually cited — it does not retrieve, and it does not regenerate. That is
 * the whole distinction from picking a different synthesizer, which merely re-answers.
 */
export function AnswerReview({ question, answer, receipt, models }: {
  question: string; answer: string; receipt: RetrievalReceipt | null; models: Synthesizer[];
}) {
  const [reviewer, setReviewer] = useState("");
  const [res, setRes] = useState<ReviewResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const legend = (receipt?.legend ?? []) as Record<string, unknown>[];
  const chunks = (receipt?.chunks ?? []) as Record<string, unknown>[];
  const citations = legend.map((l) => l.tag).filter(Boolean) as string[];
  // `chunks[]` carries only `locator`; `legend[]` carries `chunk_id` — see lib/chunkid.
  const tagById = new Map(legend.map((l) => [chunkIdOf(l), l.tag as string | undefined]));
  const evidence = chunks
    .filter((c) => tagById.has(chunkIdOf(c)))
    .map((c) => ({
      tag: tagById.get(chunkIdOf(c)),
      doc_id: c.doc_id, source_name: c.source_name, text: c.preview,
    }));

  async function run() {
    setBusy(true); setErr(null); setRes(null);
    try {
      setRes(await api.review({
        question, answer, citations, evidence,
        retrieval_meta: { engine: receipt?.engine, mode: receipt?.mode,
                          evidence_count: receipt?.evidence_count },
        ...(reviewer ? { reviewer } : {}),
      }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  const r = res?.review;
  return (
    <div>
      <div className="row" style={{ marginBottom: 10 }}>
        <div className="field">
          <span className="label">Reviewer model</span>
          <select value={reviewer} onChange={(e) => setReviewer(e.target.value)} style={{ minWidth: 260 }}>
            <option value="">backend default</option>
            {models.map((m) => {
              const id = m.id ?? m.name ?? "";
              return <option key={id} value={id}>{id}</option>;
            })}
          </select>
        </div>
        <button className="btn btn--primary" onClick={() => void run()} disabled={busy}>
          {busy ? "Reviewing…" : "Review this answer"}
        </button>
        <span className="faint" style={{ fontSize: 12 }}>
          judges the answer against its {evidence.length} cited passage(s) — no retrieval, no regeneration
        </span>
      </div>

      {err && <div className="banner banner--bad">{err}</div>}
      {res?.parse_error && (
        <div className="banner">reviewer returned unparseable output: {res.parse_error}</div>
      )}

      {r && (
        <>
          <div className="row" style={{ gap: 18, marginBottom: 10 }}>
            {([["grounding", r.grounding], ["correctness", r.correctness],
               ["completeness", r.completeness], ["citation support", r.citation_support],
               ["retrieval adequacy", r.retrieval_adequacy]] as [string, number | undefined][])
              .map(([k, v]) => (
                <div key={k}>
                  <div className="label">{k}</div>
                  <div className="mono" style={{ fontSize: 17,
                       color: v == null ? undefined : v >= 4 ? "var(--ok)" : v >= 3 ? "var(--warn)" : "var(--bad)" }}>
                    {v ?? "—"}<span className="faint" style={{ fontSize: 11 }}>/5</span>
                  </div>
                </div>
              ))}
            {r.verdict && (
              <div>
                <div className="label">verdict</div>
                <span className={`pill pill--${r.verdict === "SUPPORTED" ? "ready"
                  : r.verdict === "UNSUPPORTED" ? "blocked" : "degraded"}`}>{r.verdict}</span>
              </div>
            )}
          </div>
          {!!r.unsupported_claims?.length && (
            <div className="banner banner--bad" style={{ marginBottom: 8 }}>
              <b>Unsupported claims:</b>
              <ul style={{ margin: "6px 0 0 18px" }}>
                {r.unsupported_claims.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}
          {!!r.missing_evidence?.length && (
            <div className="banner">
              <b>Missing evidence:</b>
              <ul style={{ margin: "6px 0 0 18px" }}>
                {r.missing_evidence.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}
        </>
      )}
      {res?.raw && !r && (
        <pre className="mono" style={{ fontSize: 11.5, whiteSpace: "pre-wrap",
             background: "var(--bg-sunken)", padding: 10, borderRadius: 6, maxHeight: 240, overflow: "auto" }}>
          {res.raw}
        </pre>
      )}
    </div>
  );
}
