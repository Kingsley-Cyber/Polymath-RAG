---
change_id: AUTORESEARCH-R1-REPIN
owner: "@king"
date: 2026-09-25
status: complete
status_note: "R1 of AUTORESEARCH-SOURCES-AND-HARNESS-V1: TrailSignal's two short-video comment source rows (ADR-070, HR7) re-pinned into polymath-v4, the three M1 envelopes re-recorded under the owner's word, and the Hermes skill's receipt builder dates each comment by its own date."
architecture_impact: "governance/trail (re-pin: data/source_capabilities.csv + PROVENANCE.json; embedded.py comments / serverInfo) + tests/fixtures/trail_recorded_envelopes (snapshot id re-recorded) + the pins that name the Trail commit (embedding test, recorded-equivalence test, scaffold, ADR-0021 addendum, ARCHITECTURE_CHANGELOG) + adapters/ecommerce/python/adapter_receipt.py (source rows per page + date; video-platform classes). No runtime code in shared / orchestrator / workers."
last_reviewed: 2026-09-25
---

# AUTORESEARCH R1: TikTok and Instagram comments reach TrailSignal as field evidence

## Contract
- Plan of record `docs/wiki/plans/AUTORESEARCH-SOURCES-AND-HARNESS-V1.md` (register 11.489), slice R1 (gaps S-01, S-04).
- TrailSignal ADR-070, accepted by the owner 2026-09-25 ("Accept ADR-070"): two DATA rows, no code.
- The owner, 2026-09-25: "Yes, re-record" (the three M1 envelopes: only the snapshot id and the new rows change; the recorded
  defects stay identical).
- The owner's question "so should it find a video for a comment?" — answered yes: the VIDEO (its canonical link) is the source and
  its date is the comment's own date; the comment is the observation. The receipt builder must not give every comment under one video
  the first comment's date.

## Changes
- **TrailSignal (its own repository, its own gate; not pushed):** `9a26dcb` A47 authorizes node HR7 under ADR-070 →
  `9f5c1ec` HR7 admission anchor → `494905a` HR7: `src-tiktok-comments` and `src-instagram-comments` in
  `data/source_capabilities.csv`, an admission test, the replay fixtures re-recorded. Governor `--check` and
  `--check --base-ref de64d843…` PASS; snapshot `trs-629277494b724295`.
- **The re-pin** (`repin_trail_hr7.py`: `git archive 494905a <30 paths> | tar -x`, every hash checked against the commit's
  blobs): one pinned file changed, `data/source_capabilities.csv` (+2 rows). `PROVENANCE.json` names HR7 and the previous pin.
- **The three M1 envelopes** re-recorded (`rerecord_envelopes_hr7.py`): the requests change ONLY in the snapshot id / content hash
  (`trs-da9942986e52f832` → `trs-629277494b724295`), asserted; M1-02 still raises the same error with the same message; `hypotheses.judge`
  (M1-01, M1-03) identical once the snapshot is normalised; responses changed beyond the snapshot: none (a response's `result_sha256` is the hash of its own result, which carries the snapshot id: the re-recorder asserts that on both recordings and compares the result bodies exactly). Each fixture keeps the
  earlier (ADR-069) re-record in `re_recorded_history`, and each recording keeps its own key order, so the diff shows changed values
  only (+90 / −54 lines over the three files).
- **Pins moved:** `tests/contracts/test_trail_core_embedding.py` (commit), `tests/determinism/test_trail_core_recorded_equivalence.py`
  (heads + docstring), `governance/trail/embedded.py` (docstring, `serverInfo.version`), the scaffold comment, the ADR-0021 addendum,
  `ARCHITECTURE_CHANGELOG.md`.
- **The receipt builder** (`adapters/ecommerce/python/adapter_receipt.py`, the Hermes skill's governed path):
  - a source row per (page, publish date): comments under one video each keep their OWN date (TrailSignal anchors freshness on the
    source's date); the same date shares a row; no item's date is lent to another (the old rule copied a later item's date onto an
    undated one);
  - the source budget counts PAGES (distinct URLs), not rows, and rows stop at the contract maximum (100);
  - `PATTERN_CLASS`: a TikTok video permalink (`tiktok.com/@`) and an Instagram reel / post are `video_platform` (TrailSignal's
    comment rows); a Creative Center link stays `social_trend`; the `instagram` platform is known (before: an Instagram comment was
    omitted as "unknown source class").

## Proof
- EXECUTED, engine suite (`adapters/ecommerce/tests/run_all.py`): 611 / 611 (609 + 2 new: per-date rows and the page budget; the
  video-platform classes).
- EXECUTED, mutation: with the old keying (URL only) three comments under one video all carry the FIRST comment's date
  (`['2026-09-01…', '2026-09-01…', '2026-09-01…']`); fixed: `['2026-09-01…', '2026-09-18…', None]`.
- EXECUTED, harvest → receipt → TrailSignal (`test_comments_under_one_video_keep_their_own_dates_through_trail_admission`): RED at the
  old pin (TikTok comments `SOURCE_STAGE_UNSUITABLE` on `src-tiktok-creative`, the Instagram reel `SOURCE_UNREGISTERED`), GREEN at
  HR7: all three admitted as `video_platform`, each anchored at its own date, groups `tiktok` / `instagram`.
- EXECUTED, the re-pin's suites (worktree PYTHONPATH recipe, no database, `-k "not test_live_"`): `tests/contracts` whole plus the
  29 adapter / MCP / scope / Trail files of the R2–R5 list, plus the Trail core tests. 486 tests, 0 failures, 1 skip (the same
  skip as before, in `test_adapter_harness_action.py`). Among them:
  - the embedding pin (4 / 4 at `494905a`);
  - the embedded core (4 / 4);
  - the recorded equivalence (3 / 3: the re-recorded envelopes replay byte-equal, and M1-02 still raises its error);
  - the engine suite (611 / 611).
- EXECUTED, `live_check.py`'s admission half on the pinned core ($0):
  - a TikTok video permalink routes to `src-tiktok-comments`;
  - an Instagram reel routes to `src-instagram-comments`;
  - a Creative Center link and a short link stay on `src-tiktok-creative`;
  - the comment row serves `field_evidence` with roles behavior / competition / contradiction / friction / workaround.
- Guards: preflight, repo_guard and wiki_worm = 0 before the commit.
- TrailSignal's own agent report (A47 → HR7): the architecture suite 277 passed for both slices; the exact verifier 12 passed; the
  research suite 33 passed; agentctl check / guard / verify / close passed; the measured change HR7 = 5 hand-edited files, 4
  non-test lines, 0 runtime lines.

## Rejected claims
- "One source row per URL is enough": TrailSignal anchors freshness on the SOURCE's date, so every comment under a video inherited
  the first comment's date (a 2024 comment could pass as fresh, a fresh one could be refused as stale).
- "Count the source budget in rows": one video with ten dated comments would spend ten sources; TrailSignal's own budget
  (`gap_compiler`: 4 per registry source) means pages.
- "Copy the video's date onto a comment whose date is not shown": a comment is always later than its video, but its own date is
  unknown; null stays null, and TrailSignal's policy decides.

## Open contract gaps
- TRAIL_GOVERNANCE (the embedded core): UPDATED (re-pin; the embedding test and the recorded-equivalence test moved with it).
- ECOMMERCE_ENGINE (the receipt builder): UPDATED (engine suite + the Trail admission test).
- ADAPTER_RUNTIME, MCP_SURFACE: NOT_AFFECTED (no runtime file changed in this slice).
- Pushes (polymath-v4 and TrailSignal `agent/HR7`) are the owner's word.
