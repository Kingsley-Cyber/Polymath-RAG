import { useCallback, useEffect, useState } from "react";
import { fetchControlPlane, fetchPoolLanes, fetchPredicates } from "../api";
import type { ControlPlane, PoolLanesDetail, PoolStatus, PredicateRow } from "../types";
import FleetView from "./FleetView";

/** CONTROL-PLANE-STATUS-V1 screen (operational-UI §3-8): "is the machinery healthy?".
 * Renders the ONE backend authority — corpus summary + the four FUNCTIONAL POOLS
 * (GRAPH_EXTRACTION / DOCUMENT_PROFILE / PMAP / CHAT), each drilling into its model →
 * account/key lanes. parent_enrichment is a legacy bridge, never a fifth pool (§3).
 * Nothing here is recomputed and no API-key value is ever shown (§8, §14). */

// The four functional pools, in drain order. parent_enrichment is deliberately absent.
const POOL_ORDER = ["GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP", "CHAT"] as const;
const POOL_LABEL: Record<string, string> = {
  GRAPH_EXTRACTION: "Graph extraction",
  DOCUMENT_PROFILE: "Document profile",
  PMAP: "Parent MAP (pMAP)",
  CHAT: "Chat / synthesis",
};

function Metric({ label, value, bad, title }: { label: string; value: number | string; bad?: boolean; title?: string }) {
  return (
    <span className="cp-metric" title={title}>
      <span className="cp-metric-value" style={bad ? { color: "var(--bad)" } : undefined}>{value}</span>
      <span className="cp-metric-label">{label}</span>
    </span>
  );
}

/** healthy-lane pill: green when every configured lane is reachable, red on a
 * credential gap, amber when some are disabled. */
function LanesPill({ p }: { p: PoolStatus }) {
  const l = p.lanes;
  const gap = (l.credential_absent ?? 0) > 0;
  const disabled = (l.disabled ?? 0) > 0;
  const cls = gap ? "st-failed" : disabled ? "st-reconciling" : "st-query_ready";
  const extra = [gap ? `${l.credential_absent} missing key` : "", disabled ? `${l.disabled} disabled` : ""]
    .filter(Boolean).join(" · ");
  return (
    <span className={`status-pill ${cls}`} title={`${l.active} of ${l.total} lanes reachable${extra ? " · " + extra : ""}`}>
      {l.active}/{l.total} lanes
    </span>
  );
}

/** The queue depth is the same stage-ticket accounting the drain runs on. */
function QueueRow({ p }: { p: PoolStatus }) {
  if (p.latency_pool) return <div className="cp-metrics"><span className="cp-note">latency pool — served on demand, not queued</span></div>;
  const failed = p.failed ?? 0;
  const retry = p.retry ?? 0;
  return (
    <div className="cp-metrics">
      <Metric label="queued" value={p.queued ?? 0} />
      <Metric label="processing" value={p.processing ?? 0} />
      <Metric label="retry" value={retry} bad={retry > 0} />
      <Metric label="failed" value={failed} bad={failed > 0} />
    </div>
  );
}

/** Provider accounting — the counters that separate LOCAL limiter refusals from
 * ACTUAL provider HTTP 429 (§4), and the pMAP valid-maps/request efficiency (§6). */
