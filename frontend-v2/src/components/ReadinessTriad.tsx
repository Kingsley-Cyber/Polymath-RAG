import type { Verdict } from "../lib/readiness";
import { Pill } from "./Pill";

/**
 * FRONTEND-V2-PLAN §7 — three DISTINCT concepts, always shown together so no single
 * badge can stand in for the others.
 */
export function ReadinessTriad({ control, semantic, vnext }: {
  control: Verdict; semantic: Verdict; vnext: Verdict;
}) {
  const rows: [string, Verdict][] = [
    ["Control ready", control],
    ["Semantic ready", semantic],
    ["vNext ready", vnext],
  ];
  return (
    <div className="grid grid--3">
      {rows.map(([name, v]) => (
        <div className="card" key={name}>
          <div className="label" style={{ marginBottom: 8 }}>{name}</div>
          <Pill v={v} />
          {v.detail && <div className="dim mono" style={{ marginTop: 8 }}>{v.detail}</div>}
        </div>
      ))}
    </div>
  );
}
