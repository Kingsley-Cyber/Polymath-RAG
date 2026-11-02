// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { AnswerBody } from "../components/AnswerBody";
import { ReportPanel } from "../components/ProductReport";
import { newTurn, type Turn } from "../lib/chat";
import { emptySession, loadSessions, saveSessions, type ChatSession } from "../lib/chatStore";
import type { ProductResearchResult } from "../lib/contracts";
import {
  AGENT_REACH_CHECK, AGENT_REACH_REPO, POLL_MS, RUN_SENTENCE, forgetUploadTokens, heldUploadToken, holdUploadToken, missingNote,
  pageNavigation, reportReturnPath, reportRows, reportView, returnToReport, startBody, takeUploadToken, tokenFromUploadUrl,
} from "../lib/productReport";
import { productView } from "../lib/productResearch";
import { Chat } from "../screens/Chat";
import { Reports } from "../screens/Reports";

/** PRODUCT-DECISION-REPORT-V1 B6 — the decision report from the web: "Build decision report" under a product answer sends its
 *  hypotheses as the report's products (POST /product/report/start), the panel follows the report (status checked every few
 *  seconds while it collects; never during or after a compile, never once unmounted), shows the round's fetch script with
 *  the one sentence a web user needs, the uploads per source, Compile (any time; it names what would be missing) and Open.
 *  The id is kept on the chat turn; the upload token lives in the page's memory only and goes back with every check
 *  (ADR-0023: upload.token is minted | reused | required | expired | none). The Reports screen lists the person's reports. A
 *  report page opened without a session comes back to the app as /v2/?next=<its path>, and the app returns there once the
 *  person is signed in. The replies are synthetic, shaped as B4b's routes answer (product-report-v1); a fake server below
 *  keeps ADR-0023's rules (a held token is reused; without one it mints, at most once a minute, else answers "required").
 *  One test reads the plan's simpler wording. */

const RID = "rpt_0123456789abcdef01234567";
const TOKEN = "Zk3v9Qx2Lm8Rt5Yw1Np7Hc4Bd6Fg0Js_AeUo-iTnKy";             // 43 characters, as secrets.token_urlsafe(32)
const TOKEN2 = "Mn4b7Vc1Xz9Lk2Jh5Gf8Ds3Ap6Qw0Er_TyUi-oPaSd";
const TOKEN3 = "Qw2Er4Ty6Ui8Op0As1Df3Gh5Jk7Lz_Xc9Vb-NmQwEr";
const BOGUS = "Bogus0Token1That2The3Server4Never5Minted6xY";
const MINT_AFTER = "2026-11-02T08:01:00Z";
const QUESTION = "What could I sell to winter photographers?";
const BASE = "http://127.0.0.1:7200";
const urlFor = (token: string | null) => `${BASE}/product/report/${RID}/upload/${token ?? "UPLOAD_TOKEN"}`;
const UPLOAD = urlFor(TOKEN);
const scriptFor = (url: string, round = 1) =>
  `#!/usr/bin/env bash\nset -u\n# round ${round} of a decision report: paced reads, each uploaded as it lands\n` +
  `up() { curl -s -X POST -H 'content-type: text/plain' --data-binary @- "${url}?packet=$1"; }\n` +
  `mcporter call exa.web_search_exa query='heated hand warmer reddit' | up c1-reddit-1\n`;
const SCRIPT = scriptFor(UPLOAD);
const SHA = "9f2c1e7a55d04b3c8e6f1a2b3c4d5e6f";
const PACKETS = [
  { packet_id: "c1-reddit-1", candidate_id: "c1", source: "reddit", kind: "search" },
  { packet_id: "c1-amazon-1", candidate_id: "c1", source: "amazon", kind: "search" },
  { packet_id: "c1-alibaba-1", candidate_id: "c1", source: "alibaba", kind: "search" },
  { packet_id: "c1-ebay-1", candidate_id: "c1", source: "ebay", kind: "search" },
];
type Key = "minted" | "reused" | "required" | "expired" | "none";

/** B4b's start / status view. `key` is ADR-0023's `upload.token`; `token` the one the URLs carry (minted or reused), else the
 *  placeholder. `plan: false` is a report whose candidates are still being formed (no fetch plan yet). */
function b4b(over: Record<string, unknown> = {}, key: Key = "reused", token: string | null = TOKEN, plan = true): Record<string, unknown> {
  const url = urlFor(key === "minted" || key === "reused" ? token : null);
  return {
    contract: "product-report-v1", view: "status", report_id: RID, status: "collecting",
    created_at: "2026-11-02T08:00:00Z", updated_at: "2026-11-02T08:00:00Z",
    request: { products_from: "caller", message: QUESTION, corpus_id: "cinema", ship_to: "US", max_products: 2 },
    candidates: plan
      ? { status: "ready", source: "caller", error: null, items: [
          { candidate_id: "c1", title: "Heated camera grip wrap", search_terms: ["heated hand warmer"], source: "caller" },
          { candidate_id: "c2", title: "Cold-proof battery pouch", search_terms: [], source: "caller" }] }
      : { status: "collecting", source: "product_route", error: null, items: [] },
    host: { status: "collecting", started_at: "2026-11-02T08:00:01Z", finished_at: null, error: null, cj: {},
            ebay: { c1: { status: "UNAVAILABLE", reason_code: "EBAY_NOT_CONFIGURED", listings: 0 } } },
    round: 1, rounds: plan ? [{ round: 1, packets: 4, received: 0, complete: false }] : [],
    fetch_plan: plan ? { round: 1, packets: PACKETS, script: scriptFor(url), script_sha256: SHA, limits: { exa_parallel: 3, jina_per_minute: 20 } } : null,
    upload: { url, expires_at: key === "expired" ? "2000-01-01T06:00:00Z" : "2099-01-01T12:00:00Z", expired: key === "expired",
              via: "local", token: key, max_bytes: 2097152, max_uploads: 300, ...(key === "required" ? { mint_after: MINT_AFTER } : {}) },
    uploads: { total: 0, by_round: {}, by_source: {} },
    compiled: null,
    next: "Run round 1's fetch script (fetch_plan.script, one shell command) on the user's machine with their local Agent Reach.",
    ...over,
  };
}
const START = { ...b4b({ view: "start" }, "minted", TOKEN), upload_token: TOKEN };
const COMPILED = { contract: "product-report-v1", view: "compile", report_id: RID, status: "compiled", compiled_at: "2026-11-02T09:30:00Z",
  report_url: `${BASE}/product/report/${RID}`, report_path: `/product/report/${RID}`, html_bytes: 48213,
  summary: [{ candidate_id: "c1", title: "Heated camera grip wrap", channels: {} }], next: "Open the report." };
const STATUS_PATH = `/product/report/${RID}/status`;
const COMPILE_PATH = `/product/report/${RID}/compile`;

