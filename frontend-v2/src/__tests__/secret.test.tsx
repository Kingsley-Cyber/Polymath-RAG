// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Secret } from "../ui/Secret";

/** Settings — a key, a first password or a prompt carries the answers' hover copy button (icon-btn), and the check fades. */

let host: HTMLDivElement;
let root: Root;
beforeEach(() => { vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true); host = document.createElement("div"); document.body.append(host); root = createRoot(host); });
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); vi.useRealTimers(); });

it("a key shows its copy button as an icon labelled for the thing, and copies it", async () => {
  const writeText = vi.fn(async () => undefined);
  vi.stubGlobal("navigator", { clipboard: { writeText } });
  vi.useFakeTimers();
  await act(async () => root.render(<Secret value="pk_live_abc" what="key" />));
  const btn = host.querySelector("button.icon-btn.secret__copy") as HTMLButtonElement;
  expect(btn.getAttribute("aria-label")).toBe("Copy key");
  expect(host.querySelector("code.settings__secret")!.textContent).toBe("pk_live_abc");
  await act(async () => { btn.click(); await Promise.resolve(); });
  expect(writeText).toHaveBeenCalledWith("pk_live_abc");
  expect(btn.getAttribute("aria-label")).toBe("Copied");
  await act(async () => { vi.advanceTimersByTime(2100); });
  expect(btn.getAttribute("aria-label")).toBe("Copy key");                            // the check fades after two seconds
});

it("a prompt is a read-only block with the copy button in its corner", async () => {
  await act(async () => root.render(<Secret value="Connect to my Polymath…" what="prompt" block rows={4} />));
  const box = host.querySelector(".secret.secret--block")!;
  expect((box.querySelector("textarea") as HTMLTextAreaElement).readOnly).toBe(true);
  expect(box.querySelector("button.secret__copy")!.getAttribute("aria-label")).toBe("Copy prompt");
});
