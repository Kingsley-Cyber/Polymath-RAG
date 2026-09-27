import { useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { copyText } from "../../lib/auth";
import type { DeepAnswer, DeepCitation, Turn } from "../../lib/chat";
import type { DeepCounterFinding, DeepFinding, DeepReportModel, DeepReportSource } from "../../lib/contracts";
import {
  auditOf, auditView, confidenceOf, countOf, inverseOf, methodLines, openQuestionsOf, plural, reportFileName, reportMarkdown,
  splitTldr, type AuditView, type ProsePart,
} from "../../lib/deep";
import { Icon } from "../../ui/icons";
import { CiteRef, deepCitations, remarkCitations, type CiteInfo } from "../Citations";
import { uncitedMarks } from "./remarkUncited";
import "../../styles/deep.css";

/** DEEP-RESEARCH-MODE-V1 §11.2 parts 3–4 (DR7d) — the report of a run whose answer carries `meta.deep_research.report_model`.
 *  Report: the model's prose (Markdown, citation chips), its TL;DR first, every sentence the audit found uncited underlined
 *  with "no citation", and DR6's counter-evidence line. Evidence / Sources / Method draw the deterministic evidence model,
 *  never the model's tone. Below: "Research this next" chips from the open questions, Copy as Markdown and Download .md. */

type Tab = "report" | "evidence" | "sources" | "method";
const TABS: { id: Tab; label: string }[] = [
  { id: "report", label: "Report" }, { id: "evidence", label: "Evidence" },
  { id: "sources", label: "Sources" }, { id: "method", label: "Method" },
];

export function DeepReport({ t, report, onResearchNext }: {
  t: Turn;
  report: DeepReportModel;
  onResearchNext?: (question: string) => void;
}) {
  const [tab, setTab] = useState<Tab>("report");
  const base = useId();
  const refs = useRef(new Map<Tab, HTMLButtonElement>());
  const cites = useMemo(() => deepCitations(t.deep), [t.deep]);
  const valid = useMemo(() => new Set((t.deep?.citations ?? []).map((c) => c.cid)), [t.deep]);
  const audit = useMemo(() => auditView(t.answerText, auditOf(t), valid), [t, valid]);
  const questions = openQuestionsOf(report);

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    const i = TABS.findIndex((x) => x.id === tab);
    const next = e.key === "ArrowRight" ? (i + 1) % TABS.length : e.key === "ArrowLeft" ? (i + TABS.length - 1) % TABS.length
      : e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1 : -1;
    if (next < 0) return;
    e.preventDefault();
    const id = TABS[next]!.id;
    setTab(id);
    refs.current.get(id)?.focus();
  }

  return (
    <div className="answer deep-report">
      <div className="tabs" role="tablist" aria-label="Report views" onKeyDown={onKey}>
        {TABS.map((x) => (
          <button key={x.id} type="button" role="tab" className="tab" id={`${base}-${x.id}`} aria-selected={tab === x.id}
                  aria-controls={tab === x.id ? `${base}-panel` : undefined} tabIndex={tab === x.id ? 0 : -1}
                  ref={(el) => { if (el) refs.current.set(x.id, el); }} onClick={() => setTab(x.id)}>
            {x.label}
          </button>
        ))}
      </div>
      <div className="tabpanel" role="tabpanel" id={`${base}-panel`} aria-labelledby={`${base}-${tab}`} tabIndex={0}>
        {tab === "report" && <ReportTab t={t} cites={cites} audit={audit} counter={report.counter ?? []} />}
        {tab === "evidence" && <EvidenceTab report={report} cites={cites} />}
        {tab === "sources" && <SourcesTab report={report} deep={t.deep ?? null} cites={cites} />}
        {tab === "method" && <MethodTab t={t} audit={audit} />}
      </div>
      {questions.length > 0 && onResearchNext && <ResearchNext questions={questions} onPick={onResearchNext} />}
      {t.done && <ReportActions question={t.question} text={t.answerText} citations={t.deep?.citations ?? []} />}
      <div className="meta-row">
        <span className="badge badge-mode">{t.mode}</span>
        {t.model && <span className="badge badge-generated" title={t.model}>{t.model.split("/").pop()}</span>}
        {t.latencyMs != null && <span className="latency">{(t.latencyMs / 1000).toFixed(1)}s</span>}
      </div>
    </div>
  );
}

