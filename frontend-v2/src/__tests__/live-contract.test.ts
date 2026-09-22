/**
 * FRONTEND-BACKEND-CONTRACT-V1 — the frontend's contract with the backend, checked LIVE against a running orchestrator
 * through the REAL client code (lib/api.ts, lib/chat.ts). The contract is read from the UI's own sources with the
 * TypeScript compiler — the calls in api.ts, the request Chat.tsx builds, the response types in contracts.ts — so this
 * test cannot drift from what the UI actually does. Skips entirely when no backend answers (offline builds never block).
 *
 * FREE tier (read-only; runs whenever a backend is up — POLYMATH_BASE_URL, default http://127.0.0.1:7200):
 *   1. every client call (26 in `api` + the /chat/stream reader) is a real backend route with that HTTP method;
 *   2. every body field and query parameter the frontend SENDS is declared by the backend (an undeclared one is silently dropped);
 *   3. every read-only endpoint answers through the real client, and its live JSON conforms to the TypeScript type the UI
 *      compiles against (required fields present, primitives / literals / nested shapes right);
 *   4. /compare runs all five public modes (retrieval only — no model call) and each arm runs its own mode;
 *   5. /retrieve with mode GNN reaches the GNN route (it used to fall through to the legacy lanes).
 * PAID tier (POLYMATH_LIVE_CHAT=1 — one synthesizer call per mode + one review + one model test):
 *   the Chat screen's exact request through runTurn for each of the five modes: steps stream, the answer arrives, the receipt
 *   conforms to RetrievalReceipt, retrieval ran (require_retrieval — the question is phrased like small talk on purpose), the
 *   executed mode is the requested one, GNN_ROUTE fires only for GNN, and the Evidence panel's rows resolve.
 * Never exercised live (they mutate): upload, delete corpus / document, enrich, save / delete provider — tiers 1–2 only.
 */
import * as ts from "typescript";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import apiSrc from "../lib/api.ts?raw";
import chatSrc from "../screens/Chat.tsx?raw";
import contractsSrc from "../lib/contracts.ts?raw";
import { api } from "../lib/api";
import { newTurn, runTurn, type Turn } from "../lib/chat";
import { chunkIdOf } from "../lib/chunkid";
import { PUBLIC_MODES, type RetrievalReceipt } from "../lib/contracts";

type Env = Record<string, string | undefined>;
const ENV: Env = {
  ...((globalThis as { process?: { env?: Env } }).process?.env ?? {}),
  ...((import.meta as { env?: Env }).env ?? {}),
};
const BASE = ENV.POLYMATH_BASE_URL ?? "http://127.0.0.1:7200";
const CORPUS = ENV.POLYMATH_CONTRACT_CORPUS ?? "cinema";
const LIVE_CHAT = ENV.POLYMATH_LIVE_CHAT === "1";
/** Phrased like small talk ON PURPOSE: the compiler once read it as conversation and skipped retrieval. */
const QUESTION = "How does a lone landscape photographer keep spare batteries reachable on the trail?";

/* ── the live OpenAPI document ─────────────────────────────────────────────── */

interface OpenApiOp {
  parameters?: { name: string; in: string }[];
  requestBody?: { content?: Record<string, { schema?: { $ref?: string } }> };
}
interface OpenApi {
  paths: Record<string, Record<string, OpenApiOp>>;
  components?: { schemas?: Record<string, { properties?: Record<string, unknown> }> };
}

async function openapi(): Promise<OpenApi | null> {
  try {
    const r = await fetch(`${BASE}/openapi.json`, { signal: AbortSignal.timeout(5000) });
    return r.ok ? ((await r.json()) as OpenApi) : null;
  } catch {
    return null;
  }
}
const DOC = await openapi();
const norm = (p: string) => p.replace(/\{[^}]+\}/g, "{}");

