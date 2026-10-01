// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ControlPlane } from "../screens/ControlPlane";

/** LIBRARY-READY-LABEL (the owner, 2026-10-01): the corpus summary separates files searchable on the basic profile from files
 *  retrieval would miss part of; only the second is red. */

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

function stat(label: string): HTMLElement {
  const box = [...host.querySelectorAll(".label")].find((l) => l.textContent === label)?.parentElement;
  if (!box) throw new Error(`no stat "${label}"`);
  return box.querySelector(".mono") as HTMLElement;
}

it("21 searchable files on the basic profile count as ready, and 0 blocked is not red", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({
    contract: "control-plane-status-v1", corpus_id: "social-media-taste", pools: {},
    control_ready: { state: "degraded", label: "DEGRADED" },
    summary: { documents: 21, semantic_ready: 0, basic_profile: 21, processing: 0, processing_active: 0, processing_stalled: 0, blocked: 0 },
  })));
  await act(async () => root.render(<ControlPlane corpusId="social-media-taste" />));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(stat("ready (vNext)").textContent).toBe("0");
  expect(stat("ready (basic profile)").textContent).toBe("21");
  expect(stat("blocked").textContent).toBe("0");
  expect(stat("blocked").style.color).toBe("");
});


it("'ready (vNext)' counts files search serves with a vNext card, not cards that were written", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({
    contract: "control-plane-status-v1", corpus_id: "cinema", pools: {},
    control_ready: { state: "ready", label: "IDLE" },
    summary: { documents: 77, semantic_ready: 77, vnext_served: 0, basic_profile: 77, processing: 0, processing_active: 0,
               processing_stalled: 0, blocked: 0 },
  })));
  await act(async () => root.render(<ControlPlane corpusId="cinema" />));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(stat("ready (vNext)").textContent).toBe("0");
  expect(stat("ready (basic profile)").textContent).toBe("77");
});
