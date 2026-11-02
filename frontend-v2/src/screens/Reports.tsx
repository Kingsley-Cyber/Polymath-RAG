import { useId, useState } from "react";
import { ReportPanel } from "../components/ProductReport";
import { errorWords, reportApi, reportHref, reportRows, reportStatus, when, type ReportRow } from "../lib/productReport";
import { useAsync } from "../lib/useAsync";
import { Icon } from "../ui/icons";
import { EmptyState, ErrorState, Skeleton } from "../ui/states";
import "../styles/product.css";

/** PRODUCT-DECISION-REPORT-V1 B6 — the person's decision reports (GET /product/reports; a friend sees only their own),
 *  newest first, each with its status and, once compiled, the link that opens it in a new tab. Details opens the report's
 *  panel: the round's fetch script, the uploads so far, Compile and Open — so a report an agent started, or one built in
 *  another browser, can be fed and compiled from here too. The panel holds its upload token in this page's memory only
 *  (ADR-0023). Field text renders as text. */
export function Reports() {
  const [nonce, setNonce] = useState(0);
  const list = useAsync(
    (s) => reportApi.list(s).then(reportRows, (e: unknown) => { throw new Error(errorWords(e)); }),   // the error in words
    [nonce],
  );
  const [open, setOpen] = useState<string | null>(null);
  const [seen, setSeen] = useState<Record<string, string>>({});   // a status an open panel saw after the list loaded
  const rows = list.data ?? [];
  const refresh = () => { setSeen({}); setNonce((n) => n + 1); };
  return (
    <div className="screen screen--wide">
      <div className="screen__head files__head">
        <div>
          <h1 className="screen__title">Reports</h1>
          <p className="screen__sub">Your product decision reports, newest first. Each one opens as its own page.</p>
        </div>
        <button type="button" className="btn" onClick={refresh}><Icon name="refresh" /> Refresh</button>
      </div>
      {list.data == null && !list.error ? (
        <div className="card"><Skeleton rows={4} label="Loading reports…" /></div>
      ) : list.error && list.data == null ? (
        <div className="card"><ErrorState message={list.error} onRetry={refresh} /></div>
      ) : !rows.length ? (
        <div className="card">
          <EmptyState title="No decision reports yet">
            In Chat, ask a product question, then press Build decision report under the ideas. Your agent can start one too.
          </EmptyState>
        </div>
      ) : (
        <ul className="pr-reports" aria-label="Decision reports">
          {rows.map((r) => (
            <ReportItem key={r.key} row={r} status={seen[r.reportId] ?? r.status} open={open === r.reportId}
                        onToggle={() => setOpen((o) => (o === r.reportId ? null : r.reportId))}
                        onStatus={(s) => setSeen((m) => (m[r.reportId] === s ? m : { ...m, [r.reportId]: s }))} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ReportItem({ row, status, open, onToggle, onStatus }: {
  row: ReportRow; status: string; open: boolean; onToggle: () => void; onStatus: (status: string) => void;
}) {
  const panelId = useId();
  const s = reportStatus(status);
  const title = row.title || "Untitled report";
  const meta = [row.createdAt && `Created ${when(row.createdAt)}`, row.products,
                row.uploads !== null && `${row.uploads.toLocaleString()} upload${row.uploads === 1 ? "" : "s"}`].filter(Boolean).join(" · ");
  return (
    <li className="card pr-reports__row" data-status={status || undefined}>
      <div className="pr-reports__head">
        <h2 className="pr-reports__title">{title}</h2>
        <span className={`pill pill--${s.tone}`} title={status || undefined}><span className="pill__dot" />{s.words}</span>
      </div>
      {meta && <p className="pr-reports__meta faint">{meta}</p>}
      <div className="pr-reports__actions">
        {(row.hasPage || status === "compiled") && (
          <a className="btn" href={reportHref(row.reportId)} target="_blank" rel="noopener noreferrer">
            <Icon name="external" size={14} />Open report<span className="sr-only">: {title} (opens in a new tab)</span>
          </a>
        )}
        <button type="button" className="btn pr-reports__toggle" aria-expanded={open} aria-controls={open ? panelId : undefined}
                onClick={onToggle}>
          <Icon name="chevronDown" size={14} />{open ? "Hide details" : "Details"}<span className="sr-only">: {title}</span>
        </button>
        <span className="pr-reports__id faint mono">{row.reportId}</span>
      </div>
      {open && <div id={panelId}><ReportPanel reportId={row.reportId} onStatus={onStatus} /></div>}
    </li>
  );
}
