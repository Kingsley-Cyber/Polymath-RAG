import { useState } from "react";
import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { controlReady } from "../lib/readiness";
import { Pill } from "../components/Pill";

const FUNCTIONS = ["GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP", "CHAT"] as const;

/**
 * F10 — Control Plane (FRONTEND-V2-PLAN §9), function-first.
 *
 * Two honesty rules this screen exists to keep:
 *
 *  1. `limiter_refused` is LOCAL (zero HTTP) and must stay visually distinct from a
 *     real HTTP 429, which cost a provider request.
 *  2. A DORMANT stall (PENDING_ON_PREDECESSOR / PENDING_ADVANCE_BLOCKED /
 *     PENDING_OWNER_STAGE / RUN_SETTLED_NOT_PROMOTED — nothing live behind it) is not
 *     a current pipeline failure; this screen shows the backend's own active/dormant
 *     split (GAP-6) rather than re-deriving it from queued/blocked counts.
 *
 * GAP-1 (closed 2026-09-12): `/control_plane` is now the ONLY call this screen makes
 * for health — `control_ready` and its embedded `pipeline` snapshot replace the
 * separate `/ready` + `/health/pipeline` fetches this screen used to compose itself.
 */
export function ControlPlane({ corpusId }: { corpusId: string }) {
  const [fn, setFn] = useState<string | null>(null);
  const cp = useAsync((s) => api.controlPlane(corpusId, s), [corpusId]);
  const lanes = useAsync((s) => (fn ? api.poolLanes(fn, s) : Promise.resolve(null)), [fn]);

  const control = controlReady(cp.data?.control_ready);
  const p = (cp.data?.control_ready?.pipeline ?? {}) as Record<string, unknown>;
  const causes = (p.causes as string[] | undefined) ?? [];
  const stallsActive = typeof p.stalls_active === "number" ? p.stalls_active : null;
  const stallsDormant = typeof p.stalls_dormant === "number" ? p.stalls_dormant : null;
  const queued = typeof p.queued_tickets === "number" ? p.queued_tickets : null;
  const liveWorkers = typeof p.live_workers === "number" ? p.live_workers : null;
  const blocked = typeof p.blocked_workers === "number" ? p.blocked_workers : null;

  const pools = cp.data?.pools ?? {};

  return (
    <div className="screen screen--wide">
      <div className="screen__head">
        <h1 className="screen__title">Control Plane</h1>
        <p className="screen__sub">Is the machinery healthy? — corpus <span className="mono">{corpusId}</span></p>
      </div>

      <div className="row" style={{ marginBottom: 12 }}>
        <Pill v={control} />
        {liveWorkers != null && <span className="mono faint">{liveWorkers} live workers</span>}
        {queued != null && <span className="mono faint">{queued} queued tickets</span>}
        {blocked != null && <span className="mono faint">{blocked} blocked workers</span>}
      </div>

      {stallsDormant != null && stallsDormant > 0 && (
        <div className="banner" style={{ marginBottom: 14 }}>
          <b>{stallsDormant} dormant stall record{stallsDormant === 1 ? "" : "s"}</b> — nothing live is running
          behind them (predecessor/advance/promotion backlog), so they no longer pin this badge to DEGRADED.
          {stallsActive != null && stallsActive > 0 && (
            <> <b>{stallsActive} ACTIVE</b> stall{stallsActive === 1 ? "" : "s"} remain
            {causes.length > 0 && <>: <span className="mono">{causes.join(" · ")}</span></>}.</>
          )}
          {" "}They are not cleared, because clearing them to make this badge green would destroy the evidence
          the backlog classification depends on.
        </div>
      )}

      {cp.error && <div className="banner banner--bad" style={{ marginBottom: 14 }}>{cp.error}</div>}

      {cp.data && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div className="label" style={{ marginBottom: 8 }}>Corpus summary ({cp.data.contract})</div>
          <div className="row" style={{ gap: 20 }}>
            <Stat label="documents" value={cp.data.summary.documents} />
            <Stat label="semantic ready" value={cp.data.summary.semantic_ready} />
            <Stat label="blocked" value={cp.data.summary.blocked} bad={cp.data.summary.blocked > 0} />
            <Stat label="processing" value={cp.data.summary.processing_active}
                  note={cp.data.summary.processing_stalled > 0
                        ? `+${cp.data.summary.processing_stalled} stalled (>3min since last move)` : undefined}
                  bad={cp.data.summary.processing_stalled > 0} />
          </div>
        </div>
      )}

      <div className="grid grid--2">
        {FUNCTIONS.map((f) => {
          const pool = pools[f];
          const prov = (pool?.provider ?? {}) as Record<string, number | null>;
          const laneCounts = pool?.lanes;   // distinct from `lanes`, the drill-down fetch
          return (
            <div className="card" key={f}>
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                <b className="mono">{f}</b>
                <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }}
                        onClick={() => setFn(fn === f ? null : f)}>
                  {fn === f ? "hide lanes" : "lanes"}
                </button>
              </div>
              <div className="row" style={{ gap: 16 }}>
                <Stat label="queued" value={pool?.queued ?? 0} />
                <Stat label="processing" value={pool?.processing ?? 0} />
                <Stat label="retry" value={pool?.retry ?? 0} />
                <Stat label="failed" value={pool?.failed ?? 0} bad={(pool?.failed ?? 0) > 0} />
                {laneCounts && <Stat label="lanes active" value={laneCounts.active}
                                note={laneCounts.active === laneCounts.total ? undefined
                                      : `${laneCounts.total - laneCounts.active} not active`}
                                bad={laneCounts.active === 0} />}
              </div>
              {Object.keys(prov).length > 0 && (
                <div className="row" style={{ gap: 16, marginTop: 10 }}>
                  {"limiter_refused" in prov && (
                    <Stat label="limiter refused" value={prov.limiter_refused ?? 0}
                          note="LOCAL refusal — zero HTTP, no provider request spent" />
                  )}
                  {"http_429" in prov && (
                    <Stat label="HTTP 429" value={prov.http_429 ?? 0} bad={(prov.http_429 ?? 0) > 0}
                          note="a REAL provider request that was throttled" />
                  )}
                  {"provider_requests" in prov && <Stat label="requests" value={prov.provider_requests ?? 0} />}
                  {"valid_maps_persisted" in prov && <Stat label="maps persisted" value={prov.valid_maps_persisted ?? 0} />}
                </div>
              )}
              {fn === f && (
                <div style={{ marginTop: 12 }}>
                  {lanes.loading && <div className="faint">loading lanes…</div>}
                  {lanes.data && (
                    <table className="t">
                      <thead><tr><th>Model</th><th>Lane</th><th>Account (env name)</th><th>Role</th><th>Reach</th><th>RPD</th></tr></thead>
                      <tbody>
                        {lanes.data.models.flatMap((m) => m.lanes.map((l) => (
                          <tr key={l.lane}>
                            <td className="mono faint">{m.model}</td>
                            <td className="mono">{l.lane}</td>
                            <td className="mono faint">{l.account_env}</td>
                            <td className="mono faint">{l.role}</td>
                            <td>{l.reachability === "active"
                              ? <span className="pill pill--ready">active</span>
                              : <span className="pill pill--blocked">{l.reachability}</span>}</td>
                            <td className="mono">{l.capacity.rpd ?? "—"}</td>
                          </tr>
                        )))}
                      </tbody>
                    </table>
                  )}
                  <div className="faint" style={{ marginTop: 8, fontSize: 11.5 }}>
                    Account ENV NAMES only — no secret value is ever sent to the browser.
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="faint" style={{ marginTop: 12, fontSize: 12 }}>
        <code>parent_enrichment</code> is a legacy stage pin, not a fifth pool.
      </div>
    </div>
  );
}

function Stat({ label, value, note, bad }: { label: string; value: number; note?: string; bad?: boolean }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="mono" style={{ fontSize: 16, color: bad ? "var(--bad)" : undefined }}>{value}</div>
      {note && <div className="faint" style={{ fontSize: 11, maxWidth: 210 }}>{note}</div>}
    </div>
  );
}