function research(over: Partial<ProductResearchResult> = {}): ProductResearchResult {
  return {
    contract: "product-search-v1",
    intent: { kind: "PRODUCT_DISCOVERY", seed: "gear for winter photographers" },
    corpus_ids: ["cinema"],
    hypotheses: [
      { id: "h1", title: "Heated camera grip wrap", problem: "Numb fingers.", search_terms: ["heated hand warmer", "usb heated wrap"],
        cj: { status: "EMPTY", items: [] } },
      { id: "h2", title: "Cold-proof battery pouch", search_terms: ["insulated battery pouch"] },
      { id: "h3", title: "", search_terms: ["an idea with no title"] },                       // no title: not a product
    ],
    ...over,
  };
}

function productTurn(over: Partial<Turn> = {}): Turn {
  return { ...newTurn(QUESTION, "HYBRID"), done: true, answerText: "Two ideas.", productResearch: research(), ...over };
}

type Call = { path: string; method: string; headers: Record<string, string>; body: unknown };
let host: HTMLDivElement;
let root: Root;
let calls: Call[];
let written: string[];
let routes: Record<string, (c: Call) => Response | Promise<Response>>;
/** what the status route says besides ADR-0023's upload fields */
let statusOver: Record<string, unknown>;
/** the fake server's ADR-0023 state for RID: the tokens it holds, whether it may mint now (the once-a-minute rule), the expiry */
let server: { tokens: string[]; mintable: string[]; canMint: boolean; lapsed: boolean; plan: boolean };
let storageWrites: string[];

/** GET status, by ADR-0023: a held token is reused; a wrong or unknown one counts as none; without one the server mints, unless it
 *  minted less than a minute ago ("required", the placeholder in every URL, `mint_after`); an expired report mints nothing. */
function fakeStatus(c: Call): Response {
  const sent = c.headers["x-upload-token"] ?? "";
  if (server.lapsed) return Response.json(b4b(statusOver, "expired", null, server.plan));
  if (sent && server.tokens.includes(sent)) return Response.json(b4b(statusOver, "reused", sent, server.plan));
  if (!server.plan) return Response.json(b4b(statusOver, "none", null, false));
  if (!server.canMint) return Response.json(b4b(statusOver, "required", null));
  const minted = server.mintable.shift()!;
  server.tokens.push(minted);
  return Response.json(b4b(statusOver, "minted", minted));
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window & { Storage: typeof Storage } } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  vi.stubGlobal("sessionStorage", dom.window.sessionStorage);
  localStorage.clear();
  sessionStorage.clear();
  storageWrites = [];
  const setItem = dom.window.Storage.prototype.setItem;
  vi.spyOn(dom.window.Storage.prototype, "setItem").mockImplementation(function (this: Storage, k: string, v: string) {
    storageWrites.push(`${k}=${v}`);
    setItem.call(this, k, v);
  });
  document.cookie = "polymath_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  forgetUploadTokens();                                                   // a fresh page: no token held
  calls = [];
  written = [];
  statusOver = {};
  server = { tokens: [TOKEN], mintable: [TOKEN2, TOKEN3], canMint: true, lapsed: false, plan: true };   // the start minted TOKEN
  routes = {
    "POST /product/report/start": () => Response.json(START),
    [`GET ${STATUS_PATH}`]: fakeStatus,
    [`POST ${COMPILE_PATH}`]: () => Response.json(COMPILED),
    "GET /product/reports": () => Response.json({ contract: "product-report-v1", view: "list", reports: [] }),
  };
  Object.defineProperty(navigator, "clipboard", { configurable: true,
    value: { writeText: vi.fn(async (t: string) => { written.push(t); }) } });
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    const c: Call = { path, method: init?.method ?? "GET", headers: (init?.headers ?? {}) as Record<string, string>,
                      body: typeof init?.body === "string" ? JSON.parse(init.body) : null };
    calls.push(c);
    const route = routes[`${c.method} ${path}`];
    return route ? route(c) : Response.json({});
  }));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.cookie = "polymath_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  window.history.replaceState(null, "", "/");                                            // the address a test set (?next=…)
  vi.unstubAllGlobals();
});

/** Node's setImmediate (the project installs no @types/node): a macrotask the fake timers below leave alone. */
const nextTurn = () => new Promise<void>((r) => (globalThis as unknown as { setImmediate: (cb: () => void) => void }).setImmediate(r));

/** Run what is due now (the panel's first check has no delay) and let the replies land: the fetch mock, the body read, React's
 *  update. With the fake timers below (they fake only setTimeout) the clock is advanced by 0; setImmediate always runs. */
async function flush() {
  for (let round = 0; round < 3; round++) {
    await act(async () => {
      if (vi.isFakeTimers()) await vi.advanceTimersByTimeAsync(0);
      else await new Promise((r) => setTimeout(r, 0));
      for (let i = 0; i < 8; i++) await nextTurn();
    });
  }
}
/** Advance the faked setTimeout clock (the panel's checks), then let the replies land. */
async function advance(ms: number) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
  await flush();
}
const fakeTimers = () => vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });

const named = (name: string, scope: ParentNode = host) =>
  [...scope.querySelectorAll<HTMLElement>("button, a")].find((b) =>
    b.getAttribute("aria-label") === name || b.textContent?.trim() === name || b.textContent?.trim().startsWith(name));
const button = (name: string) => [...host.querySelectorAll<HTMLButtonElement>("button")]
  .find((b) => b.getAttribute("aria-label") === name || b.textContent?.trim() === name);
const posts = (path: string) => calls.filter((c) => c.method === "POST" && c.path === path);
const statusCalls = () => calls.filter((c) => c.method === "GET" && c.path === STATUS_PATH);
const checks = () => statusCalls().length;
/** the X-Upload-Token each status check sent ("" for none), in order */
const sentTokens = () => statusCalls().map((c) => c.headers["x-upload-token"] ?? "");
const alerts = () => [...host.querySelectorAll('[role="alert"]')].map((a) => a.textContent);
const pill = () => host.querySelector(".pr-report__status .pill")?.textContent;
const shownScript = () => host.querySelector(".pr-report__script pre")?.textContent ?? null;
const counts = () => Object.fromEntries([...host.querySelectorAll(".pr-report__counts > div")]
  .map((d) => [d.querySelector("dt")?.textContent, d.querySelector("dd")?.textContent]));
/** every value the page wrote to localStorage / sessionStorage, and what both hold now */
const storageHolds = () => [...storageWrites,
  ...[localStorage, sessionStorage].flatMap((s) => Array.from({ length: s.length }, (_, i) => `${s.key(i)}=${s.getItem(s.key(i) ?? "")}`))].join("\n");

async function showAnswer(t: Turn, product?: Parameters<typeof AnswerBody>[0]["product"]) {
  await act(async () => root.render(<AnswerBody t={t} models={[]} product={product} />));
}

/* ── 1. Build decision report ────────────────────────────────────────────────────────────────────────────────────── */

