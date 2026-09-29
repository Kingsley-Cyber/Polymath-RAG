// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Login } from "../screens/Login";
import type { Me } from "../lib/auth";

/** ONE-PROFILE (the owner, 2026-09-28: "universal log in is King ... just keep it 1 profile") — the sign-in page asks for a
 *  username and a password and nothing else; Show reveals the password; every refusal is explained in words. */

const KING: Me = { username: "king", display_name: "King", is_owner: true, must_change_password: false, principal_id: "prn_owner", local: false };

let host: HTMLDivElement;
let root: Root;
let answer: { status: number; body: unknown };
let posted: unknown[];
let signedIn: Me[];

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  posted = [];
  signedIn = [];
  answer = { status: 200, body: KING };
  vi.stubGlobal("fetch", vi.fn(async (_path: string, init?: RequestInit) => {
    posted.push(typeof init?.body === "string" ? JSON.parse(init.body) : null);
    return Response.json(answer.body, { status: answer.status });
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

async function show() {
  await act(async () => root.render(<Login onSignedIn={(m) => signedIn.push(m)} />));
}

function type(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  setter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function fields() {
  return {
    user: host.querySelector("#signin-username") as HTMLInputElement,
    pass: host.querySelector("#signin-password") as HTMLInputElement,
    submit: host.querySelector('button[type="submit"]') as HTMLButtonElement,
  };
}

async function signIn(username: string, password: string) {
  const { user, pass, submit } = fields();
  await act(async () => { type(user, username); type(pass, password); });
  await act(async () => { submit.click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

it("asks only for a username and a password: no sign-up, no invite code", async () => {
  await show();
  expect(host.querySelectorAll("input")).toHaveLength(2);
  expect(host.querySelector('label[for="signin-username"]')!.textContent).toBe("Username");
  expect(host.querySelector('label[for="signin-password"]')!.textContent).toBe("Password");
  for (const gone of ["Create your account", "invite", "Invite"]) expect(host.textContent).not.toContain(gone);
  expect(fields().submit.disabled).toBe(true);
});

it("Show reveals the password and Hide hides it again", async () => {
  await show();
  const { pass } = fields();
  const eye = host.querySelector(".pw__eye") as HTMLButtonElement;
  expect(pass.type).toBe("password");
  expect(eye.getAttribute("aria-label")).toBe("Show password");
  await act(async () => eye.click());
  expect(pass.type).toBe("text");
  expect(eye.getAttribute("aria-label")).toBe("Hide password");
  await act(async () => eye.click());
  expect(pass.type).toBe("password");
});

it("signs King in with the username as typed", async () => {
  await show();
  await signIn("King ", "any password at all");
  expect(posted[0]).toEqual({ username: "King", password: "any password at all" });
  expect(signedIn).toEqual([KING]);
});

it("an unset King password says where to set it", async () => {
  answer = { status: 409, body: { detail: { error_code: "OWNER_PASSWORD_NOT_SET", message: "not set" } } };
  await show();
  await signIn("King", "whatever");
  const alert = host.querySelector('[role="alert"]')!;
  expect(alert.textContent).toContain("King's password isn't set yet");
  expect(alert.textContent).toContain("Settings");
  expect(signedIn).toEqual([]);
});

it("a wrong password keeps the username and clears the password", async () => {
  answer = { status: 401, body: { detail: { error_code: "BAD_LOGIN", message: "wrong username or password" } } };
  await show();
  await signIn("King", "nope");
  expect(host.querySelector('[role="alert"]')!.textContent).toBe("Wrong username or password.");
  expect(fields().user.value).toBe("King");
  expect(fields().pass.value).toBe("");
});

it("too many tries says how long to wait", async () => {
  answer = { status: 429, body: { detail: { error_code: "TOO_MANY_ATTEMPTS", message: "wait" } } };
  await show();
  await signIn("King", "nope");
  expect(host.querySelector('[role="alert"]')!.textContent).toContain("Wait 15 minutes");
});
