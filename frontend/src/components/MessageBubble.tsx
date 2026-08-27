import { useState } from "react";
import type { ChunkRef, Message } from "../types";
import PhaseStream from "./PhaseStream";

export default function MessageBubble({ msg }: { msg: Message }) {
  if (msg.role === "user") {
    return (
      <div className="msg msg-user">
        <div className="bubble has-copy">
          {msg.text}
          <div className="bubble-copy"><CopyBtn text={msg.text} /></div>
        </div>
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
      {!msg.answer && msg.pending && msg.text && (
        <div className="bubble">{msg.text}<span className="cursor">▍</span></div>
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
  if (a.kind === "llm") return <LlmBody msg={msg} showChunks={showChunks} setShowChunks={setShowChunks} />;

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
        <CopyBtn text={res?.answer ?? ""} label="copy answer" />
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

function CopyBtn({ text, label = "copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="copy-btn"
      title="Copy to clipboard"
      onClick={async (e) => {
        e.stopPropagation();
        try {
          await navigator.clipboard.writeText(text);
        } catch {
          const ta = document.createElement("textarea");
          ta.value = text;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          ta.remove();
        }
        setDone(true);
        setTimeout(() => setDone(false), 1400);
      }}
    >
      {done ? "✓ copied" : `⧉ ${label}`}
    </button>
  );
}

const EXT: Record<string, string> = {
  html: "html", css: "css", javascript: "js", js: "js", typescript: "ts",
  ts: "ts", python: "py", py: "py", json: "json", bash: "sh", sh: "sh",
  sql: "sql", yaml: "yaml", markdown: "md", md: "md",
};

function fileNameFor(code: string, lang: string): string {
  let base = "polymath-generated";
  const title = code.match(/<title>([^<]{1,60})<\/title>/i)?.[1]
    ?? code.match(/<h1[^>]*>([^<]{1,60})<\/h1>/i)?.[1];
  if (title) {
    const slug = title.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "").slice(0, 48);
    if (slug) base = slug;
  }
  return `${base}.${EXT[lang] ?? "txt"}`;
}

function downloadFile(code: string, lang: string) {
  const mime = lang === "html" ? "text/html" : "text/plain";
  const url = URL.createObjectURL(new Blob([code], { type: mime }));
  const el = document.createElement("a");
  el.href = url;
  el.download = fileNameFor(code, lang);
  el.click();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

async function launchHtml(code: string) {
  // GENERATED-LAUNCH-V1: persist server-side and open the real URL —
  // survives refresh, bookmarkable, and is a real file on disk.
  // Falls back to an ephemeral blob URL if the API is unreachable.
  try {
    const name =
      code.match(/<title>([^<]{1,60})<\/title>/i)?.[1] ??
      code.match(/<h1[^>]*>([^<]{1,60})<\/h1>/i)?.[1] ??
      "generated";
    const r = await fetch("/generated", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, html: code }),
    });
    if (r.ok) {
      const out = await r.json();
      window.open(out.url, "_blank");
      return;
    }
  } catch {
    /* fall through to blob */
  }
  const url = URL.createObjectURL(new Blob([code], { type: "text/html" }));
  window.open(url, "_blank");
}

/** Split LLM output into prose and fenced code blocks; code renders in
 * a framed block with a header bar: language, Copy, and for HTML also
 * Open + Download (saves as a real .html file in ~/Downloads). */
function LlmText({ text }: { text: string }) {
  const parts: { kind: "text" | "code"; lang: string; body: string }[] = [];
  const re = /```([a-zA-Z0-9]*)\n([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last)
      parts.push({ kind: "text", lang: "", body: text.slice(last, m.index) });
    parts.push({ kind: "code", lang: (m[1] || "text").toLowerCase(), body: m[2] });
    last = m.index + m[0].length;
  }
  if (last < text.length)
    parts.push({ kind: "text", lang: "", body: text.slice(last) });
  if (parts.length === 0) parts.push({ kind: "text", lang: "", body: text });
  return (
    <div>
      {parts.map((seg, i) =>
        seg.kind === "text" ? (
          <span key={i}>{seg.body}</span>
        ) : (
          <div className="code-block" key={i}>
            <div className="code-head">
              <span className="code-lang">{seg.lang}</span>
              <span className="spacer" />
              <CopyBtn text={seg.body} label="copy code" />
              {seg.lang === "html" && (
                <>
                  <button
                    className="copy-btn"
                    onClick={() => launchHtml(seg.body)}
                  >
                    🚀 launch
                  </button>
                  <button
                    className="copy-btn"
                    onClick={() => downloadFile(seg.body, "html")}
                  >
                    ⬇ download .html
                  </button>
                </>
              )}
              {seg.lang !== "html" && (
                <button
                  className="copy-btn"
                  onClick={() => downloadFile(seg.body, seg.lang)}
                >
                  ⬇ download
                </button>
              )}
            </div>
            <pre className="code-body">{seg.body}</pre>
          </div>
        ),
      )}
    </div>
  );
}

function extractHtml(text: string): string | null {
  const m = text.match(/```html\n([\s\S]*?)```/);
  if (m) return m[1];
  const t = text.trim();
  if (t.startsWith("<!doctype") || t.startsWith("<!DOCTYPE") || t.startsWith("<html"))
    return t;
  return null;
}

function LlmBody({
  msg,
  showChunks,
  setShowChunks,
}: {
  msg: Message;
  showChunks: boolean;
  setShowChunks: (fn: (s: boolean) => boolean) => void;
}) {
  const a = msg.answer!;
  const r = a.retrieval;
  const text: string = a.result?.answer ?? msg.text;
  const html = extractHtml(text);

  const openHtml = () => {
    if (!html) return;
    launchHtml(html);
  };
  const downloadHtml = () => {
    if (!html) return;
    const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    const el = document.createElement("a");
    el.href = url;
    el.download = "polymath-generated.html";
    el.click();
  };

  const bareHtml = html && !text.includes("```");
  return (
    <div className="bubble">
      <LlmText text={text} />
      <div className="meta-row">
        <span className="badge badge-mode">{r.mode}</span>
        <span className="badge badge-generated">
          GENERATED · {a.result?.model ?? "llm"}
        </span>
        <CopyBtn text={text} label="copy output" />
        {bareHtml && (
          <>
            <button className="chunk-chip" onClick={openHtml}>
              🚀 Launch
            </button>
            <button
              className="chunk-chip"
              onClick={() => downloadFile(html, "html")}
            >
              ⬇ Download .html
            </button>
          </>
        )}
        <button
          className="chunk-chip"
          onClick={() => setShowChunks((s) => !s)}
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
