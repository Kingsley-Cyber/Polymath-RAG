---
title: "DEEP-RESEARCH-MODE-V1 — multi-round research reports over your libraries, built on dzhng/deep-research's loop and Polymath's own retrieval"
date: 2026-09-26
last_reviewed: 2026-09-26
status: "ACTIVE — plan of record (register 11.504); the owner agreed to every §9 recommendation on 2026-09-26"
owner: "@king"
scope: "A research loop in shared/ (pure, ports injected), one streaming orchestrator route, a switch in the Chat composer, receipts. Uses the existing retrieval engine, the governed LLM lanes and the chat stream's frame types. Not in scope: web acquisition for non-owners, new retrieval modes, TrailSignal."
---

# DEEP-RESEARCH-MODE-V1

## 0. The owner's request (2026-09-26)
"plan a deepresearch mode design that is based on github and easy to implement."

## 1. What exists (baseline first)
**In Polymath** (`7e1918c2`, read-only survey on 2026-09-26):
- **No deep research mode exists.** Two plans reserved room for one:
  - FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §14 lists "DEEP RESEARCH SURFACES" (ANCHOR, broad SEEALSO, broad BRIDGE, RECALLQ), all off today.
  - DOCUMENT-SEMANTIC-INDEX-V1 says "HYBRID does NOT automatically search the deeper research group. The fields are indexed now so a future research mode has something real to use."
- **Parts to reuse:**

| Part | What it gives | Where |
|---|---|---|
| Evidence retrieval with citation ids | `/chat/evidence` returns an EvidencePacket (planner, no synthesis; the one LLM call is the compiler). `/retrieve` with `evidence:true` returns contract rows with ids | `api/chat.py:221`, `api/retrieve.py` |
| Multi-round resolution | `evidence_resolution.advance_state` already supports N rounds (`POLYMATH_CHAT_RESOLUTION_MAX_ROUNDS`, default 2). The live path runs one; it is 0 LLM calls | `shared/polymath_shared/evidence_resolution.py`, `api/ui.py:1871-1907` |
| Breadth without an LLM | `/retrieve/plan`: 3–5 fixed reformulations × each library × EXPLORE | `api/corpus_plan.py:143-187` |
| A budgeted LLM call | `LLMExtractionClient(...).complete_one(...)` behind the AdaptiveLimiter (per-lane requests and tokens per day). Unlike the chat synthesizer path (`limiter_bypassed=True`), it is budgeted | `shared/polymath_shared/llm_extraction/client.py:528`, `limiter.py:484` |
| The stream contract | frames `phase{stage,label,t}` · `token` · `reasoning` · `answer{kind,result,retrieval,latency_ms}` · `done` · `error`. The UI already renders phases as a process rail ("Working · N steps") | `api/ui.py:1333`, `frontend-v2/src/lib/chat.ts:73-120` |
| One receipt per turn, with `principal_id` | `query_receipts` | `shared/polymath_shared/query_receipts.py:147` |
| A durable, owned multi-step runtime | `substack.article_development` already has the shape plan → retrieve → graph → thesis → gap check → gap retrieve → draft → cite check → compile. But only a connected agent may answer a reasoning step (ADR-0018 §2) | `config/adapters/`, `shared/polymath_shared/adapter/` |

- **Rules that bind this plan:**
  - An LLM never widens a scope (K1).
  - No second scheduler (ADR-0018 §4).
  - Generated provider configs are edited only through `config/llm_accounts.yaml`.
  - Live chat turns and `test_live_*` need the owner's word (9 of 10 used).
  - `research_acquire` stays owner-only and only inside a harness action.
  - "No new chat mode" (CONTINUITY Do Not Do) came from CODE-KNOWLEDGE-V1 decision 9, for code RAG. The older "no new public retrieval mode" rule the owner overrode for WILDCARD and GNN. Either way, the surface is the owner's call (§9.1).

**On GitHub.** Verified on 2026-09-26 through the repositories and the GitHub API. The short list:

