# Next session — handoff

> **FRESHNESS 2026-08-30 (LIVE POINTER):** superseded. Start from
> `docs/wiki/plans/CONTINUITY-PACKET-2026-08-30.md`, then `CLAUDE.md`.
> The bootstrap commands below still hold; the "where I stopped" section
> describes 2026-08-22 and is kept for history only.

**Date:** 2026-08-22 · **Branch:** `architecture/evidence-first-v5` ·
**HEAD:** `f655c07`

Read `POLYMATH_V5_RELEASE_BASELINE.md` first. It is the frozen state and
the work order. Then `AGENTS.md` §5 for the directory map.

---

## Bootstrap (do this before touching anything)

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4
git status && git log --oneline -8

# 1. the fleet must be up for the full suite (5 test files need GLiNER)
POLYMATH_PROFILE=pipeline nohup bash scripts/boot_polymath.sh > /tmp/polymath_fleet/boot.log 2>&1 &
# wait for 8740/8742/8744 to answer /ready

# 2. these three are the source of truth about state — never a document
.venv/bin/python shared/polymath_shared/bundle_integrity.py       # must print READY
.venv/bin/python eval/v5/implementation_plan.py                   # live plan
.venv/bin/python -m pytest tests/ -p no:cacheprovider             # 828 passed expected
```

`POLYMATH_PG_DSN=postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath`
must be exported for most eval scripts — the settings default resolves
elsewhere and will hang on a pool timeout.

---

## Where I stopped, precisely

Mid-way through **Phase 1 (predicate compiler repair)**, step 6 of 7.

Steps 1–5 are **done and committed**. Step 6 (shadow comparison) was
partly run; the re-extraction that would populate the newly recorded
trigger provenance **was not run** — the user interrupted before it.

**The immediate next command** is to re-extract `core-3-v1` so the
provenance fix in `f655c07` actually populates, then read which triggers
license the surviving candidates:

```bash
# fleet up under POLYMATH_PROFILE=pipeline first
.venv/bin/python - <<'PY'
import psycopg
with psycopg.connect("postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath") as c:
    c.execute("DELETE FROM relation_candidates rc USING documents d "
              "WHERE d.doc_id=rc.doc_id AND d.corpus_id='core-3-v1'")
    c.execute("DELETE FROM fact_admission_decisions WHERE corpus_id='core-3-v1'")
    c.execute("UPDATE stage_tickets SET status='ready',attempt=0,lease_owner=NULL,"
              "lease_expires_at=NULL,generation=generation+1 "
              "WHERE corpus_id='core-3-v1' AND stage='extract'")
    c.commit()