/* ── Report ─────────────────────────────────────────────────────────────────────────────────────────────────────────── */

function Prose({ part, whole, cites, audit }: { part: ProsePart; whole: string; cites: Map<string, CiteInfo>; audit: AuditView }) {
  const plugins = useMemo(() => [remarkGfm, uncitedMarks(audit.marks, part.start, whole), remarkCitations],
    [audit.marks, part.start, whole]);
  const components = useMemo(() => ({
    "cite-ref": ({ tag }: { tag?: string }) => <CiteRef tag={tag ?? ""} info={cites.get(tag ?? "")} />,
    "uncited-mark": ({ children }: { children?: ReactNode }) => (
      <span className="uncited" title="No citation supports this sentence">{children}</span>),
    "uncited-note": () => <span className="uncited__note">no citation</span>,
  }) as unknown as Components, [cites]);
  return <div className="md"><ReactMarkdown remarkPlugins={plugins} components={components}>{part.text}</ReactMarkdown></div>;
}

function AuditNote({ audit, unknown }: { audit: AuditView; unknown: string[] }) {
  if (audit.mode === "none" && !unknown.length) return null;
  const of = audit.sentences !== null ? ` of ${audit.sentences}` : "";
  return (
    <p className="audit-note">
      {audit.mode !== "none" && (audit.uncited === 0
        ? `Every sentence${audit.sentences !== null ? ` (${audit.sentences})` : ""} cites a passage.`
        : `${audit.uncited}${of} sentence${audit.uncited === 1 && !of ? "" : "s"} ${audit.uncited === 1 ? "has" : "have"} no citation${
          audit.mode === "marks" ? ": underlined below." : ". They could not be matched to the text here, so they are not marked."}`)}
      {unknown.length > 0 && <span className="faint"> Cited but not found in the research: {unknown.join(", ")}.</span>}
    </p>
  );
}

function ReportTab({ t, cites, audit, counter }: {
  t: Turn; cites: Map<string, CiteInfo>; audit: AuditView; counter: DeepCounterFinding[];
}) {
  const parts = useMemo(() => splitTldr(t.answerText), [t.answerText]);
  const unknown = [...new Set([...(t.deep?.unknown ?? []), ...audit.invalid])];
  const inverse = inverseOf(t);
  const against = inverse ? inverse.learnings : counter.length;
  return (
    <>
      <AuditNote audit={audit} unknown={unknown} />
      {parts.tldr && (
        <div className="tldr">
          <div className="tldr__label">TL;DR</div>
          <Prose part={parts.tldr} whole={t.answerText} cites={cites} audit={audit} />
        </div>
      )}
      <Prose part={parts.rest} whole={t.answerText} cites={cites} audit={audit} />
      {/* DR6 §10.7's line, as the older view shows it: only when counter-evidence searches ran (or the model lists some) */}
      {((inverse && inverse.searched >= 1) || (!inverse && counter.length > 0)) && (
        <p className="counter-evidence">
          Counter-evidence: {against > 0 ? plural(against, "finding") : "none found in the libraries"}
        </p>
      )}
    </>
  );
}

/* ── Evidence ───────────────────────────────────────────────────────────────────────────────────────────────────────── */

function Chips({ cids, cites }: { cids: string[] | undefined; cites: Map<string, CiteInfo> }) {
  return <>{(cids ?? []).map((c) => <CiteRef key={c} tag={c} info={cites.get(c)} />)}</>;
}

