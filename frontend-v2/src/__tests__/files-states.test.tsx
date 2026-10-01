// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { readable } from "../components/Pill";
import { Files } from "../screens/Files";

/** FRONTEND-REFRESH-V1 U5 — Files: loading never reads as "0 documents" or a failure (P4), errors offer Retry, an empty
 *  library invites a first file, the pipeline columns are opt-in (P7), and deleting a file goes through a dialog (P12). */

let host: HTMLDivElement;
let root: Root;
let calls: { path: string; method: string }[];
let documents: () => Promise<Response>;

const DOC = { doc_id: "doc_1", source_name: "handbook.md", media_type: "text/markdown", bytes: 2048,
              created_at: "2026-09-01T00:00:00Z", parents: 1, chunks: 2, map_active: 1 };

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  calls = [];
  documents = async () => Response.json({ documents: [DOC] });
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ path, method });
    if (path.startsWith("/documents?")) return documents();
    if (path.startsWith("/documents/summary")) return Response.json({ summaries: {} });
    if (path.startsWith("/documents/") && method === "DELETE") return Response.json({ deleted: true });
    return Response.json({});
  }));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function render(props: { isOwner?: boolean; canWrite?: boolean } = {}) {
  await act(async () => root.render(<Files corpusId="cinema" {...props} />));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

function button(text: string): HTMLButtonElement {
  const b = [...host.querySelectorAll("button")].find((x) => x.textContent?.trim() === text);
  if (!b) throw new Error(`no button "${text}"`);
  return b as HTMLButtonElement;
}

it("while documents load it shows a skeleton, never '0 documents' or 'not reachable'", async () => {
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));      // nothing has answered yet
  await render({ isOwner: true });
  expect(host.textContent).toContain("Checking");                             // the status cards wait, they do not fail
  expect(host.querySelector('[role="status"]')!.textContent).toContain("Loading documents");
  expect(host.textContent).toContain("loading documents");
  expect(host.textContent).not.toContain("0 documents");
  expect(host.textContent).not.toContain("not reachable");
});

it("a failed load says so and retries", async () => {
  documents = async () => new Response("boom", { status: 500 });
  await render();
  expect(host.querySelector('[role="alert"]')!.textContent).toContain("Couldn't load this");
  documents = async () => Response.json({ documents: [DOC] });
  await act(async () => button("Retry").click());
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(host.textContent).toContain("handbook.md");
});

it("an empty library invites the first file only to someone who can add one", async () => {
  documents = async () => Response.json({ documents: [] });
  await render({ canWrite: true });
  expect(host.textContent).toContain("No documents yet");
  expect(button("Add files")).toBeDefined();
  await act(async () => root.render(<Files corpusId="cinema" isOwner={false} canWrite={false} />));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(host.textContent).toContain("Nothing has been added to this library yet.");
  expect([...host.querySelectorAll("button")].some((b) => b.textContent === "Add files")).toBe(false);
});

it("pipeline columns are opt-in for the owner", async () => {
  await render({ isOwner: true });
  const headers = () => [...host.querySelectorAll("th")].map((h) => h.textContent);
  expect(headers()).toEqual(["File", "Type", "Added", "Size", "Status", ""]);
  const toggle = [...host.querySelectorAll("label")].find((l) => l.textContent?.includes("Pipeline details"))!.querySelector("input")!;
  await act(async () => toggle.click());
  expect(headers()).toContain("pMAP mapped");
  expect(headers()).toContain("Graph rel.");
});

it("deleting a file asks first; Cancel deletes nothing", async () => {
  await render({ isOwner: true });
  await act(async () => button("Delete").click());
  expect(host.querySelector("dialog")!.textContent).toContain("Delete handbook.md?");
  await act(async () => button("Cancel").click());
  expect(host.querySelector("dialog")).toBeNull();
  expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  await act(async () => button("Delete").click());
  const confirm = [...host.querySelectorAll("dialog button")].find((b) => b.textContent === "Delete") as HTMLButtonElement;
  await act(async () => confirm.click());
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(calls.some((c) => c.method === "DELETE" && c.path.startsWith("/documents/doc_1"))).toBe(true);
});

it("status words are the backend's own, formatted for reading", () => {
  expect(readable("SEMANTIC_INCOMPLETE")).toBe("Semantic incomplete");
  expect(readable("VNEXT READY")).toBe("vNext ready");
  expect(readable("IDLE")).toBe("Idle");
  expect(readable(undefined)).toBe("Unknown");
});

// FILES-READY-LABEL (the owner, 2026-09-29: "why are files blocked?"): a searchable file is never "Blocked"
const SUMMARY = { children: 2, parents: 1, map_eligible: 1, map_active: 1, map_excluded: 0, map_unresolved: 0, profile_present: true,
                  profile_vnext: false, graph_entities: 3, graph_relations: 1, vnext_ready: false };

