import { useSyncExternalStore } from "react";

/** FRONTEND-REFRESH-V1 §3.2 — Light / Dark / System plus one accent, stored per browser. index.html applies the stored
 *  choice before the first paint; this module owns it afterwards (Settings → Appearance and the top-bar toggle). */

export type Mode = "light" | "dark" | "system";
export type Accent = "indigo" | "teal" | "amber" | "rose";
export interface Appearance { mode: Mode; accent: Accent }

export const APPEARANCE_KEY = "polymath.appearance";
export const LEGACY_THEME_KEY = "polymath-v2.theme";
export const MODES: readonly Mode[] = ["light", "dark", "system"];
export const ACCENTS: readonly Accent[] = ["indigo", "teal", "amber", "rose"];
export const DEFAULT_APPEARANCE: Appearance = { mode: "system", accent: "indigo" };

/** The ten palettes before the refresh → the nearest mode + accent. "" was the never-chosen default: no preference. */
const LEGACY: Record<string, Appearance> = {
  "": DEFAULT_APPEARANCE,
  obsidian: { mode: "dark", accent: "indigo" },
  graphite: { mode: "dark", accent: "indigo" },
  nord: { mode: "dark", accent: "teal" },
  espresso: { mode: "dark", accent: "amber" },
  solar: { mode: "dark", accent: "amber" },
  rose: { mode: "dark", accent: "rose" },
  slate: { mode: "light", accent: "indigo" },
  paper: { mode: "light", accent: "amber" },
  champagne: { mode: "light", accent: "amber" },
};

export function migrateLegacy(id: string | null | undefined): Appearance {
  return (id != null && LEGACY[id]) || DEFAULT_APPEARANCE;
}

function valid(a: unknown): a is Appearance {
  const x = a as Appearance | null;
  return !!x && MODES.includes(x.mode) && ACCENTS.includes(x.accent);
}

function storage(): Storage | null {
  try { return typeof localStorage === "undefined" ? null : localStorage; } catch { return null; }
}

/** The stored choice; else the migrated pre-refresh theme; else System + Indigo. Never throws (private mode, bad JSON). */
export function loadAppearance(): Appearance {
  const s = storage();
  if (!s) return DEFAULT_APPEARANCE;
  try {
    const parsed: unknown = JSON.parse(s.getItem(APPEARANCE_KEY) ?? "null");
    if (valid(parsed)) return { mode: parsed.mode, accent: parsed.accent };
  } catch { /* fall through to the legacy key */ }
  const legacy = s.getItem(LEGACY_THEME_KEY);
  return legacy == null ? DEFAULT_APPEARANCE : migrateLegacy(legacy);
}

function prefersDark(): boolean {
  try { return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches; } catch { return false; }
}

export function resolveMode(mode: Mode, dark = prefersDark()): "light" | "dark" {
  return mode === "system" ? (dark ? "dark" : "light") : mode;
}

export function applyAppearance(a: Appearance, root: HTMLElement = document.documentElement): void {
  root.dataset.mode = resolveMode(a.mode);
  root.dataset.accent = a.accent;
}

// ── a tiny store so the Settings screen and the top-bar toggle share one value ─────────────────────────────────────────
let current: Appearance = loadAppearance();
const listeners = new Set<() => void>();

export function getAppearance(): Appearance { return current; }

export function setAppearance(next: Appearance): void {
  current = { mode: next.mode, accent: next.accent };
  const s = storage();
  try { s?.setItem(APPEARANCE_KEY, JSON.stringify(current)); s?.removeItem(LEGACY_THEME_KEY); } catch { /* private mode */ }
  applyAppearance(current);
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  let mql: MediaQueryList | null = null;
  const onSystem = () => { if (current.mode === "system") applyAppearance(current); };
  try { mql = matchMedia("(prefers-color-scheme: dark)"); mql.addEventListener("change", onSystem); } catch { mql = null; }
  return () => { listeners.delete(l); mql?.removeEventListener("change", onSystem); };
}

export function useAppearance(): [Appearance, (a: Appearance) => void] {
  return [useSyncExternalStore(subscribe, getAppearance, getAppearance), setAppearance];
}

/** At start-up: re-read storage and apply it. A pre-refresh theme is migrated once and saved under the new key, so from the
 *  next load on index.html applies it before the first paint. */
export function initAppearance(): Appearance {
  const s = storage();
  let migrate = false;
  try { migrate = !!s && s.getItem(APPEARANCE_KEY) == null && s.getItem(LEGACY_THEME_KEY) != null; } catch { migrate = false; }
  const a = loadAppearance();
  if (migrate) setAppearance(a);
  else { current = a; if (typeof document !== "undefined") applyAppearance(current); }
  return current;
}