function operation(method: string, path: string): OpenApiOp | undefined {
  const key = Object.keys(DOC?.paths ?? {}).find((p) => norm(p) === path);
  return key ? DOC?.paths[key]?.[method.toLowerCase()] : undefined;
}

function bodyProps(op: OpenApiOp): string[] {
  const first = Object.values(op.requestBody?.content ?? {})[0];
  const name = first?.schema?.$ref?.split("/").pop();
  return name ? Object.keys(DOC?.components?.schemas?.[name]?.properties ?? {}) : [];
}

/* ── the frontend's side, read from its own sources ────────────────────────── */

const src = (name: string, text: string) => ts.createSourceFile(name, text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TSX);
const API_AST = src("api.ts", apiSrc);
const INTERFACES = new Map<string, ts.InterfaceDeclaration>();
src("contracts.ts", contractsSrc).forEachChild((n) => {
  if (ts.isInterfaceDeclaration(n)) INTERFACES.set(n.name.text, n);
});

const propName = (n: ts.PropertyName | undefined): string =>
  n && (ts.isIdentifier(n) || ts.isStringLiteral(n)) ? n.text : "";

function memberNames(node: ts.TypeNode | undefined): string[] {
  if (!node) return [];
  if (ts.isTypeLiteralNode(node)) return node.members.map((m) => propName(m.name)).filter(Boolean);
  if (ts.isTypeReferenceNode(node) && ts.isIdentifier(node.typeName)) {
    const decl = INTERFACES.get(node.typeName.text);
    return decl ? decl.members.map((m) => propName(m.name)).filter(Boolean) : [];
  }
  return [];
}

interface ClientCall {
  name: string;
  method: "GET" | "POST" | "DELETE";
  path: string;
  query: string[];
  sends: string[];
  response?: ts.TypeNode;
}

function findCall(node: ts.Node): ts.CallExpression | undefined {
  let found: ts.CallExpression | undefined;
  const visit = (n: ts.Node): void => {
    if (found) return;
    if (ts.isCallExpression(n) && ts.isIdentifier(n.expression) && ["get", "post", "postForm", "del"].includes(n.expression.text)) {
      found = n;
      return;
    }
    n.forEachChild(visit);
  };
  visit(node);
  return found;
}

function formFields(node: ts.Node): string[] {
  const out: string[] = [];
  const visit = (n: ts.Node): void => {
    if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression) && n.expression.name.text === "append") {
      const a = n.arguments[0];
      if (a && ts.isStringLiteral(a)) out.push(a.text);
    }
    n.forEachChild(visit);
  };
  visit(node);
  return out;
}

function route(arg: ts.Expression | undefined): { path: string; query: string[] } | null {
  let raw: string | null = null;
  if (!arg) return null;
  if (ts.isStringLiteral(arg) || ts.isNoSubstitutionTemplateLiteral(arg)) raw = arg.text;
  else if (ts.isTemplateExpression(arg)) raw = arg.head.text + arg.templateSpans.map((s) => "{}" + s.literal.text).join("");
  if (raw === null) return null;
  const [path = raw, qs = ""] = raw.split("?");
  const query = qs.split("&").map((kv) => kv.split("=")[0] ?? "").filter(Boolean);
  return { path, query };
}

