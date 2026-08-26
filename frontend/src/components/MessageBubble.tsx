import { useState } from "react";
import type { ChunkRef, Message } from "../types";
import PhaseStream from "./PhaseStream";

export default function MessageBubble({ msg }: { msg: Message }) {
  if (msg.role === "user") {
    return (
      <div className="msg msg-user">
        <div className="bubble">{msg.text}</div>
      </div>
    );
  }
  return (
    <div className="msg msg-assistant">
      {(msg.phases?.length || msg.pending) && (
        <PhaseStream phases={msg.phases ?? []} live={!!msg.pending} />
      )}
      {msg.error && (
        <div className="bubble">
          <span className="badge badge-error">
            {msg.error.error_code ?? "ERROR"}
          </span>{" "}
          {msg.error.message}
        </div>
      )}
      {msg.answer && <AnswerBody msg={msg} />}
    </div>
  );
}

function AnswerBody({ msg }: { msg: Message }) {
  const [showChunks, setShowChunks] = useState(false);
  const a = msg.answer!;
  const r = a.retrieval;

  if (a.kind === "ask") return <AskBody msg={msg} />;

  const res = a.result;
  const verdict: string = res?.meta?.verdict ?? "supported";
  const abstained: boolean = !!res?.meta?.abstained;
  const uncovered: string[] = res?.meta?.uncovered_query_terms ?? [];

  return (
    <div className="bubble">
      <div>{res?.answer}</div>
      {abstained && uncovered.length > 0 && (
        <div className="phase-detail" style={{ marginTop: 6 }}>
          nothing in this corpus covers: {uncovered.join(", ")}
        </div>
      )}
      <div className="meta-row">
        <span className="badge badge-mode">{r.mode}</span>
        <span
          className={`badge ${abstained ? "badge-abstained" : "badge-supported"}`}
        >
          {abstained ? "ABSTAINED" : verdict.toUpperCase()}
        </span>
        <button
          className="chunk-chip"
          onClick={() => setShowChunks((s) => !s)}
          title="Evidence retrieved for this answer"
        >
          ⛁ {r.evidence_count} chunk{r.evidence_count === 1 ? "" : "s"}
          {typeof r.graph_fact_count === "number" && r.graph_fact_count > 0
            ? ` · ${r.graph_fact_count} graph fact${r.graph_fact_count === 1 ? "" : "s"}`
            : ""}
          {" "}{showChunks ? "▾" : "▸"}
        </button>
        <span className="latency">{(a.latency_ms / 1000).toFixed(1)}s</span>
      </div>
      {showChunks && <ChunksPanel chunks={r.chunks} />}
    </div>
  );
}

function ChunksPanel({ chunks }: { chunks: ChunkRef[] }) {
  if (chunks.length === 0)
    return <div className="chunks-panel">no evidence items retained</div>;
  return (
    <div className="chunks-panel">
      {chunks.map((c, i) => (
        <div className="chunk-row" key={i}>
          <div className="chunk-loc">
            [{i + 1}] {c.locator}
            {c.kind ? `  ·  ${c.kind}` : ""}
          </div>
          {c.preview && <div className="chunk-preview">“{c.preview}…”</div>}
        </div>
      ))}
    </div>
  );
}

function AskBody({ msg }: { msg: Message }) {
  const res = msg.answer!.result;
  const objs = res?.objects ?? {};
  const lanes: [string, any[]][] = [
    ["procedures", objs.procedures ?? []],
    ["concepts", objs.concepts ?? []],
    ["facts", objs.facts ?? []],
    ["related_concepts", objs.related_concepts ?? []],
  ];
  const total = lanes.reduce((n, [, v]) => n + v.length, 0);
  return (
    <div className="bubble">
      {total === 0 ? (
        <div>
          <span className="badge badge-abstained">NO STORED OBJECTS</span>{" "}
          Nothing in this corpus answers that as a stored knowledge object.
        </div>
      ) : (
        <div className="ask-cards">
          {lanes.map(
            ([name, items]) =>
              items.length > 0 && (
                <div className="ask-card" key={name}>
                  <h4>
                    {name} ({items.length})
                  </h4>
                  {items.map((o: any, i: number) => (
                    <AskObject key={i} lane={name} o={o} />
                  ))}
                </div>
              ),
          )}
        </div>
      )}
      <div className="meta-row">
        <span className="badge badge-mode">ASK · {res?.route}</span>
        {res?.map?.consulted && (
          <span className="chunk-chip" title="Corpus map consulted">
            🗺 map · {res.map.neighborhoods?.length ?? 0} neighborhoods
          </span>
        )}
        <span className="latency">
          {(msg.answer!.latency_ms / 1000).toFixed(1)}s
        </span>
      </div>
    </div>
  );
}

function AskObject({ lane, o }: { lane: string; o: any }) {
  if (lane === "procedures")
    return (
      <div style={{ marginBottom: 6 }}>
        <b>{o.title || o.goal}</b>
        <ol>
          {(o.steps ?? []).map((s: any, i: number) => (
            <li key={i}>{s.action ?? String(s)}</li>
          ))}
        </ol>
      </div>
    );
  if (lane === "concepts")
    return (
      <div style={{ marginBottom: 4 }}>
        <b>{o.name}</b> — {o.description}
      </div>
    );
  if (lane === "facts")
    return (
      <div style={{ marginBottom: 4 }}>
        <b>{o.subject}</b> <span className="cite">{o.predicate}</span>{" "}
        <b>{o.object}</b>
      </div>
    );
  return (
    <div style={{ marginBottom: 4 }}>
      <b>{o.canonical_concept}</b> — {o.definition}
    </div>
  );
}