describe("Build decision report", () => {
  it("sends the answer's titled hypotheses as products (title + search terms) with its library, once, with the CSRF token", async () => {
    document.cookie = "polymath_csrf=tok-123";
    const started: unknown[] = [];
    await showAnswer(productTurn(), { onReportStarted: (r) => started.push(r) });
    expect(host.querySelector(".pr-report__title")?.textContent).toBe("Decision report");
    const b = button("Build decision report")!;
    expect(b.disabled).toBe(false);
    await act(async () => { b.click(); b.click(); });                                     // a double click starts one report
    await flush();
    expect(posts("/product/report/start")).toHaveLength(1);
    const post = posts("/product/report/start")[0]!;
    expect(post.body).toEqual({
      message: QUESTION, corpus_id: "cinema", ship_to: "US", max_products: 2,
      products: [{ title: "Heated camera grip wrap", search_terms: ["heated hand warmer", "usb heated wrap"] },
                 { title: "Cold-proof battery pouch", search_terms: ["insulated battery pouch"] }],
    });
    expect(post.headers["x-polymath-csrf"]).toBe("tok-123");
    expect(started).toEqual([{ report_id: RID, status: "collecting", started_at: expect.any(Number) }]);   // the id, never the token
    expect(button("Build decision report")).toBeUndefined();                               // the panel replaces the button
    expect(pill()).toBe("Collecting data");
    expect(host.querySelector(".pr-report__status code")?.textContent).toBe(RID);
    expect([...host.querySelectorAll(".pr-report__products li")].map((l) => l.textContent))
      .toEqual(["Heated camera grip wrap · heated hand warmer", "Cold-proof battery pouch"]);
    expect(sentTokens()).toEqual([TOKEN]);                                                 // the start's token goes back: reused
    expect(server.tokens).toEqual([TOKEN]);                                                // nothing else minted
    expect(host.textContent).toContain("Round 1: 0 of 4 reads uploaded");
    expect(host.textContent).toContain("CJ Dropshipping and eBay, read by the server: collecting");
  });

  it("several libraries go as corpus_ids, a missing question falls back to the answer's seed, within the route's limits", () => {
    const many = research({ corpus_ids: ["cinema", "gear", "cinema"],
      hypotheses: Array.from({ length: 10 }, (_, i) => ({ title: `Idea ${i + 1}`, search_terms: Array.from({ length: 12 }, (__, j) => `t${j}`) })) });
    const body = startBody(productView(many)!);
    expect(body.message).toBe("gear for winter photographers");
    expect(body.corpus_ids).toEqual(["cinema", "gear"]);
    expect(body.corpus_id).toBeUndefined();
    expect(body.products).toHaveLength(8);
    expect(body.products[0]!.search_terms).toHaveLength(10);
    expect(body.max_products).toBe(8);
    expect(startBody(productView(research())!, "x".repeat(5000)).message).toHaveLength(4000);
    const none = startBody(productView(research({ corpus_ids: undefined, intent: null }))!, "  ");
    expect(none).toEqual({ products: expect.any(Array), ship_to: "US", max_products: 2 });       // no message, no library named
  });

  it("no titled idea: no button", async () => {
    await showAnswer(productTurn({ productResearch: research({ hypotheses: [{ title: "", search_terms: ["x"] }],
      limitations: ["a note so the block still shows"] }) }));
    expect(host.querySelector(".pr")).not.toBeNull();
    expect(host.querySelector(".pr-report")).toBeNull();
  });

  it("shows the round's fetch script in a copyable block with the one sentence, the Agent Reach install link and check command", async () => {
    await showAnswer(productTurn());
    await act(async () => button("Build decision report")!.click());
    await flush();
    const script = host.querySelector<HTMLElement>(".pr-report__script")!;
    expect(script.querySelector(".pr-report__run")?.textContent).toBe(RUN_SENTENCE);
    expect(RUN_SENTENCE).toBe("Run this once in a terminal on your own computer (it needs Agent Reach); it uploads the results here by itself.");
    expect(script.querySelector("pre")?.textContent).toBe(SCRIPT);                       // shown exactly as the server wrote it …
    await act(async () => named("Copy fetch script", script)!.click());
    expect(written).toEqual([SCRIPT]);                                                     // … and copied exactly
    const link = [...script.querySelectorAll("a")].find((a) => a.getAttribute("href") === AGENT_REACH_REPO)!;
    expect(AGENT_REACH_REPO).toBe("https://github.com/Panniantong/Agent-Reach");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    await act(async () => named("Copy check command", script)!.click());
    expect(written[1]).toBe(AGENT_REACH_CHECK);
    expect(AGENT_REACH_CHECK).toBe("agent-reach doctor --json");
    expect([...script.querySelectorAll("code")].map((c) => c.textContent)).toEqual([AGENT_REACH_CHECK, UPLOAD]);   // the capability
    await act(async () => named("Copy upload address", script)!.click());
    expect(written[2]).toBe(UPLOAD);
    expect(script.textContent).toContain("Anyone who has it can add results to this report until it expires");
    expect(script.textContent).toContain("This round makes 4 reads through your Agent Reach.");
    expect(script.textContent).toContain(SHA);
  });

  it("a refusal stays on screen in words (status and message) and Build is offered again; so does a reply without a report id", async () => {
    routes["POST /product/report/start"] = () => Response.json(
      { detail: { error_code: "BAD_PRODUCTS", message: "each product needs a title (and 1-3 search_terms)" } }, { status: 422 });
    await showAnswer(productTurn());
    await act(async () => button("Build decision report")!.click());
    await flush();
    expect(alerts()).toEqual(["Couldn't build the decision report. HTTP 422: each product needs a title (and 1-3 search_terms)"]);
    expect(button("Build decision report")!.disabled).toBe(false);
    routes["POST /product/report/start"] = () => Response.json({ status: "collecting" });
    await act(async () => button("Build decision report")!.click());
    await flush();
    expect(alerts()).toEqual(["Couldn't build the decision report. the server's reply names no report (no report_id)"]);
    routes["POST /product/report/start"] = () => { throw new TypeError("Failed to fetch"); };
    await act(async () => button("Build decision report")!.click());
    await flush();
    expect(alerts()).toEqual(["Couldn't build the decision report. Failed to fetch"]);
    routes["POST /product/report/start"] = () => Response.json(START);                    // the retry works and clears the error
    await act(async () => button("Build decision report")!.click());
    await flush();
    expect(alerts()).toEqual([]);
    expect(pill()).toBe("Collecting data");
  });

  it("a 429 REPORT_JOB_RUNNING shows the server's message and the report still running; Build is offered again", async () => {
    const message = "a report of yours is still gathering its data (a product turn or the CJ / eBay host data): start the next " +
      "one in about 30 seconds";                                                          // the start route's own words
    routes["POST /product/report/start"] = () => Response.json({ detail: { error_code: "REPORT_JOB_RUNNING", message,
      retry_after_s: 30, report_id: "rpt_aaaaaaaaaaaaaaaaaaaaaaaa" } }, { status: 429, headers: { "retry-after": "30" } });
    await showAnswer(productTurn());
    await act(async () => button("Build decision report")!.click());
    await flush();
    expect(alerts()).toEqual([`Couldn't build the decision report. HTTP 429: ${message}. Running report: rpt_aaaaaaaaaaaaaaaaaaaaaaaa.`]);
    expect(button("Build decision report")!.disabled).toBe(false);
    expect(checks()).toBe(0);
    routes["POST /product/report/start"] = () => Response.json({ detail: { error_code: "REPORT_JOB_RUNNING", message } }, { status: 429 });
    await act(async () => button("Build decision report")!.click());
    await flush();
    expect(alerts()).toEqual([`Couldn't build the decision report. HTTP 429: ${message}`]);   // no report id given: the message alone
  });
});