function clientCalls(): ClientCall[] {
  const calls: ClientCall[] = [];
  API_AST.forEachChild((stmt) => {
    if (!ts.isVariableStatement(stmt)) return;
    for (const d of stmt.declarationList.declarations) {
      if (!ts.isIdentifier(d.name) || d.name.text !== "api" || !d.initializer || !ts.isObjectLiteralExpression(d.initializer)) continue;
      for (const p of d.initializer.properties) {
        if (!ts.isPropertyAssignment(p) || !ts.isArrowFunction(p.initializer)) continue;
        const fn = p.initializer;
        const call = findCall(fn.body);
        const r = route(call?.arguments[0]);
        if (!call || !r || !ts.isIdentifier(call.expression)) continue;
        const helper = call.expression.text;
        const method = helper === "get" ? "GET" : helper === "del" ? "DELETE" : "POST";
        let sends: string[] = [];
        const second = call.arguments[1];
        if (helper === "postForm") sends = formFields(fn.body);
        else if (second && ts.isIdentifier(second)) {
          const param = fn.parameters.find((x) => ts.isIdentifier(x.name) && x.name.text === second.text);
          sends = memberNames(param?.type);
        } else if (second && ts.isObjectLiteralExpression(second)) sends = second.properties.map((x) => propName(x.name)).filter(Boolean);
        calls.push({ name: propName(p.name), method, path: r.path, query: r.query, sends, response: call.typeArguments?.[0] });
      }
    }
  });
  calls.push({ name: "chatStream", method: "POST", path: "/chat/stream", query: [], sends: chatBodyKeys() });
  return calls;
}

/** The fields Chat.tsx's send() puts in the /chat/stream body: the object literal + every `body.x = …` assignment. */
function chatBodyKeys(): string[] {
  const keys = new Set<string>();
  const visit = (n: ts.Node): void => {
    if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === "body" && n.initializer && ts.isObjectLiteralExpression(n.initializer)) {
      n.initializer.properties.forEach((x) => keys.add(propName(x.name)));
    }
    if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.EqualsToken && ts.isPropertyAccessExpression(n.left)
        && ts.isIdentifier(n.left.expression) && n.left.expression.text === "body") keys.add(n.left.name.text);
    n.forEachChild(visit);
  };
  visit(src("Chat.tsx", chatSrc));
  keys.delete("");
  return [...keys];
}

/* ── a runtime check of a live value against a TypeScript type node ───────── */

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const show = (v: unknown) => (v === undefined ? "undefined" : JSON.stringify(v)?.slice(0, 60));

function check(v: unknown, node: ts.TypeNode, path: string, errs: string[], depth = 0): void {
  if (depth > 10) return;
  if (ts.isParenthesizedTypeNode(node)) return check(v, node.type, path, errs, depth);
  const want = (ok: boolean, what: string) => { if (!ok) errs.push(`${path}: expected ${what}, got ${show(v)}`); };
  switch (node.kind) {
    case ts.SyntaxKind.StringKeyword: return want(typeof v === "string", "string");
    case ts.SyntaxKind.NumberKeyword: return want(typeof v === "number", "number");
    case ts.SyntaxKind.BooleanKeyword: return want(typeof v === "boolean", "boolean");
    case ts.SyntaxKind.UnknownKeyword:
    case ts.SyntaxKind.AnyKeyword: return;
  }
  if (ts.isLiteralTypeNode(node)) {
    if (node.literal.kind === ts.SyntaxKind.NullKeyword) return want(v === null, "null");
    if (ts.isStringLiteral(node.literal)) return want(v === node.literal.text, JSON.stringify(node.literal.text));
    return;
  }
  if (ts.isUnionTypeNode(node)) {
    const ok = node.types.some((t) => { const e: string[] = []; check(v, t, path, e, depth + 1); return e.length === 0; });
    return want(ok, node.getText());
  }
  if (ts.isArrayTypeNode(node)) {
    if (!Array.isArray(v)) return want(false, "array");
    v.slice(0, 5).forEach((x, i) => check(x, node.elementType, `${path}[${i}]`, errs, depth + 1));
    return;
  }
  if (ts.isTypeLiteralNode(node)) return members(v, node.members, path, errs, depth);
  if (ts.isTypeReferenceNode(node) && ts.isIdentifier(node.typeName)) {
    const name = node.typeName.text;
    const args = node.typeArguments ?? [];
    if (name === "Record") {
      if (!isObj(v)) return want(false, "object");
      const valueType = args[1];
      if (valueType) Object.entries(v).slice(0, 8).forEach(([k, x]) => check(x, valueType, `${path}.${k}`, errs, depth + 1));
      return;
    }
    if (name === "Array") {
      const el = args[0];
      if (!Array.isArray(v)) return want(false, "array");
      if (el) v.slice(0, 5).forEach((x, i) => check(x, el, `${path}[${i}]`, errs, depth + 1));
      return;
    }
    const decl = INTERFACES.get(name);
    if (decl) members(v, decl.members, path, errs, depth);
  }
}

