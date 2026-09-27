---
title: "DEEP-RESEARCH-MODE-V1 — multi-round research reports over your libraries, built on dzhng/deep-research's loop and Polymath's own retrieval"
date: 2026-09-26
last_reviewed: 2026-09-26
status: "PROPOSED — the owner's request 2026-09-26; waits for the owner's decisions in §9"
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
   2. **Retrieve.** Polymath's evidence retrieval in-process, inside the request's libraries only. It uses the reserved deep-research surfaces (ANCHOR, broad SEEALSO, broad BRIDGE, RECALLQ; DR0 finds their switches). The planner can never add a library.
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
| **DR0** | Find the switches of the reserved deep surfaces; add the `deep_research` lanes through the registry; fix the frame and receipt shapes in this plan | `llm_accounts.py validate` / `diff` clean; the surfaces' switches named with file:line |
| **DR1** | The engine (`deep_research/`) with fake ports | Unit tests: breadth halves per level; stop at 85% budget; stop on no follow-ups; a learning with a foreign cid is dropped and counted; duplicate queries dropped; deadline respected; the report cites only known cids |
| **DR2** | `POST /research/deep` + boundary line + receipts | Contract tests: frame order (phase… token… answer, done), heartbeat, a friend's scope narrowed, a second concurrent run refused, a disconnect cancels, a receipt written |
| **DR3** | Composer switch, presets, progress tree, report | vitest: the switch routes to `/research/deep`; progress renders from phase frames; Stop cancels; citation chips resolve |
| **DR4** | Live proof — **on the owner's word** | 5 smoke questions (testing policy 5–8) across cinema and commerce-v1: every cited cid resolves, stop reasons are sensible, cost matches §3 |
| **DR5** *(optional)* | The adapter for MCP agents; owner-only web branch | Only if the owner wants it |

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
1. **Surface:** a Deep research switch in the Chat composer with its own route (recommended; the retrieval modes stay as they are), a sixth chat mode "DEEP", or the adapter only (MCP agents drive it).
2. **Base:** dzhng's loop (recommended) or deep-searcher's style.
3. **Presets and default:** Quick 3×1 · Standard 3×2 (default) · Thorough 4×2 (recommended); deadline 4 minutes.
4. **Friends:** allowed, with presets and one run at a time (recommended).
5. **Web:** libraries only in v1 (recommended); owner-only web research later through the adapter.
6. **Report model:** the model chosen in the composer (recommended), or a fixed lane.
7. **Live proof:** 5 live questions for DR4 when the owner says so (they count toward the live-turn allowance).