async function renderWith(summary: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    calls.push({ path, method: init?.method ?? "GET" });
    if (path.startsWith("/documents?")) return documents();
    if (path.startsWith("/documents/summary")) return Response.json({ summaries: { doc_1: { ...SUMMARY, ...summary } } });
    return Response.json({});
  }));
  await render({ isOwner: true });
}

function statusPill(): HTMLElement {
  return host.querySelector("tbody .pill") as HTMLElement;
}

it("a fully processed file with the base profile reads 'Ready · basic profile', offers no Continue, and counts as ready", async () => {
  await renderWith({});
  expect(statusPill().textContent).toBe("Ready · basic profile");
  expect(statusPill().classList.contains("pill--degraded")).toBe(true);
  expect(host.textContent).not.toContain("Blocked");
  expect([...host.querySelectorAll("tbody button")].map((b) => b.textContent?.trim())).not.toContain("▸ Continue");
  expect(host.querySelector(".screen__sub")!.textContent).toContain("1 ready (1 with a basic profile)");
  expect(host.querySelector(".screen__sub")!.textContent).not.toContain("still processing");
  expect(button("▸ Continue corpus").disabled).toBe(true);
});

it("a file with the vNext profile reads 'Ready'", async () => {
  await renderWith({ profile_vnext: true, vnext_ready: true });
  expect(statusPill().textContent).toBe("Ready");
  expect(statusPill().classList.contains("pill--ready")).toBe(true);
  expect(host.querySelector(".screen__sub")!.textContent).toContain("1 ready");
  expect(host.querySelector(".screen__sub")!.textContent).not.toContain("basic profile");
});

it("unresolved parents or no profile still read 'Blocked' with the reason, and offer Continue", async () => {
  await renderWith({ map_unresolved: 4, map_active: 0 });
  expect(statusPill().textContent).toBe("Blocked");
  expect(statusPill().getAttribute("title")).toContain("4 unresolved parents");
  expect(button("▸ Continue").disabled).toBe(false);
  expect(host.querySelector(".screen__sub")!.textContent).toContain("1 still processing");
  await act(async () => root.unmount());
  root = createRoot(host);
  await renderWith({ profile_present: false });
  expect(statusPill().textContent).toBe("Blocked");
  expect(statusPill().getAttribute("title")).toContain("no profile");
});

// LIBRARY-READY-LABEL (the owner, 2026-10-01: "why is a corpus for taste showing files as red"): the library's vNext card
// follows the per-file rule — every parent mapped and every file profiled is searchable (amber); red only when retrieval
// would miss part of the library
const TASTE_VNEXT = { verdict: "VNEXT_INCOMPLETE", pending: ["vnext_profiles_0_of_21"], vnext_profiles: 0, profiled: 21, documents: 21,
                      parents: { eligible: 150, mapped: 150, excluded: 2, unresolved: 0 } };

async function renderReadiness(vnext: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    calls.push({ path, method: init?.method ?? "GET" });
    if (path.startsWith("/documents?")) return documents();
    if (path.startsWith("/documents/summary")) return Response.json({ summaries: { doc_1: SUMMARY } });
    if (path.startsWith("/semantic_readiness")) return Response.json({ verdict: "SEMANTIC_COMPLETE", counts: {}, vnext });
    return Response.json({});
  }));
  await render({ isOwner: true });
}

function vnextCard(): HTMLElement {
  const card = [...host.querySelectorAll(".card")].find((c) => c.querySelector(".label")?.textContent === "vNext ready");
  if (!card) throw new Error("no vNext ready card");
  return card.querySelector(".pill") as HTMLElement;
}

it("a library searchable on basic profiles reads amber 'Searchable · basic profiles', not a red vNext verdict", async () => {
  await renderReadiness(TASTE_VNEXT);
  expect(vnextCard().textContent).toBe("Searchable · basic profiles");
  expect(vnextCard().classList.contains("pill--degraded")).toBe(true);
  expect(vnextCard().getAttribute("title")).toContain("0/21 files have the vNext profile · 150/150 parents mapped");
});

it("unresolved parents, an unprofiled file or an older backend keep the red vNext verdict", async () => {
  for (const vnext of [{ ...TASTE_VNEXT, parents: { ...TASTE_VNEXT.parents, mapped: 146, unresolved: 4 } },
                       { ...TASTE_VNEXT, profiled: 20 },
                       { ...TASTE_VNEXT, profiled: undefined }]) {
    await renderReadiness(vnext);
    expect(vnextCard().textContent).toBe("vNext incomplete");
    expect(vnextCard().classList.contains("pill--blocked")).toBe(true);
    await act(async () => root.unmount());
    root = createRoot(host);
  }
});

it("a complete vNext library stays green", async () => {
  await renderReadiness({ ...TASTE_VNEXT, verdict: "VNEXT_COMPLETE", vnext_profiles: 21, pending: [] });
  expect(vnextCard().classList.contains("pill--ready")).toBe(true);
});