function members(v: unknown, list: ts.NodeArray<ts.TypeElement>, path: string, errs: string[], depth: number): void {
  if (!isObj(v)) { errs.push(`${path}: expected object, got ${show(v)}`); return; }
  for (const m of list) {
    if (!ts.isPropertySignature(m) || !m.type) continue;
    const key = propName(m.name);
    const val = v[key];
    if (val === undefined) {
      if (!m.questionToken) errs.push(`${path}.${key}: required by the UI's type, missing from the live response`);
      continue;
    }
    if (val === null && m.questionToken) continue;           // JSON null on an optional field = absent
    check(val, m.type, `${path}.${key}`, errs, depth + 1);
  }
}

function conforms(v: unknown, type: ts.TypeNode | string | undefined, label: string): string[] {
  const errs: string[] = [];
  if (typeof type === "string") {
    const decl = INTERFACES.get(type);
    if (decl) members(v, decl.members, label, errs, 0);
  } else if (type) check(v, type, label, errs);
  return errs;
}

/* ── the real client, pointed at the live backend ──────────────────────────── */

const realFetch = globalThis.fetch;
let lastJson: unknown = undefined;
const CALLS = clientCalls();
const call = (name: string): ClientCall => {
  const c = CALLS.find((x) => x.name === name);
  if (!c) throw new Error(`api.${name} not found in lib/api.ts`);
  return c;
};

beforeAll(() => {
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" && input.startsWith("/") ? `${BASE}${input}` : input;
    const res = await realFetch(url, init);
    if ((res.headers.get("content-type") ?? "").includes("application/json")) {
      lastJson = await res.clone().json().catch(() => undefined);
    }
    return res;
  });
});
afterAll(() => vi.unstubAllGlobals());

/** Call the real client, then check the raw JSON it received against the response type written at that call site. */
async function viaClient<T>(name: string, run: () => Promise<T>): Promise<T> {
  lastJson = undefined;
  const out = await run();
  expect(conforms(lastJson, call(name).response, `api.${name}`)).toEqual([]);
  return out;
}

/* ── FREE tier ─────────────────────────────────────────────────────────────── */

