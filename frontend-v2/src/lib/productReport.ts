/** PRODUCT-DECISION-REPORT-V1 B6 — the decision report from the web. A product answer's hypotheses start one
 *  (POST /product/report/start); the panel follows it while the person's own Agent Reach feeds it (the round's fetch script,
 *  upload counts per source), compiles it and opens the HTML page the server renders under its own no-script CSP. The
 *  Reports screen lists them. Pure except the client calls: every reply is read defensively (B4b's routes, contract
 *  product-report-v1: any field may be missing, and the plan's simpler names are read too) and the words for a status are
 *  mapped here, the backend's code stays in the tooltip.
 *
 *  The upload token (ADR-0023, docs/wiki/decisions/0023-report-upload-capability.md): this page keeps it in memory only,
 *  keyed by report id — never in localStorage or sessionStorage, and never on the chat turn, so it is gone after a reload. It
 *  comes from the start reply's `upload_token`, or from a status reply's `upload.url` when `upload.token` is "minted", and
 *  every status check sends it back as X-Upload-Token, so the server reuses it instead of minting another (a status call
 *  without a valid token mints one at most once a minute per report; until then it answers "required" with the placeholder
 *  UPLOAD_TOKEN in every URL).
 *
 *  After signing in: a report page opened without a session is sent to /v2/?next=<its path>; `returnToReport` takes the
 *  person back there once they are signed in (an exact report path only).
 *
 *  The client is `reportApi` below, on the raw verbs (`http`, as lib/auth.ts does), not inside `api`: the live contract test
 *  (src/__tests__/live-contract.test.ts) walks every `api` call against the RUNNING backend's /openapi.json, and these routes
 *  are not deployed there yet. Move the four calls into `api` once the backend that serves them is live. */
import { ApiError, http } from "./api";
import { startErrorWords, text, texts, httpUrl, type ProductView } from "./productResearch";

/** The report built from a product answer, kept on the chat turn so a reload finds its panel again. Its id only: the upload
 *  token stays in this page's memory (see `holdUploadToken`). */
export interface ProductReportRef { report_id: string; status?: string; started_at?: number }

export const AGENT_REACH_REPO = "https://github.com/Panniantong/Agent-Reach";
export const AGENT_REACH_CHECK = "agent-reach doctor --json";
/** The one sentence a web user needs next to the script: they have no terminal of their own in the app. */
export const RUN_SENTENCE =
  "Run this once in a terminal on your own computer (it needs Agent Reach); it uploads the results here by itself.";
/** The route's limits: at most 8 products, a 500-character title, 10 search terms, a 4,000-character message. */
export const MAX_PRODUCTS = 8;
const TITLE_MAX = 500;
const TERMS_MAX = 10;
const MESSAGE_MAX = 4000;
/** How often the panel checks a report that is still collecting or compiling. */
export const POLL_MS = 4000;
/** The upload address a status reply carries when the caller did not send the token back. */
const PLACEHOLDER = "UPLOAD_TOKEN";

export type Source = "reddit" | "amazon" | "alibaba" | "ebay";
export const SOURCES: readonly Source[] = ["reddit", "amazon", "alibaba", "ebay"];
export const SOURCE_NAMES: Record<Source, string> = { reddit: "Reddit", amazon: "Amazon", alibaba: "Alibaba", ebay: "eBay" };
/** The report section each source fills (for "compiling now leaves out …"). */
const SECTION_NAMES: Record<Source, string> = {
  reddit: "Reddit findings", amazon: "Amazon prices", alibaba: "Alibaba offers (MOQ, lead time)", ebay: "eBay prices",
};

type Obj = Record<string, unknown>;
const obj = (v: unknown): Obj | null => (v && typeof v === "object" && !Array.isArray(v) ? (v as Obj) : null);
/** A status code: a string only, lower case ("" for anything else). */
const statusCode = (v: unknown): string => (typeof v === "string" ? v.trim().toLowerCase() : "");
/** "HUMAN_CHECK" → "human check" */
const words = (code: string): string => code.replace(/[_.]/g, " ").trim().toLowerCase();

