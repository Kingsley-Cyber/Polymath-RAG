// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { AnswerBody } from "../components/AnswerBody";
import { ProductResearch } from "../components/ProductResearch";
import { newTurn, runTurn, type Turn } from "../lib/chat";
import { emptySession, loadSessions, saveSessions, type ChatSession } from "../lib/chatStore";
import type { AgentReachFallback, ProductResearchResult, RetrievalReceipt, RunView } from "../lib/contracts";
import { agentPrompt, productView, startErrorWords } from "../lib/productResearch";
import { ApiError } from "../lib/api";
import { Chat } from "../screens/Chat";

/** PRODUCT-SEARCH-E2E — a product question in chat returns `result.product_research` (contract product-search-v1): product
 *  hypotheses built from the library, each with its CJ Dropshipping finds, Alibaba through Agent Reach only, and the offer to start
 *  the full governed research (TRAIL-INTERFACE-V1 T6: start it from the web, then hand the run id and a ready prompt to the
 *  person's own agent). Before: runTurn copied only named answer fields, so the block never reached the screen, and the web had
 *  no start call at all. Fixtures are synthetic (no supplier listing or field evidence enters the repository). */

const INSTALL = { repo: "https://github.com/example/agent-reach", verify: "agent-reach doctor --json" };
const reach = (over: Partial<AgentReachFallback>): AgentReachFallback => ({
  kind: "AGENT_REACH", reason_code: "LOCAL_ONLY", why: "", run_on: "your own computer", never: "Never paste a password or cookie into Polymath.",
  install: INSTALL, commands: [], submit: { tool: "upload_text" }, ...over,
});

const NOTE = "No terminal? Ask your agent to run these commands for you.";
/** the backend's command objects (shared/polymath_shared/acquisition/agent_reach.py `fallback`), beside plain command lines */
const EXA = "mcporter call exa.web_search_exa query='site:cjdropshipping.com insulated battery pouch' numResults=10";
const JINA = "curl -s 'https://r.jina.ai/<PRODUCT_URL>'";
const HOW = "install Agent Reach on your own machine as its README says, then run the verify command";
const WALLS = "CJ often shows automated readers a human check: never solve, skip or work around it; open the page in your own browser.";

function full(): ProductResearchResult {
  return {
    contract: "product-search-v1",
    intent: { kind: "PRODUCT_DISCOVERY", seed: "gear for winter photographers", audience: "landscape photographers", geography: "US" },
    corpus_ids: ["cinema"],
    hypotheses: [
      {
        id: "h1", title: "Heated camera grip wrap", problem: "Fingers go numb holding a metal camera body in the cold.",
        audience: "Winter landscape photographers", evidence_tags: ["S1", "S3", "S1"], search_terms: ["heated hand warmer", "usb heated wrap"],
        cj: { status: "OK", fallback: null, items: [
          { title: "USB Heated Hand Warmer Wrap", price: "US$11.85", discount_price: "US$9.99", moq: "2 units",
            image: "https://cf.example-cdn.test/a.jpg", url: "https://cj.example.test/product/usb-heated-p-123.html", product_id: "123",
            sku: "CJ123", category: "Outdoor", stores_listing: "1203", warehouse_stock: "540", supplier: "Warmth Supply Co." },
          { title: "Rechargeable Pocket Warmer", price: "US$6.20", discount_price: null, moq: "1 unit", image: "https://cf.example-cdn.test/b.jpg",
            url: "https://cj.example.test/product/pocket-p-456.html", product_id: "456", stores_listing: 87, warehouse_stock: 12, supplier: "Heat Goods" },
        ] },
        alibaba: { status: "AGENT_REACH_REQUIRED", fallback: reach({ reason_code: "ALIBABA_LOCAL_ONLY", why: "Alibaba has no API this server may use.",
          commands: ['agent-reach alibaba search "heated camera wrap"'] }) },
      },
      {
        id: "h2", title: "Cold-proof battery pouch", problem: "Spare batteries die on the trail.", audience: "Hikers who film",
        evidence_tags: ["S3"], search_terms: ["insulated battery pouch"],
        cj: { status: "UNAVAILABLE", items: [], fallback: reach({ reason_code: "CJ_NOT_CONNECTED", why: "CJ is not connected on this server.",
          never: "Never share your CJ password.", install: { ...INSTALL, how: HOW }, walls: WALLS,
          commands: [{ step: 1, run: EXA, what: "searches cjdropshipping.com product pages through Exa, on your machine",
                       then: 'send its whole output, unedited, to supplier_parse with site "cjdropshipping.com"' },
                     { step: 2, run: JINA, for_each: "product page URL from step 1 you want in full",
                       what: "reads that one product page through Jina Reader, on your machine",
                       then: "send each page's output, unedited, as its own supplier_parse call" }] }) },
        alibaba: { status: "AGENT_REACH_REQUIRED", fallback: reach({ commands: ['agent-reach alibaba search "battery pouch"'] }) },
      },
    ],
    limitations: ["a listing proves supply, not demand", "prices are as CJ lists them"],
    next: { full_research: { tool: "adapter_start", adapter_id: "ecommerce.product_research",
                             input: { seed: "gear for winter photographers", corpus_ids: ["cinema"], geography: "US" },
                             who_drives: "your agent", note: "The governed research: field evidence, TrailSignal's gates and scores." } },
    agent_reach: { local_only: true, install: INSTALL, no_terminal_note: NOTE },
  };
}