describe.skipIf(!DOC)(`frontend ↔ backend contract, live at ${BASE}`, () => {
  it("every client call is a real backend route with that method", () => {
    expect(CALLS.length).toBeGreaterThanOrEqual(27);
    const missing = CALLS.filter((c) => !operation(c.method, c.path)).map((c) => `${c.name}: ${c.method} ${c.path}`);
    expect(missing, "client calls with no backend route").toEqual([]);
  });

  it("every body field and query parameter the frontend sends is declared by the backend", () => {
    const undeclared: string[] = [];
    for (const c of CALLS) {
      const op = operation(c.method, c.path);
      if (!op) continue;
      const params = new Set((op.parameters ?? []).filter((p) => p.in === "query").map((p) => p.name));
      c.query.filter((q) => !params.has(q)).forEach((q) => undeclared.push(`${c.name}: ?${q}`));
      const props = new Set(bodyProps(op));
      c.sends.filter((f) => !props.has(f)).forEach((f) => undeclared.push(`${c.name}: body.${f}`));
    }
    expect(call("chatStream").sends).toEqual(expect.arrayContaining(["message", "corpus_id", "mode", "require_retrieval"]));
    expect(undeclared, "sent by the UI but silently dropped by the backend").toEqual([]);
  });

  it("read-only endpoints answer through the real client and match the UI's types", async () => {
    const corpora = await viaClient("corpora", () => api.corpora());
    expect(corpora.map((c) => c.corpus_id)).toContain(CORPUS);
    await viaClient("semanticReadiness", () => api.semanticReadiness(CORPUS));
    await viaClient("documentSummaries", () => api.documentSummaries(CORPUS));
    await viaClient("documents", () => api.documents(CORPUS));
    const cp = await viaClient("controlPlane", () => api.controlPlane(CORPUS));
    const pool = Object.keys(cp.pools)[0];
    if (pool) await viaClient("poolLanes", () => api.poolLanes(pool));
    const synths = await viaClient("synthesizers", () => api.synthesizers());
    expect(synths.filter((s) => s.default), "exactly one default model (the picker names it)").toHaveLength(1);
    await viaClient("reasoningModes", () => api.reasoningModes());
    const ready = await viaClient("ready", () => api.ready());
    expect(ready.ready).toBe(true);
    await viaClient("pipelineHealth", () => api.pipelineHealth());
    await viaClient("predicates", () => api.predicates(CORPUS, 5));
    await viaClient("capabilities", () => api.capabilities());
    const ents = await viaClient("graphEntities", () => api.graphEntities(CORPUS, "camera", 5));
    const first = ents.entities[0];
    if (first) {
      const rels = await viaClient("graphRelationships", () => api.graphRelationships(first.entity_id, CORPUS, 5));
      expect(rels.relationships.filter((r) => r.source_count < 1), "every shown relationship is source-attested").toEqual([]);
    }
    const providers = await viaClient("llmProviders", () => api.llmProviders());
    const leaked = providers.filter((p) => p.api_key.length > 12 && !p.api_key.startsWith("env:")).map((p) => p.provider_id);
    expect(leaked, "provider keys come back masked, never raw").toEqual([]);
  }, 60_000);

  it("/compare runs all five public modes, each arm its own (retrieval only, no model call)", async () => {
    const res = await viaClient("compare", () => api.compare({ message: QUESTION, corpus_id: CORPUS, modes: [...PUBLIC_MODES] }));
    expect(res.arms.map((a) => a.mode)).toEqual([...PUBLIC_MODES]);
    for (const a of res.arms) {
      expect(a.ok, `${a.mode}: ${a.error ?? ""}`).toBe(true);
      expect(a.retrieval?.evidence_count ?? 0, `${a.mode} evidence`).toBeGreaterThan(0);
      const gnn = a.retrieval?.lane_sizes?.gnn_route ?? 0;
      if (a.mode === "GNN") expect(gnn, "GNN arm is the GNN route").toBeGreaterThan(0);
      else expect(gnn, `${a.mode} never runs the GNN lane`).toBe(0);
    }
  }, 240_000);

  it("/retrieve with mode GNN reaches the GNN route (never the legacy lanes)", async () => {
    const res = await viaClient("retrieve", () => api.retrieve({ query: QUESTION, corpus_id: CORPUS, mode: "GNN" }));
    expect(res.meta.mode).toBe("GNN");
    expect(res.evidence.length).toBeGreaterThan(0);
  }, 120_000);
});

/* ── PAID tier ─────────────────────────────────────────────────────────────── */

const executedAs = (mode: string) => (mode === "FAST" ? "VECTOR" : mode);
let reviewTurn: Turn | null = null;