/* ── 2. the upload token: memory only, sent back on every check (ADR-0023) ───────────────────────────────────────── */

describe("the upload token (ADR-0023)", () => {
  it("is kept in memory only: no storage write ever holds it, the chat turn keeps the id; after a reload the next mint is held and sent back", async () => {
    fakeTimers();
    let turns: Turn[] = [productTurn()];
    const session: ChatSession = { ...emptySession("cinema"), turns };
    await act(async () => root.render(
      <Chat corpusId="cinema" session={session} onUpdateTurns={(fn) => { turns = fn(turns); }} models={[]} corpusExploreAvailable={false} />));
    await flush();
    await act(async () => button("Build decision report")!.click());
    await flush();
    expect(turns[0]?.productReport).toEqual({ report_id: RID, status: "collecting", started_at: expect.any(Number) });
    expect(JSON.stringify(turns)).not.toContain(TOKEN);
    saveSessions([{ ...session, turns }]);                                                // the chat history, as App saves it
    expect(storageWrites.length).toBeGreaterThan(0);
    expect(storageHolds()).not.toContain(TOKEN);
    expect(sentTokens()).toEqual([TOKEN]);
    // a reload: the page's memory is gone, the chat comes back from storage
    await act(async () => root.unmount());
    forgetUploadTokens();
    calls = [];
    root = createRoot(host);
    await act(async () => root.render(
      <Chat corpusId="cinema" session={loadSessions()[0]!} onUpdateTurns={() => {}} models={[]} corpusExploreAvailable={false} />));
    await flush();
    expect(sentTokens()).toEqual([""]);                                                    // nothing held: the server mints …
    expect(shownScript()).toBe(scriptFor(urlFor(TOKEN2)));                                 // … and the script runs as given
    expect(heldUploadToken(RID)).toBe(TOKEN2);
    await advance(POLL_MS);
    await advance(POLL_MS);
    expect(sentTokens()).toEqual(["", TOKEN2, TOKEN2]);                                    // every check after the mint sends it
    expect(server.tokens).toEqual([TOKEN, TOKEN2]);                                        // one mint, then reused
    expect(storageHolds()).not.toMatch(new RegExp(`${TOKEN}|${TOKEN2}`));
    expect(button("Build decision report")).toBeUndefined();
    expect(posts("/product/report/start")).toHaveLength(0);
  });

  it("required: shows the plan without a usable link, says when a new one can be made or to use the agent's script; the next mint is then held", async () => {
    fakeTimers();
    server.canMint = false;                                                               // the agent's status minted a token seconds ago
    await act(async () => root.render(<ReportPanel reportId={RID} />));
    await flush();
    expect(sentTokens()).toEqual([""]);
    const section = host.querySelector<HTMLElement>(".pr-report__script")!;
    expect(section.getAttribute("data-link")).toBe("required");
    expect(section.querySelector("pre")).toBeNull();                                      // the placeholder script is never offered
    expect(section.querySelector("code")).toBeNull();                                     // nor an upload address
    expect(host.textContent).not.toContain("UPLOAD_TOKEN");
    expect(section.textContent).toContain("Round 1 plans 4 reads: Reddit, Amazon, Alibaba and eBay.");
    expect(section.textContent).toMatch(/^Round 1 plans .+This page holds no upload link for this report, so the script is not shown\. A new upload link can be made after .+, or use the script your agent already has\.$/);
    expect(button("Compile report")!.disabled).toBe(false);
    await advance(POLL_MS);                                                                // still within the minute: required again
    expect(sentTokens()).toEqual(["", ""]);
    server.canMint = true;
    await advance(POLL_MS);
    expect(shownScript()).toBe(scriptFor(urlFor(TOKEN2)));
    await advance(POLL_MS);
    expect(sentTokens()).toEqual(["", "", "", TOKEN2]);
    expect(server.tokens).toEqual([TOKEN, TOKEN2]);
  });

  it("a token the server no longer accepts counts as none: the panel drops it and holds the next one minted", async () => {
    fakeTimers();
    holdUploadToken(RID, BOGUS);
    server.canMint = false;
    await act(async () => root.render(<ReportPanel reportId={RID} />));
    await flush();
    expect(sentTokens()).toEqual([BOGUS]);
    expect(heldUploadToken(RID)).toBe("");
    server.canMint = true;
    await advance(POLL_MS);
    await advance(POLL_MS);
    expect(sentTokens()).toEqual([BOGUS, "", TOKEN2]);
  });

  it("expired: no script, and says the link expired; none: no plan yet, nothing to run", async () => {
    server.lapsed = true;
    holdUploadToken(RID, TOKEN);
    await act(async () => root.render(<ReportPanel reportId={RID} />));
    await flush();
    expect(shownScript()).toBeNull();
    expect(host.querySelector(".pr-report__script")?.textContent).toMatch(/^The upload link expired .+: the fetch script can no longer add results/);
    expect(heldUploadToken(RID)).toBe("");                                                 // a lapsed capability is dropped
    await act(async () => root.unmount());
    root = createRoot(host);
    server.lapsed = false;
    server.plan = false;
    await act(async () => root.render(<ReportPanel reportId={RID} />));
    await flush();
    expect(host.querySelector(".pr-report__script")).toBeNull();
    expect(host.textContent).toContain("Polymath is forming the products from your library");
    expect(server.tokens).toEqual([TOKEN]);                                                // no plan: nothing minted
  });

  it("reads a token only from the start's upload_token or a minted reply's URL of this report", () => {
    expect(tokenFromUploadUrl(urlFor(TOKEN), RID)).toBe(TOKEN);
    expect(tokenFromUploadUrl(urlFor(null), RID)).toBe("");                               // the placeholder
    expect(tokenFromUploadUrl(urlFor(TOKEN).replace(RID, "rpt_ffffffffffffffffffffffff"), RID)).toBe("");   // another report
    expect(tokenFromUploadUrl("not a url at all", RID)).toBe("");
    takeUploadToken(RID, b4b({}, "reused", TOKEN3));                                       // reused: the caller's own, nothing new
    expect(heldUploadToken(RID)).toBe("");
    takeUploadToken(RID, b4b({}, "minted", TOKEN2));
    expect(heldUploadToken(RID)).toBe(TOKEN2);
    takeUploadToken(RID, { upload_token: TOKEN3 });
    expect(heldUploadToken(RID)).toBe(TOKEN3);
    takeUploadToken(RID, b4b({}, "none", null, false));                                    // none: the held one stays
    expect(heldUploadToken(RID)).toBe(TOKEN3);
    takeUploadToken(RID, b4b({}, "required", null));
    expect(heldUploadToken(RID)).toBe("");
    holdUploadToken(RID, "UPLOAD_TOKEN");
    expect(heldUploadToken(RID)).toBe("");
  });
});