PY
# ~3 minutes, then:
#   SELECT subject_surface, predicate, object_surface, trigger_surface
#     FROM relation_candidates rc JOIN documents d USING(doc_id)
#    WHERE d.corpus_id='core-3-v1' AND rc.decision='ACCEPT';
```

**The open question that block answers:** `skill --similar_to--> users`
survived the compiler repair. `similar_to` now compiles to only
`mirror, parallel, resemble` — so something else licensed it. My
hypothesis, unverified: the `multiword` arm, which carries **`like`** —
authored, not VerbNet-inherited, and wildly ambiguous between
preposition and verb. The provenance fix exists specifically so the next
agent can *see* the trigger instead of guessing. **Do not act on that
hypothesis without reading the data.**

---

## What changed this session

| commit | what |
|---|---|
| `90f5122` | SEMANTIC-RUNTIME-INTEGRITY-V1 — bundle lock, boot gate, contract tests |
| `7946783` | one implementation of the rule-pack check |
| `7cd7059` | **A3** — wired F1–F8 as the last court before assertion |
| `2e41a44` | F1–F8 proven on the bench; F3 refuses what the compiler cannot see |
| `9254840` | **Phase 0 freeze** — `POLYMATH_V5_RELEASE_BASELINE.md` |
| `41a7ab8` | **Phase 1** — VerbNet suggestion-only; 337 → 112 triggers |
| `f655c07` | trigger provenance recorded (34,655 rows had NULL) |

Earlier the same session: MPS budget defects, Metal pool pinning, claim
starvation, two control-plane defects, E6 inventory, A2 (E1–E7 wired).
See `docs/FORENSIC_2026-08-22_RUNTIME_BUDGET.md`.

---

## Live state

```
plan          8 done · 10 open · 1 blocked · 0 unknown
tests         828 passed, 68 skipped
integrity     READY
bundle        v5-production-002
rule pack     1.3.0  (declared == loaded, boot-enforced)
```

Both admission chains are **wired and in SHADOW**:

```
POLYMATH_ENTITY_ADMISSION_ENFORCE   unset (0)
POLYMATH_FACT_ADMISSION_ENFORCE     unset (0)
```

Shadow means they run, record every decision, and change nothing.

---

## The three numbers that matter

**1. Under enforcement, `core-3-v1` produces an EMPTY T2 graph.**
Last measured: PASS 0, QUALIFY 7, REJECT 22. QUALIFY is never asserted
knowledge (R4). Consistent with the book corpus (94% of the pool
refused, 1,521 → 69 facts). The gates are precise; the recall cost is
severe. **This is a decision the owner must make before anything flips
`ENFORCE=1`.** Do not flip it unilaterally.

**2. Entity admission's net effect is currently zero.** 0 of 148
durable entities on core-3 would be demoted; all 298 refusals are
entities Harbor had already made non-durable. E1–E7 is re-asserting an
upstream decision, not adding one.

**3. The pronoun class dies at F3, not at E7.** 26 of 36 facts refused
`ENDPOINT_SUBJ_NOT_DURABLE`. Wiring E1–E7 does **not** remove pronoun
endpoints, because pronouns are already `MENTION_ONLY` as *entities*
while the relation layer uses their *surface*.

---

## Remaining Phase 1 work

- **step 6** — finish the shadow comparison (command above)
- **step 7** — evaluate recall only after precision is understood

Then Phase 2 (entity contract), Phase 3 (RelationCandidate fail-closed
contract), Phase 4 (4-document stress corpus), Phase 5 (acceptance
gates). All specified in `POLYMATH_V5_RELEASE_BASELINE.md`.

---

## Traps that cost me hours today

**Do not trust a document about state.** Three times a document asserted
something the runtime contradicted: rule pack v1.3.0 declared frozen
while v1.2.0 ran; two gate chains reported "qualified" with zero
production callers; shadow numbers quoted as production behaviour. Run
`bundle_integrity.py` and `implementation_plan.py` instead.

**A test that fails when the system is corrected is asserting
yesterday's config.** I hit this four times: a hardcoded version→filename
map, a guard test iterating a hardcoded subset of sidecars, a probe with
its own copy of a regex, and `test_class_member_absent_from_manual_
triggers_is_found` which asserted the *defect* as a requirement. Derive,
don't hardcode.

**Verify a subagent's findings before acting.** A research agent
reported rescue.py "destroys upstream evidence". Reading the ledger,
`span_hypotheses` holds 44,071 `REJECTED/SUPPRESSED_SOURCE` rows with
offsets — evidence survives; only argument-binding participation is
lost. Acting on the report would have been acting on a false premise.

**I made this mistake myself an hour later.** Seeing `trigger_surface`
NULL on all 34,655 rows, I concluded "candidates are licensed by
evidence class alone". Wrong — `_trigger_matches` validates
`trigger_lemma`; the field was missing from the *ledger*, not the
*logic*. Had I "failed closed on missing trigger", I would have rejected
100% of candidates.

**Shadow mode earns its keep.** It caught two of my own wiring bugs
before either governed anything: E3 given slice text where offsets are
chunk-absolute (359 false rejections), and F1 given the wrong accessors
(`candidate.evidence.trigger_lemma`, not `candidate.trigger_lemma` —
all 36 facts refused as MISSING_INPUT). Both times the gate was right
and my caller was wrong.

---

## Do not

Replace GLiNER · add LLM extraction · add REBEL · add generative
relations · re-enable VerbNet class expansion · flip either `ENFORCE`
flag without the owner's decision on recall · ingest the sealed holdout
to tune · modify `eval/i4/gold/` or `eval/admission/artifacts/` ·
mutate a frozen contract in place (supersede with a new version) ·
run the full fleet (19.45 GB > the 19 GB allocation — use a profile).

## Operational notes

- Profiles: `pipeline` 15.15 · `retrieval` 13.30 · `converge` 9.90 ·
  `projection` 9.30 · `graph` 5.75 GB. Full fleet does **not** fit.
- `release-books-v1` is paused at 24/25 query_ready, checkpoint intact.
- Docker VM is 5 GB; if the daemon 500s, check a VM process actually
  exists before assuming it is slow to start.
- Boot recovery is still broken: the LaunchAgent points into
  `~/Documents`, which macOS TCC blocks (exit 126). `gate_boot_recovery`
  fails by construction.