describe.skipIf(!DOC || !LIVE_CHAT)("live chat — the Chat screen's exact request, all five modes (spends)", () => {
  it.each([...PUBLIC_MODES])("%s streams steps and an answer, retrieves, and executes the requested mode", async (mode) => {
    const body: Record<string, unknown> = { message: QUESTION, corpus_id: CORPUS, mode, require_retrieval: true };
    expect(Object.keys(body).sort(), "the same fields Chat.tsx sends by default").toEqual(
      chatBodyKeys().filter((k) => ["message", "corpus_id", "mode", "require_retrieval"].includes(k)).sort());
    const turn = newTurn(QUESTION, mode);
    await runTurn(body, (patch) => Object.assign(turn, patch));

    expect(turn.error).toBeNull();
    expect(turn.done).toBe(true);
    expect(turn.phases.length, "the process rail's steps").toBeGreaterThanOrEqual(5);
    expect(turn.phases.every((p) => typeof p.stage === "string" && typeof p.label === "string")).toBe(true);
    expect(turn.answerText.length, "an answer arrived").toBeGreaterThan(40);
    expect(turn.model, "the answer names its model").toBeTruthy();

    const r = turn.receipt as RetrievalReceipt;
    expect(conforms(r, "RetrievalReceipt", `receipt[${mode}]`)).toEqual([]);
    expect(r.mode).toBe(executedAs(mode));
    expect(r.evidence_count ?? 0, "require_retrieval: small talk still searches the corpus").toBeGreaterThan(0);
    expect(r.chat_plan?.intent, "the intent badge has a value").toBeTruthy();
    const gnn = r.lane_sizes?.gnn_route ?? 0;
    if (mode === "GNN") {
      expect(gnn).toBeGreaterThan(0);
      expect((r as unknown as Record<string, unknown>).gnn, "GNN route receipt").toBeTruthy();
    } else expect(gnn).toBe(0);

    // the Evidence panel + Review read untyped rows: they must resolve the way the UI resolves them (lib/chunkid)
    const rows = (k: "chunks" | "final_detail" | "legend") => ((r[k] ?? []) as Record<string, unknown>[]);
    expect(rows("final_detail").length, "selected evidence rows").toBeGreaterThan(0);
    expect(rows("final_detail").every((d) => chunkIdOf(d) && typeof d.rerank_score === "number" && Array.isArray(d.arrivals))).toBe(true);
    expect(rows("chunks").every((c) => chunkIdOf(c) && typeof c.source_name === "string")).toBe(true);
    expect(rows("legend").every((l) => chunkIdOf(l) && typeof l.tag === "string")).toBe(true);
    if (mode === "HYBRID") reviewTurn = turn;
  }, 300_000);

  it("review judges a real answer (the request AnswerReview builds)", async () => {
    const t = reviewTurn;
    expect(t, "the HYBRID turn ran").toBeTruthy();
    const receipt = t?.receipt;
    if (!t || !receipt) return;
    const legend = (receipt.legend ?? []) as Record<string, unknown>[];
    const chunks = (receipt.chunks ?? []) as Record<string, unknown>[];
    const tagById = new Map(legend.map((l) => [chunkIdOf(l), l.tag as string | undefined]));
    const res = await viaClient("review", () => api.review({
      question: t.question, answer: t.answerText,
      citations: legend.map((l) => l.tag).filter(Boolean) as string[],
      evidence: chunks.filter((c) => tagById.has(chunkIdOf(c)))
        .map((c) => ({ tag: tagById.get(chunkIdOf(c)), doc_id: c.doc_id, source_name: c.source_name, text: c.preview })),
      retrieval_meta: { engine: receipt.engine, mode: receipt.mode, evidence_count: receipt.evidence_count },
    }));
    expect(res.review ?? res.parse_error, "a review or a stated parse error").toBeTruthy();
  }, 240_000);

  it("model test answers for a configured provider's model (the Models screen's Test button)", async () => {
    // Models.tsx tests `provider.models[0]` of a configured provider; prefer the provider serving the default model
    const defModel = (await api.synthesizers()).find((s) => s.default)?.model ?? "";
    const usable = (await api.llmProviders()).filter((x) => x.enabled && x.ready && x.models.length > 0);
    const provider = usable.find((x) => x.models.some((m) => m.endsWith(defModel))) ?? usable[0];
    const model = provider?.models.find((m) => m.endsWith(defModel)) ?? provider?.models[0];
    expect(model, "a configured, ready provider model").toBeTruthy();
    const res = await viaClient("testModel", () => api.testModel(model ?? ""));
    expect(res.ok, `${model}: ${res.error ?? ""}`).toBe(true);
  }, 120_000);
});
