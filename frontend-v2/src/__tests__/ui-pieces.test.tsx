// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import { Dialog } from "../ui/Dialog";
import { Icon, IconButton } from "../ui/icons";
import { EmptyState, ErrorState, Skeleton } from "../ui/states";

/** FRONTEND-REFRESH-V1 U3 — the shared pieces: icon buttons always carry a name, the icon rail stays labelled, and loading /
 *  empty / error never look alike. */

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

it("an icon button is named by its label and its icon is hidden from screen readers", async () => {
  const onClick = vi.fn();
  await act(async () => root.render(<IconButton icon="trash" label="Delete chat" onClick={onClick} />));
  const b = host.querySelector("button")!;
  expect(b.getAttribute("aria-label")).toBe("Delete chat");
  expect(b.title).toBe("Delete chat");
  expect(b.querySelector("svg")!.getAttribute("aria-hidden")).toBe("true");
  await act(async () => b.click());
  expect(onClick).toHaveBeenCalledOnce();
});

it("every icon renders an outline svg", async () => {
  await act(async () => root.render(<><Icon name="chat" /><Icon name="settings" size={20} /></>));
  const svgs = host.querySelectorAll("svg");
  expect(svgs).toHaveLength(2);
  expect(svgs[1]!.getAttribute("width")).toBe("20");
  expect(svgs[0]!.getAttribute("stroke")).toBe("currentColor");
});

it("the collapsed icon rail keeps every item's name", async () => {
  localStorage.setItem("polymath-v2.nav-collapsed", "1");
  vi.stubGlobal("fetch", vi.fn(async (path: string) => Response.json(
    path === "/auth/me" ? { username: "king", display_name: "King", is_owner: true, must_change_password: false, principal_id: "prn_owner", local: true }
      : path === "/corpora" ? { corpora: [{ corpus_id: "cinema", documents: 1, query_ready: true }] } : {})));
  await act(async () => root.render(<App />));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  const names = [...host.querySelectorAll(".nav__item")].map((b) => b.getAttribute("aria-label"));
  expect(names).toEqual(["Overview", "Chat", "Compare", "Files", "Graph", "Research", "Control Plane", "Models", "Settings"]);
  expect(host.querySelector(".nav__newchat")!.getAttribute("aria-label")).toBe("New chat");
});

it("loading, empty and error states are distinct and announced", async () => {
  const retry = vi.fn();
  await act(async () => root.render(<>
    <Skeleton label="Loading documents…" />
    <EmptyState title="No documents yet" action={<button type="button">Add files</button>}>Add a file to start.</EmptyState>
    <ErrorState message="The server did not answer." onRetry={retry} />
  </>));
  expect(host.querySelector('[role="status"]')!.textContent).toContain("Loading documents…");
  expect(host.textContent).toContain("No documents yet");
  const alert = host.querySelector('[role="alert"]')!;
  expect(alert.textContent).toContain("Couldn't load this");
  await act(async () => (alert.querySelector("button") as HTMLButtonElement).click());
  expect(retry).toHaveBeenCalledOnce();
});

it("a dialog is absent while closed and Esc (cancel) asks to close it", async () => {
  const onClose = vi.fn();
  await act(async () => root.render(<Dialog open={false} title="T" onClose={onClose} actions={null}>body</Dialog>));
  expect(host.querySelector("dialog")).toBeNull();
  await act(async () => root.render(<Dialog open title="Delete it?" onClose={onClose} actions={null}>body</Dialog>));
  const d = host.querySelector("dialog")!;
  expect(d.getAttribute("aria-labelledby")).toBe(d.querySelector("h2")!.id);
  await act(async () => { d.dispatchEvent(new Event("cancel", { cancelable: true })); });
  expect(onClose).toHaveBeenCalledOnce();
});
