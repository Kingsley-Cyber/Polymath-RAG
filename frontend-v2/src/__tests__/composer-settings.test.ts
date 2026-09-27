// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from "vitest";
import {
  COMPOSER_SETTINGS_KEY, DEFAULT_COMPOSER_SETTINGS, getComposerSettings, setComposerSettings, updateComposerSettings,
} from "../lib/composerSettings";

/** HEADER-CONTROLS — the per-browser store behind the top bar's Retrieval / Model / Corpus Explore: one key, defaults as
 *  before the move, each field validated on its own, and storage as the truth (a cleared value reads as the defaults). */

beforeEach(() => {
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
});

it("starts from HYBRID, the backend's default model and Corpus Explore off", () => {
  expect(getComposerSettings()).toEqual({ mode: "HYBRID", model: "", corpusExplore: false });
  expect(getComposerSettings()).toBe(getComposerSettings());                        // a stable snapshot
  expect(DEFAULT_COMPOSER_SETTINGS.mode).toBe("HYBRID");
});

it("round-trips through one key, and a patch keeps the other fields", () => {
  setComposerSettings({ mode: "GRAPH", model: "litellm:openai/glm-5-free", corpusExplore: true });
  expect(JSON.parse(localStorage.getItem(COMPOSER_SETTINGS_KEY)!)).toEqual({ mode: "GRAPH", model: "litellm:openai/glm-5-free", corpusExplore: true });
  expect(getComposerSettings()).toEqual({ mode: "GRAPH", model: "litellm:openai/glm-5-free", corpusExplore: true });
  updateComposerSettings({ mode: "GNN" });
  expect(getComposerSettings()).toEqual({ mode: "GNN", model: "litellm:openai/glm-5-free", corpusExplore: true });
});

it("validates each field on its own: an unknown mode or a non-string model falls back, the rest is kept", () => {
  localStorage.setItem(COMPOSER_SETTINGS_KEY, JSON.stringify({ mode: "VECTOR", model: "ollama:x", corpusExplore: "yes" }));
  expect(getComposerSettings()).toEqual({ mode: "HYBRID", model: "ollama:x", corpusExplore: false });
  localStorage.setItem(COMPOSER_SETTINGS_KEY, JSON.stringify({ mode: "FAST", model: 7, corpusExplore: true }));
  expect(getComposerSettings()).toEqual({ mode: "FAST", model: "", corpusExplore: true });
  localStorage.setItem(COMPOSER_SETTINGS_KEY, "{not json");
  expect(getComposerSettings()).toEqual(DEFAULT_COMPOSER_SETTINGS);
});

it("reads storage as the truth: a value cleared or written elsewhere shows on the next read", () => {
  setComposerSettings({ mode: "WILDCARD", model: "", corpusExplore: false });
  localStorage.clear();
  expect(getComposerSettings()).toEqual(DEFAULT_COMPOSER_SETTINGS);
  localStorage.setItem(COMPOSER_SETTINGS_KEY, JSON.stringify({ mode: "GNN", model: "", corpusExplore: false }));
  expect(getComposerSettings().mode).toBe("GNN");
});
