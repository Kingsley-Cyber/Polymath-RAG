// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { RunView } from "../lib/contracts";
import { Research } from "../screens/Research";

/** TRAIL-INTERFACE-V1 T2–T4 — the Research screen watches and reads runs: outcomes in words, TrailSignal's refusals with the
 *  hypothesis they refuse, gates as "observed of minimum", evidence counts by platform, polling that stops when the run ends,
 *  and Cancel only while a run can still be cancelled. Field text renders as text, never HTML. T5: the dossier is a plain link to
 *  the page the server renders (a new tab, or a download), and the owner's view carries the registry the run met. */

let host: HTMLDivElement;
let root: Root;
let calls: { path: string; method: string }[];
let view: RunView;

const RUNS = [{ run_id: "adr_1", adapter_id: "ecommerce.product_research", adapter_version: "0.7.0", title: "Cold hands while filming",
                status: "completed", current_step_id: null, steps_accepted: 84, harness_actions: 5, started_at: "2026-09-25T22:38:00Z",
                updated_at: null, finished_at: "2026-09-26T00:04:00Z", agent_identity: "claude-code", owner: null,
                outcome: "TrailSignal refused all 6 scores" }];

function makeView(over: Partial<RunView["run"]> = {}): RunView {
  return {
    run: { run_id: "adr_1", adapter_id: "ecommerce.product_research", adapter_version: "0.7.0", title: "Cold hands while filming",
           status: "completed", terminal: true, current_step_id: null, started_at: null, updated_at: null, finished_at: null,
           agent_identity: "claude-code", gap: null, steps_accepted: 84, harness_actions: 5, ...over },
    progress: [{ step_id: "A", type: "VALIDATE", title: "Understand seed", state: "done", visits: 1 },
               { step_id: "B", type: "AGENT_REASON", title: "Gather field evidence", state: "done", visits: 3 }],
    sections: {
      hypothesis_semantics: [{ hypothesis: { hypothesis_id: "hyp_a", statement: "<b>Photographers</b> lose feeling in their fingers" } }],
      score_refusals: [{ record_id: "r1", reason_code: "HARD_GATE_UNMET", hypothesis_id: "hyp_a" }],
      qualifications: [{ record_id: "q1", stage: "market_delta", state: "UNPROVEN", hypothesis_ids: ["hyp_a"],
                         gate_results: [{ gate_id: "current_price_checks", minimum: 3, observed: 1, passed: false }] }],
      evidence_admissions: [{ admitted: [{ evidence_role: "friction", independence_group: "reddit" },
                                         { evidence_role: "friction", independence_group: "tiktok" }],
                              rejected: [{ reason_code: "STALE" }] }],
      lived_clusters: [{ id: "c1", community: "hikers who carry camera kits", authority: "THIN", record_count: 3, thread_count: 2,
                         threshold: { min_records: 5, min_threads: 2 } }],
    },
    other_output_keys: ["mechanisms"], contradictions: [], unknowns: [], stored_result_shadowed: true,
  };
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  calls = [];
  view = makeView();
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    calls.push({ path, method: init?.method ?? "GET" });
    if (path.startsWith("/adapter/runs")) return Response.json({ runs: RUNS });
    if (path.endsWith("/view")) return Response.json(view);
    if (path.endsWith("/cancel")) return Response.json({ status: "cancelled" });
    return Response.json({});
  }));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function settle() { await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); }

async function openRun() {
  await act(async () => root.render(<Research />));
  await settle();
  await act(async () => (host.querySelector(".run-row") as HTMLButtonElement).click());
  await settle();
}

it("lists runs with their outcome in words", async () => {
  await act(async () => root.render(<Research />));
  await settle();
  expect(host.textContent).toContain("Cold hands while filming");
  expect(host.textContent).toContain("TrailSignal refused all 6 scores");
  expect(host.querySelector(".run-row .pill--degraded")).not.toBeNull();            // a refusal is not shown as success
});

it("shows TrailSignal's refusal with the hypothesis it refuses, as plain text", async () => {
  await openRun();
  expect(host.textContent).toContain("A required check wasn't met");
  expect(host.textContent).toContain("<b>Photographers</b> lose feeling in their fingers");   // text, not HTML
  expect(host.querySelector("b")).toBeNull();
  expect(host.textContent).toContain("rebuilt here from the run's own steps");
});