const RECEIPT: RetrievalReceipt = {
  mode: "HYBRID", engine: "chat-retrieval-v2", evidence_count: 2,
  legend: [{ tag: "S1", chunk_id: "c1", locator: "chunk:c1@0:9", breadcrumb: "Field Notes › Cold hands" },
           { tag: "S3", chunk_id: "c3", locator: "chunk:c3@0:9", breadcrumb: "Gear Guide › Batteries" }],
  chunks: [{ locator: "chunk:c1@0:9", doc_id: "doc_a", title: "Cold hands", source_name: "Field Notes.pdf", preview: "Fingers go numb below freezing." },
           { locator: "chunk:c3@0:9", doc_id: "doc_b", title: "Batteries", source_name: "Gear Guide.pdf", preview: "Cells lose charge in the cold." }],
};

const RUN = { run_id: "adr_0123456789abcdef", adapter_id: "ecommerce.product_research", adapter_version: "0.7.0",
              workflow_version: "1.0.0", created_at: "2026-11-01T10:00:00Z", status: "running" };

function productTurn(over: Partial<Turn> = {}): Turn {
  return { ...newTurn("What could I sell to winter photographers?", "HYBRID"), done: true,
           answerText: "Three ideas grounded in your library [S1].", receipt: RECEIPT, productResearch: full(), ...over };
}

let host: HTMLDivElement;
let root: Root;
let written: string[];
let calls: { path: string; method: string; headers: Record<string, string>; body: unknown }[];
let startReply: () => Response | Promise<Response>;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  document.cookie = "polymath_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  written = [];
  calls = [];
  startReply = () => Response.json(RUN);
  Object.defineProperty(navigator, "clipboard", { configurable: true,
    value: { writeText: vi.fn(async (t: string) => { written.push(t); }) } });
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    calls.push({ path, method: init?.method ?? "GET", headers: (init?.headers ?? {}) as Record<string, string>,
                 body: typeof init?.body === "string" ? JSON.parse(init.body) : null });
    if (path === "/adapter/start") return startReply();
    return Response.json({});
  }));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  document.cookie = "polymath_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  vi.unstubAllGlobals();
});

async function settle() { await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); }

async function show(t: Turn, product?: Parameters<typeof AnswerBody>[0]["product"]) {
  await act(async () => root.render(<AnswerBody t={t} models={[]} product={product} />));
}

const sections = () => [...host.querySelectorAll<HTMLElement>("section.pr-hyp")];
const buttonNamed = (name: string, scope: ParentNode = host) =>
  [...scope.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.getAttribute("aria-label") === name || b.textContent?.trim() === name);
const startPosts = () => calls.filter((c) => c.path === "/adapter/start");

/* ── 1. the answer field reaches the turn, and persists with the chat ─────────────────────────────────────────────── */

describe("runTurn and the chat store", () => {
  async function streamAnswer(result: Record<string, unknown>): Promise<Partial<Turn> | undefined> {
    const body = `event: answer\ndata: ${JSON.stringify({ kind: "llm", latency_ms: 10, result, retrieval: RECEIPT })}\n\nevent: done\ndata: {}\n\n`;
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new ReadableStream<Uint8Array>({
      start(c) { c.enqueue(new TextEncoder().encode(body)); c.close(); },
    }))));
    const seen: Partial<Turn>[] = [];
    await runTurn({ message: "q" }, (p) => seen.push(p));
    return seen.find((p) => "answerText" in p);
  }

  it("carries result.product_research onto the turn; an answer without one (or a non-object) leaves it null", async () => {
    const withBlock = await streamAnswer({ answer: "Ideas [S1].", model: "ollama:fake", meta: { verdict: "generated" }, product_research: full() });
    expect(withBlock?.productResearch?.contract).toBe("product-search-v1");
    expect(withBlock?.productResearch?.hypotheses?.[0]?.cj?.items?.[0]?.price).toBe("US$11.85");
    expect(withBlock?.answerText).toBe("Ideas [S1].");
    expect(withBlock?.verdict).toBe("generated");                    // the named fields still land as before
    expect((await streamAnswer({ answer: "Plain answer." }))?.productResearch).toBeNull();
    expect((await streamAnswer({ answer: "x", product_research: ["not", "an", "object"] }))?.productResearch).toBeNull();
    expect((await streamAnswer({ answer: "x", product_research: "text" }))?.productResearch).toBeNull();
  });

  it("a product turn and the run started from it survive a save and a reload; an older turn loads and renders as before", async () => {
    const run = { run_id: RUN.run_id, adapter_id: RUN.adapter_id, status: "running", started_at: 1 };
    const older = { ...newTurn("An old question", "HYBRID"), done: true, answerText: "Old answer." };
    const session: ChatSession = { ...emptySession("cinema"), turns: [older, productTurn({ productRun: run })] };
    saveSessions([session]);
    const [loaded] = loadSessions();
    expect(loaded?.turns[0]?.productResearch).toBeUndefined();
    expect(loaded?.turns[1]?.productResearch).toEqual(full());
    expect(loaded?.turns[1]?.productRun).toEqual(run);
    await show(loaded!.turns[0]!);
    expect(host.querySelector(".pr")).toBeNull();
    expect(host.textContent).toContain("Old answer.");
    await show(loaded!.turns[1]!);
    expect(sections()).toHaveLength(2);
    expect(host.textContent).toContain(`Started run ${RUN.run_id}`);
  });
});

