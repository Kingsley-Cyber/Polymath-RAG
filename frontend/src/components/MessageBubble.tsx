import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChunkRef, Message, Retrieval } from "../types";
import PhaseStream from "./PhaseStream";

/** Compact raw grounding locators for reading. The model cites with
 * [chunk_<hash>@start:end] — ~80 characters mid-prose. Matched
 * citations become [n] pointing at the evidence panel's numbering;
 * unmatched ones collapse to a short tag. Full locators stay available
 * via "copy output" and the ⛁ evidence panel. */
function compactCitations(body: string, chunks: ChunkRef[]): string {
  const index = new Map<string, number>();
  chunks.forEach((c, i) => {
    if (c.locator) index.set(c.locator, i + 1);
  });
  return body.replace(/\[([^\[\]\s]{12,})\]/g, (whole, loc: string) => {
    const n = index.get(loc);
    if (n !== undefined) return `[${n}]`;
    if (loc.startsWith("fact:")) return "[fact]";
    if (loc.startsWith("chunk_") || loc.startsWith("doc_")) return "[ref]";
    return whole;
  });
}

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
        <PhaseStream
          phases={msg.phases ?? []}
          live={!!msg.pending}
          reasoning={msg.reasoning}
        />
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
      <DegradedNote retrieval={r} />
      <WildcardCards retrieval={r} />
      <div className="meta-row">
        <span className="badge badge-mode">{r.mode}</span>
        <span
          className={`badge ${abstained ? "badge-abstained" : "badge-supported"}`}
        >
          {abstained ? "ABSTAINED" : verdict.toUpperCase()}
        </span>
        <LatentChip retrieval={r} />
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

/** A lane that degraded instead of failing (e.g. the reranker parked
 * behind extraction). The answer is real and complete — this states
 * plainly what was skipped, so a quiet downgrade is never invisible. */
/** LATENT-DIAGNOSTICS chip: nominated -> survived -> admitted. */
function WildcardCards({ retrieval }: { retrieval: Retrieval }) {
  // DIVERGENT-RETRIEVAL-V1: derived insights, clearly labelled, each
  // grounded by its real source passage — never mixed into evidence.
  const bridges = retrieval.wildcard ?? [];
  if (!bridges.length) return null;
  return (
    <div className="wildcard-cards">
      {bridges.map((b, i) => (
        <div key={i} className="wildcard-card panel" style={{ marginTop: 8 }}>
          <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 4 }}>
            🃏 wildcard · derived insight · {b.source_name}
          </div>
          <div style={{ fontWeight: 600 }}>{b.principle}</div>
          {b.why_it_may_transfer && (
            <div style={{ marginTop: 4, fontSize: 13, opacity: 0.9 }}>
              {b.why_it_may_transfer}
            </div>
          )}
          <div
            className="phase-detail"
            style={{ marginTop: 6, fontSize: 12, opacity: 0.8 }}
            title="The real source passage grounding this bridge"
          >
            source: “{b.source_evidence?.text?.slice(0, 240)}…”
          </div>
        </div>
      ))}
    </div>
  );
}

function LatentChip({ retrieval }: { retrieval: Retrieval }) {
  const l = retrieval.latent;
  if (!l || !l.enabled) return null;
  const nom = l.parents_nominated ?? 0;
  const sur = l.parents_survived ?? 0;
  const kids = l.children_admitted ?? 0;
  return (
    <span
      className="chunk-chip"
      title={`Latent lane: ${nom} section(s) nominated, ${sur} survived rerank, ${kids} chunk(s) admitted${
        l.kinds ? ` · ${Object.entries(l.kinds).map(([k, v]) => `${k}:${v}`).join(" ")}` : ""}${
        l.degraded ? ` · degraded: ${l.degraded}` : ""}`}
    >
      ✨ {sur}/{nom} · {kids}
    </span>
  );
}

function DegradedNote({ retrieval }: { retrieval: Retrieval }) {
  const items = retrieval.degraded ?? [];
  if (items.length === 0) return null;
  return (
    <div className="degraded-note">
      {items.map((d, i) => (
        <div key={i} title={d.reason}>
          ⚠ {d.component} unavailable — {d.effect}
        </div>
      ))}
    </div>
  );
}

/** UI-V3 Sources panel (v3.3 style): each source leads with its human
 * identity — document name › section — and the verbatim quote. Raw
 * chunk locators and ids live behind a per-row provenance expander, so
 * internal machinery never occupies the default view. Rows without
 * presentation fields (pre-UI-V3 payloads) fall back to the locator. */
function ChunksPanel({ chunks }: { chunks: ChunkRef[] }) {
  if (chunks.length === 0)
    return <div className="chunks-panel">no evidence items retained</div>;
  return (
    <div className="chunks-panel">
      {chunks.map((c, i) => (
        <SourceRow key={i} n={i + 1} c={c} />
      ))}
    </div>
  );
}

function SourceRow({ n, c }: { n: number; c: ChunkRef }) {
  const [showProv, setShowProv] = useState(false);
  const human = c.human_locator || c.source_name || "";
  return (
    <div className="chunk-row">
      <div className="chunk-loc">
        [{n}] {human ? <b>{human}</b> : c.locator}
        {c.kind ? `  ·  ${c.kind}` : ""}
        <button
          className="copy-btn"
          style={{ marginLeft: 8 }}
          title="Raw locator and ids"
          onClick={() => setShowProv((s) => !s)}
        >
          {showProv ? "▾ provenance" : "▸ provenance"}
        </button>
        <CopyBtn text={c.preview ?? ""} label="quote" />
      </div>
      {c.preview && <div className="chunk-preview">“{c.preview}…”</div>}
      {showProv && (
        <div className="chunk-loc" style={{ opacity: 0.7, fontSize: "0.85em" }}>
          {c.locator}
          {c.doc_id ? `  ·  ${c.doc_id}` : ""}
          {c.heading_path ? `  ·  ${c.heading_path}` : ""}
          <CopyBtn text={c.locator} label="locator" />
        </div>
      )}
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
function LlmText({ text, chunks = [] }: { text: string; chunks?: ChunkRef[] }) {
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
          <div className="md" key={i}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {compactCitations(seg.body, chunks)}
            </ReactMarkdown>
          </div>
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
      <LlmText text={text} chunks={r.chunks} />
      <DegradedNote retrieval={r} />
      <div className="meta-row">
        <span className="badge badge-mode">{r.mode}</span>
        <span className="badge badge-generated">
          GENERATED · {a.result?.model ?? "llm"}
        </span>
        <LatentChip retrieval={r} />
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