/* ── the start request ────────────────────────────────────────────────────────────────────────────────────────────── */

export interface ReportProduct { title: string; search_terms: string[] }
export interface ReportStartBody {
  message?: string; corpus_id?: string; corpus_ids?: string[];
  products: ReportProduct[]; ship_to: "US"; max_products: number;
}

/** The answer's hypotheses that have a title, as the route's products (title and search terms as written), at most 8. */
export function reportProducts(v: ProductView): ReportProduct[] {
  return v.hypotheses.filter((h) => h.title).slice(0, MAX_PRODUCTS)
    .map((h) => ({ title: h.title.slice(0, TITLE_MAX), search_terms: h.terms.slice(0, TERMS_MAX) }));
}

/** POST /product/report/start's body: the products, the turn's libraries (one → `corpus_id`, several → `corpus_ids`), the
 *  person's question as the message (else the answer's seed), shipping to the US, and room for every product sent. */
export function startBody(v: ProductView, question = ""): ReportStartBody {
  const products = reportProducts(v);
  const message = (question.trim() || v.seed).slice(0, MESSAGE_MAX);
  const [only, ...more] = v.corpusIds;
  return {
    ...(message ? { message } : {}),
    ...(only && !more.length ? { corpus_id: only } : only ? { corpus_ids: v.corpusIds } : {}),
    products, ship_to: "US", max_products: products.length,
  };
}

/* ── a reply, read once into what the panel draws ─────────────────────────────────────────────────────────────────── */

export interface CandidateView { key: string; title: string; terms: string[] }
export interface FetchView {
  round: number | null;
  /** the POSIX script the person runs once; shown and copied exactly as the server wrote it */
  script: string; sha256: string;
  /** the one-time upload capability: anyone with the address can add results until it expires */
  uploadUrl: string; expiresAt: string;
  packets: number; sources: Source[];
  /** why the plan's upload link is not usable here ("" = it is: the token was minted for this reply or reused). `expired`: the
   *  capability lapsed; `required`: this page holds no valid token and the server minted one less than a minute ago (a new one
   *  after `mintAfter`); `none`: no plan to run yet; `no-link`: the link carries the placeholder for a reason not given. */
  blocked: "" | "expired" | "required" | "none" | "no-link";
  /** when the server will mint a new upload token for a caller without one (with `required`) */
  mintAfter: string;
  /** the server's note on the upload address (e.g. it has no public web address, so the link works only on its host) */
  note: string;
}
export interface UploadCount { n: number; issues: string }
export interface ReportView {
  reportId: string;
  /** the backend's status code, lower case ("" when not given) */
  status: string;
  candidates: CandidateView[] | null;
  /** Polymath is still forming the products from a library (a report started without products) */
  forming: boolean;
  round: number | null;
  /** the current round's progress: packets planned and received */
  progress: { round: number; packets: number; received: number } | null;
  fetch: FetchView | null;
  /** uploads per source (with the ones the parser could not use, in words); null until the server has said */
  uploads: Record<Source, UploadCount> | null;
  /** CJ Dropshipping and eBay, which the server reads itself */
  host: { status: string; words: string; error: string } | null;
  /** the server said it has no eBay key (EBAY_NOT_CONFIGURED): eBay prices then come from the person's Agent Reach too */
  ebayNotConfigured: boolean;
  /** a compiled page exists (the last compile succeeded, even if a later one failed) */
  hasPage: boolean;
  compiledAt: string;
  /** uploads arrived after the last compile */
  stale: boolean;
  /** why a failed report failed, as the server words it */
  failure: string;
}

function count(v: unknown): number {
  if (typeof v === "number" && Number.isFinite(v) && v >= 0) return Math.floor(v);
  if (typeof v === "string" && /^\d{1,9}$/.test(v.trim())) return Number(v.trim());
  return 0;
}

