/** PRODUCT-SEARCH-E2E — a product question in chat. The answer frame's `result.product_research` (contract product-search-v1)
 *  read defensively (any field may be missing, a listing's text is the supplier's own), the web start of the full governed
 *  research (TRAIL-INTERFACE-V1 T6, "start a run from the web, then hand the run id and a ready prompt to your agent") and that
 *  prompt. Pure: no React. The words of a status are mapped here; the backend's code stays in the tooltip. */
import { ApiError } from "./api";

/** The governed run started from an answer's offer. Kept on the turn, so the run id and the agent prompt survive a reload. */
export interface ProductRunRef { run_id: string; adapter_id?: string; status?: string; started_at?: number }

type Obj = Record<string, unknown>;
const obj = (v: unknown): Obj | null => (v && typeof v === "object" && !Array.isArray(v) ? (v as Obj) : null);

/** A field shown as text: a string as written, a finite number as is; an object, array or boolean is not text. */
export function text(v: unknown): string {
  if (typeof v === "string") return v.trim();
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  return "";
}

/** The text entries of a list, blanks and non-text dropped; `unique` drops repeats (citation tags, React keys). */
export function texts(v: unknown, unique = false): string[] {
  const out = Array.isArray(v) ? v.map(text).filter(Boolean) : [];
  return unique ? [...new Set(out)] : out;
}

/** A count as listed: 1203 or "1203" → "1,203" (the reader's digit grouping); other text as written; a per-place map
 *  {"US": 120, "CN": 3400} → "US 120 · CN 3,400". */
export function countText(v: unknown): string {
  if (typeof v === "number" && Number.isFinite(v)) return v.toLocaleString();
  if (typeof v === "string") {
    const s = v.trim();
    return /^\d{4,15}$/.test(s) ? Number(s).toLocaleString() : s;
  }
  if (Array.isArray(v)) return v.map(countText).filter(Boolean).join(" · ");
  const o = obj(v);
  if (!o) return "";
  return Object.entries(o).map(([k, x]) => { const t = countText(x); return t ? `${k} ${t}` : ""; }).filter(Boolean).join(" · ");
}

/** An http(s) URL to link to or load an image from, else null. A listing's URL is the supplier's own text: never a
 *  `javascript:` or `data:` URL. A scheme-relative "//host/path" is read as https. */