/* ── 3. the panel's status checks ────────────────────────────────────────────────────────────────────────────────── */

describe("the report panel's status checks", () => {
  it("checks at once, then every few seconds while collecting; the counts per source follow; unmounting stops the checks", async () => {
    fakeTimers();
    await act(async () => root.render(<ReportPanel reportId={RID} initial={START} />));
    await flush();
    expect(checks()).toBe(1);                                                               // at once: the uploads so far
    expect(counts()).toEqual({ Reddit: "0", Amazon: "0", Alibaba: "0", eBay: "0" });
    await advance(POLL_MS - 1);
    expect(checks()).toBe(1);
    statusOver = { uploads: { total: 6, by_round: { 1: 6 }, by_source: { reddit: { OK: 2, BLOCKED: 1 }, amazon: { OK: 1 }, ebay: { EMPTY: 2 } } },
                   rounds: [{ round: 1, packets: 4, received: 3, complete: false }] };
    await advance(1);
    expect(checks()).toBe(2);
    expect(counts()).toEqual({ Reddit: "3 (1 blocked)", Amazon: "1", Alibaba: "0", eBay: "2 (2 empty)" });
    expect(host.textContent).toContain("Round 1: 3 of 4 reads uploaded");
    await advance(POLL_MS);
    expect(checks()).toBe(3);
    expect(sentTokens()).toEqual([TOKEN, TOKEN, TOKEN]);
    await act(async () => root.unmount());
    await advance(POLL_MS * 5);
    expect(checks()).toBe(3);
    root = createRoot(host);
  });

  it("round 2 brings its own script, and the panel shows it", async () => {
    fakeTimers();
    await act(async () => root.render(<ReportPanel reportId={RID} initial={START} />));
    await flush();
    const round2 = scriptFor(UPLOAD, 2);
    statusOver = { round: 2, rounds: [{ round: 1, packets: 4, received: 4, complete: true }, { round: 2, packets: 2, received: 0, complete: false }],
                   fetch_plan: { round: 2, packets: PACKETS.slice(1, 3), script: round2, script_sha256: "77aa" } };
    await advance(POLL_MS);
    expect(shownScript()).toBe(round2);
    expect(host.textContent).toContain("Round 2 is a new script");
    expect(host.textContent).toContain("Round 2: 0 of 2 reads uploaded");
    expect(host.querySelector(".pr-report__status")?.textContent).toContain("round 2");
  });

  it("Compile stops the checks: none while it is on its way, none once compiled; Open report opens the report in a new tab", async () => {
    fakeTimers();
    document.cookie = "polymath_csrf=tok-9";
    let release!: () => void;
    routes[`POST ${COMPILE_PATH}`] = () => new Promise<Response>((r) => { release = () => r(Response.json(COMPILED)); });
    await act(async () => root.render(<ReportPanel reportId={RID} initial={START} />));
    await flush();
    expect(checks()).toBe(1);
    expect(named("Open report")).toBeUndefined();
    const compile = button("Compile report")!;
    expect(compile.disabled).toBe(false);
    await act(async () => compile.click());
    expect(button("Compiling…")?.disabled).toBe(true);
    await advance(POLL_MS * 3);
    expect(checks()).toBe(1);                                                               // no check while the compile runs
    await act(async () => release());
    await flush();
    expect(posts(COMPILE_PATH)).toHaveLength(1);
    expect(posts(COMPILE_PATH)[0]!.body).toEqual({});
    expect(posts(COMPILE_PATH)[0]!.headers["x-polymath-csrf"]).toBe("tok-9");
    expect(pill()).toBe("Compiled");
    expect(host.querySelector(".pr-report__status")?.textContent).toContain("compiled ");
    const open = named("Open report") as HTMLAnchorElement;
    expect(open.getAttribute("href")).toBe(`/product/report/${RID}`);
    expect(open.getAttribute("target")).toBe("_blank");
    expect(open.getAttribute("rel")).toBe("noopener noreferrer");
    expect(open.textContent).toContain("(opens in a new tab)");
    await advance(POLL_MS * 5);
    expect(checks()).toBe(1);                                                               // compiled: never checked again
    expect(button("Compile report")!.disabled).toBe(false);                                 // still there: compile again any time
    expect(host.querySelector("details.pr-report__more summary")?.textContent).toBe("Fetch script for round 1");
  });

  it("a failed report is not checked again and says why; its earlier page still opens; Check again asks once more", async () => {
    fakeTimers();
    statusOver = { status: "failed", compiled: { at: "2026-11-02T09:00:00Z", report_url: null, stale: true,
                                                 error: { error_code: "RENDER_FAILED", message: "the report could not be rendered" } } };
    await act(async () => root.render(<ReportPanel reportId={RID} />));
    expect(pill()).toBe("Checking…");
    await flush();
    await advance(POLL_MS * 4);
    expect(checks()).toBe(1);
    expect(pill()).toBe("Failed");
    expect(host.querySelector(".pr-report__why")?.textContent).toBe("the report could not be rendered (RENDER_FAILED)");
    expect(named("Open report")).toBeDefined();                                             // the last good compile's page
    expect(host.textContent).toContain("New uploads arrived after the last compile: compile again to include them.");
    statusOver = { status: "compiled", compiled: { at: "2026-11-02T09:40:00Z", stale: false, error: null } };
    await act(async () => button("Check again")!.click());
    await flush();
    expect(checks()).toBe(2);
    expect(sentTokens()).toEqual(["", TOKEN2]);                                             // the first check's mint went back
    expect(pill()).toBe("Compiled");
    expect(host.querySelector(".pr-report__why")).toBeNull();
    expect(button("Check again")).toBeUndefined();
    await advance(POLL_MS * 4);
    expect(checks()).toBe(2);
  });

  it("a refusal stops the checks and says why (status and message); Check again resumes them", async () => {
    fakeTimers();
    routes[`GET ${STATUS_PATH}`] = () => Response.json(
      { detail: { error_code: "REPORT_NOT_FOUND", message: "no such product report for this caller" } }, { status: 404 });
    await act(async () => root.render(<ReportPanel reportId={RID} initial={START} />));
    await flush();
    expect(alerts()).toEqual(["Couldn't check the report's status. HTTP 404: no such product report for this caller"]);
    await advance(POLL_MS * 4);
    expect(checks()).toBe(1);
    routes[`GET ${STATUS_PATH}`] = fakeStatus;
    await act(async () => button("Check again")!.click());
    await flush();
    expect(checks()).toBe(2);
    expect(alerts()).toEqual([]);
    await advance(POLL_MS);
    expect(checks()).toBe(3);                                                               // collecting again: the checks go on
  });

  it("a server error or a dropped connection is shown, the checks go on, and the next answer clears it", async () => {
    fakeTimers();
    routes[`GET ${STATUS_PATH}`] = () => new Response("<html><body><h1>503 Service Unavailable</h1></body></html>", { status: 503 });
    await act(async () => root.render(<ReportPanel reportId={RID} initial={START} />));
    await flush();
    expect(alerts()).toEqual(["Couldn't check the report's status. HTTP 503: 503 Service Unavailable"]);
    routes[`GET ${STATUS_PATH}`] = () => { throw new TypeError("Failed to fetch"); };
    await advance(POLL_MS);
    expect(alerts()).toEqual(["Couldn't check the report's status. Failed to fetch"]);
    routes[`GET ${STATUS_PATH}`] = fakeStatus;
    await advance(POLL_MS);
    expect(checks()).toBe(3);
    expect(alerts()).toEqual([]);
    expect(pill()).toBe("Collecting data");
    expect(sentTokens()).toEqual([TOKEN, TOKEN, TOKEN]);                                    // the held token survived the errors
  });

  it("Compile any time: it names the sections the report will leave out; a compile refusal is shown in words", async () => {
    routes[`POST ${COMPILE_PATH}`] = () => Response.json({ detail: { error_code: "HOST_DATA_PENDING",
      message: "the CJ / eBay host data is still being collected: call status again shortly" } }, { status: 409 });
    await act(async () => root.render(<ReportPanel reportId={RID} initial={START} />));
    await flush();
    expect(host.querySelector(".pr-report__missing")?.textContent).toBe(
      "Nothing has been uploaded yet: compiling now leaves out the Reddit findings, Amazon prices, Alibaba offers (MOQ, lead time) " +
      "and eBay prices (each marked “needs a local agent”).");
    expect(button("Compile report")!.disabled).toBe(false);
    await act(async () => button("Compile report")!.click());
    await flush();
    expect(alerts()).toEqual(["Couldn't compile the report. HTTP 409: the CJ / eBay host data is still being collected: call status again shortly"]);
    expect(button("Compile report")!.disabled).toBe(false);
    expect(named("Open report")).toBeUndefined();
  });
});

