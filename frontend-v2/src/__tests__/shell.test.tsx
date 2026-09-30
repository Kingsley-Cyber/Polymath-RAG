// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import { setAppearance } from "../lib/appearance";
import type { Me } from "../lib/auth";

/** FRONTEND-REFRESH-V1 U2 — the shell: a top bar (library, light/dark, account), a phone drawer, and a Files screen that
 *  shows only the controls the person can use, with the owner's library delete behind a type-the-name dialog. */

const FRIEND: Me = { username: "fred", display_name: "Fred Smith", is_owner: false, must_change_password: false, principal_id: "prn_fred", local: false };
const OWNER: Me = { username: "king", display_name: "King", is_owner: true, must_change_password: false, principal_id: "prn_owner", local: true };

let host: HTMLDivElement;
let root: Root;
let me: Me;
let calls: { path: string; method: string; body?: unknown }[];

function route(path: string, init?: RequestInit): Response {
  const method = init?.method ?? "GET";
  if (path === "/auth/me") return Response.json(me);
  if (path === "/corpora") return Response.json({ corpora: [
    { corpus_id: "cinema", documents: 3, query_ready: true, query_enabled: true },
    { corpus_id: "commerce-v1", documents: 2, query_ready: true, query_enabled: true },
  ] });
  if (path.startsWith("/documents?")) return Response.json({ documents: [
    { doc_id: "doc_1", source_name: "handbook.md", media_type: "text/markdown", bytes: 2048, created_at: "2026-09-01T00:00:00Z", parents: 1, chunks: 2, map_active: 1 },
  ] });
  if (path.startsWith("/documents/summary")) return Response.json({ summaries: {} });
  if (path.startsWith("/corpora/") && method === "DELETE") return Response.json({ deleted: true });
  if (path === "/auth/owner-password") return Response.json({ owner_password: "set", username: "king" });
  if (path === "/keys") return Response.json({ is_owner: me.is_owner, keys: [], max_active: 3, mcp_url: "https://mcp.example.test/mcp" });
  if (path === "/keys/prompt") return Response.json({ prompt: "Header: Authorization: Bearer <YOUR_KEY>", placeholder: "<YOUR_KEY>", mcp_url: "x" });
  if (path === "/admin/friends") return Response.json({ friends: [], libraries: ["cinema"], adapters: [], max_active_keys: 3 });
  return Response.json({});
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  localStorage.setItem("polymath-v2.nav-collapsed", "0");
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    calls.push({ path, method: init?.method ?? "GET", body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined });
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

async function render(who: Me) {
  me = who;
  await act(async () => root.render(<App />));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

async function settle() { await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); }

function byLabel(label: string): HTMLButtonElement {
  const b = [...host.querySelectorAll("button")].find((x) => x.getAttribute("aria-label") === label || x.textContent?.trim() === label);
  if (!b) throw new Error(`no button "${label}"`);
  return b as HTMLButtonElement;
}

function openScreen(label: string) {
  const b = [...host.querySelectorAll(".nav__item")].find((x) => x.textContent?.trim() === label) as HTMLButtonElement;
  b.click();
}

it("puts the library picker in the top bar, not the sidebar", async () => {
  await render(OWNER);
  const topSelect = host.querySelector(".topbar select") as HTMLSelectElement;
  expect([...topSelect.options].map((o) => o.value)).toEqual(["cinema", "commerce-v1"]);
  expect(host.querySelector(".nav select")).toBeNull();
  expect(host.querySelector(".nav")!.textContent).not.toContain("Delete");      // the destructive button left the sidebar
});

it("switches light and dark from the top bar", async () => {
  setAppearance({ mode: "light", accent: "indigo" });
  await render(OWNER);
  await act(async () => byLabel("Switch to dark mode").click());
  expect(document.documentElement.dataset.mode).toBe("dark");
  expect(JSON.parse(localStorage.getItem("polymath.appearance")!).mode).toBe("dark");
  await act(async () => byLabel("Switch to light mode").click());
  expect(document.documentElement.dataset.mode).toBe("light");
});

it("opens Settings and signs out from the account menu", async () => {
  await render(FRIEND);
  await act(async () => byLabel("Account: Fred Smith").click());
  expect(host.querySelector(".account__menu")!.textContent).toContain("fred");
  const item = [...host.querySelectorAll(".account__menu [role=menuitem]")].find((b) => b.textContent === "Settings") as HTMLButtonElement;
  await act(async () => item.click());
  await settle();
  expect(host.querySelector(".screen__title")!.textContent).toBe("Settings");
  expect(host.querySelector(".account__menu")).toBeNull();                         // choosing an item closes the menu
  await act(async () => byLabel("Account: Fred Smith").click());
  expect(host.querySelector(".account__menu")!.textContent).toContain("Sign out");
});

it("the owner on the server itself has no Sign out", async () => {
  await render(OWNER);
  await act(async () => byLabel("Account: King").click());
  expect(host.querySelector(".account__menu")!.textContent).not.toContain("Sign out");
});

it("opens and closes the phone drawer", async () => {
  await render(OWNER);
  const shell = host.querySelector(".shell")!;
  await act(async () => byLabel("Open menu").click());
  expect(shell.classList.contains("shell--drawer")).toBe(true);
  await act(async () => { window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })); });
  expect(shell.classList.contains("shell--drawer")).toBe(false);
  await act(async () => byLabel("Open menu").click());
  await act(async () => openScreen("Files"));
  expect(shell.classList.contains("shell--drawer")).toBe(false);                  // choosing a screen closes it
});

