---
title: "WORK LOG — FINAL-STATE-VERIFIER-V1 (one re-firable command for every REQUIRED FINAL STATE gate) and the stale acronym heuristic that had deadlocked the pronoun-endpoint gate"
change_id: FINAL-STATE-VERIFIER-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.231
architecture_impact: "additive: one new read-only verifier script. Two bug fixes in existing governance scripts (retire_claim_sets.py census self-match; retire_pronoun_facts.py acronym floor). No production data mutated, no schema change, no retrieval/extraction behaviour touched."
---

> A Stop-hook rejection listed seven REQUIRED FINAL STATE items as having "NO EVIDENCE".
> Several were in fact measured earlier this session — but scattered across a dozen
> work-logs, which makes "is it done?" a reading exercise rather than a measurement. §17
> asks for re-firable proof. So rather than re-argue, this slice makes the answer one
> command — and running it immediately found three real defects, two of them in code
> written earlier in this same session.

## Contract

Requested outcome: a single re-firable command that evaluates every REQUIRED FINAL STATE
line against live state, with honest per-gate verdicts.

- **Smallest acceptance:** it runs read-only, reports PASS/FAIL/BLOCKED_OWNER/NOT_TESTED
  per gate, never counts NOT_TESTED as green (§18), and re-fires identically (§17).
- **Verifier / rollback:** the script is the verifier; it writes nothing.

## Changes

- `scripts/verify_final_state.py` — NEW. Fourteen gates, all observed live:
  fires `/retrieve` for HYBRID/GRAPH/WILDCARD and asserts ONE engine across all three
  plus truthful requested/executed mode · runs the standing guard that `/chat`'s core
  never reaches the legacy retrieval functions · reads the live readiness triad ·
  `EXPLAIN`s the hot `_graph_provider` query and asserts no TOAST/payload access ·
  `EXPLAIN`s the outbox join and asserts no `Seq Scan on outbox_events` · re-fires both
  shadow-parity scripts · runs the §12 legacy census · re-proves the `claim_sets`
  retirement · checks the public cutover redirect and the V2 entry cache headers ·
  checks `HEAD == upstream`. Exit 0 only when nothing FAILs; BLOCKED_OWNER and
  NOT_TESTED are reported distinctly and never as green.

**Three defects the first run found — all real, two of them mine from earlier today:**

1. `retire_claim_sets.py` refused to run. Its census used `git grep -l claim_sets`, which
   matched its OWN FILENAME (`retire_claim_sets.py`) wherever the script is registered —
   so the act of registering the tool made it permanently report "still referenced" and
   decline. Fail-closed was the safe direction, but it would have blocked a legitimately
   authorized deletion forever. Fixed with `git grep -lw` (word boundary: `_` is a word
   character, so `retire_claim_sets` no longer matches `claim_sets`) plus `scripts/README.md`
   in the allow-list, since that entry necessarily describes the table it retires.
2. The verifier's own `hot_path_readers_cut_over` gate reported FAIL against correct code:
   it scanned `_graph_provider`'s raw source for `llm_extraction`, and the function's
   DOCSTRING legitimately names the old `payload->'llm_extraction'->'stats'` expression to
   explain what it replaced. Fixed by stripping docstrings and comparing CODE only — the
   same docstring-self-reference false positive already fixed once this session in the
   conformance census (11.218), recurring in a new place.
3. The verifier reported the public URL gate as FAIL (HTTP 403) while `curl` got a clean
   302. Cloudflare 403s the default `Python-urllib/3.x` User-Agent as a bot. A CDN
   challenge means "could not observe the origin", NOT "the origin is wrong"; collapsing
   those two is exactly how a false red gets reported as fact. Fixed with a browser UA
   and an explicit NOT_TESTED branch for CDN challenges.

**The pronoun-endpoint deadlock, resolved (`scripts/retire_pronoun_facts.py`):**

Register 11.226 named this failure owner-gated and recommended BUILDING a cleanup tool.
That recommendation was wrong in one respect worth recording: the tool already existed —
`scripts/retire_pronoun_facts.py`, dry-run by default, registered since before this
session. Running it revealed a genuine contradiction between two gates enforcing the same
invariant:

