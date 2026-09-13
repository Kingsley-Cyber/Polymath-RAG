---
title: "WORK LOG — FRONTEND-V2-PARITY-02: Models screen, corpus delete, and the themed selector"
change_id: FRONTEND-V2-PARITY-02
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.247
architecture_impact: "frontend-v2 only, over backend contracts that already exist (GET/POST/DELETE /llm/providers, POST /llm/test, DELETE /corpora/{id}). Wires the legacy `/ui` Models screen into V2, adds a corpus-delete control, and fixes the native <select> popup rendering black off-theme. No backend change, no schema change."
---

> Owner, viewing the live URL: "there's no way to delete a corpus … and the selector is
> black and doesn't work with the theme." Both are V2 gaps against the legacy `/ui`, and
> both backends already exist.

## Contract

§23 frontend: V2 must be a working, backend-integrated replacement for the legacy `/ui`.
Legacy has Models and corpus management; V2 lacked both, and its selector mis-rendered.

## Changes

**1 — the selector rendered black off-theme (bug).** Root cause: nothing set
`color-scheme`, so the browser drew the native `<select>` dropdown popup (and scrollbars)
in the OS default — black — regardless of the active palette, worst on the light themes
(slate/paper/champagne). Fix: `color-scheme: dark` on `:root`, `color-scheme: light` on
the three light palettes, `<option>` styled with theme tokens, and the closed control
moved to `--bg-raised` with a themed hover border. Verified in the served CSS:
`color-scheme:dark` and `color-scheme:light` both present.

**2 — corpus delete (feature).** `DELETE /corpora/{id}` already wipes a corpus and
everything derived (PG, Qdrant collection, Neo4j substrate) and requires
`confirm==corpus_id`. Added `api.deleteCorpus` and a "Delete corpus" control under the
sidebar selector that makes the owner TYPE the corpus name (matching the backend guard),
then refetches the corpus list and switches to another corpus. A typed confirm, not a
one-click wipe.

**3 — Models screen (parity).** Legacy `/ui` has a Models screen V2 lacked. Wired the
screen (built earlier, previously unattached) into the nav and router: it lists the
configured LLM providers from `GET /llm/providers` (never showing a raw key — only the
last 4 chars or the `env:NAME`), tests a model via `POST /llm/test`, adds/updates a
provider via `POST /llm/providers` (an empty key keeps the stored one), and deletes one
via `DELETE /llm/providers/{id}`.

## Proof

**Build + guards.** `tsc && vite build` clean (52 modules), vitest proxy-coverage guard
green (`/llm`, `/corpora` already proxied).

**Live at the origin the proxy fronts:**
- served bundle `index-BPFxW3wn.js` contains "Add / update a provider", "Save provider",
  "LLM providers the chat", "Delete corpus"; served CSS carries `color-scheme` dark+light;
- `GET /llm/providers` → 3 providers (anthropic 9 models/ready, openai 8/ready,
  ollama 2/not-ready) — the Models screen has real data.

**Corpus delete proven end-to-end with ZERO impact on real corpora:**
- guard: `DELETE /corpora/rag-canary?confirm=WRONG` → **422** (rag-canary untouched);
- round-trip on a throwaway: upload created `zqx-corpusdel-probe` → present →
  `DELETE ?confirm=zqx-corpusdel-probe` → **200** → gone. No real corpus was deleted.

## Rejected claims

- **"Delete a real corpus to prove it."** Rejected — that destroys owner data. A
  throwaway create→delete proves the exact wiring at zero cost, and the wrong-confirm
  422 proves the guard on a real corpus without touching it.
- **"The selector just needs a darker background."** Rejected: the closed control was
  already themed; the black was the NATIVE popup, which only `color-scheme` controls.
- **"Ship the Models screen unwired."** Rejected: it was sitting as dead code in api.ts/
  contracts.ts; wiring it into the nav makes the slice coherent and gives V2 the screen
  legacy has.

## Open contract gaps

- Corpus CREATE is still implicit (first upload to a new corpus_id); no explicit "new
  corpus" form in V2 yet. Delete is the destructive half the owner asked for.
- The `window.prompt`/`window.confirm` dialogs are deliberate for a tight slice; inline
  modals are a later polish.
- Safari aggressively caches; the entry doc is already `no-cache, no-store`, so a fresh
  load / private window shows the new bundle — nothing more to do server-side.