/* ── 2. the block, from a full answer ─────────────────────────────────────────────────────────────────────────────── */

describe("rendering a full product answer", () => {
  it("draws one section per hypothesis: title, problem, audience and its evidence tags as the answer's citation chips", async () => {
    await show(productTurn());
    const [a, b] = sections();
    expect(sections()).toHaveLength(2);
    expect(host.querySelector(".pr__title")?.textContent).toBe("Product ideas from your library");
    expect(host.querySelector(".pr__intent")?.textContent).toBe("“gear for winter photographers” · for landscape photographers · in US");
    expect(a!.querySelector("h4")?.textContent).toBe("Heated camera grip wrap");
    expect(a!.textContent).toContain("Fingers go numb holding a metal camera body in the cold.");
    expect(a!.textContent).toContain("Winter landscape photographers");
    expect(a!.textContent).toContain("Searched for: heated hand warmer · usb heated wrap");
    const chips = [...a!.querySelectorAll<HTMLButtonElement>(".cite__btn")];
    expect(chips.map((c) => c.textContent)).toEqual(["[S1]", "[S3]"]);          // the repeated S1 is shown once
    expect(chips[0]!.getAttribute("aria-label")).toBe("Source S1: Cold hands");    // resolved through the chat receipt
    expect(a!.querySelector(".cite__card")?.textContent).toContain("Fingers go numb below freezing.");
    expect(b!.querySelector("h4")?.textContent).toBe("Cold-proof battery pouch");
  });

  it("shows CJ's listings as cards: lazy photo with alt text, title, price and discount, MOQ, supplier, stores, stock, a safe link", async () => {
    await show(productTurn());
    const [a] = sections();
    expect(a!.querySelector('[data-source="cj"] .pill')?.textContent).toBe("Listings found");
    const cards = [...a!.querySelectorAll<HTMLElement>(".pr-grid > li.pr-card")];
    expect(cards).toHaveLength(2);
    const img = cards[0]!.querySelector("img")!;
    expect(img.getAttribute("src")).toBe("https://cf.example-cdn.test/a.jpg");
    expect(img.getAttribute("alt")).toBe("USB Heated Hand Warmer Wrap");
    expect(img.getAttribute("loading")).toBe("lazy");
    expect(cards[0]!.querySelector(".pr-card__title")?.textContent).toBe("USB Heated Hand Warmer Wrap");
    expect(cards[0]!.querySelector(".pr-card__price strong")?.textContent).toBe("US$9.99");   // the discount price leads …
    expect(cards[0]!.querySelector(".pr-card__price s")?.textContent).toBe("was US$11.85");    // … the listed price struck through
    const facts = (card: HTMLElement) => Object.fromEntries([...card.querySelectorAll(".pr-card__facts > div")]
      .map((d) => [d.querySelector("dt")?.textContent, d.querySelector("dd")?.textContent]));
    expect(facts(cards[0]!)).toEqual({ MOQ: "2 units", Supplier: "Warmth Supply Co.", "Stores listing": (1203).toLocaleString(), "Warehouse stock": "540" });
    expect(facts(cards[1]!)).toEqual({ MOQ: "1 unit", Supplier: "Heat Goods", "Stores listing": "87", "Warehouse stock": "12" });
    expect(cards[1]!.querySelector(".pr-card__price s")).toBeNull();                         // no discount, no strike-through
    const link = cards[0]!.querySelector("a")!;
    expect(link.getAttribute("href")).toBe("https://cj.example.test/product/usb-heated-p-123.html");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    expect(link.textContent).toContain("View on CJ");
  });

  it("shows Alibaba as Agent Reach only with its panel, the limitations as a note, the no-terminal note exactly once, and the offer", async () => {
    await show(productTurn());
    const ali = sections()[0]!.querySelector<HTMLElement>('[data-source="alibaba"]')!;
    expect(ali.textContent).toContain("Alibaba runs only through Agent Reach on your own device.");
    expect(ali.textContent).toContain("Alibaba has no API this server may use.");
    expect(ali.querySelector("details summary")?.textContent).toBe("Run it on your own device with Agent Reach");
    expect(ali.querySelector(".pr-reach__cmds code")?.textContent).toBe('agent-reach alibaba search "heated camera wrap"');
    const limits = host.querySelector(".pr__limits")!;
    expect([...limits.querySelectorAll("li")].map((l) => l.textContent)).toEqual(["a listing proves supply, not demand", "prices are as CJ lists them"]);
    expect(host.querySelectorAll("details.pr-reach")).toHaveLength(3);                      // Alibaba (h1, h2) and CJ (h2) each have a panel …
    expect(host.textContent!.split(NOTE).length - 1).toBe(1);                                // … but the no-terminal note shows once
    expect(host.querySelector(".pr-offer")?.textContent).toContain("The governed research: field evidence, TrailSignal's gates and scores.");
    expect(host.querySelector(".pr-offer")?.textContent).toContain("Who drives it: your agent");
    expect(buttonNamed("Start full research")).toBeDefined();
  });
});

