// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import type { Me } from "../lib/auth";

/** INVITE-SIGNUP — one sign-in page for everyone: "Create your account" (username, password, type it again, invite code)
 *  posts /auth/register and lands in the app as a friend; each refusal is explained in words; the owner's Invite card shows
 *  the code with the hover copy button and regenerates after the confirm dialog; a friend has no card. */

const FRIEND: Me = { username: "ann", display_name: "ann", is_owner: false, must_change_password: false, principal_id: "prn_ann", local: false };
const OWNER: Me = { ...FRIEND, username: "king", display_name: "King", is_owner: true, principal_id: "prn_owner" };
const OLD_CODE = "k7mp-4xwq-9nfr";
const NEW_CODE = "b3ry-8cdf-w2hq";

let host: HTMLDivElement;
let root: Root;
let me: Me | 401;
let invite: { code: string | null; rotated_at: string | null };
let registerAnswer: () => Response;
let calls: { path: string; method: string; body: unknown }[];

function refused(status: number, error_code: string, message = "refused"): Response {
  return Response.json({ detail: { error_code, message } }, { status });
}

function route(path: string, init?: RequestInit): Response {
  const method = init?.method ?? "GET";
  if (path === "/auth/me") return me === 401 ? refused(401, "LOGIN_REQUIRED") : Response.json(me);
  if (path === "/auth/register") return registerAnswer();
  if (path === "/friends/invite" && method === "GET") return Response.json(invite);
  if (path === "/friends/invite/rotate" && method === "POST") {
    invite = { code: NEW_CODE, rotated_at: "2026-09-27T12:00:00Z" };
    return Response.json(invite);
  }
  if (path === "/corpora") return Response.json({ corpora: [{ corpus_id: "cinema", documents: 3, query_ready: true, query_enabled: true }] });
  if (path === "/keys" && method === "GET") return Response.json({ is_owner: false, keys: [], max_active: 3, mcp_url: "https://mcp.example.test/mcp" });
  if (path === "/keys/prompt") return Response.json({ prompt: "Header: Authorization: Bearer <YOUR_KEY>", placeholder: "<YOUR_KEY>", mcp_url: "x" });
  if (path === "/admin/friends" && method === "GET") return Response.json({ friends: [], libraries: ["cinema"], adapters: [], max_active_keys: 3 });
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
  invite = { code: OLD_CODE, rotated_at: "2026-09-26T10:00:00Z" };
  registerAnswer = () => Response.json(FRIEND, { status: 201 });
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    calls.push({ path, method: init?.method ?? "GET", body: typeof init?.body === "string" ? JSON.parse(init.body) : init?.body ?? null });
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
  await settle();
}

