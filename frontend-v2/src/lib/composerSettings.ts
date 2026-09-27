import { useSyncExternalStore } from "react";
import { PUBLIC_MODES, type PublicMode } from "./contracts";

/** HEADER-CONTROLS (owner, 2026-09-27) — the chat's retrieval mode, model and Corpus Explore switch. They are chosen in
 *  the top bar (components/ChatControls) and read by the composer (screens/Chat) when it sends, so one value has to be
 *  shared: a tiny store in the pattern of appearance.ts, kept per browser under ONE key. The stored string is the truth: a
 *  reader re-checks it, so a value cleared or written elsewhere (another window) shows on the next render, and storage that
 *  is unavailable (private mode) keeps the choice in memory for the session. Reasoning and Deep research stay the
 *  composer's own state. */

export interface ComposerSettings { mode: PublicMode; model: string; corpusExplore: boolean }

export const COMPOSER_SETTINGS_KEY = "polymath-v2.chat-settings";
/** As before the move: HYBRID, the backend's default model ("" = nothing picked), Corpus Explore off. */
export const DEFAULT_COMPOSER_SETTINGS: ComposerSettings = { mode: "HYBRID", model: "", corpusExplore: false };

function storage(): Storage | null {
  try { return typeof localStorage === "undefined" ? null : localStorage; } catch { return null; }
}

const isMode = (m: unknown): m is PublicMode => typeof m === "string" && (PUBLIC_MODES as readonly string[]).includes(m);

/** Each field on its own: a malformed one falls back to its default, the others are kept. Never throws. */
function clean(x: unknown): ComposerSettings {
  const o = (x && typeof x === "object" ? x : {}) as Partial<Record<keyof ComposerSettings, unknown>>;
  return {
    mode: isMode(o.mode) ? o.mode : DEFAULT_COMPOSER_SETTINGS.mode,
    model: typeof o.model === "string" ? o.model : DEFAULT_COMPOSER_SETTINGS.model,
    corpusExplore: o.corpusExplore === true,
  };
}

function parse(raw: string | null): ComposerSettings {
  if (raw == null) return DEFAULT_COMPOSER_SETTINGS;
  try { return clean(JSON.parse(raw)); } catch { return DEFAULT_COMPOSER_SETTINGS; }
}

/** The stored string, or undefined when storage cannot be read at all. */
function readRaw(): string | null | undefined {
  const s = storage();
  if (!s) return undefined;
  try { return s.getItem(COMPOSER_SETTINGS_KEY); } catch { return undefined; }
}

// The snapshot: the stored string parsed once, and again only when the string changes (the same reference otherwise, as
// useSyncExternalStore requires). Without storage, `cached` is the value set this session.
let cachedRaw: string | null = null;
let cached: ComposerSettings = DEFAULT_COMPOSER_SETTINGS;
const listeners = new Set<() => void>();

export function getComposerSettings(): ComposerSettings {
  const raw = readRaw();
  if (raw === undefined) return cached;
  if (raw !== cachedRaw) { cachedRaw = raw; cached = parse(raw); }
  return cached;
}

export function setComposerSettings(next: ComposerSettings): void {
  cached = clean(next);
  try { storage()?.setItem(COMPOSER_SETTINGS_KEY, JSON.stringify(cached)); } catch { /* private mode: kept in memory */ }
  cachedRaw = readRaw() ?? null;          // what storage holds now, so a failed write is not re-read over the new value
  listeners.forEach((l) => l());
}

export function updateComposerSettings(patch: Partial<ComposerSettings>): void {
  setComposerSettings({ ...getComposerSettings(), ...patch });
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  const onStorage = (e: StorageEvent) => { if (e.key === null || e.key === COMPOSER_SETTINGS_KEY) l(); };   // another window
  window.addEventListener("storage", onStorage);
  return () => { listeners.delete(l); window.removeEventListener("storage", onStorage); };
}

/** The current settings and a patch function; the top bar's controls and the composer share the value. */
export function useComposerSettings(): [ComposerSettings, (patch: Partial<ComposerSettings>) => void] {
  return [useSyncExternalStore(subscribe, getComposerSettings, getComposerSettings), updateComposerSettings];
}