function round(v: unknown): number | null {
  const n = count(v);
  return n > 0 ? n : null;
}

function sourceOf(v: unknown): Source | null {
  const s = text(v).toLowerCase();
  return (SOURCES as readonly string[]).includes(s) ? (s as Source) : null;
}

export function expired(iso: string, now = Date.now()): boolean {
  const t = Date.parse(iso);
  return Number.isFinite(t) && t <= now;
}

/** The round's plan (`fetch_plan`, or `fetch` as the plan words it) and the upload capability (top-level `upload`, or the
 *  plan's own) → the script section; null when there is no script to show nor any read planned. */
function fetchOf(planRaw: unknown, uploadRaw: unknown): FetchView | null {
  const f = obj(planRaw);
  if (!f) return null;
  const upload = obj(uploadRaw) ?? obj(f.upload);
  const url = text(upload?.url);
  const script = typeof f.script === "string" && f.script.trim() ? f.script : "";
  const packets = Array.isArray(f.packets) ? f.packets : [];
  const key = statusCode(upload?.token);                  // ADR-0023: minted | reused | required | expired | none
  const expiresAt = text(upload?.expires_at);
  const placeholder = url.includes(PLACEHOLDER) || script.includes(`/upload/${PLACEHOLDER}`);
  // the server's word first (this page's clock never overrules a minted or reused token); a reply without one (the plan's
  // wording) is read from the link and the expiry
  const blocked: FetchView["blocked"] = key === "minted" || key === "reused" ? (placeholder ? "no-link" : "")
    : key === "expired" || upload?.expired === true ? "expired"
    : key === "required" ? "required"
    : key === "none" ? "none"
    : key ? "no-link"
    : expired(expiresAt) ? "expired" : placeholder ? "no-link" : "";
  const view: FetchView = {
    round: round(f.round), script, sha256: text(f.script_sha256), uploadUrl: httpUrl(url) && !placeholder ? url : "",
    expiresAt, packets: packets.length,
    sources: [...new Set(packets.map((p) => sourceOf(obj(p)?.source)).filter((s): s is Source => s !== null))],
    blocked, mintAfter: text(upload?.mint_after), note: text(upload?.note),
  };
  return view.script || view.packets ? view : null;
}

/** `candidates` as a list (the plan's words) or as {status, items, error} (B4b). */
function candidatesOf(v: unknown): { items: CandidateView[] | null; status: string; error: string } {
  const o = obj(v);
  const list = Array.isArray(v) ? v : Array.isArray(o?.items) ? (o!.items as unknown[]) : null;
  const items = list === null ? null : list.map((c, i): CandidateView => {
    const x = obj(c);
    return { key: `${i}:${text(x?.candidate_id)}`, title: x ? text(x.title) || text(x.candidate_id) : text(c), terms: texts(x?.search_terms) };
  }).filter((c) => c.title);
  return { items, status: statusCode(o?.status), error: errorText(o?.error) };
}

const ISSUE_WORDS: Record<string, string> = {
  BLOCKED: "blocked", HUMAN_CHECK: "stopped at a human check", EMPTY: "empty", UNRECOGNISED: "unreadable", NONE: "not read",
};

/** Uploads per source: flat counts ({reddit: 3, …}, the plan's words) or B4b's {total, by_round, by_source: {source:
 *  {status: n}}}, where every status but OK is named ("1 blocked"). */
function uploadsOf(v: unknown): Record<Source, UploadCount> | null {
  const u = obj(v);
  if (!u) return null;
  const bySource = obj(u.by_source);
  return Object.fromEntries(SOURCES.map((s): [Source, UploadCount] => {
    if (!bySource) return [s, { n: count(u[s]), issues: "" }];
    const st = Object.entries(obj(bySource[s]) ?? {}).map(([k, x]) => [k.toUpperCase(), count(x)] as const).filter(([, x]) => x > 0);
    return [s, { n: st.reduce((a, [, x]) => a + x, 0),
                 issues: st.filter(([k]) => k !== "OK").map(([k, x]) => `${x.toLocaleString()} ${ISSUE_WORDS[k] ?? words(k)}`).join(", ") }];
  })) as Record<Source, UploadCount>;
}