it("reads gates as observed of minimum, and counts evidence by platform", async () => {
  await openRun();
  expect(host.textContent).toContain("Current price checks: 1 of 3");
  expect(host.querySelector(".gate--fail")).not.toBeNull();
  expect(host.textContent).toContain("2 admitted from 2 independent platform(s)");
  expect(host.textContent).toContain("3 of 5 records");
});

it("a finished run offers no Cancel and is not polled", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  await openRun();
  expect(host.textContent).not.toContain("Cancel run");
  const before = calls.filter((c) => c.path.endsWith("/view")).length;
  await act(async () => { vi.advanceTimersByTime(12_000); });
  expect(calls.filter((c) => c.path.endsWith("/view")).length).toBe(before);
});

it("offers the dossier as a link that opens a new tab, and as a download — never fetched by the page", async () => {
  view = { ...makeView(), report: { available: true } };
  await openRun();
  const links = [...host.querySelectorAll("a")];
  const open = links.find((a) => a.textContent?.includes("Dossier"))!;
  expect(open.getAttribute("href")).toBe("/adapter/adr_1/report");
  expect(open.getAttribute("target")).toBe("_blank");
  expect(open.getAttribute("rel")).toBe("noopener noreferrer");
  const download = links.find((a) => a.textContent?.includes("Download"))!;
  expect(download.getAttribute("href")).toBe("/adapter/adr_1/report?download=1");
  expect(calls.some((c) => c.path.includes("/report"))).toBe(false);
});

it("offers no dossier for an adapter that has none", async () => {
  view = { ...makeView(), report: { available: false } };
  await openRun();
  expect([...host.querySelectorAll("a")].some((a) => a.textContent?.includes("Dossier"))).toBe(false);
});

it("shows the owner the registry the run met; a view without one shows no Registry section", async () => {
  view = { ...makeView(), registry: {
    snapshot: { snapshot_id: "trs_2026_09_26", content_hash: "sha256:abab" }, snapshot_ids: ["trs_2026_09_26", "trs_2026_09_20"],
    priors: [{ registry_record_id: "reg_friction_07", prior_role: "friction_primitive", label: "<i>access</i> interruption", hypothesis_ids: ["hyp_a"] }],
    territories: [{ territory_id: "ter_03", territory: "friction_primitive", territory_name: "Cold-weather handling", hypothesis_ids: ["hyp_a"] }] } };
  await openRun();
  const registry = [...host.querySelectorAll("section")].find((s) => s.querySelector("h2")?.textContent?.startsWith("Registry"))!;
  expect(registry.textContent).toContain("trs_2026_09_26");
  expect(registry.textContent).toContain("sha256:abab");
  expect(registry.textContent).toContain("2 snapshots");
  expect(registry.textContent).toContain("<i>access</i> interruption");                          // registry text, as text
  expect(registry.querySelector("i")).toBeNull();
  expect(registry.textContent).toContain("Friction primitive");
  expect(registry.textContent).toContain("Cold-weather handling");
  await act(async () => root.unmount());
  root = createRoot(host);
  view = makeView();
  await openRun();
  expect([...host.querySelectorAll("h2")].some((h) => h.textContent?.startsWith("Registry"))).toBe(false);
});

it("a live run is followed and can be cancelled after confirming", async () => {
  view = makeView({ status: "awaiting_agent", terminal: false, current_step_id: "B" });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  await openRun();
  const before = calls.filter((c) => c.path.endsWith("/view")).length;
  await act(async () => { vi.advanceTimersByTime(5_100); });
  await settle();
  expect(calls.filter((c) => c.path.endsWith("/view")).length).toBeGreaterThan(before);
  const cancel = [...host.querySelectorAll("button")].find((b) => b.textContent === "Cancel run") as HTMLButtonElement;
  await act(async () => cancel.click());
  const confirm = [...host.querySelectorAll("dialog button")].find((b) => b.textContent === "Cancel run") as HTMLButtonElement;
  await act(async () => confirm.click());
  await settle();
  expect(calls.some((c) => c.method === "POST" && c.path === "/adapter/adr_1/cancel")).toBe(true);
});