/* ── 4. what a compile now leaves out ────────────────────────────────────────────────────────────────────────────── */

it("names only the sections with nothing uploaded; eBay only when the person's Agent Reach has to read it; nothing before the counts", () => {
  const v = (over: Record<string, unknown>) => reportView(b4b({ uploads: undefined, ...over }))!;
  const bySource = (x: Record<string, Record<string, number>>) => ({ total: 1, by_round: {}, by_source: x });
  expect(missingNote(v({}))).toBe("");                                                      // the counts are not known yet
  expect(missingNote(v({ uploads: bySource({ reddit: { OK: 2 }, alibaba: { OK: 1 }, ebay: { BLOCKED: 3 } }) }))).toBe(
    "Nothing has been uploaded yet for the Amazon prices: compiling now leaves it out (marked “needs a local agent”).");
  expect(missingNote(v({ uploads: bySource({ reddit: { OK: 1 }, amazon: { OK: 1 }, alibaba: { OK: 1 }, ebay: { OK: 1 } }) }))).toBe("");
  // the server reads eBay itself (its key is set): no eBay read in the round, no EBAY_NOT_CONFIGURED
  const served = { host: { status: "done", ebay: { c1: { status: "OK", listings: 4 } } },
                   fetch_plan: { round: 1, packets: PACKETS.slice(0, 3), script: SCRIPT } };
  expect(missingNote(v({ ...served, uploads: bySource({}) }))).toBe(
    "Nothing has been uploaded yet: compiling now leaves out the Reddit findings, Amazon prices and Alibaba offers (MOQ, lead time) " +
    "(each marked “needs a local agent”).");
  expect(missingNote(v({ ...served, uploads: bySource({ alibaba: { OK: 4 } }) }))).toBe(
    "Nothing has been uploaded yet for the Reddit findings and Amazon prices: compiling now leaves them out (marked “needs a local agent”).");
  // round 2 plans no eBay read, but the server said it has no eBay key: eBay still counts as the person's to read
  expect(missingNote(v({ fetch_plan: { round: 2, packets: PACKETS.slice(1, 3), script: SCRIPT },
                         uploads: bySource({ reddit: { OK: 1 }, amazon: { OK: 1 }, alibaba: { OK: 1 } }) })))
    .toBe("Nothing has been uploaded yet for the eBay prices: compiling now leaves it out (marked “needs a local agent”).");
});

/* ── 5. the Reports screen ───────────────────────────────────────────────────────────────────────────────────────── */