| Repo | License | Stars | Activity | Algorithm | Private corpus | Size |
|---|---|---|---|---|---|---|
| **dzhng/deep-research** | MIT | 19.7k | core unchanged since 2025-03 | breadth × depth recursion: queries with a research goal → search → ≤ 3 learnings + follow-ups → recurse (breadth halves, depth − 1) → report | search is one call site | ~300-line loop |
| zilliztech/deep-searcher | Apache-2.0 | 8.3k | 2026-09-22 | ≤ 4 sub-queries → vector search → per-chunk filter → ≤ 3 gap queries, ≤ 3 rounds → summary | built in | ~320 lines |
| assafelovic/gpt-researcher | Apache-2.0 | 29.6k | v3.7.0, 2026-09-26 | planner → parallel researchers → writer; its "deep" mode reuses dzhng's loop | yes (custom retriever) | 127 files |
| langchain-ai/open_deep_research | MIT | 12.7k | **archived 2026-08-21** | supervisor + parallel researchers, LangGraph | via MCP tools | ~2.4k lines |
| stanford-oval/storm | MIT | 31.5k | dormant since 2025-09 | perspectives → simulated Q&A → outline → article | yes (dspy retriever) | dspy |

Left out:
- jina node-DeepResearch: answers, not reports, and no private corpus.
- smolagents: runs arbitrary code.
- Tongyi DeepResearch: needs its own 30B model.
- HKUDS Auto-Deep-Research: no LICENSE file.
- khoj: AGPL.