it("the owner deletes a library only after typing its name", async () => {
  await render(OWNER);
  await act(async () => openScreen("Files"));
  await settle();
  await act(async () => byLabel("Delete library…").click());
  const confirm = byLabel("Delete library");
  expect(confirm.disabled).toBe(true);
  const input = host.querySelector("dialog input") as HTMLInputElement;
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  await act(async () => { setter.call(input, "cinem"); input.dispatchEvent(new Event("input", { bubbles: true })); });
  expect(confirm.disabled).toBe(true);
  await act(async () => { setter.call(input, "cinema"); input.dispatchEvent(new Event("input", { bubbles: true })); });
  expect(confirm.disabled).toBe(false);
  await act(async () => confirm.click());
  await settle();
  expect(calls.some((c) => c.method === "DELETE" && c.path === "/corpora/cinema?confirm=cinema")).toBe(true);
});

it("a friend's Files shows no owner controls and no writes in a shared library", async () => {
  await render(FRIEND);
  await act(async () => openScreen("Files"));
  await settle();
  const text = host.textContent ?? "";
  for (const hidden of ["Continue corpus", "Add Files", "Delete library"]) expect(text).not.toContain(hidden);
  expect([...host.querySelectorAll(".files__del")]).toHaveLength(0);
  expect(text).toContain("shared with you to read");
  expect(calls.some((c) => c.path.startsWith("/control_plane"))).toBe(false);      // owner-only data is never requested
});

it("a friend can add and delete files in their private library", async () => {
  await render(FRIEND);
  const topSelect = host.querySelector(".topbar select") as HTMLSelectElement;
  expect([...topSelect.options].map((o) => o.value)).toContain("fr-fred");
  await act(async () => { topSelect.value = "fr-fred"; topSelect.dispatchEvent(new Event("change", { bubbles: true })); });
  await act(async () => openScreen("Files"));
  await settle();
  expect(host.textContent).toContain("Add Files");
  expect(host.querySelectorAll(".files__del").length).toBeGreaterThan(0);
  expect(host.textContent).not.toContain("Delete library");
});


it("the owner sets the website password in Settings on the server itself: one field with Show, first while unset", async () => {
  await render({ ...OWNER, web_password_set: false });
  await act(async () => openScreen("Settings"));
  await settle();
  const cards = [...host.querySelectorAll(".settings__cards > .card")];
  expect(cards[0]!.getAttribute("aria-label")).toBe("Profile");
  const card = cards[1] as HTMLFormElement;                                           // unset: the password comes first
  expect(card.textContent).toContain("Website password");
  expect(card.textContent).toContain("Username: King");
  expect(card.querySelector(".pill")!.textContent).toBe("Not set");
  const inputs = [...card.querySelectorAll("input")] as HTMLInputElement[];
  expect(inputs).toHaveLength(1);
  const pw = inputs[0]!;
  expect(pw.type).toBe("password");
  await act(async () => (card.querySelector('button[aria-label="Show password"]') as HTMLButtonElement).click());
  expect(pw.type).toBe("text");
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  await act(async () => { setter.call(pw, "any password at all"); pw.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => (card.querySelector('button[type="submit"]') as HTMLButtonElement).click());
  await settle();
  const post = calls.find((c) => c.method === "POST" && c.path === "/auth/owner-password");
  expect(post?.body).toEqual({ password: "any password at all" });
  expect(card.textContent).toContain("sign in with username King");
  expect(card.querySelector(".pill")!.textContent).toBe("Set");
});

it("once the password is set, connecting the agents comes first", async () => {
  await render({ ...OWNER, web_password_set: true });
  await act(async () => openScreen("Settings"));
  await settle();
  const cards = [...host.querySelectorAll(".settings__cards > .card")];
  expect(cards[1]!.textContent).toContain("Connect Claude Code and Codex");
  expect(cards[2]!.textContent).toContain("API key for another computer");        // OWNER-KEY-VISIBLE
  expect(cards[3]!.textContent).toContain("Website password");
});

it("a friend changes their own password and never sees the owner's password form", async () => {
  await render(FRIEND);
  await act(async () => openScreen("Settings"));
  await settle();
  expect(host.textContent).toContain("Change the password for fred");
  expect(host.textContent).not.toContain("Username: King");
  expect(host.querySelector("#owner-password")).toBeNull();
});
