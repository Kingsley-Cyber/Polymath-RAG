import { useEffect, useId, useRef, useState } from "react";
import type { ProductView } from "../lib/productResearch";
import {
  AGENT_REACH_CHECK, AGENT_REACH_REPO, POLL_MS, RUN_SENTENCE, SOURCES, SOURCE_NAMES, errorWords, heldUploadToken, isLive,
  listWords, missingNote, permanent, reportApi, reportHref, reportProducts, reportStatus, reportView, startBody,
  startRefusalWords, takeUploadToken, when,
  type FetchView, type ProductReportRef, type ReportView,
} from "../lib/productReport";
import { CopyField } from "../ui/CopyField";
import { Icon } from "../ui/icons";
import "../styles/product.css";

/** PRODUCT-DECISION-REPORT-V1 B6 — under a product answer: "Build decision report" sends the answer's hypotheses as the
 *  report's products with the answer's libraries (POST /product/report/start), then the panel follows that report. The
 *  report id is kept on the chat turn, so a reload finds the panel; the upload token stays in this page's memory only
 *  (ADR-0023). A failure stays on screen in words (status and message; a 429 REPORT_JOB_RUNNING also names the report still
 *  running) and Build is offered again. */
export function BuildReport({ view, question = "", report = null, onReportStarted }: {
  view: ProductView;
  /** the person's question: the report's message */
  question?: string;
  /** the report already built from this answer (kept on the turn) */
  report?: ProductReportRef | null;
  onReportStarted?: (report: ProductReportRef) => void;
}) {
  const headId = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [local, setLocal] = useState<{ ref: ProductReportRef; reply: unknown } | null>(null);
  const sending = useRef(false);                            // one start per click, even on a double click
  const kept = report && typeof report.report_id === "string" && report.report_id.trim() ? report : null;
  const ref = local?.ref ?? kept;
  const products = reportProducts(view);

  async function start() {
    if (sending.current) return;
    sending.current = true;
    setBusy(true);
    setError("");
    try {
      const reply = await reportApi.start(startBody(view, question));
      const r = reportView(reply);
      if (!r?.reportId) throw new Error("the server's reply names no report (no report_id)");
      takeUploadToken(r.reportId, reply);                  // memory only: the turn below keeps the id, never the token
      const started: ProductReportRef = { report_id: r.reportId, ...(r.status ? { status: r.status } : {}), started_at: Date.now() };
      setLocal({ ref: started, reply });
      onReportStarted?.(started);
    } catch (e) {
      setError(startRefusalWords(e));
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }

  if (!ref && !products.length) return null;                    // no titled idea: nothing to build a report on
  return (
    <section className="pr-report" aria-labelledby={headId}>
      <h4 className="pr-report__title" id={headId}>Decision report</h4>
      {ref ? (
        <ReportPanel key={ref.report_id} reportId={ref.report_id}
                     initial={local?.ref.report_id === ref.report_id ? local.reply : undefined} />
      ) : (
        <>
          <p className="pr-report__note">
            One page that weighs these ideas as a dropshipper would: supplier cost, MOQ and delivery time from CJ Dropshipping and
            Alibaba, market prices on Amazon and eBay, what Reddit says, and the margin and delivery check for TikTok Shop,
            Shopify, eBay and Amazon.
          </p>
          <div className="pr-report__actions">
            <button type="button" className="btn btn--primary" onClick={() => void start()} disabled={busy} aria-busy={busy || undefined}>
              <Icon name="report" size={14} />{busy ? "Building…" : "Build decision report"}
            </button>
          </div>
        </>
      )}
      {error && <div className="banner banner--bad" role="alert">Couldn't build the decision report. {error}</div>}
    </section>
  );
}

/** One decision report: its status, checked at once and then every few seconds while it is collecting (or compiling) — never
 *  while a compile is on its way, never after it is compiled or failed, never once this panel is gone. Every check sends the
 *  upload token this page holds (X-Upload-Token), and every reply may hand it a new one (ADR-0023). Then its products, the round's
 *  fetch script (web users have no terminal of their own in the app), the uploads per source, Compile (any time; it says
 *  which sections would be missing) and Open, which opens the server's page in a new tab. */
export function ReportPanel({ reportId, initial, onStatus }: {
  reportId: string;
  /** the start reply, when this panel follows a report it has just started */
  initial?: unknown;
  /** told whenever the status changes (the Reports screen keeps its row in step) */
  onStatus?: (status: string) => void;
}) {
  const [view, setView] = useState<ReportView | null>(() => {
    takeUploadToken(reportId, initial);                    // a start reply's token (held already when Build sent it)
    return reportView(initial, null, reportId);
  });
  const [checks, setChecks] = useState(0);                  // status checks answered so far; the first one runs at once
  const [checkError, setCheckError] = useState("");
  const [halted, setHalted] = useState(false);              // a refusal that asking again will not change
  const [compiling, setCompiling] = useState(false);
  const [compileError, setCompileError] = useState("");
  const sending = useRef(false);                            // one compile per click
  const onStatusRef = useRef(onStatus);
  const status = view?.status ?? "";
  // check while the report collects; also while its state is unknown and the last check failed on something passing
  const polling = !compiling && !halted && (checks === 0 || isLive(status) || (!status && checkError !== ""));

  useEffect(() => {
    if (!polling) return;
    const ac = new AbortController();
    const timer = setTimeout(() => {
      reportApi.status(reportId, heldUploadToken(reportId), ac.signal).then((raw) => {
        if (ac.signal.aborted) return;
        takeUploadToken(reportId, raw);                    // minted: hold it; expired or required: drop the one held
        setView((prev) => reportView(raw, prev, reportId));
        setCheckError("");
        setChecks((n) => n + 1);
      }, (e: unknown) => {
        if (ac.signal.aborted) return;
        setCheckError(errorWords(e));
        if (permanent(e)) setHalted(true);
        setChecks((n) => n + 1);
      });
    }, checks === 0 ? 0 : POLL_MS);
    return () => { clearTimeout(timer); ac.abort(); };    // unmount, a compile, or the next state: this check is dropped
  }, [polling, checks, reportId]);

  useEffect(() => { onStatusRef.current = onStatus; });
  useEffect(() => { if (status) onStatusRef.current?.(status); }, [status]);

  async function compile() {
    if (sending.current) return;
    sending.current = true;
    setCompiling(true);
    setCompileError("");
    try {
      const raw = await reportApi.compile(reportId, {});
      setView((prev) => reportView(raw, prev, reportId));
      setChecks((n) => Math.max(n, 1));                    // the compile reply stands in for a first check
    } catch (e) {
      setCompileError(errorWords(e));
    } finally {
      sending.current = false;
      setCompiling(false);
    }
  }

  function checkAgain() {
    setHalted(false);
    setCheckError("");
    setChecks(0);
  }

  const s = view == null && !checkError ? { tone: "unknown", words: "Checking…" } : reportStatus(status);
  const note = view ? missingNote(view) : "";
  const fetch = view?.fetch ?? null;
  const roundNo = view?.round ?? fetch?.round ?? null;
  const uploads = view?.uploads ?? null;
  const progress = view?.progress ?? null;
  const host = view?.host ?? null;
  return (
    <div className="pr-report__panel" data-status={status || undefined}>
      <p className="pr-report__status">
        <span role="status">
          <span className={`pill pill--${s.tone}`} title={status || undefined}><span className="pill__dot" />{s.words}</span>
        </span>
        <span className="faint">
          Report <code className="mono">{reportId}</code>{roundNo ? ` · round ${roundNo}` : ""}
          {view?.compiledAt ? ` · compiled ${when(view.compiledAt)}` : ""}
        </span>
      </p>
      {view?.failure && <p className="pr-report__why">{view.failure}</p>}
      {view?.forming && <p className="pr-report__line">Polymath is forming the products from your library…</p>}
      {view?.candidates && view.candidates.length > 0 && (
        <div className="pr-report__block">
          <span className="label">Products in this report</span>
          <ul className="pr-report__products">
            {view.candidates.map((c) => (
              <li key={c.key}>{c.title}{c.terms.length > 0 && <span className="faint"> · {c.terms.join(" · ")}</span>}</li>
            ))}
          </ul>
        </div>
      )}
      {fetch && (!status || status === "collecting" ? <ScriptSection fetch={fetch} roundNo={roundNo} /> : (
        <details className="pr-report__more">
          <summary>Fetch script{roundNo ? ` for round ${roundNo}` : ""}</summary>
          <ScriptSection fetch={fetch} roundNo={roundNo} />
        </details>
      ))}
      {(uploads || progress) && (
        <div className="pr-report__block">
          <span className="label">Uploaded so far</span>
          {progress && (
            <p className="pr-report__line">
              Round {progress.round}: {progress.received.toLocaleString()} of {progress.packets.toLocaleString()} reads uploaded
            </p>
          )}
          {uploads && (
            <dl className="pr-report__counts">
              {SOURCES.map((x) => (
                <div key={x}>
                  <dt>{SOURCE_NAMES[x]}</dt>
                  <dd>{uploads[x].n.toLocaleString()}{uploads[x].issues && <span className="faint"> ({uploads[x].issues})</span>}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}
      {host && (
        <p className="pr-report__line">
          <span className="label">CJ Dropshipping and eBay, read by the server:</span> {host.words}{host.error ? `: ${host.error}` : ""}
        </p>
      )}
      {note && <p className="pr-report__missing"><Icon name="info" size={14} />{note}</p>}
      {view?.stale && view.hasPage && (
        <p className="pr-report__missing"><Icon name="info" size={14} />New uploads arrived after the last compile: compile again to include them.</p>
      )}
      <div className="pr-report__actions">
        <button type="button" className={`btn${view?.hasPage ? "" : " btn--primary"}`} onClick={() => void compile()} disabled={compiling}
                aria-busy={compiling || undefined}>
          {compiling ? "Compiling…" : "Compile report"}
        </button>
        {view?.hasPage && (
          <a className="btn" href={reportHref(reportId)} target="_blank" rel="noopener noreferrer">
            <Icon name="external" size={14} />Open report<span className="sr-only"> (opens in a new tab)</span>
          </a>
        )}
        {!polling && !compiling && (status !== "compiled" || fetch?.blocked === "required") && (
          <button type="button" className="linklike" onClick={checkAgain}>Check again</button>
        )}
      </div>
      {checkError && <div className="banner banner--bad" role="alert">Couldn't check the report's status. {checkError}</div>}
      {compileError && <div className="banner banner--bad" role="alert">Couldn't compile the report. {compileError}</div>}
    </div>
  );
}

/** The round's fetch script with its copy button, the one sentence that says what to do with it, where Agent Reach installs
 *  from and the command that checks it works, and the upload capability with its expiry. A script whose upload link is not
 *  usable here (ADR-0023: expired, required, none, or a placeholder) is never offered to copy: the panel shows the plan and says
 *  why, and what to do instead. */
function ScriptSection({ fetch, roundNo }: { fetch: FetchView; roundNo: number | null }) {
  const until = when(fetch.expiresAt);
  const plan = fetch.packets > 0 && (
    <p className="pr-report__fine">
      {roundNo ? `Round ${roundNo} plans` : "This round plans"} {fetch.packets.toLocaleString()} read{fetch.packets === 1 ? "" : "s"}
      {fetch.sources.length > 0 ? `: ${listWords(fetch.sources.map((x) => SOURCE_NAMES[x]))}.` : "."}
    </p>
  );
  if (fetch.blocked === "expired") {
    return (
      <div className="pr-report__script" data-link="expired">
        <p className="pr-report__line">
          The upload link {until ? `expired ${until}` : "has expired"}: the fetch script can no longer add results to this report.
          Compile with what arrived, or build a new report.
        </p>
      </div>
    );
  }
  if (fetch.blocked === "required") {
    const after = when(fetch.mintAfter);
    return (
      <div className="pr-report__script" data-link="required">
        {plan}
        <p className="pr-report__line">
          This page holds no upload link for this report, so the script is not shown. A new upload link can be made
          {after ? ` after ${after}` : " in about a minute"}, or use the script your agent already has.
        </p>
      </div>
    );
  }
  if (fetch.blocked || !fetch.script) {
    return (
      <div className="pr-report__script" data-link={fetch.blocked || "no-script"}>
        {plan}
        <p className="pr-report__line">
          This page has no usable upload link for the fetch script yet. Compile with what has arrived, or use the script your agent
          already has.
        </p>
      </div>
    );
  }
  return (
    <div className="pr-report__script">
      <p className="pr-report__run"><Icon name="terminal" size={15} />{RUN_SENTENCE}</p>
      {(roundNo ?? 0) > 1 && (
        <p className="pr-report__fine">Round {roundNo} is a new script: it reads the product pages the first round found.</p>
      )}
      {fetch.packets > 0 && (
        <p className="pr-report__fine faint">This round makes {fetch.packets.toLocaleString()} read{fetch.packets === 1 ? "" : "s"} through your Agent Reach.</p>
      )}
      <CopyField value={fetch.script} what="fetch script" block primary />
      <p className="pr-report__line">
        <span className="label">Install Agent Reach from</span>{" "}
        <a href={AGENT_REACH_REPO} target="_blank" rel="noopener noreferrer">
          {AGENT_REACH_REPO}<span className="sr-only"> (opens in a new tab)</span>
        </a>
      </p>
      <div className="pr-report__field">
        <span className="label">Check it works</span>
        <CopyField value={AGENT_REACH_CHECK} what="check command" />
      </div>
      {fetch.uploadUrl && (
        <div className="pr-report__field">
          <span className="label">Upload address{until ? `, open until ${until}` : ""}</span>
          <CopyField value={fetch.uploadUrl} what="upload address" />
          <p className="pr-report__fine faint">The script already holds this address. Anyone who has it can add results to this report until it expires.</p>
        </div>
      )}
      {fetch.note && <p className="pr-report__fine">{fetch.note}</p>}
      {fetch.sha256 && <p className="pr-report__fine faint">Script SHA-256 <span className="mono">{fetch.sha256}</span></p>}
    </div>
  );
}
