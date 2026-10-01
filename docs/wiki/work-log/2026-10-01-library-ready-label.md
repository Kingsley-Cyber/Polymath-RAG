---
change_id: LIBRARY-READY-LABEL
owner: "@king"
date: 2026-10-01
status: complete
status_note: "A library whose files are all searchable on the basic profile no longer reads red: the Files / Overview vNext card says 'Searchable · basic profiles' (amber) and the Control Plane summary counts those files as ready (basic profile), not blocked. Same commit: GNN-DEGRADED-LIST — a GNN turn on a library without its GNN index answered 500; it now answers with a typed degradation. LIVE at 438e4af8 (deployed, pushed, proven through Cloudflare)."
architecture_impact: "shared/polymath_shared/control_plane_status.py (summary: basic_profile; blocked = not searchable); shared/polymath_shared/semantic_readiness.py (vnext.profiled, display-only); orchestrator/orchestrator/api/chat_retrieval.py (_retrieve_gnn appends to meta.degraded); frontend-v2 lib/readiness.ts (vnextReady), lib/contracts.ts, screens/ControlPlane.tsx; tests."
last_reviewed: 2026-10-01
---

# LIBRARY-READY-LABEL: a searchable library is never red (+ GNN-DEGRADED-LIST)

## Contract
- The owner, 2026-10-01: "why is a corpus for taste showing files as red i used heremes to upload the files", then "yes" (the
  badge fix) and "do the files have pmap ? and adhere to current codes retrieval and index?".
- The answer, from the app's own read-only API and the code (no direct database reads):
  - `social-media-taste`: 21 files, 21 / 21 runs `query_ready`, SEMANTIC_COMPLETE (21 document summaries, 152 parent summaries,
    229 accepted facts, 108 procedures, 29 concepts, extraction coverage ok, no failures or warnings).
  - pMAP complete: 150 / 150 eligible parents mapped, 2 excluded, 0 unresolved; every file has a profile (the BASE profile);
    0 / 21 have the vNext profile — by design since 2026-09-17 (`POLYMATH_DOC_PROFILE_VNEXT=0`), whatever the upload path.
  - Current code: nothing under `workers/`, `control/` or the ingestion parts of `shared/` changed after the upload
    (2026-09-30 05:00); the only later `shared/` changes are the adapter evidence boundary, the MCP tool module and receipts.
  - Retrieval, every mode on the library: FAST / HYBRID / GRAPH / WILDCARD ok (24 evidence each, 7–8 files; GRAPH 6 attested
    facts, WILDCARD 3 picks); a direct search returned matching passages from 3 files in 4.4 s. GNN: no GNN index for this
    library (it is built offline per library) — and the GNN turn answered **500** (below).
- What was red: the Files / Overview "vNext ready" card (`VNEXT_INCOMPLETE`, red for any verdict but COMPLETE) and the Control
  Plane summary ("blocked 21", "semantic ready 0"): both still used the rule FILES-READY-LABEL (11.554) had retired for the
  file labels — "no vNext profile = blocked". Each file's own label already read "Ready · basic profile".

## Changes
- **Control Plane summary** (`control_plane_status`): the per-file rule — mapped + ANY profile = searchable. `blocked` = files
  retrieval would miss part of (unresolved parents or no profile); new `basic_profile` = searchable without the vNext profile;
  `semantic_ready` (vNext-ready files) unchanged; the three add up to `documents`. The screen's labels say what they count:
  "ready (vNext)", "ready (basic profile)", "blocked" (red only above 0).
- **The vNext card** (`vnextReady`): VNEXT_COMPLETE green as before; every parent mapped AND every file profiled → amber
  "Searchable · basic profiles" with "x/y files have the vNext profile · m/e parents mapped"; anything else (unresolved
  parents, an unprofiled file, an older backend without the count) keeps the red verdict.
- **`semantic_readiness.vnext_readiness`** adds `profiled` (files with any profile) in its OWN guarded read: the vNext verdict —
  which gates the QUERY_READY flip and the cutover — is untouched, and a failed count is `None`, never another verdict.