async function settle() {
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

function navLabels(): string[] {
  return [...host.querySelectorAll(".nav__item span")].map((s) => s.textContent ?? "");
}

function button(text: string, within: ParentNode = host): HTMLButtonElement {
  const b = [...within.querySelectorAll("button")].find((x) => x.textContent === text);
  if (!b) throw new Error(`no button "${text}" in: ${host.textContent}`);
  return b as HTMLButtonElement;
}

function type(input: Element | null | undefined, value: string) {
  if (!input) throw new Error("no such input");
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  setter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

/** Opens the sign-up form from the sign-in page and fills it. */
async function openSignUp(username = "Ann", password = "her own password", again = password, code = OLD_CODE) {
  me = 401;
  await render();
  expect(host.textContent).toContain("Sign in to continue.");
  expect(host.querySelectorAll("input").length).toBe(2);                              // the sign-in form is as it was
  await act(async () => { button("New here? Create your account").click(); });
  const inputs = host.querySelectorAll("input");
  expect(inputs.length).toBe(4);
  expect([...host.querySelectorAll(".label")].map((l) => l.textContent)).toEqual(["Username", "Password", "Type it again", "Invite code"]);
  await act(async () => {
    type(inputs[0], username); type(inputs[1], password); type(inputs[2], again); type(inputs[3], code);
  });
}

it("creates the account from the sign-in page and lands in the app as a friend", async () => {
  await openSignUp();
  expect(button("Create account").disabled).toBe(false);
  await act(async () => { button("Create account").click(); });
  await settle();
  const post = calls.find((c) => c.path === "/auth/register");
  expect(post?.method).toBe("POST");
  expect(post?.body).toEqual({ username: "Ann", password: "her own password", invite_code: OLD_CODE });
  expect(navLabels()).toContain("Chat");
  expect(navLabels()).not.toContain("Overview");                                       // a friend, not the owner
  expect(host.textContent).not.toContain("Choose your own password");                 // no first-password step
});

it("holds the button until the two passwords match and every field is filled", async () => {
  await openSignUp("ann", "one", "two");
  expect(host.textContent).toContain("The two passwords differ.");
  expect(button("Create account").disabled).toBe(true);
  await act(async () => { type(host.querySelectorAll("input")[2], "one"); });
  expect(host.textContent).not.toContain("The two passwords differ.");
  expect(button("Create account").disabled).toBe(false);
  await act(async () => { type(host.querySelectorAll("input")[3], ""); });
  expect(button("Create account").disabled).toBe(true);
  await act(async () => { button("Back to sign in").click(); });
  expect(host.textContent).toContain("Sign in to continue.");
  expect(calls.some((c) => c.path === "/auth/register")).toBe(false);
});

it("explains each refusal in words and keeps the form", async () => {
  await openSignUp();
  const cases: [number, string, string][] = [
    [403, "INVITE_INVALID", "The invite code is wrong."],
    [409, "USERNAME_TAKEN", "That username is taken."],
    [422, "USERNAME_INVALID", "Usernames are 2–32 characters: lowercase letters, digits, - or _."],
    [422, "WEAK_PASSWORD", "Choose a password."],
    [503, "INVITES_OFF", "Sign-ups are not open yet. Ask King for an invite code."],
    [429, "TOO_MANY_ATTEMPTS", "Too many failed tries. Wait 15 minutes and try again."],
    [503, "LOGIN_NOT_CONFIGURED", "Sign-in is not set up on the server yet."],
    [500, "SESSION_REFRESH_FAILED", "Could not create the account: the account was created; please sign in"],
  ];
  for (const [status, code, words] of cases) {
    registerAnswer = () => refused(status, code, "the account was created; please sign in");
    await act(async () => { button("Create account").click(); });
    await settle();
    expect(host.querySelector('[role="alert"]')?.textContent).toBe(words);
    expect(host.querySelectorAll("input").length).toBe(4);                            // still on the form, values kept
    expect((host.querySelectorAll("input")[0] as HTMLInputElement).value).toBe("Ann");
  }
  expect(calls.filter((c) => c.path === "/auth/register").length).toBe(cases.length);
  expect(navLabels()).toEqual([]);
});

it("shows the owner the invite code with a hover copy button and regenerates it after the confirm dialog", async () => {
  me = OWNER;
  await render();
  await act(async () => { button("Settings").click(); });
  await settle();
  expect(host.textContent).toContain("Send a friend the website address and this code; they create their own account.");
  expect(host.textContent).toContain(OLD_CODE);
  const copy = host.querySelector('button.icon-btn.secret__copy[aria-label="Copy invite code"]');   // the answers' hover copy
  expect(copy).not.toBeNull();
  expect(copy!.closest(".secret")!.querySelector("code.settings__secret")!.textContent).toBe(OLD_CODE);
  expect(host.textContent).toContain("Add friend");                                   // the owner's own flow stays below
  expect(host.textContent.indexOf("Invite code")).toBeLessThan(host.textContent.indexOf("Add friend"));
  await act(async () => { button("Regenerate").click(); });
  await settle();
  const dialog = host.querySelector("dialog")!;
  expect(dialog.textContent).toContain("Friends who have not signed up yet will need the new code.");
  expect(calls.some((c) => c.path === "/friends/invite/rotate")).toBe(false);          // nothing changed before the answer
  await act(async () => { button("Cancel", dialog).click(); });
  expect(host.querySelector("dialog")).toBeNull();
  expect(host.textContent).toContain(OLD_CODE);
  await act(async () => { button("Regenerate").click(); });
  await settle();
  await act(async () => { button("Regenerate", host.querySelector("dialog")!).click(); });
  await settle();
  expect(calls.find((c) => c.path === "/friends/invite/rotate")?.method).toBe("POST");
  expect(host.textContent).toContain(NEW_CODE);
  expect(host.textContent).not.toContain(OLD_CODE);
});

it("offers Create invite code while none exists, without a dialog", async () => {
  me = OWNER;
  invite = { code: null, rotated_at: null };
  await render();
  await act(async () => { button("Settings").click(); });
  await settle();
  expect(host.textContent).toContain("No invite code yet.");
  expect([...host.querySelectorAll("button")].some((b) => b.textContent === "Regenerate")).toBe(false);
  await act(async () => { button("Create invite code").click(); });
  await settle();
  expect(host.querySelector("dialog")).toBeNull();
  expect(calls.find((c) => c.path === "/friends/invite/rotate")?.method).toBe("POST");
  expect(host.textContent).toContain(NEW_CODE);
  expect(host.querySelector('button.secret__copy[aria-label="Copy invite code"]')).not.toBeNull();
  expect(button("Regenerate")).toBeTruthy();
});

it("shows a friend no invite card", async () => {
  me = FRIEND;
  await render();
  await act(async () => { button("Settings").click(); });
  await settle();
  expect(host.textContent).not.toContain("Send a friend the website address");
  expect(host.textContent).not.toContain(OLD_CODE);
  expect([...host.querySelectorAll("button")].map((b) => b.textContent)).not.toContain("Create invite code");
  expect(calls.some((c) => c.path.startsWith("/friends/invite"))).toBe(false);
});
