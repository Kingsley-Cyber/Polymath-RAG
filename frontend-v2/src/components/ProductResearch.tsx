import { useId, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import type { ProductResearchResult } from "../lib/contracts";
import {
  agentPrompt, cjEmptyWords, cjStatus, httpUrl, productView, startErrorWords,
  type HypothesisView, type ItemView, type OfferView, type ProductRunRef, type ProductView, type ReachView,
} from "../lib/productResearch";
import type { ProductReportRef } from "../lib/productReport";
import { CopyField } from "../ui/CopyField";
import { Icon } from "../ui/icons";
import { CiteRef, type CiteInfo } from "./Citations";
import { BuildReport } from "./ProductReport";
import "../styles/product.css";

/** PRODUCT-SEARCH-E2E — under the answer to a product question: one section per product hypothesis built from the person's
 *  library (its evidence tags resolve through the chat receipt like the answer's [S#] chips), what CJ Dropshipping lists for
 *  it, and Alibaba, which runs only through Agent Reach on the person's own device. When the server could not search a source
 *  the section says why and offers the Agent Reach commands to run locally. Then the decision report (PRODUCT-DECISION-REPORT-V1
 *  B6, components/ProductReport): build one from these hypotheses, feed it, compile it, open it. Last, the offer
 *  (TRAIL-INTERFACE-V1 T6): start the full governed research from here, then hand the run to the person's own agent with a
 *  ready prompt. Every field may be missing; field text renders as text, and only http(s) URLs become links or images. */

export interface ProductHandlers {
  /** The run started from the offer: Chat keeps it on the turn, so it persists with the chat. */
  onRunStarted?: (run: ProductRunRef) => void;
  /** Open the Research screen at that run. */
  onOpenResearch?: (runId: string) => void;
  /** PRODUCT-DECISION-REPORT-V1 B6: the decision report built from this answer — Chat keeps its id on the turn. */
  onReportStarted?: (report: ProductReportRef) => void;
}

export function ProductResearch({ data, cites, run = null, report = null, question = "", onRunStarted, onOpenResearch, onReportStarted }: {
  data: ProductResearchResult | null | undefined;
  cites: Map<string, CiteInfo>;
  /** the run already started from this answer (kept on the turn) */
  run?: ProductRunRef | null;
  /** the decision report already built from this answer (kept on the turn) */
  report?: ProductReportRef | null;
  /** the person's question, sent as the report's message */
  question?: string;
} & ProductHandlers) {
  const v = useMemo(() => productView(data), [data]);
  const headId = useId();
  if (!v) return null;
  const intent = [v.seed && `“${v.seed}”`, v.audience && `for ${v.audience}`, v.geography && `in ${v.geography}`].filter(Boolean);
  return (
    <section className="pr" aria-labelledby={headId} data-contract={v.contract || undefined}>
      <div className="pr__head">
        <h3 className="pr__title" id={headId}>Product ideas from your library</h3>
        {intent.length > 0 && <p className="pr__intent">{intent.join(" · ")}</p>}
      </div>
      {v.hypotheses.map((h, i) => <Hypothesis key={h.key} h={h} n={i + 1} cites={cites} />)}
      {v.noTerminalNote && <p className="pr__note"><Icon name="info" size={15} />{v.noTerminalNote}</p>}
      {v.limitations.length > 0 && (
        <div className="pr__limits">
          <span className="label">Keep in mind</span>
          <ul>{v.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </div>
      )}
      <BuildReport view={v} question={question} report={report} onReportStarted={onReportStarted} />
      {v.offer && <Offer offer={v.offer} view={v} run={run} onRunStarted={onRunStarted} onOpenResearch={onOpenResearch} />}
    </section>
  );
}

function Hypothesis({ h, n, cites }: { h: HypothesisView; n: number; cites: Map<string, CiteInfo> }) {
  const id = useId();
  return (
    <section className="pr-hyp" aria-labelledby={id}>
      <h4 className="pr-hyp__title" id={id}>{h.title || `Idea ${n}`}</h4>
      {h.problem && <p className="pr-hyp__problem">{h.problem}</p>}
      {(h.audience || h.tags.length > 0) && (
        <p className="pr-hyp__meta">
          {h.audience && <span><span className="label">For</span> {h.audience}</span>}
          {h.tags.length > 0 && (
            <span className="pr-hyp__tags">
              <span className="label">From your library</span>{" "}
              {h.tags.map((tag) => <CiteRef key={tag} tag={tag} info={cites.get(tag)} />)}
            </span>
          )}
        </p>
      )}
      {h.terms.length > 0 && <p className="pr-hyp__terms faint">Searched for: {h.terms.join(" · ")}</p>}
      {h.cj && <CjFinds cj={h.cj} />}
      {h.alibaba && (
        <div className="pr-src" data-source="alibaba" data-status={h.alibaba.status || undefined}>
          <div className="pr-src__head"><span className="pr-src__name">Alibaba</span></div>
          <p className="pr-src__only">Alibaba runs only through Agent Reach on your own device.</p>
          {h.alibaba.reach?.why && <p className="pr-src__why">{h.alibaba.reach.why}</p>}
          {h.alibaba.reach && <ReachPanel reach={h.alibaba.reach} />}
        </div>
      )}
    </section>
  );
}

function CjFinds({ cj }: { cj: NonNullable<HypothesisView["cj"]> }) {
  const s = cjStatus(cj.status);
  const why = cj.reach?.why ?? "";
  return (
    <div className="pr-src" data-source="cj">
      <div className="pr-src__head">
        <span className="pr-src__name">CJ Dropshipping</span>
        <span className={`pill pill--${s.tone}`} title={cj.status || undefined} data-status={cj.status || undefined}>
          <span className="pill__dot" />{s.words}
        </span>
      </div>
      {cj.items.length > 0 ? (
        <>
          <ul className="pr-grid" aria-label="CJ Dropshipping listings">
            {cj.items.map((it) => <CjCard key={it.key} item={it} />)}
          </ul>
          {why && <p className="pr-src__why">{why}</p>}
        </>
      ) : (
        <div className="pr-empty" title={cj.reach?.reasonCode || undefined}>
          <p className="pr-empty__title">{cjEmptyWords(cj.status)}</p>
          {why && <p className="pr-empty__why">{why}</p>}
        </div>
      )}
      {cj.reach && <ReachPanel reach={cj.reach} />}
    </div>
  );
}

function CjCard({ item }: { item: ItemView }) {
  const [broken, setBroken] = useState(false);              // a photo that fails to load leaves the placeholder, not a broken icon
  const price = item.discount || item.price;
  const facts = ([["MOQ", item.moq], ["Supplier", item.supplier], ["Stores listing", item.stores], ["Warehouse stock", item.stock]] as const)
    .filter(([, value]) => value);
  return (
    <li className="pr-card">
      {item.image && !broken ? (
        <img className="pr-card__img" src={item.image} alt={item.title || "CJ Dropshipping product photo"} loading="lazy"
             decoding="async" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
      ) : (
        <div className="pr-card__img pr-card__img--none" aria-hidden="true">No photo</div>
      )}
      <div className="pr-card__body">
        <p className="pr-card__title" title={item.title || undefined}>{item.title || "Untitled listing"}</p>
        {price && (
          <p className="pr-card__price">
            <strong>{price}</strong>
            {item.discount && item.price && <s><span className="sr-only">was </span>{item.price}</s>}
          </p>
        )}
        {facts.length > 0 && (
          <dl className="pr-card__facts">
            {facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
        )}
        {item.url && (
          <a className="pr-card__link" href={item.url} target="_blank" rel="noopener noreferrer">
            View on CJ<span className="sr-only">: {item.title || "this listing"} (opens in a new tab)</span>
            <Icon name="external" size={13} />
          </a>
        )}
      </div>
    </li>
  );
}

/** The commands to run on one's own device when the server could not search a source, each with its copy button, and where
 *  Agent Reach installs from with the command that checks it works. Collapsed until opened. */
function ReachPanel({ reach }: { reach: ReachView }) {
  const repoUrl = httpUrl(reach.repo);
  return (
    <details className="pr-reach">
      <summary className="pr-reach__summary"><Icon name="terminal" size={15} />Run it on your own device with Agent Reach</summary>
      <div className="pr-reach__body">
        {reach.runOn && <p className="pr-reach__line"><span className="label">Where</span> {reach.runOn}</p>}
        {reach.commands.length > 0 && (
          <ol className="pr-reach__cmds" aria-label="Commands to run">
            {reach.commands.map((c, i) => (
              <li key={i}>
                {(c.what || c.forEach) && (
                  <p className="pr-reach__what">{[c.what, c.forEach && `for each ${c.forEach}`].filter(Boolean).join(", ")}</p>
                )}
                <CopyField value={c.run} what={`command ${i + 1}`} />
                {c.then && <p className="pr-reach__then">Then {c.then}</p>}
              </li>
            ))}
          </ol>
        )}
        {reach.repo && (
          <div className="pr-reach__line">
            <span className="label">Install Agent Reach from</span>{" "}
            {repoUrl
              ? <a href={repoUrl} target="_blank" rel="noopener noreferrer">{reach.repo}<span className="sr-only"> (opens in a new tab)</span></a>
              : <CopyField value={reach.repo} what="install source" />}
            {reach.how && <p className="pr-reach__then">{reach.how}</p>}
          </div>
        )}
        {reach.verify && (
          <div className="pr-reach__line pr-reach__verify">
            <span className="label">Check it works</span>
            <CopyField value={reach.verify} what="check command" />
          </div>
        )}
        {reach.never && <p className="pr-reach__never"><Icon name="alert" size={14} />{reach.never}</p>}
        {reach.walls && <p className="pr-reach__then">{reach.walls}</p>}
      </div>
    </details>
  );
}

/** T6: start the full governed research for the signed-in person, then show the run id, the way to the Research screen and the
 *  prompt that hands the run to their own agent. A failure stays on screen in words (status and message); Start is offered again. */
function Offer({ offer, view, run, onRunStarted, onOpenResearch }: {
  offer: OfferView; view: ProductView; run: ProductRunRef | null;
} & ProductHandlers) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [local, setLocal] = useState<ProductRunRef | null>(null);
  const sending = useRef(false);                            // one start per click, even on a double click
  const kept = run && typeof run.run_id === "string" && run.run_id ? run : null;
  const started = kept ?? local;

  async function start() {
    if (sending.current) return;
    sending.current = true;
    setBusy(true);
    setError("");
    try {
      const ref = await api.adapterStart({ adapter_id: offer.adapterId, input: offer.input });
      if (!ref || typeof ref.run_id !== "string" || !ref.run_id) throw new Error("the server's reply names no run (no run_id)");
      const r: ProductRunRef = { run_id: ref.run_id, adapter_id: ref.adapter_id || offer.adapterId, status: ref.status, started_at: Date.now() };
      setLocal(r);
      onRunStarted?.(r);
    } catch (e) {
      setError(startErrorWords(e));
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="pr-offer">
      <h4 className="pr-offer__title">Full product research</h4>
      {offer.note && <p className="pr-offer__note">{offer.note}</p>}
      {offer.whoDrives && <p className="pr-offer__note dim">Who drives it: {offer.whoDrives}</p>}
      {started ? (
        <div className="pr-offer__started">
          <p className="pr-offer__run" role="status">
            Started run <code className="mono">{started.run_id}</code>
            {onOpenResearch && (
              <> · <button type="button" className="linklike" onClick={() => onOpenResearch(started.run_id)}>Open it in Research</button></>
            )}
          </p>
          <p className="pr-offer__note dim">Your agent drives the run from here: paste this prompt into it.</p>
          <CopyField value={agentPrompt(started, { seed: view.seed, repo: view.repo, verify: view.verify })}
                     what="prompt for your agent" block primary />
        </div>
      ) : (
        <div className="pr-offer__actions">
          <button type="button" className="btn btn--primary" onClick={() => void start()} disabled={busy} aria-busy={busy || undefined}>
            <Icon name="play" size={14} />{busy ? "Starting…" : "Start full research"}
          </button>
        </div>
      )}
      {error && <div className="banner banner--bad" role="alert">Couldn't start the full research. {error}</div>}
    </div>
  );
}