function Finding({ f, cites }: { f: DeepFinding; cites: Map<string, CiteInfo> }) {
  const conf = confidenceOf(f.confidence);
  return (
    <li className="finding">
      {conf && <span className={`conf conf--${conf.key}`} title={conf.why || undefined}>{conf.label}</span>}
      {f.text} <Chips cids={f.cids} cites={cites} />
    </li>
  );
}

function CounterList({ items, cites, title }: { items: DeepCounterFinding[]; cites: Map<string, CiteInfo>; title: string }) {
  return (
    <div className="counter">
      <h4 className="counter__title">{title}</h4>
      <ul className="findings">
        {items.map((c, i) => <li key={i} className="finding">{c.text} <Chips cids={c.cids} cites={cites} /></li>)}
      </ul>
    </div>
  );
}

function EvidenceTab({ report, cites }: { report: DeepReportModel; cites: Map<string, CiteInfo> }) {
  const goals = (report.goals ?? []).filter((g) => g && typeof g === "object");
  const counter = (report.counter ?? []).filter((c) => c && typeof c === "object");
  const ids = new Set(goals.map((g) => g.id));
  const loose = counter.filter((c) => !c.goal_id || !ids.has(c.goal_id));
  const questions = openQuestionsOf(report);
  return (
    <div className="evidence">
      {goals.length === 0 && <p className="faint" style={{ margin: 0 }}>The research recorded no findings.</p>}
      {goals.map((g, i) => {
        const findings = (g.findings ?? []).filter((f) => f && typeof f === "object");
        const books = countOf(g.documents);
        const against = counter.filter((c) => c.goal_id === g.id);
        return (
          <section key={g.id || i} className="evidence-goal" aria-label={g.goal || `Part ${i + 1}`}>
            <h3 className="evidence-goal__title">{g.goal || `Part ${i + 1}`}</h3>
            <p className="evidence-goal__meta faint">
              {plural(findings.length, "finding")}{books !== null ? ` · ${plural(books, "book")}` : ""}
            </p>
            {findings.length ? (
              <ul className="findings">{findings.map((f, j) => <Finding key={j} f={f} cites={cites} />)}</ul>
            ) : <p className="faint" style={{ margin: 0 }}>Nothing found for this part.</p>}
            {against.length > 0 && <CounterList items={against} cites={cites} title="Counter-evidence" />}
          </section>
        );
      })}
      {loose.length > 0 && (
        <section className="evidence-goal" aria-label="Counter-evidence">
          <CounterList items={loose} cites={cites} title="Counter-evidence" />
        </section>
      )}
      <section className="evidence-goal" aria-label="Open questions">
        <h3 className="evidence-goal__title">Open questions</h3>
        {questions.length ? (
          <ul className="plain-list">{questions.map((q) => <li key={q}>{q}</li>)}</ul>
        ) : <p className="faint" style={{ margin: 0 }}>None: the libraries answered every part.</p>}
      </section>
    </div>
  );
}

/* ── Sources ────────────────────────────────────────────────────────────────────────────────────────────────────────── */

/** Without the report model's sources (it should always carry them), group the report's citations by book. */
function sourcesOf(report: DeepReportModel, deep: DeepAnswer | null): DeepReportSource[] {
  if (Array.isArray(report.sources) && report.sources.length) return report.sources.filter((s) => s && typeof s === "object");
  const books = new Map<string, DeepReportSource>();
  for (const c of deep?.citations ?? []) {
    const key = c.title || c.id || c.cid;
    const b = books.get(key) ?? { title: c.title, cids: [] };
    b.cids = [...(b.cids ?? []), c.cid];
    books.set(key, b);
  }
  return [...books.values()];
}

function SourcesTab({ report, deep, cites }: { report: DeepReportModel; deep: DeepAnswer | null; cites: Map<string, CiteInfo> }) {
  return <SourcesByBook books={sourcesOf(report, deep)} cites={cites} empty="The report cites no passage." />;
}