function ProviderRow({ fn, p }: { fn: string; p: PoolStatus }) {
  const pv = p.provider;
  if (!pv) return null;
  if (fn === "PMAP") {
    return (
      <div className="cp-metrics cp-provider">
        <Metric label="requests" value={pv.provider_requests ?? 0} title="provider HTTP requests dispatched" />
        <Metric label="valid maps" value={pv.valid_maps_persisted ?? 0} />
        <Metric label="maps / request" value={(pv.maps_per_request ?? 0).toFixed(2)}
          title="efficiency — valid maps persisted per HTTP request. compound-mini qualifies batches of 15; architectural target is 60." />
        <Metric label="limiter refused" value={pv.limiter_refused ?? 0}
          title="LOCAL limiter refusals — zero provider HTTP, not consumption. NEVER an HTTP 429." />
        <Metric label="HTTP 429" value={pv.http_429 ?? 0} bad={(pv.http_429 ?? 0) > 0}
          title="ACTUAL provider rate-limit responses (real capacity events)" />
        <Metric label="transport err" value={pv.transport_errors ?? 0} bad={(pv.transport_errors ?? 0) > 0} />
        <Metric label="empty 200" value={pv.empty_completions ?? 0} bad={(pv.empty_completions ?? 0) > 0}
          title="200 OK with no usable map (structured-output miss)" />
      </div>
    );
  }
  // GRAPH_EXTRACTION
  const unacc = pv.neighborhoods_unaccounted ?? 0;
  return (
    <div className="cp-metrics cp-provider">
      <Metric label="requests" value={pv.provider_requests ?? 0} title="provider HTTP requests dispatched" />
      <Metric label="neighborhoods" value={pv.neighborhoods_sent ?? 0} title="neighborhoods sent to the extractor" />
      <Metric label="dropped" value={pv.neighborhoods_dropped ?? 0} bad={(pv.neighborhoods_dropped ?? 0) > 0} />
      <Metric label="unaccounted" value={unacc} bad={unacc > 0} title="sent − (returned + dropped); should be 0" />
      <Metric label="entities" value={pv.entities ?? 0} />
      <Metric label="relations" value={pv.relations ?? 0} />
    </div>
  );
}

/** Model → account/key lanes (§8): VIEW-ONLY, non-secret. account_env is the env
 * NAME; no key value is ever present in the payload or rendered here. */