/* ── 3. a source the server could not search ──────────────────────────────────────────────────────────────────────── */

describe("CJ UNAVAILABLE with an Agent Reach fallback", () => {
  it("says why, and the collapsed panel lists the commands with copy buttons, the install repo and the check command", async () => {
    await show(productTurn());
    const cj = sections()[1]!.querySelector<HTMLElement>('[data-source="cj"]')!;
    expect(cj.querySelector(".pill")?.textContent).toBe("Unavailable here");
    expect(cj.querySelector(".pill")?.getAttribute("title")).toBe("UNAVAILABLE");          // the backend's code stays in the tooltip
    expect(cj.querySelector(".pr-grid")).toBeNull();
    expect(cj.querySelector(".pr-empty__title")?.textContent).toBe("CJ Dropshipping could not be searched from here.");
    expect(cj.querySelector(".pr-empty__why")?.textContent).toBe("CJ is not connected on this server.");
    expect(cj.querySelector(".pr-empty")?.getAttribute("title")).toBe("CJ_NOT_CONNECTED");
    const panel = cj.querySelector<HTMLDetailsElement>("details.pr-reach")!;
    expect(panel.open).toBe(false);                                                          // collapsed until opened
    expect(panel.querySelector("summary")?.textContent).toBe("Run it on your own device with Agent Reach");
    await act(async () => panel.querySelector("summary")!.click());
    expect(panel.open).toBe(true);
    const cmds = [...panel.querySelectorAll(".pr-reach__cmds li")];
    expect(cmds.map((li) => li.querySelector("code")?.textContent)).toEqual([EXA, JINA]);
    expect(cmds[0]!.querySelector(".pr-reach__what")?.textContent).toBe("searches cjdropshipping.com product pages through Exa, on your machine");
    expect(cmds[0]!.querySelector(".pr-reach__then")?.textContent).toBe('Then send its whole output, unedited, to supplier_parse with site "cjdropshipping.com"');
    expect(cmds[1]!.querySelector(".pr-reach__what")?.textContent).toBe(
      "reads that one product page through Jina Reader, on your machine, for each product page URL from step 1 you want in full");
    expect(panel.textContent).toContain(HOW);
    expect(panel.textContent).toContain(WALLS);
    expect(buttonNamed("Copy command 1", panel)).toBeDefined();
    expect(buttonNamed("Copy command 2", panel)).toBeDefined();
    const repo = [...panel.querySelectorAll("a")].find((x) => x.getAttribute("href") === INSTALL.repo)!;
    expect(repo.getAttribute("target")).toBe("_blank");
    expect(repo.getAttribute("rel")).toBe("noopener noreferrer");
    expect(panel.querySelector(".pr-reach__verify code")?.textContent).toBe("agent-reach doctor --json");
    expect(panel.textContent).toContain("your own computer");
    expect(panel.textContent).toContain("Never share your CJ password.");
  });

  it("an EMPTY search says so, and its fallback's install falls back to the answer's own Agent Reach install", async () => {
    const data = full();
    data.hypotheses![1]!.cj = { status: "EMPTY", items: [], fallback: { kind: "AGENT_REACH", why: "Nothing listed for these terms.", commands: ["agent-reach cj search pouch"] } };
    await show(productTurn({ productResearch: data }));
    const cj = sections()[1]!.querySelector<HTMLElement>('[data-source="cj"]')!;
    expect(cj.querySelector(".pill")?.textContent).toBe("No listings");
    expect(cj.querySelector(".pr-empty__title")?.textContent).toBe("No CJ Dropshipping listing matched this idea's search terms.");
    expect(cj.querySelector(".pr-empty__why")?.textContent).toBe("Nothing listed for these terms.");
    expect(cj.querySelector(`details a[href="${INSTALL.repo}"]`)).not.toBeNull();
    expect(cj.querySelector(".pr-reach__verify code")?.textContent).toBe(INSTALL.verify);
  });
});