/** The current round's entry of B4b's `rounds` ([{round, packets, received, complete}]). */
function progressOf(v: unknown, current: number | null): ReportView["progress"] {
  if (!Array.isArray(v)) return null;
  const all = v.map(obj).filter((r): r is Obj => r !== null)
    .map((r) => ({ round: round(r.round) ?? 0, packets: count(r.packets), received: count(r.received) }));
  const cur = all.find((r) => r.round === current) ?? all[all.length - 1];
  return cur && cur.round && cur.packets ? { ...cur, received: Math.min(cur.received, cur.packets) } : null;
}

const HOST_WORDS: Record<string, string> = { pending: "waiting to start", collecting: "collecting", done: "ready", failed: "failed" };

function hostOf(h: Obj | null): ReportView["host"] {
  const st = statusCode(h?.status);
  if (!h || !st) return null;
  return { status: st, words: HOST_WORDS[st] ?? words(st), error: errorText(h.error) };
}

/** Every status / reason code in the host's eBay block: a code, `{status, reason_code}`, or one of those per candidate. */
function codes(v: unknown): string[] {
  if (typeof v === "string") return [v.trim().toUpperCase()];
  const o = obj(v);
  if (!o) return [];
  const own = [o.status, o.reason_code];
  const each = Object.values(o).map(obj).filter((x): x is Obj => x !== null).flatMap((x) => [x.status, x.reason_code]);
  return [...own, ...each].map((c) => text(c).toUpperCase()).filter(Boolean);
}

/** An error as text: a string, or {message, error_code} → "message (CODE)". */
function errorText(v: unknown): string {
  const e = obj(v);
  if (!e) return text(v);
  const message = text(e.message);
  const code = text(e.error_code);
  return message && code ? `${message} (${code})` : message || code;
}

function failureOf(r: Obj): string {
  return errorText(r.error) || errorText(obj(r.compiled)?.error) || errorText(obj(r.candidates)?.error) || text(r.message)
    || text(r.reason) || errorText(r.detail);
}

/** A start, status or compile reply → what the panel draws. A field the reply leaves out (or sends as null) keeps what an
 *  earlier reply said: a check need not repeat everything. A compile reply with a link and no status is compiled. */
export function reportView(raw: unknown, prev: ReportView | null = null, reportId = ""): ReportView | null {
  const r = obj(raw);
  if (!r) return prev;
  const status = statusCode(r.status) || (text(r.url) || text(r.report_url) ? "compiled" : "") || prev?.status || "";
  const fetch = fetchOf(r.fetch_plan ?? r.fetch, r.upload) ?? prev?.fetch ?? null;
  const cands = candidatesOf(r.candidates);
  const host = obj(r.host);
  const compiled = obj(r.compiled);
  const current = round(r.round) ?? fetch?.round ?? prev?.round ?? null;
  const known = "compiled" in r;                          // B4b says null before the first compile
  return {
    reportId: text(r.report_id) || prev?.reportId || reportId,
    status,
    candidates: cands.items ?? prev?.candidates ?? null,
    forming: cands.status ? cands.status === "collecting" && !cands.items?.length : prev?.forming ?? false,
    round: current,
    progress: progressOf(r.rounds, current) ?? prev?.progress ?? null,
    fetch,
    uploads: uploadsOf(r.uploads) ?? prev?.uploads ?? null,
    host: hostOf(host) ?? prev?.host ?? null,
    ebayNotConfigured: host && "ebay" in host ? codes(host.ebay).includes("EBAY_NOT_CONFIGURED") : prev?.ebayNotConfigured ?? false,
    hasPage: status === "compiled" || (known ? Boolean(text(compiled?.at)) || r.compiled === true : prev?.hasPage ?? false),
    compiledAt: text(compiled?.at) || text(r.compiled_at) || prev?.compiledAt || "",
    stale: known ? compiled?.stale === true : prev?.stale ?? false,
    failure: status === "failed" ? failureOf(r) || prev?.failure || "" : "",
  };
}

