---
change_id: SERVED-PROFILE-LABEL
owner: "@king"
date: 2026-10-01
status: complete
status_note: "'vNext' in the labels now means the document card SEARCH serves, read from the profile index — not the latest card written. Cinema (vNext card written on 77 / 77 files, served on 0) reads amber 'Searchable · basic profiles', its files 'Ready · basic profile', its Control Plane 'ready (vNext) 0'. The written-card fields and the vNext verdict are unchanged. Live after the deploy."
architecture_impact: "shared/polymath_shared/document_profile/served.py (new: the served card per file, read-only, fail-open); orchestrator/orchestrator/api/ui.py (/documents/summary profile_served, /documents/{id}/status served + corrected projected, /control_plane served); orchestrator/orchestrator/api/health.py (/semantic_readiness vnext.vnext_served); shared/polymath_shared/control_plane_status.py (summary vnext_served, basic_profile from it); shared/polymath_shared/document_status.py (profile.compiled_hash); frontend-v2 lib/readiness.ts (servesVnext, servedWriter, docVnext, vnextReady), lib/contracts.ts, screens/Files.tsx, screens/ControlPlane.tsx; tests."
last_reviewed: 2026-10-01
---

# SERVED-PROFILE-LABEL: "vNext" means the card search uses

## Contract
- The owner, 2026-10-01, after learning cinema's green "vNext complete" badge counted vNext cards that search does not use:
  "yes fix the cinema badge so this confusion doesnt happen i dont want worse commit ensure code is working latest and
  greatest".
- Measured before the change (read-only: the app's API and the profile index): cinema's latest card is the vNext card on
  77 / 77 files, but the profile index serves the BASIC card on 77 / 77 (~30 questions + searches each; the vNext cards have
  2–6: the CANONICAL-PROFILE-SELECTION-V1 guard kept the richer cards, `kept_last_known_good`); the two giant books also carry
  vNext-written SECTION cards (72 and 25). `social-media-taste` 21 / 21 and `commerce-v1` 10 / 10: basic, served.
- Constraint "no worse commit": no gate, retrieval path or pipeline reads the vNext flags (only two verification scripts and
  the screens), so the written-card fields stay byte-identical and only the LABELS change.

## Changes
- **`document_profile/served.py`** (new, read-only, fail-open): `served_profiles(corpus)` scrolls the profile index for the
  corpus and returns each file's DOCUMENT card writer (`doc-profile-vnext-*` = vnext, else basic; section cards excluded);
  None when the index cannot be read, and every caller then keeps its old label. `apply_served`, `served_vnext_count`.
- **API** (labels only): `/documents/summary` adds `profile_served`; `/semantic_readiness` adds `vnext.vnext_served` (off the
  event loop); `/control_plane` passes the served map in — the summary adds `vnext_served` and counts `basic_profile` from it
  (`semantic_ready`, written cards, unchanged); `/documents/{id}/status` adds `profile.served` and sets `profile.projected` to
  "the latest card is the served card" (compiled hashes) — it read "the card is valid", so a refused card showed projected.
- **UI**: a file is "Ready" (vNext) only when search serves its vNext card, else "Ready · basic profile" with the reason
  (written but kept out by the guard / none built); the Profile column shows the served card's writer ("basic" with "a vNext
  card was written" in its title); the library card is green only when search uses the vNext cards on every file — cinema
  reads amber "Searchable · basic profiles" ("vNext cards written for 77/77 files · search uses 0"); Control Plane "ready
  (vNext)" = files served by vNext. Without the index's answer (older backend, index unread) every label keeps the old basis.

## Proof
- `tests/contracts/test_served_profile_label.py` (5): the reader pages the index, drops section cards and doc-less points,
  leaves an injected client open, returns None when the index fails; labels are added only when the index answered;
  `/documents/summary`, `/documents/{id}/status` (refused card → projected false, served basic; used card → projected true;
  index unread → unchanged) and `/semantic_readiness` (verdict and `vnext_profiles` unchanged, `vnext_served` beside them)
  through FastAPI with the stores faked. `test_control_plane_status` +1 (served basic → ready (vNext) 0, basic 2, semantic_ready
  unchanged; no answer → previous counting).
- UI +5 (`files-states.test.tsx` +3, `control-plane-summary.test.tsx` +1, one updated detail line): the cinema case reads amber
  with the counts; a written-but-unused vNext card reads "Ready · basic profile" and "basic"; a served vNext card and an older
  backend still read "Ready" / green. vitest 171 passed (24 files), `tsc` clean.
- The real reader against the live profile index from this branch (read-only): cinema 77 basic (555 ms cold), taste 21 basic,
  commerce 10 basic (18 ms each) — the counts measured by hand.
- Fail first on the deployed code (`1880530b`): the 4 UI tests of the new behaviour failed (13 unchanged passed); the backend
  test cannot load there (the reader does not exist).
- A sealed reproduction of CI on this tree (both workflows' steps; throwaway Postgres with every migration; git and curl present;
  nothing else reachable): contracts **867 passed**, 5 skipped, 1 failed = the code-wiki check on a snapshot taken before this
  slice's wiki refresh (18 / 18 on the refreshed tree); determinism **3,289 passed**, 35 skipped, 1 failed = the container's own
  trusted-login artifact (passes on GitHub). Code wiki refreshed: 2,235 / 2,235 on 342 pages.

## Contract impact (pre-commit)
- EVIDENCE_BOUNDARY_API [live] and PROFILE_SCOUT_WIRING [live] (their spec families include `api/ui.py`): NOT_AFFECTED —
  the ui.py changes are confined to `/documents/summary`, `/documents/{id}/status` and `/control_plane` (labels); the evidence
  route and the profile scout are untouched. Transitive (ACCEPTANCE, ADAPTER_RUNTIME, CANDIDATE_ENGINE, EVIDENCE_PACKET,
  MCP_SURFACE, PROFILE_YIELD_RECEIPT, QUERY_PLANNER, RESOLUTION_STATE, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE): TESTED_UNCHANGED —
  every listed file ran in the sealed reproduction above and passed.

## Rejected claims
- "Cinema runs on vNext": it has vNext cards; search serves the basic ones.
- "Change the vNext verdict instead": it counts written cards and two verification scripts read it; the served count rides
  beside it, so nothing that reads the verdict changes.

## Open contract gaps
- The vNext writer still produces thin cards (2–6 direct surfaces against ~30); until it is fixed, the guard keeps the basic
  cards and no library turns green honestly.