- `test_no_active_fact_has_a_pronoun_endpoint` → "1 pronoun surfaces are live fact
  endpoints: ['you']"
- the retirement tool → "pronoun-endpoint facts: 0" (nothing to do)

Root cause: entities store only the lowercased surface, so the tool consults `mentions`
(which keep raw casing) and protects any surface ever seen ALL-CAPS — a sound safeguard,
since "US"/"IT"/"WHO" would otherwise be destroyed. But it protected on a SINGLE
occurrence, and the justification in its own comment ("MEASURED in this corpus: US
appears 49x, IT 6x, WHO 10x") is **stale**. Re-measured live:

```
us -> 0 mentions   who -> 0   one -> 0
it -> 1 ("IT")     they -> 1 ("THEY")   you -> 1 ("YOU")
```

Every surface it was protecting now has exactly one all-caps mention, so the rule was
protecting styling (a shouted heading), not acronym identity. That is precisely why the
two gates never converged: the test reported a violation the tool then refused to act on.

Fixed with an evidence floor of ≥2 all-caps mentions, the stale comment replaced by the
re-measured numbers, and the affected surfaces printed before any write. Dry-run now
reports **3** pronoun-endpoint facts (`it`, `they`, `you`) instead of 0.

**Residual ambiguity, stated not hidden:** with one occurrence, "IT" cannot be
distinguished from the pronoun "it" shouted in a heading. The floor makes the tool
WILLING to retire it; `--apply` still performs the write, so the judgement stays with the
owner.

## Proof

- **Verifier, RUN 1 → RUN 2, same entrypoint, no edits between (§17): identical.**
  Final state: **13 PASS · 1 BLOCKED_OWNER · 0 FAIL**, exit 0.
  The one BLOCKED_OWNER is `dead_proven_removed` — `claim_sets` re-proven live (0 rows,
  0 lifetime writes, 0 code references) with the DROP left to the owner.
- `frontend_public_url_serves_v2` → PASS: `https://rag.kingsleylab.xyz/ → HTTP 302,
  location='/v2/'`.
- `retrieval_core_one_engine` → PASS: all three public modes report
  `candidate-retrieval-v1` — one engine, measured by firing them, not inferred.
- `shadow_parity_*` → PASS: both scripts re-fired, 100% / 0 mismatches.
- `retire_pronoun_facts.py` dry-run: 32,222 facts examined, 3 pronoun-endpoint facts, 95
  already retired. **Nothing applied** — the data is unchanged, and
  `test_fact_endpoint_eligibility.py` therefore still fails, correctly.
- Guards: `agent_preflight` ok · `repo_guard` ok.

## Rejected claims

- **"Re-argue the hook's list of un-evidenced gates."** REJECTED — scattered prose is
  weak evidence even when accurate. One command that anyone can re-run is stronger than
  any argument, and it found three defects that arguing would not have.
- **"Build a pronoun cleanup tool."** REJECTED once the repo was actually checked: it
  already existed. 11.226's recommendation to build one was a failure to look first.
- **"Apply the pronoun retirement now that the tool works."** REJECTED — it mutates
  live `facts.decision` on production rows; §1 reserves that. The heuristic fix and the
  dry-run are the safe half; `--apply` is the owner's.
- **"Lower the ≥2 floor to 1 so nothing is unprotected."** REJECTED — that is the old
  behaviour, and it is what deadlocked the gate. A single all-caps occurrence of a
  closed-class pronoun is styling, per the re-measured data.

## Open contract gaps

- `test_no_active_fact_has_a_pronoun_endpoint` still FAILS, correctly: the data is
  unchanged. It clears the moment
  `scripts/retire_pronoun_facts.py --apply` runs with owner authorization — now a
  one-command action against exactly 3 facts, rather than an open investigation.
- `claim_sets` DROP remains owner-gated (`scripts/retire_claim_sets.py --execute`).
- The authenticated in-app click-through at the PUBLIC host still needs the Caddy
  password; the verifier reports the redirect and cache headers, which is everything
  observable without it.
