# Next Session

## Start Here

Read:
1. `AGENTS.md`
2. `CURRENT_STATE.md`
3. `ARCHITECTURE.md`
4. `RAG_E2E_CHECKLIST.md` (next unchecked gate: E1)

## Last Completed

- Phase H v1.1 — boundary corpus (33 items, frozen `3ee7065a…`) +
  rerun: hybrid **REJECT** as production default (Δcorrect +1,
  Δincorrect +4, Δmissed −4). Evidence: `eval/phase_h/REPORT_v1.1.md`.
- Bootstrap continuity system — `AGENTS.md` §0 (Mandatory Bootstrap),
  `CURRENT_STATE.md`, `NEXT_SESSION.md`, `RAG_E2E_CHECKLIST.md`.

## What Was Validated (at checkpoint)

- 77 unit tests passed / 15 skipped; 12 integration passed / 2 skipped.
- All three guards green (preflight / repo guard / wiki worm).
- Frozen hashes re-verified: relations_v1 `fdfd75b4…`, relations_v1.1
  `3ee7065a…`, resource contract `03a513ec…`, tables `0ac3002a…`,
  compiled lexical `5c58adbd…`.

## Current Verified Commit

- branch: `main`
- commit: `3ada0af` (+ checkpoint commit from this handoff)

## Current Blockers

- **No git remote for polymath-v4.** `git remote -v` is empty; the
  GitHub account `Kingsley-Cyber` has `polymath_v3.3` but no
  `polymath-v4` repository. Pushing requires either creating the repo
  (public/private decision) or a user-supplied remote URL. Do NOT
  invent one.

## Next Unchecked RAG E2E Gate

**E1** — run the two measured extraction experiments SEPARATELY on the
frozen v1.1 corpus, each as a before/after delta:
1. class-expanded triggers require resolved-roleset compatibility;
2. the FN anchor filter must not exclude on composed-only frame
   mismatch.
Report Δ-correct / Δ-incorrect per experiment. Promote hybrid only on
a measured precision-first pass.

## Do Not Do

- No production extraction changes without a measured delta.
- No edits to `eval/gold/relations_v1.yaml` / `relations_v1.1.yaml`.
- No G3/G4/G5 until E1 is decided.
- No fuzzy SemLink joins; no composed-as-direct attestation.
- Do not create a GitHub remote or run `docker system prune` without
  explicit approval.

## Verification Before Work

```bash
git status --short && git rev-parse HEAD
make guards
.venv/bin/python -m pytest tests -q
shasum -a 256 eval/gold/relations_v1.1.yaml   # expect 3ee7065a…
```

## Notes Requiring Attention

* Qdrant for this repo is on 6334; the live v3.3 stack on 6333/7474 is
  off-limits.