/* ── status, uploads and what a compile now would leave out ───────────────────────────────────────────────────────── */

export type ReportTone = "ready" | "working" | "blocked" | "unknown";

const STATUS: Record<string, { tone: ReportTone; words: string }> = {
  collecting: { tone: "working", words: "Collecting data" },
  compiling: { tone: "working", words: "Compiling" },
  compiled: { tone: "ready", words: "Compiled" },
  failed: { tone: "blocked", words: "Failed" },
};

export function reportStatus(code: string): { tone: ReportTone; words: string } {
  const known = STATUS[code.toLowerCase()];
  if (known) return known;
  if (!code) return { tone: "unknown", words: "Status not given" };
  const w = words(code);
  return { tone: "unknown", words: w.charAt(0).toUpperCase() + w.slice(1) };
}

/** The panel checks again every few seconds only while the report is collecting (or compiling); never once it is compiled,
 *  failed, or in a state it does not know. */
export function isLive(status: string): boolean {
  return status === "collecting" || status === "compiling";
}

export function totalUploads(v: ReportView): number {
  return v.uploads ? SOURCES.reduce((n, s) => n + v.uploads![s].n, 0) : 0;
}

/** The sections only the person's Agent Reach can fill that have nothing uploaded yet: Reddit, Amazon and Alibaba always;
 *  eBay when the round plans an eBay read or the server has no eBay key (otherwise the server reads eBay itself). Nothing
 *  until the server has said what arrived. */
export function missingSections(v: ReportView): string[] {
  if (!v.uploads) return [];
  const local = SOURCES.filter((s) => s !== "ebay" || v.ebayNotConfigured || (v.fetch?.sources ?? []).includes("ebay"));
  return local.filter((s) => !(v.uploads![s].n > 0)).map((s) => SECTION_NAMES[s]);
}

/** "a", "a and b", "a, b and c" */
export function listWords(xs: string[]): string {
  return xs.length <= 2 ? xs.join(" and ") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;
}

/** What a compile now leaves out, in one sentence ("" when nothing is missing or the uploads are not known yet). */
export function missingNote(v: ReportView): string {
  const missing = missingSections(v);
  if (!missing.length) return "";
  const list = listWords(missing);
  return totalUploads(v) === 0
    ? `Nothing has been uploaded yet: compiling now leaves out the ${list} (each marked “needs a local agent”).`
    : `Nothing has been uploaded yet for the ${list}: compiling now leaves ${missing.length === 1 ? "it" : "them"} out (marked “needs a local agent”).`;
}