export function httpUrl(v: unknown): string | null {
  const s = text(v);
  if (!s) return null;
  try {
    const u = new URL(s.startsWith("//") ? `https:${s}` : s);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch {
    return null;
  }
}

/* ── the answer, read once into what the view draws ───────────────────────────────────────────────────────────────── */

export type Tone = "ready" | "degraded" | "blocked" | "unknown";

/** CJ's search status → a pill's tone and words. */
const CJ_STATUS: Record<string, { tone: Tone; words: string }> = {
  OK: { tone: "ready", words: "Listings found" },
  PARTIAL: { tone: "degraded", words: "Partly searched" },
  EMPTY: { tone: "unknown", words: "No listings" },
  UNAVAILABLE: { tone: "blocked", words: "Unavailable here" },
  AGENT_REACH_REQUIRED: { tone: "degraded", words: "Needs Agent Reach" },
};

export function cjStatus(code: string): { tone: Tone; words: string } {
  const known = CJ_STATUS[code];
  if (known) return known;
  if (!code) return { tone: "unknown", words: "Status not given" };
  const w = code.replace(/[_.]/g, " ").trim().toLowerCase();
  return { tone: "unknown", words: w.charAt(0).toUpperCase() + w.slice(1) };
}

/** The headline of a CJ search that shows no listing. */
export function cjEmptyWords(code: string): string {
  switch (code) {
    case "EMPTY": return "No CJ Dropshipping listing matched this idea's search terms.";
    case "UNAVAILABLE": return "CJ Dropshipping could not be searched from here.";
    case "AGENT_REACH_REQUIRED": return "This CJ Dropshipping search runs through Agent Reach on your own device.";
    case "PARTIAL": return "Only part of the CJ Dropshipping search ran, and it found no listing.";
    default: return "No CJ Dropshipping listing to show.";
  }
}

/** One command to run: the line itself, what it does, what to run it for, and where its output goes next. */
export interface CommandView { run: string; what: string; forEach: string; then: string }
export interface ReachView {
  reasonCode: string; why: string; runOn: string; never: string; commands: CommandView[];
  /** where Agent Reach installs from, how, and the command that checks it works */
  repo: string; verify: string; how: string;
  /** what to do when the site shows an automated reader a human check */
  walls: string;
}
export interface ItemView {
  key: string; title: string; price: string; discount: string; moq: string; image: string | null; url: string | null;
  supplier: string; stores: string; stock: string;
}
export interface HypothesisView {
  key: string; title: string; problem: string; audience: string; tags: string[]; terms: string[];
  cj: { status: string; items: ItemView[]; reach: ReachView | null } | null;
  alibaba: { status: string; reach: ReachView | null } | null;
}
export interface OfferView { adapterId: string; input: Obj; note: string; whoDrives: string }
export interface ProductView {
  contract: string; seed: string; audience: string; geography: string;
  /** the libraries the answer searched (PRODUCT-DECISION-REPORT-V1 B6: a report built from it uses the same ones) */
  corpusIds: string[];
  hypotheses: HypothesisView[]; limitations: string[]; noTerminalNote: string;
  /** Agent Reach's install source and check command (the answer's, else the first source fallback's) */
  repo: string; verify: string;
  offer: OfferView | null;
}

/** A fallback's commands: plain lines, or objects {run, what, for_each, then} (an entry with nothing to run is dropped). */
function commandsOf(v: unknown): CommandView[] {
  if (!Array.isArray(v)) return [];
  return v.map((c): CommandView => {
    const o = obj(c);
    return o ? { run: text(o.run), what: text(o.what), forEach: text(o.for_each), then: text(o.then) }
      : { run: text(c), what: "", forEach: "", then: "" };
  }).filter((c) => c.run);
}

function reachOf(fallback: unknown, install: Obj | null): ReachView | null {
  const f = obj(fallback);
  if (!f) return null;
  const own = obj(f.install);
  return {
    reasonCode: text(f.reason_code), why: text(f.why), runOn: text(f.run_on), never: text(f.never), commands: commandsOf(f.commands),
    repo: text(own?.repo) || text(install?.repo), verify: text(own?.verify) || text(install?.verify),
    how: text(own?.how) || text(install?.how), walls: text(f.walls),
  };
}

/** CJ's listings. The contract's names come first; a raw CJ listing record (shared/polymath_shared/acquisition/cj_api.py
 *  `listing_record`: its fields under `listing`, named `price_as_listed`, `listed_by_stores`, …) is read too, so the finds
 *  still show if a record arrives unrenamed. */
function itemsOf(v: unknown): ItemView[] {
  if (!Array.isArray(v)) return [];
  return v.map(obj).filter((x): x is Obj => x !== null).map((it, i) => {
    const raw = obj(it.listing);
    const f = (name: string, rawName = name): unknown => it[name] ?? it[rawName] ?? raw?.[name] ?? raw?.[rawName];
    const price = text(f("price", "price_as_listed"));
    const discount = text(f("discount_price", "discount_price_as_listed"));
    return {
      key: `${i}:${text(f("product_id", "ref"))}`, title: text(f("title")), price, discount: discount === price ? "" : discount,
      moq: countText(f("moq", "minimum_order_as_listed")), image: httpUrl(f("image")), url: httpUrl(f("url")),
      supplier: text(f("supplier")), stores: countText(f("stores_listing", "listed_by_stores")),
      stock: countText(f("warehouse_stock", "warehouse_inventory")),
    };
  });
}

/** The answer's offer as sent: an adapter id is required to offer anything; null-valued input fields are dropped (JSON null on
 *  an optional field means absent, and the adapter's input schema refuses a null where it wants a string). */
function offerOf(v: unknown): OfferView | null {
  const f = obj(v);
  const adapterId = text(f?.adapter_id);
  if (!f || !adapterId) return null;
  const input = Object.fromEntries(Object.entries(obj(f.input) ?? {}).filter(([, x]) => x !== null && x !== undefined));
  return { adapterId, input, note: text(f.note), whoDrives: text(f.who_drives) };
}

/** `result.product_research` → what the view draws, or null when it is not an object or holds nothing to show. */
export function productView(data: unknown): ProductView | null {
  const d = obj(data);
  if (!d) return null;
  const intent = obj(d.intent);
  const reach = obj(d.agent_reach);
  const install = obj(reach?.install);
  const hypotheses: HypothesisView[] = (Array.isArray(d.hypotheses) ? d.hypotheses : []).map(obj)
    .filter((x): x is Obj => x !== null).map((h, i) => {
      const cj = obj(h.cj);
      const ali = obj(h.alibaba);
      return {
        key: `${i}:${text(h.id)}`, title: text(h.title), problem: text(h.problem), audience: text(h.audience),
        tags: texts(h.evidence_tags, true), terms: texts(h.search_terms),
        cj: cj ? { status: text(cj.status).toUpperCase(), items: itemsOf(cj.items), reach: reachOf(cj.fallback, install) } : null,
        alibaba: ali ? { status: text(ali.status).toUpperCase(), reach: reachOf(ali.fallback, install) } : null,
      };
    });
  const firstReach = hypotheses.flatMap((h) => [h.cj?.reach, h.alibaba?.reach]).find((r) => r && (r.repo || r.verify));
  const view: ProductView = {
    contract: text(d.contract), seed: text(intent?.seed), audience: text(intent?.audience), geography: text(intent?.geography),
    corpusIds: texts(d.corpus_ids, true), hypotheses, limitations: texts(d.limitations), noTerminalNote: text(reach?.no_terminal_note),
    repo: text(install?.repo) || firstReach?.repo || "", verify: text(install?.verify) || firstReach?.verify || "",
    offer: offerOf(obj(d.next)?.full_research),
  };
  return view.hypotheses.length || view.offer || view.limitations.length || view.noTerminalNote ? view : null;
}

/* ── the full research: start it, then hand it to the person's own agent ──────────────────────────────────────────── */

/** The prompt the person pastes into their agent: continue THIS run (never start another), drive it with adapter_next /
 *  adapter_submit, research with the local Agent Reach and never the agent's built-in web search. */
export function agentPrompt(run: ProductRunRef, opts: { seed?: string; repo?: string; verify?: string } = {}): string {
  const id = run.run_id;
  const install = opts.repo || opts.verify
    ? ` Not installed yet? ${[opts.repo && `Install it from ${opts.repo}`, opts.verify && `check it with \`${opts.verify}\``].filter(Boolean).join(", then ")}.`
    : "";
  return [
    `Continue Polymath research run ${id}${run.adapter_id ? ` (${run.adapter_id})` : ""}. I started it from the Polymath web app: do not start a new run.`,
    opts.seed ? `The idea it researches: ${opts.seed}` : "",
    `Drive it with the Polymath tools. Call adapter_next("${id}"). When it returns a step, do that step and send your answer with ` +
      `adapter_submit (kind "reasoning" for an AGENT_REASON step, kind "receipt" for a HARNESS_ACTION step); a rejected submission ` +
      `leaves the step open, so fix it and resubmit the same step. Repeat until the run ends, then call adapter_result("${id}") and ` +
      `tell me what it found: a refusal or a gap is a finding, not an error.`,
    `For every research step use your local Agent Reach on this device, never your built-in web search or browsing tools.${install}`,
    `The full operating guide is the Polymath prompt run_governed_research (resource polymath://adapter/guide).`,
  ].filter(Boolean).join("\n\n");
}