function LaneTable({ detail }: { detail: PoolLanesDetail }) {
  return (
    <div className="cp-lanes">
      {detail.models.map((m) => (
        <div key={m.model} className="cp-model">
          <div className="cp-model-head">
            <span className="mono">{m.model}</span>
            <span className="cp-note">{m.lanes.length} account lane{m.lanes.length === 1 ? "" : "s"}</span>
          </div>
          <table className="doc-table cp-lane-table">
            <thead>
              <tr>
                <th>Lane</th><th>Account key (name)</th><th>Reach</th><th>Role</th>
                <th title="rpm · rpd · concurrency · MAP batch cap">Capacity</th>
                <th title="live AIMD limiter: effective/ceiling, ↑/↓, today's count">Limiter</th>
              </tr>
            </thead>
            <tbody>
              {m.lanes.map((l) => {
                const c = l.capacity ?? {};
                const live = l.live ?? {};
                const cap = [
                  c.rpm != null ? `${c.rpm}rpm` : "",
                  c.rpd != null ? `${c.rpd}rpd` : "",
                  c.concurrency != null ? `${c.concurrency}c` : "",
                  c.map_batch_cap != null ? `batch ${c.map_batch_cap}` : "",
                ].filter(Boolean).join(" · ");
                const hasLive = live.effective != null || live.ceiling != null || live.day_count != null;
                return (
                  <tr key={l.lane}>
                    <td className="mono">{l.lane}</td>
                    <td className="mono">{l.account_env}{l.configured ? "" : " (unset)"}</td>
                    <td>
                      <span className={`status-pill ${l.reachability === "active" ? "st-query_ready"
                        : l.reachability === "credential_absent" ? "st-failed" : "st-reconciling"}`}>
                        {l.reachability}
                      </span>
                    </td>
                    <td>{l.role}{l.family ? <span className="cp-note"> · {l.family}</span> : null}</td>
                    <td className="mono">{cap || "—"}</td>
                    <td className="mono">
                      {hasLive
                        ? `${live.effective ?? "?"}/${live.ceiling ?? "?"}  ↑${live.increases ?? 0}/↓${live.decreases ?? 0}`
                          + (live.day_count != null ? `  ${live.day_count}/day` : "")
                        : <span className="cp-note">idle (no traffic yet)</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

function PredicateBars({ rows }: { rows: PredicateRow[] }) {
  if (rows.length === 0) return <div className="cp-note">no accepted facts yet</div>;
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <div className="cp-predicates">
      {rows.map((r) => (
        <div key={r.predicate} className="cp-pred-row">
          <span className="cp-pred-name mono">{r.predicate}</span>
          <span className="cp-pred-bar"><span style={{ width: `${(r.count / max) * 100}%` }} /></span>
          <span className="cp-pred-count">{r.count}</span>
        </div>
      ))}
    </div>
  );
}

function PoolCard({
  fn, p, corpus, lanes, onToggleLanes, predicates, onTogglePredicates,
}: {
  fn: string; p: PoolStatus; corpus: string;
  lanes: PoolLanesDetail | null; onToggleLanes: () => void;
  predicates: PredicateRow[] | null; onTogglePredicates: () => void;
}) {
  return (
    <div className="panel cp-pool">
      <div className="cp-pool-head">
        <h3 style={{ margin: 0 }}>{POOL_LABEL[fn] ?? fn}</h3>
        <span className="cp-fn mono">{fn}</span>
        <span className="cp-spacer" />
        <LanesPill p={p} />
      </div>
      <QueueRow p={p} />
      <ProviderRow fn={fn} p={p} />
      <div className="cp-actions">
        <button className="chunk-chip" onClick={onToggleLanes}>
          {lanes ? "▾ lanes" : "▸ model / account lanes"}
        </button>
        {fn === "GRAPH_EXTRACTION" && corpus && (
          <button className="chunk-chip" onClick={onTogglePredicates}>
            {predicates ? "▾ predicates" : "▸ predicate distribution"}
          </button>
        )}
      </div>
      {lanes && <LaneTable detail={lanes} />}
      {fn === "GRAPH_EXTRACTION" && predicates && <PredicateBars rows={predicates} />}
    </div>
  );
}

export default function ControlPlaneView({ corpus }: { corpus: string }) {
  const [cp, setCp] = useState<ControlPlane | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lanes, setLanes] = useState<Record<string, PoolLanesDetail>>({});
  const [predicates, setPredicates] = useState<PredicateRow[] | null>(null);
  const [showFleet, setShowFleet] = useState(false);

  const load = useCallback(async () => {
    if (!corpus) { setCp(null); return; }
    try {
      setCp(await fetchControlPlane(corpus));
      setErr(null);
    } catch (e) {
      setErr(String(e));
    }
  }, [corpus]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const toggleLanes = async (fn: string) => {
    if (lanes[fn]) {
      setLanes((m) => { const n = { ...m }; delete n[fn]; return n; });
      return;
    }
    try {
      const d = await fetchPoolLanes(fn);
      setLanes((m) => ({ ...m, [fn]: d }));
    } catch { /* drill-down is best-effort */ }
  };

  const togglePredicates = async () => {
    if (predicates) { setPredicates(null); return; }
    try {
      setPredicates(await fetchPredicates(corpus, 14));
    } catch { setPredicates([]); }
  };

  if (!corpus)
    return (
      <div className="view-scroll">
        <div className="panel">Select a corpus in the top bar to scope the control plane.</div>
      </div>
    );
  if (err && !cp) return <div className="view-scroll"><div className="panel">control plane unavailable: {err}</div></div>;
  if (!cp) return <div className="view-scroll"><div className="panel">loading control plane…</div></div>;

  const s = cp.summary;
  const blockedBad = s.blocked > 0;
  return (
    <div className="view-scroll">
      <div className="panel">
        <h3>Control plane · {cp.corpus_id}</h3>
        <div className="cp-summary">
          <Metric label="documents" value={s.documents} />
          <Metric label="semantic ready" value={s.semantic_ready} />
          <Metric label="processing" value={s.processing} />
          <Metric label="blocked" value={s.blocked} bad={blockedBad} />
        </div>
      </div>

      {POOL_ORDER.filter((fn) => cp.pools[fn]).map((fn) => (
        <PoolCard
          key={fn}
          fn={fn}
          p={cp.pools[fn]}
          corpus={corpus}
          lanes={lanes[fn] ?? null}
          onToggleLanes={() => toggleLanes(fn)}
          predicates={predicates}
          onTogglePredicates={togglePredicates}
        />
      ))}

      <div className="panel">
        <div className="cp-pool-head">
          <h3 style={{ margin: 0 }}>Fleet detail</h3>
          <span className="cp-note">workers · AIMD lanes · job queue (legacy fleet board)</span>
          <span className="cp-spacer" />
          <button className="chunk-chip" onClick={() => setShowFleet((v) => !v)}>
            {showFleet ? "▾ hide" : "▸ show"}
          </button>
        </div>
        <p className="cp-note" style={{ marginTop: 6 }}>
          parent_enrichment is a legacy retrieval-surface bridge, not a functional pool — it appears in the
          fleet lanes below, never as a fifth drain pool above.
        </p>
        {showFleet && <FleetView />}
      </div>
    </div>
  );
}
