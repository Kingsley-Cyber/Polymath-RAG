import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Turn } from "../lib/chat";
import type { Synthesizer } from "../lib/contracts";
import { EvidenceInspector } from "./EvidenceInspector";
import { QueryTrace } from "./QueryTrace";
import { AnswerReview } from "./AnswerReview";

/** The synthesis surface (ported from the original Polymath UI): the answer as
 *  real Markdown (GFM tables, emphasis, lists, code), then a quiet meta row
 *  (mode · intent · verdict · model · evidence · latency). The evidence chip
 *  opens the retrieved sources; the query trace and the reviewer stay one
 *  collapsed line each — the machinery, kept out of the reading path. */
export function AnswerBody({ t, models }: { t: Turn; models: Synthesizer[] }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const r = t.receipt;
  const intent = r?.chat_plan?.intent;
  const ec = typeof r?.evidence_count === "number" ? r.evidence_count : null;
  const gf = typeof r?.graph_fact_count === "number" ? r.graph_fact_count : 0;
  const verdict = t.verdict ?? "supported";
  return (
    <div className="answer">
      <div className="md">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.answerText}</ReactMarkdown>
      </div>
      {t.abstained && t.uncovered.length > 0 && (
        <div className="uncovered-note">nothing in this corpus covers: {t.uncovered.join(", ")}</div>
      )}
      <div className="meta-row">
        <span className="badge badge-mode">{t.mode}</span>
        {intent && (
          <span className="badge badge-intent" title="Classified by the compiler from your question — read-only, not a control.">
            ⌖ {String(intent).toLowerCase().replace(/_/g, " ")}
          </span>
        )}
        <span className={`badge ${t.abstained ? "badge-abstained" : "badge-supported"}`}>
          {t.abstained ? "ABSTAINED" : verdict.toUpperCase()}
        </span>
        {t.model && (
          <span className="badge badge-generated" title={t.model}>{t.model.split("/").pop()}</span>
        )}
        {ec !== null && (
          <button className="chunk-chip" onClick={() => setShowEvidence((s) => !s)} title="Evidence retrieved for this answer">
            ⛁ {ec} chunk{ec === 1 ? "" : "s"}
            {gf > 0 ? ` · ${gf} graph fact${gf === 1 ? "" : "s"}` : ""} {showEvidence ? "▾" : "▸"}
          </button>
        )}
        {t.latencyMs != null && <span className="latency">{(t.latencyMs / 1000).toFixed(1)}s</span>}
      </div>
      {showEvidence && r && (
        <div className="evidence-drawer">
          <EvidenceInspector receipt={r} />
        </div>
      )}
      {r && (
        <>
          <details style={{ marginTop: 10 }}>
            <summary className="label" style={{ cursor: "pointer" }}>Query trace</summary>
            <div style={{ marginTop: 10 }}><QueryTrace receipt={r} requestedMode={t.mode} /></div>
          </details>
          <details style={{ marginTop: 6 }}>
            <summary className="label" style={{ cursor: "pointer" }}>Review this answer</summary>
            <div style={{ marginTop: 10 }}>
              <AnswerReview question={t.question} answer={t.answerText} receipt={r} models={models} />
            </div>
          </details>
        </>
      )}
    </div>
  );
}