/* ── 4. any field may be missing ──────────────────────────────────────────────────────────────────────────────────── */

describe("missing and malformed fields", () => {
  it("renders nothing for an empty or non-object block, and never crashes on holes", async () => {
    for (const data of [{}, null, "text", [], { hypotheses: "x", limitations: 3, next: null, agent_reach: [] }]) {
      await show(productTurn({ productResearch: data as unknown as ProductResearchResult }));
      expect(host.querySelector(".pr")).toBeNull();
      expect(host.textContent).toContain("Three ideas grounded in your library");
    }
    expect(productView({})).toBeNull();
  });

  it("draws what is there: an untitled idea, holes in the lists, no CJ or Alibaba, an item with no fields", async () => {
    const data = { hypotheses: [null, "a string", {}, { title: "Only a title", evidence_tags: [null, 4, "S1"], cj: { items: [null, {}, 7] } },
                                { cj: { status: "OK", items: "none" }, alibaba: {} },
                                { title: "Holes in a fallback", alibaba: { fallback: { commands: [null, {}, { what: "nothing to run" }, "agent-reach doctor"] } } }] } as unknown as ProductResearchResult;
    await show(productTurn({ productResearch: data, receipt: null }));
    const hs = sections();
    expect(hs.map((s) => s.querySelector("h4")?.textContent)).toEqual(["Idea 1", "Only a title", "Idea 3", "Holes in a fallback"]);
    expect([...hs[3]!.querySelectorAll(".pr-reach__cmds code")].map((c) => c.textContent)).toEqual(["agent-reach doctor"]);
    expect(hs[0]!.querySelector(".pr-src")).toBeNull();                                      // no cj, no alibaba: no source rows
    expect([...hs[1]!.querySelectorAll(".cite__btn")].map((c) => c.textContent)).toEqual(["[4]", "[S1]"]);
    const card = hs[1]!.querySelector(".pr-card")!;                                          // the one object item
    expect(hs[1]!.querySelectorAll(".pr-card")).toHaveLength(1);
    expect(card.textContent).toContain("Untitled listing");
    expect(card.textContent).toContain("No photo");
    expect(card.querySelector("img, a, .pr-card__price, .pr-card__facts")).toBeNull();
    expect(hs[1]!.querySelector(".pill")?.textContent).toBe("Status not given");
    expect(hs[2]!.querySelector(".pr-empty__title")?.textContent).toBe("No CJ Dropshipping listing to show.");
    expect(hs[2]!.querySelector('[data-source="alibaba"]')?.textContent).toBe("AlibabaAlibaba runs only through Agent Reach on your own device.");
    expect(hs[2]!.querySelector("details")).toBeNull();                                      // no fallback: no panel
    expect(host.querySelector(".pr-offer")).toBeNull();
  });

  it("reads a raw CJ listing record too (cj_api.listing_record: its fields under `listing`, by the API's own names)", async () => {
    const data = full();
    data.hypotheses![0]!.cj!.items = [{ kind: "listing", ref: "789", url: "https://cj.example.test/product/raw-p-789.html", text: "x",
      listing: { title: "Raw Record Warmer", price_as_listed: "US$3.10", discount_price_as_listed: "US$2.50", minimum_order_as_listed: "5 units",
                 supplier: "Raw Co.", image: "https://cf.example-cdn.test/r.jpg", product_id: "789", listed_by_stores: "2500",
                 warehouse_inventory: "40" } }] as unknown as NonNullable<NonNullable<ProductResearchResult["hypotheses"]>[number]["cj"]>["items"];
    await show(productTurn({ productResearch: data }));
    const card = sections()[0]!.querySelector<HTMLElement>(".pr-card")!;
    expect(card.querySelector(".pr-card__title")?.textContent).toBe("Raw Record Warmer");
    expect(card.querySelector("img")?.getAttribute("src")).toBe("https://cf.example-cdn.test/r.jpg");
    expect(card.querySelector(".pr-card__price strong")?.textContent).toBe("US$2.50");
    expect(card.querySelector(".pr-card__price s")?.textContent).toBe("was US$3.10");
    expect([...card.querySelectorAll(".pr-card__facts dd")].map((d) => d.textContent))
      .toEqual(["5 units", "Raw Co.", (2500).toLocaleString(), "40"]);
    expect(card.querySelector("a")?.getAttribute("href")).toBe("https://cj.example.test/product/raw-p-789.html");
  });

  it("never links or loads a javascript: or data: URL from a listing", async () => {
    const data = full();
    data.hypotheses![0]!.cj!.items = [{ title: "Bad", image: "data:image/svg+xml,<svg/>", url: "javascript:alert(1)", price: 4.5 },
                                     { title: "Scheme-relative", image: "//cf.example-cdn.test/c.jpg", url: "//cj.example.test/p-9.html" }];
    await show(productTurn({ productResearch: data }));
    const cards = [...sections()[0]!.querySelectorAll<HTMLElement>(".pr-card")];
    expect(cards[0]!.querySelector("img")).toBeNull();
    expect(cards[0]!.querySelector("a")).toBeNull();
    expect(cards[0]!.querySelector(".pr-card__price strong")?.textContent).toBe("4.5");
    expect(cards[1]!.querySelector("img")?.getAttribute("src")).toBe("https://cf.example-cdn.test/c.jpg");
    expect(cards[1]!.querySelector("a")?.getAttribute("href")).toBe("https://cj.example.test/p-9.html");
  });

  it("a photo that fails to load is replaced by the placeholder", async () => {
    await show(productTurn());
    const img = sections()[0]!.querySelector<HTMLImageElement>(".pr-card img")!;
    await act(async () => { img.dispatchEvent(new Event("error")); });
    expect(sections()[0]!.querySelector(".pr-card")?.textContent).toContain("No photo");
  });

  it("an offer without an adapter id offers nothing to start; null input fields are not sent", async () => {
    const data = full();
    data.next = { full_research: { note: "x" } };
    await show(productTurn({ productResearch: data }));
    expect(host.querySelector(".pr-offer")).toBeNull();
    const offer = productView({ next: { full_research: { adapter_id: "ecommerce.product_research", input: { seed: "s", geography: null, corpus_ids: ["c"] } } } })!.offer;
    expect(offer?.input).toEqual({ seed: "s", corpus_ids: ["c"] });
  });

  it("a product answer with no prose still shows its hypotheses in the chat (not the 'no answer text' notice)", async () => {
    await act(async () => root.render(
      <Chat corpusId="cinema" session={{ ...emptySession("cinema"), turns: [productTurn({ answerText: "" })] }} onUpdateTurns={() => {}}
            models={[]} corpusExploreAvailable={false} />));
    await settle();
    expect(sections()).toHaveLength(2);
    expect(host.textContent).not.toContain("The model returned no answer text");
    expect(buttonNamed("Copy answer")).toBeUndefined();                                      // nothing to copy
  });
});

