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
  if (path === "/keys/owner") {
    return Response.json({ key: "main-key-XYZ-0123456789", mcp_url: "https://mcp.example.test/mcp",
                           prompt: "Connect with Authorization: Bearer main-key-XYZ-0123456789" });
  }
  if (path === "/keys/prompt") {
    return me !== 401 && me !== 404 && me.is_owner
      ? Response.json({ prompt: 'You can use my Polymath research library: it is connected to you as the MCP server "polymath".',
                        connect_command: "bash /Users/king/polymath-v4/scripts/connect_agents.sh", key_included: false,
                        placeholder: null, mcp_url: "x" })
      : Response.json({ prompt: "Header: Authorization: Bearer <YOUR_KEY>", placeholder: "<YOUR_KEY>", mcp_url: "x" });
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
  expect(host.querySelector('form[aria-label="Sign in"]')).not.toBeNull();
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
  expect(host.querySelector('form[aria-label="Sign in"]')).not.toBeNull();
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

it("ONE-PROFILE: gives the owner one command and one prompt to copy, and no key, friends or invite to manage", async () => {
  const writeText = vi.fn(async () => undefined);
  vi.stubGlobal("navigator", { clipboard: { writeText } });
  me = OWNER;
  await render();
  expect(navLabels()).toContain("Control Plane");
  await act(async () => { button("Settings").click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(host.textContent).toContain("Connect Claude Code and Codex");
  expect(host.textContent).toContain("There is no key to create");
  for (const gone of ["Friends", "Invite", "Add friend", "Create key", "API keys", "<YOUR_KEY>", "Bearer"]) {
    expect(host.textContent).not.toContain(gone);
  }
  const copyCommand = host.querySelector('button[aria-label="Copy command"]') as HTMLButtonElement;
  await act(async () => { copyCommand.click(); await Promise.resolve(); });
  expect(writeText).toHaveBeenLastCalledWith("bash /Users/king/polymath-v4/scripts/connect_agents.sh");
  const copyPrompt = host.querySelector('button[aria-label="Copy prompt"]') as HTMLButtonElement;
  expect(copyPrompt.classList.contains("btn--primary")).toBe(true);
  await act(async () => { copyPrompt.click(); await Promise.resolve(); });
  expect(writeText).toHaveBeenLastCalledWith('You can use my Polymath research library: it is connected to you as the MCP server "polymath".');
  expect(calls.some((c) => c.path.startsWith("/admin/") || c.path.startsWith("/friends/"))).toBe(false);
});

it("treats a backend without logins as the owner, as before", async () => {
  expect(normalizeMe({})).toEqual(LEGACY_OWNER);
  me = 404;
  await render();
  expect(navLabels()).toContain("Overview");
});

it("OWNER-KEY-VISIBLE: the main key stays hidden and unfetched until Show; Copy key and Copy prompt with key copy it", async () => {
  const writeText = vi.fn(async () => undefined);
  vi.stubGlobal("navigator", { clipboard: { writeText } });
  me = OWNER;
  await render();
  await act(async () => { button("Settings").click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(host.textContent).toContain("API key for another computer");
  expect(host.textContent).toContain("Full access");
  expect(host.textContent).not.toContain("main-key-XYZ");
  expect(calls.some((c) => c.path === "/keys/owner")).toBe(false);                    // never fetched on page load
  await act(async () => { button("Show").click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(host.querySelector('[aria-label="Main API key"]')!.textContent).toBe("main-key-XYZ-0123456789");
  await act(async () => { button("Hide").click(); });
  expect(host.textContent).not.toContain("main-key-XYZ");
  await act(async () => { (host.querySelector('button[aria-label="Copy key"]') as HTMLButtonElement).click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(writeText).toHaveBeenLastCalledWith("main-key-XYZ-0123456789");
  await act(async () => { (host.querySelector('button[aria-label="Copy prompt with key"]') as HTMLButtonElement).click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(writeText).toHaveBeenLastCalledWith("Connect with Authorization: Bearer main-key-XYZ-0123456789");
  expect(calls.filter((c) => c.path === "/keys/owner")).toHaveLength(1);              // fetched once, then kept
});

it("OWNER-KEY-VISIBLE: a friend never sees the main-key card and never asks for it", async () => {
  me = FRIEND;
  await render();
  await act(async () => { button("Settings").click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  expect(host.textContent).not.toContain("API key for another computer");
  expect(calls.some((c) => c.path === "/keys/owner")).toBe(false);
});