describe("the Reports screen", () => {
  const row = (over: Record<string, unknown>) => ({ round: 1, updated_at: null, products_from: "caller", candidates_status: "ready",
    candidates: [], uploads: 0, compiled: false, compiled_at: null, upload_expires_at: null, ...over });
  const LIST = { contract: "product-report-v1", view: "list", reports: [
    row({ report_id: "rpt_old", created_at: "2026-10-30T09:00:00Z", status: "failed", compiled: true, uploads: 12,
          candidates: [{ candidate_id: "c1", title: "Cable tidy" }, { candidate_id: "c2", title: "Desk lamp" }] }),
    row({ report_id: "rpt_undated", created_at: "not a date", status: "collecting", candidates: [] }),
    row({ report_id: RID, created_at: "2026-11-02T08:00:00Z", status: "collecting", uploads: 1,
          candidates: [{ candidate_id: "c1", title: "Heated camera grip wrap" }, { candidate_id: "c2", title: "Cold-proof battery pouch" }] }),
    row({ report_id: "", status: "compiled" }),
    "not a row",
  ] };

  it("lists the person's reports newest first, with their status, and an open link only where a compiled page exists", async () => {
    routes["GET /product/reports"] = () => Response.json(LIST);
    await act(async () => root.render(<Reports />));
    await flush();
    const rows = [...host.querySelectorAll<HTMLElement>(".pr-reports__row")];
    expect(rows.map((r) => r.querySelector("h2")?.textContent))
      .toEqual(["Heated camera grip wrap · Cold-proof battery pouch", "Cable tidy · Desk lamp", "Untitled report"]);
    expect(rows.map((r) => r.querySelector(".pill")?.textContent)).toEqual(["Collecting data", "Failed", "Collecting data"]);
    expect(rows.map((r) => r.querySelector(".pill")?.getAttribute("title"))).toEqual(["collecting", "failed", "collecting"]);
    expect(rows[0]!.querySelector(".pr-reports__meta")?.textContent).toMatch(/^Created .+ · 2 products · 1 upload$/);
    expect(rows[2]!.querySelector(".pr-reports__meta")?.textContent).toBe("Created not a date · 0 uploads");
    expect(rows.map((r) => r.querySelector("a")?.getAttribute("href") ?? null)).toEqual([null, "/product/report/rpt_old", null]);
    expect(rows[1]!.querySelector("a")?.getAttribute("target")).toBe("_blank");
    expect(rows[1]!.querySelector("a")?.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("Details opens a report's panel (it gets its own upload link and sends it back), Compile, and keeps the row in step", async () => {
    fakeTimers();
    routes["GET /product/reports"] = () => Response.json(LIST);
    await act(async () => root.render(<Reports />));
    await flush();
    const first = () => host.querySelector<HTMLElement>(".pr-reports__row")!;
    const toggle = first().querySelector<HTMLButtonElement>(".pr-reports__toggle")!;
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    await act(async () => toggle.click());
    await flush();
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(sentTokens()).toEqual([""]);                                                    // a page that holds no token …
    expect(first().querySelector(".pr-report__script pre")?.textContent).toBe(scriptFor(urlFor(TOKEN2)));   // … gets one minted
    await advance(POLL_MS);
    expect(sentTokens()).toEqual(["", TOKEN2]);                                            // and sends it back
    await act(async () => button("Compile report")!.click());
    await flush();
    expect(first().querySelector(".pr-reports__head .pill")?.textContent).toBe("Compiled");   // the row follows the panel
    expect(first().querySelector(".pr-reports__actions a")?.getAttribute("href")).toBe(`/product/report/${RID}`);
    await act(async () => toggle.click());
    expect(first().querySelector(".pr-report__panel")).toBeNull();
    expect(storageHolds()).not.toContain(TOKEN2);
  });

  it("no reports yet: says how to make one; a refusal: status and message, then Retry", async () => {
    await act(async () => root.render(<Reports />));
    await flush();
    expect(host.textContent).toContain("No decision reports yet");
    expect(host.textContent).toContain("press Build decision report");
    routes["GET /product/reports"] = () => Response.json({ detail: { message: "the report store is not reachable" } }, { status: 500 });
    await act(async () => button("Refresh")!.click());
    await flush();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("HTTP 500: the report store is not reachable");
    routes["GET /product/reports"] = () => Response.json(LIST);
    await act(async () => button("Retry")!.click());
    await flush();
    expect(host.querySelectorAll(".pr-reports__row")).toHaveLength(3);
    expect(host.querySelector('[role="alert"]')).toBeNull();
  });

  it("Reports is in the navigation and opens the list", async () => {
    vi.stubGlobal("fetch", vi.fn(async (path: string) => {
      calls.push({ path, method: "GET", headers: {}, body: null });
      if (path === "/auth/me") return Response.json({ username: "fred", display_name: "Fred", is_owner: false, must_change_password: false,
                                                      principal_id: "prn_fred", local: false });
      if (path === "/corpora") return Response.json({ corpora: [{ corpus_id: "cinema", documents: 3, query_ready: true, query_enabled: true }] });
      if (path === "/product/reports") return Response.json(LIST);
      return Response.json({});
    }));
    await act(async () => root.render(<App />));
    await flush();
    const nav = [...host.querySelectorAll<HTMLButtonElement>(".nav__item")].find((b) => b.textContent?.trim() === "Reports")!;
    expect(nav.querySelector("svg")).not.toBeNull();
    await act(async () => nav.click());
    await flush();
    expect(host.querySelector(".nav__item[aria-current=page]")?.textContent).toBe("Reports");
    expect(host.querySelector(".screen__title")?.textContent).toBe("Reports");
    expect(calls.some((c) => c.path === "/product/reports")).toBe(true);
    expect(host.querySelectorAll(".pr-reports__row")).toHaveLength(3);
  });
});

/* ── 6. any field may be missing ─────────────────────────────────────────────────────────────────────────────────── */

describe("replies with holes", () => {
  it("a panel over a reply with nothing usable draws its status and Compile, and never crashes", async () => {
    routes[`GET ${STATUS_PATH}`] = () => Response.json({ status: 5, candidates: "x", fetch_plan: [], uploads: 3, host: null, round: "two",
                                                          rounds: "x", compiled: "yes", upload: "x" });
    await act(async () => root.render(<ReportPanel reportId={RID} initial={{ report_id: RID }} />));
    await flush();
    expect(pill()).toBe("Status not given");
    expect(host.querySelector(".pr-report__status code")?.textContent).toBe(RID);
    expect(host.querySelector(".pr-report__script, .pr-report__counts, .pr-report__products, .pr-report__missing")).toBeNull();
    expect(named("Open report")).toBeUndefined();
    expect(button("Compile report")!.disabled).toBe(false);
    expect(button("Check again")).toBeDefined();                                             // an unknown state: not checked on its own
  });

  it("the plan's simpler wording reads too: `fetch` with its own upload, flat counts, a candidate list, a compile `url`", async () => {
    const plain = { report_id: RID, status: "collecting", candidates: [{ candidate_id: "c1", title: "Heated camera grip wrap", search_terms: ["warmer"] }],
      fetch: { round: 1, script: SCRIPT, script_sha256: SHA, upload: { url: UPLOAD, expires_at: "2099-01-01T12:00:00Z" }, packets: PACKETS },
      uploads: { reddit: 2, amazon: "1", alibaba: 0, ebay: -4 }, next: "run it" };
    routes[`GET ${STATUS_PATH}`] = () => Response.json(plain);
    routes[`POST ${COMPILE_PATH}`] = () => Response.json({ report_id: RID, url: `/product/report/${RID}`, summary: [] });
    await act(async () => root.render(<ReportPanel reportId={RID} initial={plain} />));
    await flush();
    expect(shownScript()).toBe(SCRIPT);
    expect([...host.querySelectorAll(".pr-report__script code")].map((c) => c.textContent)).toEqual([AGENT_REACH_CHECK, UPLOAD]);
    expect(counts()).toEqual({ Reddit: "2", Amazon: "1", Alibaba: "0", eBay: "0" });
    expect(host.querySelector(".pr-report__products li")?.textContent).toBe("Heated camera grip wrap · warmer");
    await act(async () => button("Compile report")!.click());
    await flush();
    expect(pill()).toBe("Compiled");
    expect(named("Open report")?.getAttribute("href")).toBe(`/product/report/${RID}`);
  });

  it("a later reply keeps what an earlier one said and it leaves out; the link's state follows ADR-0023's word", () => {
    const first = reportView(START)!;
    expect(first.fetch?.blocked).toBe("");
    const later = reportView({ status: "collecting", fetch_plan: null, candidates: null }, first)!;
    expect(later.fetch?.script).toBe(SCRIPT);
    expect(later.candidates?.map((c) => c.title)).toEqual(["Heated camera grip wrap", "Cold-proof battery pouch"]);
    expect(later.ebayNotConfigured).toBe(true);
    expect(later.round).toBe(1);
    expect(later.progress).toEqual({ round: 1, packets: 4, received: 0 });
    expect(reportView({ report_url: `${BASE}/product/report/x` }, later)!.status).toBe("compiled");
    expect(reportView("not an object", later)).toBe(later);
    expect(reportView({ fetch_plan: { script: "  ", packets: [] } })!.fetch).toBeNull();     // no plan worth showing
    const link = (key: Key, token: string | null = null) => reportView(b4b({}, key, token))!.fetch!;
    expect(link("minted", TOKEN2)).toEqual(expect.objectContaining({ blocked: "", uploadUrl: urlFor(TOKEN2) }));
    expect(link("reused", TOKEN)).toEqual(expect.objectContaining({ blocked: "", uploadUrl: UPLOAD }));
    expect(link("required")).toEqual(expect.objectContaining({ blocked: "required", mintAfter: MINT_AFTER, uploadUrl: "" }));
    expect(link("expired")).toEqual(expect.objectContaining({ blocked: "expired", uploadUrl: "" }));
    expect(reportView(b4b({ upload: { url: urlFor(null), token: "none" } }))!.fetch?.blocked).toBe("none");
    expect(reportView(b4b({ upload: { url: urlFor(null) } }))!.fetch?.blocked).toBe("no-link");   // no word, a placeholder link
    // the server's "minted" stands even when this page's clock reads the expiry as past
    expect(reportView(b4b({ upload: { url: urlFor(TOKEN2), token: "minted", expires_at: "2000-01-01T00:00:00Z" } }))!.fetch?.blocked).toBe("");
  });

  it("reads the list defensively: rows without an id are dropped, a product count or list reads as words", () => {
    expect(reportRows(null)).toEqual([]);
    expect(reportRows({ reports: "x" })).toEqual([]);
    const rows = reportRows({ reports: [{ report_id: "a", products: 1 }, { report_id: "b", title: "Mitts", products: [null, "Mitts", { title: 3 }] }] });
    expect(rows.map((r) => [r.reportId, r.title, r.products, r.status, r.hasPage]))
      .toEqual([["a", "", "1 product", "", false], ["b", "Mitts", "Mitts · 3", "", false]]);
  });
});

/* ── 7. back to the report page after signing in ─────────────────────────────────────────────────────────────────── */

describe("back to the report page after signing in", () => {
  const FRED = { username: "fred", display_name: "Fred", is_owner: false, must_change_password: false, principal_id: "prn_fred", local: false };
  const PAGE = `/product/report/${RID}`;
  /** the web boundary's redirect for a report page opened without a session: /v2/?next=<the path, percent-encoded> */
  const fromBoundary = (path: string) => `?next=${encodeURIComponent(path)}`;
  let leave: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    leave = vi.fn();
    vi.spyOn(pageNavigation, "assign").mockImplementation(leave);                       // a full page load, recorded instead
    routes["GET /corpora"] = () => Response.json({ corpora: [{ corpus_id: "cinema", documents: 3, query_ready: true, query_enabled: true }] });
    routes["POST /auth/login"] = () => Response.json(FRED);
  });

  /** The app at /v2/<search>, with the person signed in already (`me`) or not (401: the sign-in screen). */
  async function openApp(search: string, me: Record<string, unknown> | null) {
    window.history.replaceState(null, "", `/v2/${search}`);
    routes["GET /auth/me"] = () => (me ? Response.json(me)
      : Response.json({ detail: { error_code: "LOGIN_REQUIRED", message: "please sign in" } }, { status: 401 }));
    await act(async () => root.render(<App />));
    await flush();
  }

  function type(input: HTMLInputElement, value: string) {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  async function signIn() {
    const user = host.querySelector<HTMLInputElement>("#signin-username")!;
    const pass = host.querySelector<HTMLInputElement>("#signin-password")!;
    await act(async () => { type(user, "fred"); type(pass, "a long enough password"); });
    await act(async () => host.querySelector<HTMLButtonElement>('button[type="submit"]')!.click());
    await flush();
  }

  it("a valid next sends the person back to the report after they sign in, with a full page load, and drops the param", async () => {
    await openApp(fromBoundary(PAGE), null);
    expect(host.querySelector("#signin-username")).not.toBeNull();                         // the sign-in screen first …
    expect(leave).not.toHaveBeenCalled();                                                  // … and nowhere yet
    await signIn();
    expect(posts("/auth/login")).toHaveLength(1);
    expect(leave).toHaveBeenCalledTimes(1);
    expect(leave).toHaveBeenCalledWith(PAGE);
    expect(window.location.pathname).toBe("/v2/");
    expect(window.location.search).toBe("");                                               // Back does not send them on again
  });

  it("already signed in: goes back at once", async () => {
    await openApp(fromBoundary(PAGE), FRED);
    expect(leave).toHaveBeenCalledWith(PAGE);
    expect(leave).toHaveBeenCalledTimes(1);
    expect(window.location.search).toBe("");
  });

  it("any other next is ignored, before and after signing in", async () => {
    const others = [
      "//evil.com", "https://evil.com", "/product/report/rpt_x/../../x", "/v2/x",
      `/product/report/rpt_${"a".repeat(25)}`,                                             // a too-long id
      `/product/report/rpt_${"a".repeat(23)}`, `/product/report/rpt_${"A".repeat(24)}`, `${PAGE}?x=1`, `${PAGE}/`,
      `//evil.com${PAGE}`, `https://evil.com${PAGE}`, `/v2/..${PAGE}`, ` ${PAGE}`, `${PAGE}\n`, "",
    ];
    for (const next of others) {
      await act(async () => root.unmount());
      root = createRoot(host);
      await openApp(fromBoundary(next), null);
      await signIn();
      expect(leave, JSON.stringify(next)).not.toHaveBeenCalled();
      expect(new URLSearchParams(window.location.search).get("next"), "left as it was").toBe(next);
    }
    await act(async () => root.unmount());
    root = createRoot(host);
    await openApp(`?next=${encodeURIComponent(PAGE)}&next=${encodeURIComponent("//evil.com")}`, FRED);   // two: ambiguous
    expect(leave).not.toHaveBeenCalled();
  });

  it("a forced password change comes first: no return while it is pending", async () => {
    await openApp(fromBoundary(PAGE), { ...FRED, must_change_password: true });
    expect(host.querySelector('form[aria-label="Change password"]')).not.toBeNull();
    expect(leave).not.toHaveBeenCalled();
  });

  it("reads next exactly: percent-encoded or not, other params and the fragment stay", () => {
    expect(reportReturnPath(fromBoundary(PAGE))).toBe(PAGE);
    expect(reportReturnPath(`?next=${PAGE}`)).toBe(PAGE);
    expect(reportReturnPath("")).toBeNull();
    expect(reportReturnPath(`?other=${encodeURIComponent(PAGE)}`)).toBeNull();
    window.history.replaceState(null, "", `/v2/?a=1&next=${encodeURIComponent(PAGE)}&b=2#chat`);
    expect(returnToReport()).toBe(true);
    expect(leave).toHaveBeenCalledWith(PAGE);
    expect(`${window.location.pathname}${window.location.search}${window.location.hash}`).toBe("/v2/?a=1&b=2#chat");
    expect(returnToReport()).toBe(false);                                                  // once: the param is gone
    expect(leave).toHaveBeenCalledTimes(1);
  });
});