/** The sources by document: one entry per book with the passages it lent, each id a citation chip. Shared by the deep report's
 *  Sources tab and the chat answer's "Sources by document" panel (FACET-RETRIEVAL-V1 F5 — `meta.synthesis.sources`, whose
 *  cids are the answer's [S#] tags resolved through the chat receipt). */
export function SourcesByBook({ books, cites, empty = "The answer cites no passage." }: {
  books: DeepReportSource[]; cites: Map<string, CiteInfo>; empty?: string;
}) {
  if (!books.length) return <p className="faint" style={{ margin: 0 }}>{empty}</p>;
  return (
    <ol className="book-list">
      {books.map((b, i) => {
        const cids = b.cids ?? [];
        return (
          <li key={b.doc_id || b.title || i} className="book">
            <div className="book__head">
              <strong>{b.title || b.doc_id || "Untitled"}</strong>
              <span className="faint">
                {typeof b.findings === "number" ? `supports ${plural(b.findings, "finding")} · ` : ""}{plural(cids.length, "passage")} used
              </span>
            </div>
            {cids.length > 0 && (
              <ul className="book__passages">
                {cids.map((c) => {
                  const info = cites.get(c);
                  return (
                    <li key={c}>
                      <span className="cite-id mono">{c}</span>{info?.where ? <span className="faint"> {info.where}</span> : null}
                      {info?.text && <details><summary className="faint">Passage</summary><p className="sources__text">{info.text}</p></details>}
                    </li>
                  );
                })}
              </ul>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/* ── Method ─────────────────────────────────────────────────────────────────────────────────────────────────────────── */

function MethodTab({ t, audit }: { t: Turn; audit: AuditView }) {
  const lines = methodLines(t);
  if (audit.mode !== "none" && audit.sentences !== null) {
    lines.push(`Citation check: ${audit.sentences - audit.uncited} of ${plural(audit.sentences, "sentence")} cite a passage.`);
  }
  return lines.length ? <ul className="method">{lines.map((l) => <li key={l}>{l}</li>)}</ul>
    : <p className="faint" style={{ margin: 0 }}>This run recorded no method details.</p>;
}

/* ── actions (DR7d) ─────────────────────────────────────────────────────────────────────────────────────────────────── */

function ResearchNext({ questions, onPick }: { questions: string[]; onPick: (q: string) => void }) {
  const id = useId();
  return (
    <div className="next-chips" role="group" aria-labelledby={id}>
      <span className="label" id={id}>Research this next <span className="faint">(fills the box with Deep research on, Quick depth)</span></span>
      <div className="next-chips__list">
        {questions.map((q) => (
          <button key={q} type="button" className="starter next-chip" onClick={() => onPick(q)}>{q}</button>
        ))}
      </div>
    </div>
  );
}

/** Copy as Markdown and Download .md: the prose with its [cN] as footnotes `[^cN]: Title — where`. */
export function ReportActions({ question, text, citations }: { question: string; text: string; citations: DeepCitation[] }) {
  const [copied, setCopied] = useState(false);
  const markdown = () => reportMarkdown(question, text, citations);
  function download() {
    const url = URL.createObjectURL(new Blob([markdown()], { type: "text/markdown;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = reportFileName(question);
    document.body.append(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return (
    <div className="report-actions">
      <button type="button" className="btn" onClick={() => void copyText(markdown()).then((ok) => {
        if (ok) { setCopied(true); window.setTimeout(() => setCopied(false), 2000); }
      })}>
        <Icon name={copied ? "check" : "copy"} size={14} /> {copied ? "Copied" : "Copy as Markdown"}
      </button>
      <button type="button" className="btn" onClick={download}><Icon name="download" size={14} /> Download .md</button>
    </div>
  );
}
