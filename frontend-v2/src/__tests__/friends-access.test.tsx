// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import { api, AUTH_REQUIRED_EVENT, csrfToken } from "../lib/api";
import { auth, LEGACY_OWNER, normalizeMe, type Me } from "../lib/auth";

/** FRIENDS-ACCESS-V1 F4 — the sign-in gate, the first-password change, friend-only navigation, the CSRF header, Settings. */

const FRIEND: Me = { username: "fred", display_name: "Fred", is_owner: false, must_change_password: false, principal_id: "prn_fred", local: false };
const OWNER: Me = { ...FRIEND, username: "king", display_name: "King", is_owner: true, principal_id: "prn_owner" };

let host: HTMLDivElement;
let root: Root;
let me: Me | 401 | 404;
let calls: { path: string; method: string; headers: Record<string, string>; body: unknown }[];

function route(path: string, init?: RequestInit): Response {
  const method = init?.method ?? "GET";
  if (path === "/auth/me") {
    if (me === 401) return Response.json({ detail: { error_code: "LOGIN_REQUIRED" } }, { status: 401 });
    if (me === 404) return Response.json({ detail: "Not Found" }, { status: 404 });
    return Response.json(me);
  }
  if (path === "/auth/login") return Response.json(FRIEND);
  if (path === "/auth/logout") return Response.json({ signed_out: true });
  if (path === "/corpora") return Response.json({ corpora: [{ corpus_id: "cinema", documents: 3, query_ready: true, query_enabled: true }] });
  if (path === "/keys" && method === "GET") return Response.json({ is_owner: false, keys: [], max_active: 3, mcp_url: "https://mcp.example.test/mcp" });
  if (path === "/keys" && method === "POST") {
    return Response.json({ key: "pmk_abcdef123456_SECRET", key_id: "abcdef123456", label: "laptop", created_at: "2026-09-26T00:00:00Z",
                           revoked_at: null, shown_once: true, prompt: "Connect with Authorization: Bearer pmk_abcdef123456_SECRET" }, { status: 201 });
  }
  if (path === "/keys/prompt") return Response.json({ prompt: "Header: Authorization: Bearer <YOUR_KEY>", placeholder: "<YOUR_KEY>", mcp_url: "x" });
  if (path === "/admin/friends" && method === "GET") return Response.json({ friends: [], libraries: ["cinema"], adapters: [], max_active_keys: 3 });
  if (path === "/admin/friends" && method === "POST") {
    return Response.json({ friend: { username: "ann" }, first_password: "FIRST-PASS-123", shown_once: true }, { status: 201 });
  }
  if (path === "/synthesizers") return Response.json({ synthesizers: [] });
  if (path === "/reasoning_modes") return Response.json({ modes: [], default: "none" });
  return Response.json({});
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  document.cookie = "polymath_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    calls.push({ path, method: init?.method ?? "GET", headers: (init?.headers ?? {}) as Record<string, string>,
                 body: typeof init?.body === "string" ? JSON.parse(init.body) : init?.body ?? null });
    return route(path, init);
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

async function render() {
  await act(async () => root.render(<App />));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

function navLabels(): string[] {
  return [...host.querySelectorAll(".nav__item span")].map((s) => s.textContent ?? "");
}

function button(text: string): HTMLButtonElement {
  const b = [...host.querySelectorAll("button")].find((x) => x.textContent === text);
  if (!b) throw new Error(`no button "${text}" in: ${host.textContent}`);
  return b as HTMLButtonElement;
}

function type(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  setter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

it("shows the sign-in screen on 401 and a friend's workspace after signing in", async () => {
  me = 401;
  await render();
  expect(host.textContent).toContain("Sign in to continue.");
  const [user, pass] = host.querySelectorAll("input");
  await act(async () => { type(user as HTMLInputElement, "fred"); type(pass as HTMLInputElement, "correct horse battery"); });
  await act(async () => { button("Sign in").click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(calls.find((c) => c.path === "/auth/login")?.body).toEqual({ username: "fred", password: "correct horse battery" });
  const labels = navLabels();
  expect(labels).toContain("Chat");
  expect(labels).toContain("Settings");
  for (const hidden of ["Overview", "Control Plane", "Models"]) expect(labels).not.toContain(hidden);
  expect(host.textContent).not.toContain("Delete library");                          // the owner-only library delete
  expect(calls.some((c) => c.path.startsWith("/control_plane"))).toBe(false);          // owner-only data is never requested
})

it("returns to the sign-in screen when any request answers 401", async () => {
  me = FRIEND;
  await render();
  expect(navLabels()).toContain("Chat");
  await act(async () => { window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT)); });
  expect(host.textContent).toContain("Sign in to continue.");
});

it("asks for a new password before anything else when the first one must change", async () => {
  me = { ...FRIEND, must_change_password: true };
  await render();
  expect(host.textContent).toContain("Choose your own password to continue");
  expect(navLabels()).toEqual([]);
});

it("sends the CSRF token on every state-changing request", async () => {
  document.cookie = "polymath_csrf=tok-123";
  expect(csrfToken()).toBe("tok-123");
  await auth.createKey("laptop");
  await api.upload("fr-fred", new File(["x"], "a.md"));
  const writes = calls.filter((c) => c.method !== "GET");
  expect(writes.length).toBe(2);
  for (const w of writes) expect(w.headers["x-polymath-csrf"]).toBe("tok-123");
});

it("shows a friend's new key once, with the prompt filled in", async () => {
  me = FRIEND;
  await render();
  await act(async () => { button("Settings").click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(host.textContent).toContain("fr-fred");
  await act(async () => { button("Create key").click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(host.textContent).toContain("This key is shown only now");
  expect(host.textContent).toContain("pmk_abcdef123456_SECRET");
  const prompt = [...host.querySelectorAll("textarea")].map((t) => t.value).join("\n");
  expect(prompt).toContain("Bearer pmk_abcdef123456_SECRET");
  await act(async () => { button("I've saved it").click(); });
  expect(host.textContent).not.toContain("pmk_abcdef123456_SECRET");
  expect(host.textContent).not.toContain("Friends");                                 // no admin for a friend
});

it("gives the owner the friends manager and shows a new friend's first password once", async () => {
  me = OWNER;
  await render();
  expect(navLabels()).toContain("Control Plane");
  await act(async () => { button("Settings").click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(host.textContent).toContain("Friends");
  expect(host.textContent).toContain("POLYMATH_MCP_API_KEY");
  const username = host.querySelector('input[placeholder="username (lowercase)"]') as HTMLInputElement;
  await act(async () => { type(username, "ann"); });
  await act(async () => { button("Add friend").click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(host.textContent).toContain("FIRST-PASS-123");
  await act(async () => { button("Done").click(); });
  expect(host.textContent).not.toContain("FIRST-PASS-123");
});

it("treats a backend without logins as the owner, as before", async () => {
  expect(normalizeMe({})).toEqual(LEGACY_OWNER);
  me = 404;
  await render();
  expect(navLabels()).toContain("Overview");
});
