---
title: "FRONTEND-V2-PLAN — greenfield Polymath application (owner-approved)"
change_id: FRONTEND-V2-PLAN
owner: governance
date: 2026-09-10
last_reviewed: 2026-09-10
status: ACTIVE
scope: greenfield frontend replacement
backend_architecture: FROZEN
old_frontend: LEGACY / rollback reference
register: 11.199
architecture_impact: "frontend only. No retrieval, ranking, readiness or provider policy changes. New backend CONTRACTS may be added where F0 recorded a gap (GAP-1..GAP-5); no existing contract is altered."
---

# Frontend V2 — plan of record

Owner-approved 2026-09-10 and persisted here because a design that lives only in a session is not an
authority. Supersedes nothing: the legacy `frontend/` stays runnable as the rollback reference.

## 0. Laws

1. **Greenfield.** V2 is built in `frontend-v2/`, beside `frontend/`. **The old frontend is NOT refactored
   into V2** and is not modified except where required to keep it runnable.
2. **Backend architecture is FROZEN.** V2 consumes backend authority. It does **not** reimplement Python
   retrieval, ranking or readiness policy in TypeScript. If a number is not served, that is a backend gap
   (F0 GAP-1…GAP-5) — never UI arithmetic.
3. **Do not wait for cinema.** `rag-canary` is the covered qualification corpus. Incomplete corpora
   (`cinema`: 14/67 vNext-ready) are the **honesty fixtures** — the UI must render incomplete readiness
   accurately, never green.
4. **No secret is ever rendered.** Account ENV NAMES only, as the control-plane contract already enforces.
5. Policy held constant while the application surface is built: `POLYMATH_CHAT_INTENT_POLICY = OFF`,
   `POLYMATH_CHAT_SYNTH_ROLES = OFF`, pMAP auto-mint scoped to `rag-canary`.

## 1. Navigation

```
Chat
Files
Graph
────────
Control Plane
Settings
```

## 2. Chat

Exposed controls: **Corpus · Retrieval (Hybrid / Graph / Wildcard) · Intent · Model · Reasoning · Streaming**.

- **VECTOR is NOT a public mode.** It remains a backend primitive.
- **Intent** is Auto by default. It is *classified by the compiler* and displayed read-only; an explicit
  override appears ONLY if the backend grows an override contract (none today — `POLYMATH_CHAT_INTENT_POLICY`
  is off, so a displayed intent is honest but inert for routing, and the UI must say so).
- Model = `/synthesizers`; Reasoning = `/reasoning_modes` (default `none`); Streaming = `/chat/stream` SSE.

## 3. Query Inspector — backend truth only

Displays: requested mode · executed mode · classified intent · compiler/query plan · retrieval version ·
lane activity · candidate counts · selected evidence · degradation · timings.

**Per lane, four distinct states — never collapsed:**

```
ENABLED          the lane is configured and permitted for this turn
FIRED            the lane actually ran and produced candidates
ENTERED UNION    its candidates reached the merged candidate set
SURVIVED RERANK  its candidates survived the cross-encoder into the final selection
USED IN ANSWER   the answer cites at least one of its chunks
```

**A lane that FIRED did not thereby affect the answer.** This distinction is the point of the screen: U-1
measured additive lanes that fire, enter the union, and never survive rerank. Sources: `lane_sizes`
(fired/size), `arrivals` (per-chunk lane provenance ⇒ union + survival), citations (used in answer).

## 4. Evidence Inspector

Per row: source **document** · **section/parent** · **source child** · **exact text** · rerank score where
available · evidence role · arrivals/provenance · citation.

**Profiles, Atoms and pMAP explain WHY A SOURCE WAS FOUND. They are routing artifacts, never factual
evidence, and must never be presented as an answer's grounding.**

## 5. Compare Retrieval

User-triggered only. Same query across **HYBRID / GRAPH / WILDCARD**, comparing: answer · documents ·
candidate behaviour · selected evidence · roles · citations · latency · review result.

> Backend gap **GAP-2**: no compare contract exists. N independent calls share no compiled plan and no
> retrieval seed, so a naive diff confounds mode with run-to-run variance, and each arm costs a synthesis.
> F6 ships only once a compare contract runs N modes over ONE compiled plan.

## 6. Answer Review — evaluation only

Inputs: question · answer · citations · selected evidence · retrieval metadata.
Scores: grounding · correctness against evidence · completeness · citation support · unsupported claims ·
retrieval adequacy · potential missing evidence.

**The reviewer must not mutate retrieval and must not silently regenerate the answer.**

> Backend gap **GAP-3**: no review contract exists (`synthesizer` re-answers; it does not review). F7 ships
> only once one does.

## 7. Files — three readiness concepts, never one badge

```
CONTROL READY     is the machinery healthy?   /health/pipeline + /control_plane + /fleet + /ready
SEMANTIC READY    is the corpus's meaning built?  /semantic_readiness -> verdict
VNEXT READY       can this document answer from source?  vnext{} + per-doc /documents/summary
```

The legacy `query_ready` boolean is **banned as a readiness signal** — measured 2026-09-10:
`cinema.query_ready = true` while SEMANTIC/VNEXT are INCOMPLETE, 14/67 documents ready, 10,176 unresolved
parents. Also exposed per document: Graph · Profile · Atoms · pMAP (eligible / mapped / excluded /
unresolved) · projection state · timings, with the backend's own ordered blockers.

> Backend gap **GAP-1**: there is no single CONTROL-READY verdict; composing it in the client is
> recomputation. **GAP-4**: `control_plane.processing` has no age qualifier (cinema reports 64 runs
> "processing" that last moved 2026-09-07) — until fixed, the UI must not paint those as live.

## 8. Graph

Entity search · relationships · source documents · supporting source chunks.
**Only source-attested relationships may appear as canonical truth.**

## 9. Control Plane — function-first

Cards for `GRAPH_EXTRACTION` · `DOCUMENT_PROFILE` · `PMAP` · `CHAT`: function-level health, queues, failures,
providers/accounts/models, useful metrics. `limiter_refused` (LOCAL, 0 HTTP) stays visually DISTINCT from
HTTP 429. `parent_enrichment` is a legacy bridge, **not** a fifth pool. Never a secret.

## 10. Phases

| phase | deliverable | gate |
|---|---|---|
| F0 | backend contract inventory | DONE (11.195) |
| F1 | shell · navigation · design system · typed backend client | app boots, nav routes, backend reachable |
| F2 | Chat | a real answer on `rag-canary` |
| F3 | streaming · model · reasoning | SSE phases render; model/reasoning selectable |
| F4 | evidence inspector | every row traces to document/section/child/text |
| F5 | query trace | the five lane states rendered from backend fields |
| F6 | compare retrieval | **blocked on GAP-2** |
| F7 | answer review | **blocked on GAP-3** |
| F8 | Files / readiness | the triad, and cinema renders RED |
| F9 | Graph | source-attested relationships only |
| F10 | Control Plane | four function cards; GAP-4 honesty |
| F11 | integration tests | contract tests against the live backend |
| F12 | real E2E | a real browser session end to end |

## 11. Qualification corpora

- `rag-canary` — VNEXT_COMPLETE, 10/10 documents, 0 unresolved parents. The green path.
- `cinema` — SEMANTIC_INCOMPLETE / VNEXT_INCOMPLETE, 14/67 ready. **The UI must show this as blocked.**
- `ecom-meta-v1` — legacy, `query_enabled=true`. Proves the final core serves legacy corpora.
