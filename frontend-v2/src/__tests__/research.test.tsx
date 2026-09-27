// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { RunView } from "../lib/contracts";
import { Research } from "../screens/Research";

/** TRAIL-INTERFACE-V1 T2–T4 — the Research screen watches and reads runs: outcomes in words, TrailSignal's refusals with the
 *  hypothesis they refuse, gates as "observed of minimum", evidence counts by platform, polling that stops when the run ends,
 *  and Cancel only while a run can still be cancelled. Field text renders as text, never HTML. */

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
