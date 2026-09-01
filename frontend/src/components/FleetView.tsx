import { useEffect, useState } from "react";

type LaneRow = {
  name: string;
  model: string;
  role: string;
  structured?: string | null;
  limiter?: {
    effective?: number;
    ceiling?: number;
    increases?: number;
    decreases?: number;
    updated_at?: string;
  };
};
type WorkerRow = {
  worker_id: string;
  worker_type: string;
  status: string;
  processed: number;
  current_ticket: string | null;
  last_error: string | null;
  heartbeat_age_s: number | null;
};
type QueueRow = { stage: string; status: string; count: number };
type Fleet = {
  lanes: LaneRow[];
  workers: WorkerRow[];
  queue: QueueRow[];
  enrichment: Record<string, number>;
};

export default function FleetView() {
  const [fleet, setFleet] = useState<Fleet | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const r = await fetch("/fleet");
        if (!r.ok) throw new Error(String(r.status));
        const d = await r.json();
        if (live) {
          setFleet(d);
          setErr(null);
        }
      } catch (e) {
        if (live) setErr(String(e));
      }
    };
    load();
    const t = setInterval(load, 5000);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, []);
  if (err) return <div className="panel">fleet board unavailable: {err}</div>;
  if (!fleet) return <div className="panel">loading fleet…</div>;
  const active = fleet.workers.filter(
    (w) => (w.heartbeat_age_s ?? 9e9) < 120,
  );
  const enr = fleet.enrichment;
  const ready = enr.READY ?? 0;
  const parents = enr.parents ?? 0;
  return (
    <div className="view-scroll">
      <div className="panel">
        <h3>Provider lanes ({fleet.lanes.length})</h3>
        <table className="doc-table">
          <thead>
            <tr>
              <th>Lane</th>
              <th>Model</th>
              <th>Role</th>
              <th>Concurrency (eff / cap)</th>
              <th>AIMD ↑ / ↓</th>
            </tr>
          </thead>
          <tbody>
            {fleet.lanes.map((l) => (
              <tr key={l.name}>
                <td className="mono">{l.name}</td>
                <td className="mono">{l.model}</td>
                <td>
                  <span
                    className={`status-pill ${
                      l.role === "enrichment"
                        ? "st-reconciling"
                        : "st-query_ready"
                    }`}
                  >
                    {l.role}
                  </span>
                </td>
                <td>
                  {l.limiter
                    ? `${l.limiter.effective ?? "?"} / ${l.limiter.ceiling ?? "?"}`
                    : "idle (no traffic yet)"}
                </td>
                <td>
                  {l.limiter
                    ? `${l.limiter.increases ?? 0} / ${l.limiter.decreases ?? 0}`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h3>
          Workers ({active.length} live / {fleet.workers.length} known)
        </h3>
        <table className="doc-table">
          <thead>
            <tr>
              <th>Worker</th>
              <th>Status</th>
              <th>Done</th>
              <th>Working on</th>
              <th>Beat</th>
            </tr>
          </thead>
          <tbody>
            {active.map((w) => (
              <tr key={w.worker_id}>
                <td className="mono">{w.worker_type}</td>
                <td>
                  <span
                    className={`status-pill ${
                      w.status === "quarantined"
                        ? "st-failed"
                        : "st-query_ready"
                    }`}
                    title={w.last_error ?? undefined}
                  >
                    {w.status}
                  </span>
                </td>
                <td>{w.processed}</td>
                <td className="mono">
                  {w.current_ticket ? w.current_ticket.slice(0, 18) + "…" : "idle"}
                </td>
                <td>{w.heartbeat_age_s}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h3>Job queue</h3>
        {fleet.queue.length === 0 ? (
          <p style={{ opacity: 0.8 }}>Queue empty — everything settled.</p>
        ) : (
          <div className="readiness" style={{ flexWrap: "wrap", gap: 8 }}>
            {fleet.queue.map((q) => (
              <span
                key={`${q.stage}:${q.status}`}
                className={`status-pill ${
                  q.status === "failed" ? "st-failed" : "st-reconciling"
                }`}
              >
                {q.stage} · {q.status} · {q.count}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Enrichment coverage</h3>
        <div className="readiness">
          <span
            className={`status-pill ${
              parents > 0 && ready >= parents ? "st-query_ready" : "st-reconciling"
            }`}
          >
            ✨ {ready} / {parents} sections
          </span>
          {Object.entries(enr)
            .filter(([k]) => k !== "parents" && k !== "READY")
            .map(([k, v]) => (
              <span key={k} className="status-pill st-failed">
                {k}: {v}
              </span>
            ))}
        </div>
      </div>
    </div>
  );
}