- **GNN-DEGRADED-LIST**: `_retrieve_gnn` assigned `meta.degraded` a dict; everywhere else it is a list of
  {component, code, message} (`_attach_graph`, the composer), and `ui.py:4235` iterates it — iterating a dict yields its keys,
  so `'str' object has no attribute 'get'`. Every GNN turn whose route nominated nothing (a library without its GNN index)
  answered 500 on `/chat`, `/chat/stream` and `/chat/evidence` (agent search). The degradation is now appended to the list.

## Proof
- Backend (fakes, no database): `test_control_plane_status` (+1: vNext / basic / unprofiled files counted 1 / 1 / 1, the three
  add up; the existing expectation gains `basic_profile: 0`); `test_vnext_readiness_report` (`profiled` reported, verdict
  unchanged; a failed count leaves the verdict COMPLETE and `profiled` None); `test_chat_runtime` +1: a real runtime GNN turn
  with no candidates answers 200 on `/chat/evidence` (empty packet, the gnn_route degradation in the list) and on `/chat`.
- UI: `files-states.test.tsx` +3 (amber "Searchable · basic profiles" with the counts in its title; unresolved parents / an
  unprofiled file / an older backend stay red; COMPLETE stays green); `control-plane-summary.test.tsx` (new: "ready (basic
  profile)" 21, "blocked" 0 and not red). vitest 167 passed (24 files), `tsc` clean.
- Fail first on the deployed code (`a288c0f7`): the GNN turn answered 500 (reproduced in the runtime harness, the line located);
  the two UI tests of the new behaviour and the backend summary tests failed; the unchanged-behaviour UI tests passed.
- A sealed reproduction of CI on this tree (both workflows' steps; throwaway Postgres with every migration; git and curl present;
  nothing else reachable): contracts **863 passed**, 5 skipped, 0 failed; determinism **3,288 passed**, 35 skipped, 1 failed =
  `test_wrong_credentials_fail_at_startup_with_a_code`, the container's own artifact (its database trusts a login on its own
  127.0.0.1; it passes on GitHub). Code wiki refreshed (the 4 changed units, the chat-turn flow): 2,229 / 2,229.

- **Live, after deploying `438e4af8`** (merge, UI build, bounce READY 26 / 13 / one bundle, push; local = origin =
  `438e4af8`, bundle READY): `social-media-taste` — vNext verdict still `VNEXT_INCOMPLETE` (the gates are unchanged) with
  `profiled` 21 / 21 and 150 / 150 parents mapped, so the card reads "Searchable · basic profiles"; Control Plane summary
  `semantic_ready 0, basic_profile 21, blocked 0`. `cinema` — `VNEXT_COMPLETE` (77 / 77), summary `semantic_ready 77,
  basic_profile 0, blocked 0`. `rag.kingsleylab.xyz` serves the new build (`index-CyUHqtL6.js` = the local `dist`, carrying the
  new label). Through the public connector URL: `polymath_search` GNN on the taste library 200 in 1.0 s with the
  `gnn_route` / `GNN_NO_CANDIDATES` degradation (was 500); HYBRID 200, 5 rows.

## Contract impact (pre-commit)
- CANDIDATE_ENGINE [live] (its spec family includes `api/chat_retrieval.py`): UPDATED — `_retrieve_gnn` appends its
  degradation to the `meta.degraded` LIST (the shape every other path writes and every reader expects); no candidate, ranking
  or lane changes. Transitive ACCEPTANCE, PROFILE_YIELD_RECEIPT, RESOLUTION_STATE, RETRIEVAL_RECEIPT: TESTED_UNCHANGED — every
  contracts / determinism file ran in the sealed reproduction above and passed.
- The Control Plane summary (`control_plane_status`) and `vnext_readiness`: additive fields (`basic_profile`, `profiled`) and a
  corrected `blocked`; the vNext verdict, its pending reasons and every gate reading them are unchanged.

## Rejected claims
- "Hermes' upload left the files broken": the files are complete and searchable; any library uploaded since 2026-09-17 shows
  the same vNext state, however it was uploaded.

## Open contract gaps
- The vNext profiles themselves (the green path) are not built for libraries uploaded since 2026-09-17; building them spends
  model calls per file and the vNext index was last judged too thin.
- GNN has no index for `social-media-taste` (or any library it was not trained for); GNN questions there now say so instead of
  failing.
