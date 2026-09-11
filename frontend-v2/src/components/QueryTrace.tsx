import type { RetrievalReceipt } from "../lib/contracts";
import { LaneTable } from "./LaneTable";

/**
 * F5 — the complete Query Trace (FRONTEND-V2-PLAN §3).
 *
 * requested mode · executed mode · classified intent · compiler/query plan ·
 * retrieval version · lane activity · candidate counts · selected evidence ·
 * degradation · timings. All read from the backend receipt; nothing recomputed.
 */
export function QueryTrace({ receipt, requestedMode }: {
  receipt: RetrievalReceipt; requestedMode: string;
}) {
  const plan = receipt.chat_plan ?? {};
  const executed = receipt.mode ?? "—";
  const drift = Boolean(requestedMode) && executed !== "—" && requestedMode !== executed;

  return (
    <>
      <div className="grid grid--3" style={{ marginBottom: 12 }}>
        <Fact label="Requested mode" value={requestedMode} />
        <Fact label="Executed mode" value={executed} warn={drift}
              note={drift ? "the backend executed a different mode than requested" : undefined} />
        <Fact label="Retrieval version" value={receipt.engine ?? "—"} />
        <Fact label="Classified intent" value={String(plan.intent ?? "—")}
              note="classified by the compiler; INTENT_POLICY is OFF, so it is inert for routing" />
        <Fact label="Latency" value={receipt.latency_ms != null ? `${(receipt.latency_ms / 1000).toFixed(1)}s` : "—"} />
        <Fact label="Degradation"
              value={receipt.degraded && receipt.degraded.length ? receipt.degraded.join(", ") : "none"}
              warn={!!receipt.degraded?.length} />
      </div>

      <LaneTable receipt={receipt} />

      {Object.keys(plan).length > 0 && (
        <details style={{ marginTop: 12 }}>
          <summary className="label" style={{ cursor: "pointer" }}>Compiler / query plan</summary>
          <pre className="mono" style={{ marginTop: 8, whiteSpace: "pre-wrap", fontSize: 11.5,
                                          background: "var(--bg-sunken)", padding: 10, borderRadius: 6,
                                          maxHeight: 320, overflow: "auto" }}>
            {JSON.stringify(plan, null, 2)}
          </pre>
        </details>
      )}
    </>
  );
}

function Fact({ label, value, note, warn }: { label: string; value: string; note?: string; warn?: boolean }) {
  return (
    <div className="card" style={{ padding: "10px 12px" }}>
      <div className="label" style={{ marginBottom: 5 }}>{label}</div>
      <div className="mono" style={{ color: warn ? "var(--warn)" : undefined }}>{value}</div>
      {note && <div className="faint" style={{ marginTop: 5, fontSize: 11.5 }}>{note}</div>}
    </div>
  );
}