/* ── 5. copy buttons ──────────────────────────────────────────────────────────────────────────────────────────────── */

describe("copy buttons", () => {
  it("each command, the check command and the install source copy exactly their text", async () => {
    const data = full();
    data.hypotheses![1]!.cj!.fallback!.install = { repo: "example/agent-reach (git)", verify: "agent-reach doctor" };
    await show(productTurn({ productResearch: data }));
    const panel = sections()[1]!.querySelector<HTMLElement>('[data-source="cj"] details')!;
    await act(async () => buttonNamed("Copy command 2", panel)!.click());
    await act(async () => buttonNamed("Copy command 1", panel)!.click());
    await act(async () => buttonNamed("Copy check command", panel)!.click());
    await act(async () => buttonNamed("Copy install source", panel)!.click());              // not a URL: copyable, not a link
    expect(written).toEqual([JINA, EXA, "agent-reach doctor", "example/agent-reach (git)"]);
    expect(buttonNamed("Copied", panel)).toBeDefined();
  });
});

/* ── 6. the offer: start the full research, then hand it to the agent ─────────────────────────────────────────────── */

describe("Start full research", () => {
  it("POSTs /adapter/start with the offer's adapter and input, then shows the run, the way to Research and the agent prompt", async () => {
    document.cookie = "polymath_csrf=tok-123";
    const started: unknown[] = [];
    const opened: string[] = [];
    await show(productTurn(), { onRunStarted: (r) => started.push(r), onOpenResearch: (id) => opened.push(id) });
    await act(async () => buttonNamed("Start full research")!.click());
    await settle();
    expect(startPosts()).toHaveLength(1);
    expect(startPosts()[0]!.method).toBe("POST");
    expect(startPosts()[0]!.body).toEqual({ adapter_id: "ecommerce.product_research",
                                            input: { seed: "gear for winter photographers", corpus_ids: ["cinema"], geography: "US" } });
    expect(startPosts()[0]!.headers["x-polymath-csrf"]).toBe("tok-123");                    // a state change carries the CSRF token
    expect(started).toEqual([expect.objectContaining({ run_id: RUN.run_id, adapter_id: RUN.adapter_id, status: "running" })]);
    expect(host.querySelector(".pr-offer__run")?.textContent).toContain(`Started run ${RUN.run_id}`);
    expect(buttonNamed("Start full research")).toBeUndefined();
    await act(async () => buttonNamed("Open it in Research")!.click());
    expect(opened).toEqual([RUN.run_id]);
    await act(async () => buttonNamed("Copy prompt for your agent")!.click());
    const prompt = written[0]!;
    expect(prompt).toBe(host.querySelector(".pr-offer pre")?.textContent);                  // what is shown is what is copied
    expect(prompt).toContain(`Continue Polymath research run ${RUN.run_id}`);
    expect(prompt).toContain("do not start a new run");
    expect(prompt).toContain(`adapter_next("${RUN.run_id}")`);
    expect(prompt).toContain("adapter_submit");
    expect(prompt).toContain("use your local Agent Reach");
    expect(prompt).toContain("never your built-in web search");
    expect(prompt).toContain(INSTALL.repo);
    expect(prompt).toContain(INSTALL.verify);
  });

  it("a refusal stays on screen in words (status and message), and Start is offered again", async () => {
    startReply = () => Response.json({ detail: { error_code: "ADAPTER_NOT_ALLOWED", message: "that research workflow is not open to this account" } },
                                     { status: 403 });
    await show(productTurn());
    await act(async () => buttonNamed("Start full research")!.click());
    await settle();
    const alert = host.querySelector(".pr-offer [role=alert]")!;
    expect(alert.textContent).toBe("Couldn't start the full research. HTTP 403: that research workflow is not open to this account");
    expect(buttonNamed("Start full research")!.disabled).toBe(false);
    expect(host.querySelector(".pr-offer__run")).toBeNull();
    startReply = () => Response.json(RUN);                                                  // the retry works and clears the error
    await act(async () => buttonNamed("Start full research")!.click());
    await settle();
    expect(host.querySelector(".pr-offer [role=alert]")).toBeNull();
    expect(host.querySelector(".pr-offer__run")?.textContent).toContain(RUN.run_id);
  });

  it("a validation refusal and an unreachable server are named too", async () => {
    startReply = () => Response.json({ detail: ["'seed' is a required property"] }, { status: 422 });
    await show(productTurn());
    await act(async () => buttonNamed("Start full research")!.click());
    await settle();
    expect(host.querySelector(".pr-offer [role=alert]")?.textContent).toContain("HTTP 422: 'seed' is a required property");
    startReply = () => { throw new TypeError("Failed to fetch"); };
    await act(async () => buttonNamed("Start full research")!.click());
    await settle();
    expect(host.querySelector(".pr-offer [role=alert]")?.textContent).toContain("Failed to fetch");
    startReply = () => Response.json({ status: "running" });                                // a reply without a run id is not a start
    await act(async () => buttonNamed("Start full research")!.click());
    await settle();
    expect(host.querySelector(".pr-offer [role=alert]")?.textContent).toContain("names no run");
  });

  it("a double click starts one run", async () => {
    let release!: () => void;
    startReply = () => new Promise<Response>((r) => { release = () => r(Response.json(RUN)); });
    await show(productTurn());
    const b = buttonNamed("Start full research")!;
    await act(async () => { b.click(); b.click(); });
    expect(buttonNamed("Starting…")?.disabled).toBe(true);
    await act(async () => release());
    await settle();
    expect(startPosts()).toHaveLength(1);
  });

  it("in the chat, the started run is kept on its turn: after a reload the run and the prompt are still there", async () => {
    let turns: Turn[] = [productTurn()];
    const session = { ...emptySession("cinema"), turns };
    await act(async () => root.render(
      <Chat corpusId="cinema" session={session} onUpdateTurns={(fn) => { turns = fn(turns); }} models={[]} corpusExploreAvailable={false} />));
    await settle();
    await act(async () => buttonNamed("Start full research")!.click());
    await settle();
    expect(turns[0]?.productRun).toEqual(expect.objectContaining({ run_id: RUN.run_id, adapter_id: RUN.adapter_id }));
    saveSessions([{ ...session, turns }]);
    await act(async () => root.unmount());
    root = createRoot(host);
    await act(async () => root.render(
      <Chat corpusId="cinema" session={loadSessions()[0]!} onUpdateTurns={() => {}} models={[]} corpusExploreAvailable={false} />));
    await settle();
    expect(host.querySelector(".pr-offer__run")?.textContent).toContain(`Started run ${RUN.run_id}`);
    expect(buttonNamed("Start full research")).toBeUndefined();
    expect(buttonNamed("Copy prompt for your agent")).toBeDefined();
    expect(startPosts()).toHaveLength(1);
  });

  it("'Open it in Research' opens the Research screen at that run", async () => {
    const view: RunView = {
      run: { run_id: RUN.run_id, adapter_id: RUN.adapter_id, adapter_version: "0.7.0", title: "Gear for winter photographers", status: "awaiting_agent",
             terminal: false, current_step_id: "B", started_at: null, updated_at: null, finished_at: null, agent_identity: null, gap: null,
             steps_accepted: 1, harness_actions: 0 },
      progress: [{ step_id: "B", type: "AGENT_REASON", title: "Frame hypotheses", state: "waiting_agent", visits: 1 }],
      sections: {}, other_output_keys: [], contradictions: [], unknowns: [], stored_result_shadowed: false,
    };
    const run = { run_id: RUN.run_id, adapter_id: RUN.adapter_id, status: "running", started_at: 1 };
    saveSessions([{ ...emptySession("cinema"), title: "What could I sell to winter photographers?", turns: [productTurn({ productRun: run })] }]);
    vi.stubGlobal("fetch", vi.fn(async (path: string) => {
      calls.push({ path, method: "GET", headers: {}, body: null });
      if (path === "/auth/me") return Response.json({ username: "fred", display_name: "Fred", is_owner: false, must_change_password: false,
                                                      principal_id: "prn_fred", local: false });
      if (path === "/corpora") return Response.json({ corpora: [{ corpus_id: "cinema", documents: 3, query_ready: true, query_enabled: true }] });
      if (path === "/synthesizers") return Response.json({ synthesizers: [] });
      if (path === "/reasoning_modes") return Response.json({ modes: [], default: "none" });
      if (path === `/adapter/${RUN.run_id}/view`) return Response.json(view);
      return Response.json({});
    }));
    await act(async () => root.render(<App />));
    await settle();
    const entry = [...host.querySelectorAll<HTMLButtonElement>(".nav__chat-open")].find((b) => b.title.startsWith("What could I sell"))!;
    await act(async () => entry.click());
    await settle();
    await act(async () => buttonNamed("Open it in Research")!.click());
    await settle();
    expect(calls.some((c) => c.path === `/adapter/${RUN.run_id}/view`)).toBe(true);
    expect(host.querySelector(".screen__title")?.textContent).toBe("Gear for winter photographers");
    expect(host.querySelector(".nav__item[aria-current=page]")?.textContent).toBe("Research");
    expect(host.textContent).toContain("Waiting for your agent");
  });
});