/** An ISO time as the reader's date and time; text that is not a time as written. */
export function when(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/* ── the Reports screen ───────────────────────────────────────────────────────────────────────────────────────────── */

export interface ReportRow {
  key: string; reportId: string; title: string; createdAt: string; status: string;
  /** the products in words, when the title is not already made of them */
  products: string;
  uploads: number | null;
  /** a compiled page exists */
  hasPage: boolean;
}

function titlesOf(v: unknown): string[] {
  return Array.isArray(v) ? v.map((p) => (obj(p) ? text(obj(p)!.title) : text(p))).filter(Boolean) : [];
}

const plural = (n: number, one: string) => `${n.toLocaleString()} ${one}${n === 1 ? "" : "s"}`;

/** GET /product/reports → the rows, newest first (a row without a readable date goes after the dated ones, in the server's
 *  order); a row without a report id is dropped (nothing to open). The products are `products` (titles or a count) or B4b's
 *  `candidates`; a report without a title is named by its products. */
export function reportRows(raw: unknown): ReportRow[] {
  const list = obj(raw)?.reports;
  const rows = (Array.isArray(list) ? list : []).map(obj).filter((r): r is Obj => r !== null).map((r, i) => {
    const titles = titlesOf(r.products).length ? titlesOf(r.products) : titlesOf(r.candidates);
    const n = typeof r.products === "number" && Number.isFinite(r.products) ? r.products : titles.length;
    const own = text(r.title);
    const createdAt = text(r.created_at);
    const status = statusCode(r.status);
    const t = Date.parse(createdAt);
    return {
      row: {
        key: `${i}:${text(r.report_id)}`, reportId: text(r.report_id), title: own || titles.join(" · "), createdAt, status,
        products: own && titles.length ? titles.join(" · ") : n ? plural(n, "product") : "",
        uploads: typeof r.uploads === "number" && Number.isFinite(r.uploads) ? r.uploads : null,
        hasPage: status === "compiled" || r.compiled === true,
      },
      at: Number.isFinite(t) ? t : -Infinity, i,
    };
  }).filter((x) => x.row.reportId);
  return rows.sort((a, b) => (b.at - a.at) || (a.i - b.i)).map((x) => x.row);
}

/* ── the upload token: in this page's memory only (ADR-0023) ──────────────────────────────────────────────────────── */

/** report id → the upload token this page holds for it. Module memory, nothing else: never localStorage or sessionStorage,
 *  never the chat turn, so a reload (or closing the tab) forgets it. Shared by every panel of the page (the chat's and the
 *  Reports screen's), so moving between screens does not make the server mint another. */
const held = new Map<string, string>();
const HELD_MAX = 256;
/** an upload token as the server mints it (secrets.token_urlsafe: 43 characters); the placeholder is never one */
const TOKEN_RE = /^[A-Za-z0-9_-]{20,128}$/;

export function heldUploadToken(reportId: string): string {
  return held.get(reportId) ?? "";
}

export function holdUploadToken(reportId: string, token: string): void {
  if (!reportId || token === PLACEHOLDER || !TOKEN_RE.test(token)) return;
  held.delete(reportId);                                   // the newest last: the oldest is dropped past the cap
  held.set(reportId, token);
  while (held.size > HELD_MAX) {
    const oldest = held.keys().next().value;
    if (oldest === undefined) break;
    held.delete(oldest);
  }
}

export function forgetUploadToken(reportId: string): void {
  held.delete(reportId);
}

/** Forget every token (tests; nothing else needs it: a reload already does). */
export function forgetUploadTokens(): void {
  held.clear();
}

/** The token an upload URL of this report carries ("" for the placeholder, another report's URL, or anything else). */
export function tokenFromUploadUrl(url: string, reportId: string): string {
  let path: string;
  try {
    path = new URL(url, "http://localhost").pathname;
  } catch {
    return "";
  }
  const m = /\/product\/report\/([^/]+)\/upload\/([^/]+)$/.exec(path);
  if (!m || m[1] !== encodeURIComponent(reportId)) return "";
  const token = m[2] ?? "";
  return token !== PLACEHOLDER && TOKEN_RE.test(token) ? token : "";
}

/** Take the upload token a start or status reply gives this page (ADR-0023): the start's `upload_token`, or the token in
 *  `upload.url` when `upload.token` is "minted". A reply that says the capability expired, or that this page's token was
 *  not accepted ("required": a wrong or unknown token counts as none), drops the one held. */
export function takeUploadToken(reportId: string, raw: unknown): void {
  const r = obj(raw);
  if (!r || !reportId) return;
  const upload = obj(r.upload);
  const key = statusCode(upload?.token);
  const fresh = (typeof r.upload_token === "string" ? r.upload_token : "")
    || (key === "minted" ? tokenFromUploadUrl(text(upload?.url), reportId) : "");
  if (fresh) holdUploadToken(reportId, fresh);
  else if (key === "expired" || key === "required" || upload?.expired === true) forgetUploadToken(reportId);
}

/* ── the client ───────────────────────────────────────────────────────────────────────────────────────────────────── */

const reportPath = (id: string) => `/product/report/${encodeURIComponent(id)}`;

/** The report itself: HTML the server renders under its own CSP — a plain link opened in a new tab, never fetched in here. */
export function reportHref(id: string): string {
  return reportPath(id);
}

export const reportApi = {
  start: (body: ReportStartBody, s?: AbortSignal) => http.post<unknown>("/product/report/start", body, s),
  /** sends the token this page holds (X-Upload-Token): the server reuses it instead of minting another */
  status: (reportId: string, uploadToken = "", s?: AbortSignal) =>
    http.get<unknown>(`${reportPath(reportId)}/status`, s, uploadToken ? { "x-upload-token": uploadToken } : {}),
  compile: (reportId: string, body: { verdicts?: Record<string, string> } = {}, s?: AbortSignal) =>
    http.post<unknown>(`${reportPath(reportId)}/compile`, body, s),
  list: (s?: AbortSignal) => http.get<unknown>("/product/reports", s),
};

/** Why a call failed, in words: the HTTP status and the server's message (never swallowed, never a bare "failed"). */
export const errorWords = startErrorWords;

/** Why a start failed, in words. The start route's 429 REPORT_JOB_RUNNING (this person already has a report's background job
 *  running; its message says when to start the next) also names the report still running, when the server gives it. */
export function startRefusalWords(e: unknown): string {
  const said = errorWords(e);
  if (!(e instanceof ApiError) || e.code !== "REPORT_JOB_RUNNING") return said;
  let body: Obj | null = null;
  try {
    body = obj(JSON.parse(e.body));
  } catch {
    return said;
  }
  const running = text(obj(body?.detail)?.report_id) || text(body?.report_id);
  return running ? `${/[.!?]$/.test(said) ? said : `${said}.`} Running report: ${running}.` : said;
}

/* ── back to the report page after signing in ─────────────────────────────────────────────────────────────────────── */

/** The only page a sign-in may send a person on to: a report page of this site, exactly — no other path, no scheme, no
 *  host, no `//`, no query. */
const REPORT_PAGE_RE = /^\/product\/report\/rpt_[0-9a-f]{24}$/;

/** `next` of an address's query when it names a report page exactly (one `next` only), else null. */
export function reportReturnPath(search: string): string | null {
  const values = new URLSearchParams(search).getAll("next");
  const next = values.length === 1 ? values[0] ?? "" : "";
  return REPORT_PAGE_RE.test(next) ? next : null;
}

/** How this page is left for another one: a full page load. Tests replace `assign`. */
export const pageNavigation = {
  assign: (url: string): void => { window.location.assign(url); },
};

/** A report page opened without a session is answered by the web boundary with 302 to /v2/?next=<its path>
 *  (orchestrator/web_boundary.py; the page is the report's own, ADR-0023). Once the person is signed in — already, or after
 *  signing in — call this: when `next` names a report page exactly it drops `next` from this page's address (so Back does not
 *  send them on again) and goes there with a full page load. Any other `next` is ignored. Returns whether it left. */
export function returnToReport(): boolean {
  const next = reportReturnPath(window.location.search);
  if (!next) return false;
  const params = new URLSearchParams(window.location.search);
  params.delete("next");
  const rest = params.toString();
  window.history.replaceState(window.history.state, "", `${window.location.pathname}${rest ? `?${rest}` : ""}${window.location.hash}`);
  pageNavigation.assign(next);
  return true;
}

/** A refusal that asking again will not change (the report is gone or not this person's, the session ended): the panel
 *  stops checking and offers "Check again" instead. A timeout, a rate limit, a server error or a dropped connection keeps
 *  the checks going. */
export function permanent(e: unknown): boolean {
  return e instanceof ApiError && e.status >= 400 && e.status < 500 && ![408, 425, 429].includes(e.status);
}
