// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  APPEARANCE_KEY, DEFAULT_APPEARANCE, LEGACY_THEME_KEY, applyAppearance, getAppearance, initAppearance, loadAppearance,
  migrateLegacy, resolveMode, setAppearance,
} from "../lib/appearance";

/** FRONTEND-REFRESH-V1 U1 — Light / Dark / System + accent; the ten pre-refresh themes migrate to the nearest pair once. */

beforeEach(() => {
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  delete document.documentElement.dataset.mode;
  delete document.documentElement.dataset.accent;
});

describe("the ten old themes", () => {
  it.each([
    ["", "system", "indigo"],
    ["obsidian", "dark", "indigo"],
    ["graphite", "dark", "indigo"],
    ["nord", "dark", "teal"],
    ["espresso", "dark", "amber"],
    ["solar", "dark", "amber"],
    ["rose", "dark", "rose"],
    ["slate", "light", "indigo"],
    ["paper", "light", "amber"],
    ["champagne", "light", "amber"],
  ])("%s → %s + %s", (id, mode, accent) => {
    expect(migrateLegacy(id)).toEqual({ mode, accent });
  });

  it("an unknown id falls back to System + Indigo", () => {
    expect(migrateLegacy("neon")).toEqual(DEFAULT_APPEARANCE);
    expect(migrateLegacy(null)).toEqual(DEFAULT_APPEARANCE);
  });

  it("is migrated once at start-up, saved under the new key and applied", () => {
    localStorage.setItem(LEGACY_THEME_KEY, "nord");
    initAppearance();
    expect(JSON.parse(localStorage.getItem(APPEARANCE_KEY)!)).toEqual({ mode: "dark", accent: "teal" });
    expect(localStorage.getItem(LEGACY_THEME_KEY)).toBeNull();
    expect(document.documentElement.dataset.mode).toBe("dark");
    expect(document.documentElement.dataset.accent).toBe("teal");
  });
});

describe("the stored choice", () => {
  it("round-trips and wins over the legacy key", () => {
    localStorage.setItem(LEGACY_THEME_KEY, "paper");
    setAppearance({ mode: "light", accent: "rose" });
    expect(loadAppearance()).toEqual({ mode: "light", accent: "rose" });
    expect(getAppearance()).toEqual({ mode: "light", accent: "rose" });
    expect(document.documentElement.dataset.mode).toBe("light");
    expect(document.documentElement.dataset.accent).toBe("rose");
  });

  it("ignores a malformed value", () => {
    localStorage.setItem(APPEARANCE_KEY, JSON.stringify({ mode: "neon", accent: "indigo" }));
    expect(loadAppearance()).toEqual(DEFAULT_APPEARANCE);
    localStorage.setItem(APPEARANCE_KEY, "{not json");
    expect(loadAppearance()).toEqual(DEFAULT_APPEARANCE);
  });

  it("System follows the OS setting", () => {
    expect(resolveMode("system", true)).toBe("dark");
    expect(resolveMode("system", false)).toBe("light");
    expect(resolveMode("dark", false)).toBe("dark");
    const root = document.createElement("html");
    applyAppearance({ mode: "light", accent: "amber" }, root);
    expect(root.dataset.mode).toBe("light");
    expect(root.dataset.accent).toBe("amber");
  });
});