## 2. Decision proposed: rebuild dzhng's loop in Python on Polymath's retrieval
- **Why dzhng.**
  - It is the most-copied design (gpt-researcher's deep mode is the same loop).
  - It is small: its README aims to stay under 500 lines.
  - MIT license.
  - Its search is a single call we replace with Polymath's own evidence retrieval.
- **Runner-up.** zilliztech/deep-searcher, closest in spirit (private corpus first).
- **Three ideas taken from others.**
  1. Every learning carries citation ids (gpt-researcher).
  2. Stop when a round yields no new gap questions (deep-searcher).
  3. A token budget that keeps a reserve for the final report (Jina).
- **Copy:**
  - the algorithm;
  - the three-prompt structure (queries with a research goal; dense learnings that keep names, numbers and dates; a report built from all learnings);
  - today's date in the system prompt;
  - the progress fields.
- **Leave out:**
  - web scraping (Firecrawl) and JSON-object reports that cannot stream;
  - "sources = every visited URL" (Polymath lists only cited rows);
  - per-branch learnings (siblings repeat each other's queries);
  - the prompt lines that relax sourcing ("the source is irrelevant", "high levels of speculation"), which fight Polymath's evidence gating;
  - LangGraph, dspy and smolagents.
- **License.**
  - Re-implementing an algorithm needs no notice.
  - Any prompt text copied closely keeps dzhng's MIT notice ("© 2025 David Zhang") in the prompts module header and in `THIRD_PARTY_NOTICES`.
  - Nothing is copied from repos without a license or under AGPL.

## 3. The loop
The recursion is flattened into levels, so progress is easy to stream and budgets are easy to enforce.

1. **Input.** `{question, libraries (the request's scope, narrowed for a friend), preset, model}`.
   - Presets: Quick 3×1 · Standard 3×2 (default) · Thorough 4×2. Breadth × depth.
2. **State.** `frontier = [{query: question, goal: "", depth, breadth}]`, plus shared `learnings[]`, `evidence{cid → row}`, `seen_queries`.
3. **One level.** Concurrency 2, because the embedder and reranker share the Metal GPU. For each frontier node:
   1. **Plan.** One LLM call writes ≤ breadth `{query, goal}`, given the node and the top learnings so far. Near-duplicates of `seen_queries` are dropped.
   2. **Retrieve.** Polymath's evidence retrieval in-process, inside the request's libraries only. It uses the reserved deep-research surfaces (ANCHOR, broad SEEALSO, broad BRIDGE, RECALLQ; DR0 finds their switches). DR0 (11.519): they switch on per query intent (`query_intent.py:149-158`), and only the chat path applies that policy (`ui.py:3897`); deep research's searches go through `/retrieve` with a mode and no plan, so they are off for it today. Turning them on is a later slice with a measured A/B. The planner can never add a library.
   3. **Extract.** One LLM call over the rows, each tagged `[cid]`, returns ≤ 3 learnings `{text, cids}`, ≤ ⌈breadth/2⌉ follow-ups, and `done`. A learning whose cids are not in those rows is dropped and counted.
   4. **Stream.** A `phase` frame: `{depth, completed/total, query, new_learnings}`.
   5. **Recurse.** If depth > 1, there are follow-ups, `done` is false and budget remains, queue a child: `{goal + follow-ups, depth − 1, ⌈breadth/2⌉}`.
4. **Stop** when the frontier is empty, a level brings no new follow-ups, 85% of the token budget is spent, or the deadline passes.
   - The deadline is 4 minutes by default, with a hard cap of 6.
   - An empty or low-score retrieval ends its branch: the libraries hold no more on that thread.
5. **Report.**
   - Stream a markdown report from the learnings, grouped by goal. Every claim cites `[cid]`, and every cid is checked against `evidence`.
   - Sources list only cited rows. What the libraries could not answer is listed as open questions.
   - The report uses the model chosen in the composer, like chat. The plan and extract calls use a budgeted `deep_research` lane.

**Cost per run.**

| Preset | Retrievals | LLM calls | Estimated time |
|---|---|---|---|
| Quick 3×1 | 3 | 5 | ~40 s |
| Standard 3×2 | 9 | 14 | ~1.5–2 min |
| Thorough 4×2 | 12 | 18 | ~2–2.5 min |

Times are estimates from concurrency 2 and today's retrieval latency; DR4 measures them. Every run writes a receipt with the counts, the stop reason and the dropped-citation count.

## 4. Where it lives
- **Engine: `shared/polymath_shared/deep_research/`.** Pure code: prompts, the level runner, the budget, citation checks, stop rules. It has two injected ports:
  - `retrieve(query, scope) → rows`;
  - `complete(prompt, lane) → text`.
  Unit tests run it with fakes; no I/O inside.
- **Route: `POST /research/deep`** (orchestrator). It streams the chat's own frame types:
  - `phase` for progress, plus a heartbeat every ≤ 15 s. Cloudflare drops a proxied response that sends nothing for 100 s.
  - `token` for the report.
  - `answer{kind: "deep", result, retrieval: {trace}}`, then `done` or `error`.
  - It streams exactly like `/chat/stream` (same response class and headers), so the gzip-buffering fix applies.
  - The scope comes from the request (`narrow_scope` for friends). One deep run at a time per person. A client disconnect cancels the run. One receipt per run.
- **Boundary.** One line in the web boundary's policy table (USER class) and its test case.
- **LLM lanes.** A `deep_research` stage added in `config/llm_accounts.yaml`, then `scripts/llm_accounts.py write` (never a hand edit).
- **UI.** A **Deep research** switch in the Chat composer, beside the mode chip. When on:
  - a preset picker and a progress tree (levels → queries → learnings found) replace the answer area until the report streams;
  - the report uses the same citation chips as chat answers;
  - **Stop** ends it.
  The switch does not add a retrieval mode: the loop calls the existing retrieval as a tool.
- **Later (optional).** A `research.deep_report` adapter for MCP agents. The agent answers the reasoning steps, as ADR-0018 already allows, and runs are durable. Owner-only web acquisition can join there as a branch.

## 5. Slices
| Slice | What | Proof ($0 unless marked) |
|---|---|---|
| **DR0** — DONE 11.519 | Find the switches of the reserved deep surfaces; add the `deep_research` lanes through the registry; fix the frame and receipt shapes in this plan | `llm_accounts.py validate` / `diff` clean; the surfaces' switches named with file:line |
| **DR1** — DONE 11.513 | The engine (`deep_research/`) with fake ports | Unit tests: breadth halves per level; stop at 85% budget; stop on no follow-ups; a learning with a foreign cid is dropped and counted; duplicate queries dropped; deadline respected; the report cites only known cids |
| **DR2** — DONE 11.514 | `POST /research/deep` + boundary line + receipts | Contract tests: frame order (phase… token… answer, done), heartbeat, a friend's scope narrowed, a second concurrent run refused, a disconnect cancels, a receipt written |
| **DR3** — DONE 11.516 | Composer switch, presets, progress tree, report | vitest: the switch routes to `/research/deep`; progress renders from phase frames; Stop cancels; citation chips resolve |
| **DR4** — PARTIAL 11.520 (4/5 live; the 5th's fix awaits the next deploy) | Live proof — **on the owner's word** | 5 smoke questions (testing policy 5–8) across cinema and commerce-v1: every cited cid resolves, stop reasons are sensible, cost matches §3 |
| **DR5** *(optional)* | The adapter for MCP agents; owner-only web branch | Only if the owner wants it |
| **DR6a** | Research moves in the engine (§10): the MOVE grammar, the controller, anchors, the gate and spawn floor as ports, gap nodes, dry moves, receipts | Unit tests with fake ports (§10.8); moves off = today's behaviour, byte for byte |
| **DR6b** | The route per move + `/retrieve`'s optional `intent` + the relevance gate on the reranker | Contract tests: each move builds its own search request; `intent` absent = unchanged, present = chat's intent budget, unknown = 422 |
| **DR6c** | UI: each search's move in the progress rail; the counter-evidence line under the report | vitest |
| **DR6d** | Live A/B on the 5 DR4 questions, moves off vs on | §10.9 acceptance; the owner sees the table |

DR1 can start at once. DR3 fits best after FRONTEND-REFRESH-V1 U4 (the new composer); on today's composer it is a small switch.

## 6. Quality gates
- **Citations.** 100% of report citations resolve to rows retrieved in the run; the dropped-learning rate is reported.
- **No new facts.** The report is built only from learnings; "unknown" lists what the libraries could not answer.
- **Scope.** No retrieval outside the request's libraries, proven by a test with a friend's narrowed scope.
- **Fallback accounting.** JSON repair, retries and empty retrievals are counted and shown in the receipt, never hidden.

## 7. Risks
- **Fan-out cost.** Hard presets, a token budget with a report reserve, one run at a time per person, and receipts.
- **Invented or misattached citations.** Checked against the run's rows; dropped and counted.
- **Follow-ups drifting past what the libraries hold.** Empty or low-score retrieval ends a branch.
- **Weaker models break structured output.** A small JSON repair, counted; the extract prompt asks for a fixed line format.
- **Prompt size.** Learnings are capped (top N by coverage) before the report.
- **GPU contention.** Concurrency 2.
- **Prompt injection in retrieved text.** Rows are data inside delimiters; instructions in them are ignored.
- **No upstream fixes.** dzhng's core is frozen and open_deep_research is archived; Polymath owns every fix. The loop is small on purpose.

## 8. Friends
Friends may use it: the owner's decision is "everything" and "no daily cap". Safety comes from the per-run presets and one run at a time per person. An owner-set daily count is available but off by default. Web research stays owner-only.

## 9. Owner decisions
**DECIDED 2026-09-26** (the owner: "i agree please fix it all"): a Deep research switch in the Chat composer with its own route; dzhng's loop; presets Quick 3×1 · Standard 3×2 (default) · Thorough 4×2, 4-minute deadline; friends allowed with presets and one run at a time; libraries only in v1; the composer's model writes the report; DR4's five live questions wait for the owner's word.

1. **Surface:** a Deep research switch in the Chat composer with its own route (recommended; the retrieval modes stay as they are), a sixth chat mode "DEEP", or the adapter only (MCP agents drive it).
2. **Base:** dzhng's loop (recommended) or deep-searcher's style.
3. **Presets and default:** Quick 3×1 · Standard 3×2 (default) · Thorough 4×2 (recommended); deadline 4 minutes.
4. **Friends:** allowed, with presets and one run at a time (recommended).
5. **Web:** libraries only in v1 (recommended); owner-only web research later through the adapter.
6. **Report model:** the model chosen in the composer (recommended), or a fixed lane.
7. **Live proof:** 5 live questions for DR4 when the owner says so (they count toward the live-turn allowance).

## 10. Research moves (DR6) — DECIDED 2026-09-26 (the owner: "go for the deep research moves design")
Today every search is the same HYBRID search, breadth and depth are fixed by the preset, and a level's follow-ups are the only
way down (DR4: runs went 1–2 levels and ended `frontier_empty`). DR6 gives every planned search a **move**, sends each move to the
retrieval surface built for it, lets a small deterministic controller choose the mix, and keeps every move tied to the question.

### 10.1 The moves
| Move | Asks | Search (all already built) |
|---|---|---|
| `broad` | another part of the question | HYBRID over the libraries; rows built with the EXPLORE cap (2 per document) so they spread |
| `deep` | drill into a strong finding | the default lane with `document_ids` = the anchor documents (DOCUMENT-SCOPED-RETRIEVE-V1); without anchors, HYBRID with the normal cap (4 per document) |
| `adjacent` | nearby ideas that connect | HYBRID with `intent: RELATIONSHIP` (CONCEPT, THEORY, SEEALSO, BRIDGE, ANCHOR, TENSION atoms; SEEALSO fan-out; graph destinations; graph assist `auto`) |
| `inverse` | limits, exceptions, failure cases, critiques, opposite cases | HYBRID with `intent: COMPARISON` (CONCEPT, BOUNDARY, TENSION, INVERSION atoms; MULTI_REQUIRED breadth) + a query phrased against the finding |

`/retrieve` gains an optional `intent` (a canonical §33 intent) honoured on the v2 engine path of HYBRID / GRAPH / WILDCARD: the
budget becomes `apply_intent_policy(intent, default_budget())` (with `latent` still honoured) and the graph assist follows the
policy, exactly as chat applies it (`ui.py` P2b / P6). Absent = byte-identical; unknown = typed 422 `unknown_intent`. This is how
the reserved surfaces DR0 named (11.519) reach deep research without changing chat.

### 10.2 The planner
- Grammar: `QUERY: <q> || GOAL: <g> || MOVE: <broad|deep|adjacent|inverse>`. MOVE is optional: missing = `broad` at level 1 and
  `deep` below (today's meaning); an unknown value = that default, counted as a repair.
- The plan prompt carries the controller's quota ("write 1 broad, 1 deep and 1 inverse query") with one line per move. An
  inverse query keeps the key terms of the finding or goal it tests ("when does habit stacking fail?", never "criticisms of
  psychology").
- Acceptance: per move up to its quota, in plan order; slots left empty are filled by the remaining queries in order, so a
  level never runs under its breadth because the model ignored the quota. An inverse query that shares no content term with its
  goal / anchor finding is dropped (`inverse_unanchored`).

### 10.3 The controller (pure, `deep_research/moves.py`)
- The question's intent comes from `query_intent.classify_intent(question)` (deterministic, no model call). Starting weights
  (broad / deep / adjacent / inverse):

  | Intent | Weights |
  |---|---|
  | EXACT, DEFINITION | 1 / 3 / 0 / 0 |
  | MECHANISM, PROCEDURE, APPLICATION | 1 / 2 / 0 / 1 |
  | COMPARISON | 2 / 0 / 0 / 2 |
  | RELATIONSHIP | 1 / 0 / 3 / 0 |
  | SYNTHESIS, EXPLORATORY | 2 / 0 / 2 / 0 |
  | RECALL | 2 / 1 / 1 / 0 |

- An evaluative question ("should", "worth", "best", "does it work", "is it true", "effective", "pros and cons") reserves one
  inverse slot on every level.
- `allocate(weights, n)`: largest-remainder rounding, ties in move order, sum = n, deterministic.
- Level ≥ 2 (a child node plans `ceil(breadth / 2)` queries from its parent branch's follow-ups): the child starts from its
  parent's move (a broad or deep parent → deep-heavy, adjacent → adjacent + deep, inverse → inverse + deep), then the signals:
  - **repeat**: ≥ 50% of the parent's rows were already seen in the run → one slot moves from deep to adjacent;
  - **concentration**: the parent's learnings cite rows from ≤ 2 documents → its deep queries anchor to those documents;
  - **one-sided**: ≥ 3 learnings so far and none from an inverse search, and the question is evaluative or MECHANISM /
    PROCEDURE / APPLICATION → the child with the most learnings gets one inverse slot;
  - **dry**: a move that produced 0 learnings on two levels gets weight 0 for the rest of the run.
- **Gap nodes:** a level-1 branch that ended empty or with 0 learnings, when depth remains, spawns one child with the same goal and
  one `broad` reformulation, inside the run's retrieval budget.

### 10.4 Staying aligned with the question
1. **Relevance gate** before a search: the reranker scores each planned query against the ORIGINAL question
   (`probe_gate.gate_probes`, with a new optional `gated_origins` so deep research uses origin `DEEP_RESEARCH`; floor 0.2, the
   probe gate's default). Dropped queries are counted; a reranker error or timeout keeps them (fail-open, counted).
2. **No drift chains:** a query whose gate score is under the spawn floor (0.35) keeps its learnings but spawns no children
   (`drift_stopped`).
3. Every query carries its goal and move; learnings carry their move, so the report can group them.

### 10.5 The report
- The learnings are grouped: **What the libraries say** (broad + deep), **How it connects** (adjacent), **What cuts against it**
  (inverse).
- When inverse searches ran and found nothing, the report says "The libraries hold no counter-evidence on this". The answer's
  meta carries `moves.inverse = {searched, learnings}`, so the UI can show it whatever the model writes.

### 10.6 Engine and route interfaces
- `Row` gains `doc_id: str = ""`; `Learning` gains `move: str = "broad"`; `Config` gains `moves: bool = False`, `gate_floor = 0.2`,
  `spawn_floor = 0.35`. With `moves=False`, the engine is today's engine.
- Ports: `retrieve(query, scope, /, *, move, anchor_docs)` is called with the keywords only when `moves` is on, so the two-argument
  fakes keep working. `gate(question, [(id, text)]) -> {id: score}` is optional (`None` = no gate).
- Route: `DeepResearchRequest.moves: bool = True`; `POLYMATH_DEEP_RESEARCH_MOVES=0` forces it off. The port builds each move's
  `RetrieveRequest` (§10.1) and rows (`evidence_rows_of(..., explore=True)` for broad). The gate port wraps
  `chat_retrieval._rerank_children`.

### 10.7 Receipts and UI
- `summary()["moves"]`:
  - the intent and whether the question is evaluative;
  - per level: `asked` / `planned` / `searched` / `learnings` per move;
  - the gate (`scored`, `dropped`, `failed_open`);
  - `drift_stopped`, `gap_nodes`, `dry_moves`, `inverse_unanchored`;
  - deep anchored / unanchored.
- Phase frames for plan / retrieve carry `move`.
- The progress rail labels each search "Broad · / Deep · / Adjacent · / Inverse · <query>", in text, not only icons.
- Under the report, a line reads "Counter-evidence: N findings" or "Counter-evidence: none found in the libraries".

### 10.8 Tests (DR6a–c)
- Grammar:
  - MOVE optional, with the default by level;
  - an unknown MOVE is a repair;
  - quotas are filled in order, and a short level is filled from the leftovers.
- Controller:
  - `allocate` sums to n and is deterministic;
  - each intent's mix;
  - the evaluative reserve;
  - each signal: repeat, concentration anchors, one-sided, dry;
  - gap nodes stay inside the budget.
- Gate:
  - drops below the floor;
  - fails open on an error;
  - spawn floor stops children.
- Engine: `moves=False` gives the same queries, calls and outcome as today (the existing DR1 tests pass unchanged).
- Route:
  - each move's request (a fake `_retrieve_impl` records them): deep uses `document_ids` on the default lane, adjacent and inverse
    pass `intent`, broad uses the EXPLORE cap;
  - `/retrieve` `intent` absent / present / unknown;
  - the receipt's `moves` block.
- UI: the rail labels and the counter-evidence line.

### 10.9 DR6d acceptance (live, after the deploy)
The 5 DR4 questions, `moves: false` then `moves: true` (10 runs). Moves must:
- cite ≥ the baseline's distinct documents on at least 4 of 5 questions;
- cover ≥ the baseline's goals (goals with a learning / goals planned);
- on the evaluative or mechanism questions, show at least one inverse learning or the explicit "none found";
- stay inside the preset deadline, with LLM calls ≤ the baseline + 10%.
The owner sees the table; the default stays on only if it passes.
