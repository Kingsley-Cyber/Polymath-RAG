import type { RetrievalReceipt } from "../lib/contracts";

/**
 * FRONTEND-V2-PLAN §3 — the five lane states, never collapsed.
 *
 *   ENABLED          the lane is configured for this turn        lane_sizes has the key
 *   FIRED            it ran and produced candidates              lane_sizes[lane] > 0
 *   ENTERED UNION    its candidates reached the merged set       funnel.lane_counts[lane]
 *   SURVIVED RERANK  they survived into the final selection      final_detail[].arrivals
 *   USED IN ANSWER   the answer cites one of its chunks          legend[].tag + chunk_id
 *
 * "A lane that FIRED did not thereby affect the answer" — U-1 measured additive lanes
 * that fire, enter the union, and never survive rerank. These columns exist so that is
 * visible instead of inferred.
 *
 * The backend names one lane three ways across the three receipt sections
 * (lane_sizes `hierarchical_children` · funnel `hierarchical` · arrivals
 * `HIERARCHICAL_ROUTE`). ALIASES is that mapping, written down rather than guessed; an
 * unknown name is shown under its own key rather than silently dropped.
 */
const ALIASES: Record<string, string> = {
  hierarchical_children: "hierarchical",
  HIERARCHICAL_ROUTE: "hierarchical",
  GLOBAL_DENSE_CHILD: "global_dense_child",
  GLOBAL_SPARSE_CHILD: "global_sparse_child",
  SHADOW_DUALREAD: "dualread",
  SEEALSO_FANOUT: "seealso_fanout",
  GRAPH_DEST: "graph_dest",
  LATENT_RESCUE: "latent_rescue",
  RESOLUTION_LIFT: "resolution_lift",
  ENTITY_CARD: "entity_card",
  SECTION_SUMMARY: "section_summary",
  DOCUMENT_SUMMARY: "document_summary",
};
const canon = (n: string) => ALIASES[n] ?? n;

/** Aggregate counts that are totals, not lanes. */
const NOT_A_LANE = new Set(["union", "union_uncapped"]);

interface Row {
  lane: string; fired: number | null; union: number | null;
  survived: number; used: number;
}

export function LaneTable({ receipt }: { receipt: RetrievalReceipt }) {
  const laneSizes = receipt.lane_sizes ?? {};
  const funnel = (receipt.funnel ?? {}) as { lane_counts?: Record<string, number>; counts?: Record<string, number> };
  const laneCounts = funnel.lane_counts ?? {};
  const finalDetail = (receipt.final_detail ?? []) as { chunk_id?: string; arrivals?: string[] }[];
  const legend = (receipt.legend ?? []) as { chunk_id?: string; tag?: string }[];

  const citedChunks = new Set(legend.filter((l) => l.tag).map((l) => l.chunk_id));

  const survived: Record<string, number> = {};
  const used: Record<string, number> = {};
  for (const d of finalDetail) {
    for (const a of d.arrivals ?? []) {
      const k = canon(a);
      survived[k] = (survived[k] ?? 0) + 1;
      if (d.chunk_id && citedChunks.has(d.chunk_id)) used[k] = (used[k] ?? 0) + 1;
    }
  }

  const names = new Set<string>();
  for (const k of Object.keys(laneSizes)) if (!NOT_A_LANE.has(k)) names.add(canon(k));
  for (const k of Object.keys(laneCounts)) names.add(canon(k));
  for (const k of Object.keys(survived)) names.add(k);

  const rows: Row[] = [...names].map((lane) => {
    const sizeKey = Object.keys(laneSizes).find((k) => canon(k) === lane);
    const unionKey = Object.keys(laneCounts).find((k) => canon(k) === lane);
    return {
      lane,
      fired: sizeKey ? (laneSizes[sizeKey] ?? 0) : null,
      union: unionKey ? (laneCounts[unionKey] ?? 0) : null,
      survived: survived[lane] ?? 0,
      used: used[lane] ?? 0,
    };
  }).sort((a, b) => (b.survived - a.survived) || ((b.fired ?? 0) - (a.fired ?? 0)) || a.lane.localeCompare(b.lane));

  const counts = funnel.counts ?? {};

  return (
    <>
      <div className="row mono faint" style={{ marginBottom: 10, gap: 14 }}>
        <span>engine <b className="dim">{receipt.engine}</b></span>
        <span>mode <b className="dim">{receipt.mode}</b></span>
        {Object.entries(counts).map(([k, v]) => <span key={k}>{k} <b className="dim">{v}</b></span>)}
        {receipt.graph_fact_count != null && <span>graph_facts <b className="dim">{receipt.graph_fact_count}</b></span>}
      </div>

      {receipt.degraded && receipt.degraded.length > 0 && (
        <div className="banner" style={{ marginBottom: 10 }}>degraded: {receipt.degraded.join(", ")}</div>
      )}

      <table className="t">
        <thead>
          <tr>
            <th>Lane</th><th>Enabled</th><th>Fired</th><th>Entered union</th>
            <th>Survived rerank</th><th>Used in answer</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.lane}>
              <td className="mono">{r.lane}</td>
              <td>{r.fired === null && r.union === null ? <span className="faint">—</span> : <span className="pill pill--unknown">yes</span>}</td>
              <td className="mono">{r.fired === null ? "—" : r.fired > 0
                ? <span className="pill pill--ready">{r.fired}</span>
                : <span className="faint">0</span>}</td>
              <td className="mono">{r.union === null ? "—" : r.union}</td>
              <td className="mono">{r.survived > 0
                ? <span className="pill pill--ready">{r.survived}</span>
                : <span className="faint">0</span>}</td>
              <td className="mono">{r.used > 0
                ? <span className="pill pill--ready">{r.used}</span>
                : <span className="faint">0</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="faint" style={{ marginTop: 10, fontSize: 12 }}>
        A lane that <b>fired</b> did not thereby affect the answer — read across to
        <b> survived rerank</b> and <b>used in answer</b>.
        {counts.cited === 0 && " (cited = 0: this synthesizer emitted no citations.)"}
      </div>
    </>
  );
}