/** Why a start failed, in words: the HTTP status and the server's message (never swallowed, never a bare "failed"). */
export function startErrorWords(e: unknown): string {
  if (e instanceof ApiError) return `HTTP ${e.status}: ${serverMessage(e.body) || "the server sent no message"}`;
  if (e instanceof Error) return e.message || e.name;
  return String(e);
}

/** A FastAPI error body's `detail` in words: a string; `{message}` (the web boundary's refusals); a list of strings or of
 *  `{loc, msg}` (validation); `{rejected: [...]}` (the adapter contract). A body that is not JSON (a proxy's page) as text. */
function serverMessage(body: string): string {
  let detail: unknown;
  try {
    detail = (JSON.parse(body) as { detail?: unknown }).detail;
  } catch {
    return body.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 300);
  }
  const one = (x: unknown): string => {
    if (typeof x === "string") return x;
    const o = obj(x);
    if (!o) return x == null ? "" : JSON.stringify(x);
    if (typeof o.message === "string") return o.message;
    if (typeof o.msg === "string") return Array.isArray(o.loc) ? `${o.loc.join(".")}: ${o.msg}` : o.msg;
    if (Array.isArray(o.rejected)) return o.rejected.map(one).filter(Boolean).join("; ");
    return JSON.stringify(o);
  };
  const words = Array.isArray(detail) ? detail.map(one).filter(Boolean).join("; ") : one(detail);
  return (words || body).trim().slice(0, 600);
}