/* ── 7. the pure pieces ───────────────────────────────────────────────────────────────────────────────────────────── */

it("the agent prompt names the run, the loop tools, Agent Reach and the ban on built-in web search, with or without an install", () => {
  const bare = agentPrompt({ run_id: "adr_x" });
  expect(bare).toContain("adr_x");
  expect(bare).toMatch(/adapter_next\("adr_x"\)[\s\S]*adapter_submit[\s\S]*adapter_result\("adr_x"\)/);
  expect(bare).toContain("never your built-in web search or browsing tools");
  expect(bare).not.toContain("Not installed yet");
  expect(agentPrompt({ run_id: "adr_x" }, { verify: "agent-reach doctor" })).toContain("Not installed yet? check it with `agent-reach doctor`.");
});

it("start errors read as status and message for every body shape the server sends", () => {
  const err = (status: number, body: string) => startErrorWords(new ApiError(status, "/adapter/start", body));
  expect(err(404, JSON.stringify({ detail: "unknown adapter 'x.y'" }))).toBe("HTTP 404: unknown adapter 'x.y'");
  expect(err(422, JSON.stringify({ detail: [{ loc: ["body", "input"], msg: "Field required", type: "missing" }] }))).toBe("HTTP 422: body.input: Field required");
  expect(err(422, JSON.stringify({ detail: { rejected: ["seed too short"] } }))).toBe("HTTP 422: seed too short");
  expect(err(502, "<html><body><h1>502 Bad Gateway</h1></body></html>")).toBe("HTTP 502: 502 Bad Gateway");
  expect(err(500, "")).toBe("HTTP 500: the server sent no message");
  expect(startErrorWords(new TypeError("Failed to fetch"))).toBe("Failed to fetch");
});

it("ProductResearch renders on its own (no receipt, no handlers): tags without a source still show, Start still works", async () => {
  await act(async () => root.render(<ProductResearch data={full()} cites={new Map()} />));
  expect([...host.querySelectorAll(".cite__btn")].map((c) => c.getAttribute("aria-label"))).toContain("Source S3");
  await act(async () => buttonNamed("Start full research")!.click());
  await settle();
  expect(host.querySelector(".pr-offer__run")?.textContent).toBe(`Started run ${RUN.run_id}`);   // no Research link without a handler
  expect(buttonNamed("Copy prompt for your agent")).toBeDefined();
});
