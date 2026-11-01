# unit: adapters/ecommerce/python/executors.py
anchor: adapters/ecommerce/python/executors.py:1-952

Note: the SOURCE excerpt covers file lines 1–673; everything past line 673 is cited from FACTS static analysis only (signatures, no bodies).

## purpose
Deterministic transform/gate executors for the ecommerce adapter's `python.*` graph nodes: lens selection, breadth/structural lookup, research triage, gap + query compilation, observation curation, supplier normalization, scoring and stopping gates. — adapters/ecommerce/python/executors.py:1-5 [DERIVED]
Contract stated in the docstring: reproducible from state + registry + policies alone, "No LLM calls, ever". — adapters/ecommerce/python/executors.py:3-5 [DERIVED]

## public surface
"used by" is "—" everywhere: FACTS lists no importers. `join_leads` and `interleave_leads` have in-file callers (scoring); `join_leads` also has an external caller per its docstring ("standalone scoring and the governed binding both call it"). — adapters/ecommerce/python/executors.py:648

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| load_lenses | def | () -> dict | adapters/ecommerce/python/executors.py:25-27 | — |
| load_csv | def | (name: str) -> list[dict] | adapters/ecommerce/python/executors.py:30-32 | — |
| lens_gate | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/executors.py:53-66 | — |
| signal_gate | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/executors.py:70-78 | — |
| structural_lookup | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/executors.py:81-125 | — |
| triage | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/executors.py:169-189 | — |
| channel_table | def | (path: str \| None = None) -> dict | adapters/ecommerce/python/executors.py:203-207 | — |
| render_command | def | (argv: list, values: dict) -> str | adapters/ecommerce/python/executors.py:226-235 | — |
| tool_chain | def | (row: dict, query: str) -> list[str] | adapters/ecommerce/python/executors.py:242-246 | — |
| channel_queries | def | (gid, question, state, policies, id_prefix="q", short=None) -> list[dict] | adapters/ecommerce/python/executors.py:289-315 | gap_compiler (348) |
| gap_compiler | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/executors.py:318-358 | — |
| comments | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/executors.py:362-424 | — |
| sourcing_plan_compiler | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/executors.py:491-515 | — |
| sourcing_coverage | def | (state: dict) -> list[dict] | adapters/ecommerce/python/executors.py:539-550 | supplier (579), scoring (638) |
| supplier | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/executors.py:553-586 | — |
| scoring | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/executors.py:590-644 | — |
| join_leads | def | (mech: dict, d: dict, pol: dict) -> list[dict] | adapters/ecommerce/python/executors.py:647-670 | scoring (611); "the governed binding" (external, per 648) |
| interleave_leads | def | (leads: list[dict]) -> list[dict] | adapters/ecommerce/python/executors.py:673-689 | scoring (616) |
| apply_evaluations | def | (state, policies) | adapters/ecommerce/python/executors.py:726-728 | — |
| frontier_gate | def | (state, policies) | adapters/ecommerce/python/executors.py:732-739 | — |
| voi_gate | def | (state, policies) | adapters/ecommerce/python/executors.py:742-752 | — |
| portfolio_gate | def | (state, policies) | adapters/ecommerce/python/executors.py:755-770 | — |
| discovery_loop_gate | def | (state, policies) | adapters/ecommerce/python/executors.py:773-796 | — |
| loadout_ready | def | (state, policies) | adapters/ecommerce/python/executors.py:799-838 | — |
| agent_reach_plan | def | (intents, stage, assigned, context, policies, table) | adapters/ecommerce/python/executors.py:892-951 | — |
| AGENT_REACH_PLAN_VERSION | const | = "agent_reach_plan.v1" | adapters/ecommerce/python/executors.py:878 | — |
| SOURCING_SITES | const | dict channel -> where (kind == "supply") | adapters/ecommerce/python/executors.py:482 | — |
| _MOQ | const | alias of _MOQ_UNIT | adapters/ecommerce/python/executors.py:440 | legacy importers of the old name |

## contracts

**lens_gate** — adapters/ecommerce/python/executors.py:53-66
- in: `state["data"]["signal"]` + summaries/texts of `state["data"]["corpus_evidence"]`, lowercased; lenses from `registry/lenses.yaml` (25-27, 55-57).
- out: `state["data"]["lenses"]` = list of `{name, question}`; returns `"selected N lenses: ..."`.
- post: never empty — falls back to `[{"name": "minimal-interference", ...}]` when no keyword hits; pre: `lenses.yaml` must contain the key `minimal-interference` (62-64).

**signal_gate** — adapters/ecommerce/python/executors.py:70-78
- in: `state["data"]["primitives"]`.
- out: sets `state["verdict"] = "NO_GENERATIVE_SIGNAL"` when `generative_signal` missing; otherwise returns counts only. Verdict set here, routing done by the edge (71-72, 75).

**structural_lookup** — adapters/ecommerce/python/executors.py:81-125
- pre: `prim["transferable_invariants"]` non-empty unless `policies.breadth.require_invariant_for_transfer` is falsy (default `True`) (86).
- out: `state["data"]["cross_domain_analogies"]` = registry hits (matched via `shared_predicates` × `frictions` against `index_by_predicate` / `index_by_predicate_friction`, authority `SEED_HYPOTHESIS`) + corpus hits, total capped at `max_cross_domain_analogies` (default 8) (97-117, 122-123).
- fail-closed: missing registry snapshot → empty list, returns `"no registry snapshot — structural pass skipped"` (94-96).

**triage** — adapters/ecommerce/python/executors.py:169-189
- in: hypotheses with status in `("WORKING_HYPOTHESIS", "WORKING_ANALOGY", "CHALLENGED")` (173-174).
- out: writes `h["research_priority"] = min(len(falsifiers),2) + min(len(gaps),2) + 1 if alternatives + 1 if exploratory`; keeps top `max_research_ready` (default 3) with priority >= `min_priority` (default 2); all other non-`SUPPORTED` live hypotheses set to `"HOLD"` (176-188). Priority is a prior, never evidence (170-171).

**channel_queries** — adapters/ecommerce/python/executors.py:289-315
- in: gap id + question; optional `short` (pre-compiled search string from governed runs).
- out: one row per enabled channel in `policies.evidence_channels` order; `query = tpl.format(q=short)` where `short` defaults to the first 6 gap keywords; every row carries rendered `tools`, `identity`, `freshness_hint`, `where`, `collect`, optional `law`/`limits`, and `cannot_satisfy = ["SUPPLIER_AVAILABILITY", "PRICE_EVIDENCE", "MOQ_EVIDENCE", "CURRENT_PRODUCT_REFERENCE"]` (294-314).
- `subreddit_hints` (top 6 from `state["data"]["communities"`) only when the channel row has `scope_hints == "communities"` — data, never a channel name (296, 302, 307).

**gap_compiler** — adapters/ecommerce/python/executors.py:318-358
- in: hypotheses with status not in `("REJECTED", "HOLD")` (323).
- out: per new gap question: gap `{id: stable_id("gap", h["id"], q), required_evidence_roles: _GAP_DEFAULT_ROLES, required_freshness: ["LIVE"] if genesis in ("TREND_LED","SHIFT_LED") else ["FAST","LIVE"]}` plus its channel_queries batch; then `state["data"]["queries"]` rewritten via `allocation.interleave_queries` and `research_allocation` stored (326-355).
- idempotent on gap ids via the `known` set (320, 326-329).

**comments** — adapters/ecommerce/python/executors.py:362-424
- pre (hard `[]` access, KeyError on missing): `policies["evidence"]["min_independent_sources"]` (390), `state["rounds"]["research"]` (414).
- out: deduped observations keyed `((quote_ref or stable_id("obs", source, problem)), gap_id)` (383-388); optional `lexicon_flags` = `workaround_marker:<m>` (max 4) only when `WORKAROUND_EVIDENCE` not already in roles — detection only, never assigns a family/role (365-379); gap → `"supported"` when `verifiers.independence_groups(support)["independent_groups"] >= min_independent_sources`, → `"contradicted"` when `len(against) > len(support)` (409-413); freshness enforced: observation `freshness.class` must be in gap `required_freshness` when set (398-401); increments research round; refreshes coverage and allocation (414-419).

**supplier** — adapters/ecommerce/python/executors.py:553-586
- in: raw `state["data"]["supplier_candidates"]`.
- out: normalized candidates with `price_usd_low/high`, `moq_units` (channel default from `policies.supplier.moq_default_by_channel`, noted `"<channel> default MOQ <n>"`), `concept_id`/`mechanism_id` stamped when exactly one concept matches by name (`concept_resolved_by = "name_overlap"`); writes `sourcing_coverage` (557-579, 518-536).
- twin merge: same `(concept_id, url, product_name.lower, supplier_name.lower)` listings merge missing `price_raw`/`moq_raw` from each other (557-567).

**scoring** — adapters/ecommerce/python/executors.py:590-644
- pre (hard `[]` access): `policies["evidence"]["min_total_observations"]`, `policies["scoring"]["purchase_language_bonus"]`, `["min_mechanism_support"]`, `policies["supplier"]["require_price"]`, `["require_moq"]`, `["max_leads"]` (598, 607-609, 653-654, 619).
- out: `NO_DEFENSIBLE_BRIDGE` + empty leads when no SUPPORTED mechanism, coverage not core-satisfied, or observations under the floor (596-602); else leads from `join_leads` scored `len(support) + purchase_language_bonus * count(purchase_language)`, sorted desc, `interleave_leads`, capped at `min(settings.effective(state, "opportunity_research.max_leads", supplier.max_leads), supplier.max_leads + 2)`; verdict one of `QUALIFIED_LEADS` / `PROVISIONAL_LEADS` / `provenance.echo_verdict` default `"CORPUS_ECHO_UNGROUNDED"` / `MECHANISM_WITHOUT_SUPPLY`; writes `d["utilization"]` (605-640).

**join_leads** — adapters/ecommerce/python/executors.py:647-670
- out: lead dicts pairing ONE mechanism × one supplier candidate with parsed price and MOQ (when required) that passes `_supplier_fits` (`require_mechanism_fit` default `True`); lead `channel` defaults to `"alibaba"`; "No score, no verdict — the caller owns those" (648-665).

**render_command / tool_chain** — adapters/ecommerce/python/executors.py:226-246
- out: one shell-safe command string; every `{slot}` filled in ONE pass (`_SLOT = \{([a-z_]+)\}`, single `re.sub`), tokens matching `^<[A-Za-z_]+>$` left bare, all others `shlex.quote`d; `tool_chain` renders `row["commands"]` then each of `row["alternatives"]` with `{"query": q}` (199-200, 222-235, 242-246).
- `_clean_query` collapses whitespace and strips a leading `"@ "` (mcporter reads a FILE for `key=@path`) (238-239, 228-229).

**sourcing_plan_compiler** — adapters/ecommerce/python/executors.py:491-515
- out: `d["sourcing_plan"]` with one job per `product_concept` × channel (default `["alibaba", "cjdropshipping"]`), id `f"sp_{concept_id}_{ch}"`, `search_terms` capped at 8, `tools` from `_SOURCING_TOOLS`, `min_candidates_per_concept` default 1; a concept nobody sourced stays UNSOURCED — no borrowing across concepts (498-515).

**channel_table** — adapters/ecommerce/python/executors.py:203-207
- returns a fresh `json.load` copy every call; callers may not mutate a shared table.

## effect surface
- Files read: `registry/lenses.yaml` (25-27); `registry/<name>` CSVs via `load_csv` (30-32); `docs/24_agent_reach_channels.json` via `CHANNEL_TABLE_PATH` (198, 206) — also read at import time by `_CHANNEL_TEMPLATES` (249), `SOURCING_SITES` (482) and `_SOURCING_TOOLS` (484).
- Registry snapshot: `import registry as _reg; _reg.load_snapshot()` in structural_lookup (89-91), gap_compiler (337-339), comments (368-370).
- Postgres: none (FACTS `tables_read` / `tables_written` empty). Qdrant: none.
- Network/subprocess: none in lines 1-673 — Agent Reach commands are rendered strings, never executed here (226-246); "No LLM calls, ever" (5).
- Sibling modules imported lazily inside functions: `allocation` (352, 417), `satisfaction` (415, 593), `settings` (617), `provenance` (623), `candidates` (635), `utilization` (639); top-level: `verifiers` (16), `models.stable_id` (18).
- Env flags: none read in the visible source.

## invariants
INVARIANT: len(channel_queries(gap)) == len(enabled evidence channels) — adapters/ecommerce/python/executors.py:299-301 [DERIVED]
  fails-if: a channel row missing `kind == "evidence"` silently drops that channel's query for every gap (214-215).
INVARIANT: len(cross_domain_analogies) <= max_cross_domain_analogies default 8 — adapters/ecommerce/python/executors.py:117,122-123 [DERIVED]
  fails-if: corpus budget formula `8 - len(hits)` goes negative → `_corpus_analogies` returns [] (133-134).
INVARIANT: triage keep set <= max_research_ready (3) and each kept priority >= min_priority (2) — adapters/ecommerce/python/executors.py:183-184 [DERIVED]
  fails-if: lowering min_priority admits low-prior hypotheses and starves the research budget.
INVARIANT: gap "supported" only when independence_groups >= policies.evidence.min_independent_sources — adapters/ecommerce/python/executors.py:409-413 [DERIVED]
  fails-if: counting distinct `source` strings would close a gap on three URLs from one author (comment at 405-408).
INVARIANT: gap "contradicted" only when len(against) > len(support) — adapters/ecommerce/python/executors.py:410-411 [DERIVED]
  fails-if: ties resolve to the support branch.
INVARIANT: _parse_price result == (None, None) whenever _NON_USD or _FOREIGN_DOLLAR matches and no explicit _USD_AMOUNT — adapters/ecommerce/python/executors.py:445-450 [DERIVED]
  fails-if: "¥18.50" would parse as 18.50 USD; explicit USD wins ("≈ US$2.60" → 2.60).
INVARIANT: _parse_moq takes the LAST unit match ("1-10 pieces" -> 10); refuses strings containing "$" or `\d\.\d`; lone integer only when exactly one — adapters/ecommerce/python/executors.py:461-470 [DERIVED]
  fails-if: a price-looking string becomes a quantity.
INVARIANT: len(leads) <= min(effective max_leads, supplier.max_leads + 2) — adapters/ecommerce/python/executors.py:618-620 [DERIVED]
  fails-if: the cap re-collapses the concept portfolio (docs/20 §2, per 673 docstring).
INVARIANT: observation dedupe key == (lowered quote_ref or stable_id("obs", source, problem), gap_id) — adapters/ecommerce/python/executors.py:383-388 [DERIVED]
  fails-if: one quote answering two questions is dropped (docs/19, per 382).
INVARIANT: render_command fills slots in ONE pass — a filled value can never inject another slot — adapters/ecommerce/python/executors.py:227,233 [DERIVED]
  fails-if: a query value containing `{query}` would rewrite the command (injection).
INVARIANT: corpus analogies only from rows with row_relevance not in (None, "IRRELEVANT") and tags ∩ {graph_fact, graph_hop} — adapters/ecommerce/python/executors.py:142-146 [DERIVED]
  fails-if: unclassified corpus rows leak in as analogies (docs/26 §2 fail-closed).

## determinism & idempotency
determinism: DETERMINISTIC — pure functions of state + policies + local files (561-565, i.e. file lines 3-5); no clock/random/uuid/network/db/env in lines 1-673; ids via `models.stable_id` (18). Import-time file reads at 249, 482, 484 make results depend on `docs/24_agent_reach_channels.json` contents.
idempotency: UNSAFE — `comments` increments `state["rounds"]["research"]` on every call (414); `supplier` mutates candidates in place and stamps `concept_id` (575), which changes the listing merge key on a second pass [INFERRED: key includes concept_id, 559].

## failure behaviour
- `Exception` swallowed at 92 (structural_lookup): registry load failure → `snap = None` → empty `cross_domain_analogies`, return string `"no registry snapshot — structural pass skipped"`; caller sees success-shaped output (89-96).
- `Exception` swallowed at 342 (gap_compiler): registry query-grammar load failure → `_grammars = []`; gap records simply omit `registry_query_grammars` (337-347).
- `Exception` swallowed at 372 (comments): workaround-lexicon load failure → `_lex = set()`; no `lexicon_flags` emitted (368-379).
- `_num` returns `None` on `ValueError`/`AttributeError` (474-478) — parse failures surface as missing values, never raises.
- Scoring signals failure via `state["verdict"]` values, not exceptions: `NO_DEFENSIBLE_BRIDGE` (599), `MECHANISM_WITHOUT_SUPPLY` (634), echo verdict default `CORPUS_ECHO_UNGROUNDED` (632).
- Hard `KeyError` risk (no defaults): `policies["evidence"]["min_independent_sources"]` (390), `policies["evidence"]["min_total_observations"]` (598), `policies["scoring"][...]` (607-609), `policies["supplier"][...]` (619, 653-654).

## dumb-code flags
- `_MOQ = _MOQ_UNIT  # kept for callers that imported the old name` — alias retained for legacy importers — adapters/ecommerce/python/executors.py:440 [DERIVED]
- Duplicated stopword literals: `_CQ_STOP` and `_GAP_STOP` share e.g. "about", "from", "that", "this", "their", "than", "then", "have", "into", "were" — adapters/ecommerce/python/executors.py:128-129,253-256 [DERIVED]
- Channel defaults disagree in role: sourcing channels default `["alibaba", "cjdropshipping"]` (498) vs lead `channel` fallback `"alibaba"` (665) — adapters/ecommerce/python/executors.py:498,665 [DERIVED]
- Two channel-table sources: module-level `_CHANNEL_TEMPLATES` built at import (249) is bypassed whenever `policies["_channel_table"]` is a dict (297-298) — adapters/ecommerce/python/executors.py:249,297-298 [DERIVED]
- Magic caps: `kw[:6]` / `hints[:6]` (295, 307), quotes `[:5]` (613), markers `[:4]` (379), `terms[:8]` (509), grammars `[:6]` (347), lead headroom `+ 2` (620) — [DERIVED]
- Verdict literal `CORPUS_ECHO_UNGROUNDED` appears both as policy default `echo_verdict` and as the fallback in the same expression — adapters/ecommerce/python/executors.py:632 [DERIVED]
- Dead-channel comment: "not compiled (honest): facebook — groups need membership" — adapters/ecommerce/python/executors.py:250 [DERIVED]

## refactor notes
- `join_leads` has two callers by design ("standalone scoring and the governed binding both call it") — signature or lead-key changes hit an external file — adapters/ecommerce/python/executors.py:647-649.
- `channel_queries` row keys (query, question, keywords, tools, identity, freshness_hint, where, collect, law, limits, cannot_satisfy, ...) flow into `state["data"]["queries"]` and `allocation.interleave_queries` — renaming keys breaks the allocation layer — adapters/ecommerce/python/executors.py:303-314,348-355.
- `docs/24_agent_reach_channels.json` row schema (kind, query, family, why, expected_roles, identity, freshness, where, collect, law, limits, commands, alternatives, scope_hints, rule) is read at five sites — schema change is a multi-site edit — adapters/ecommerce/python/executors.py:213-218,245,302,311-312,482-484,512.
- Status/freshness vocabularies are cross-node contracts: hypothesis statuses `REJECTED`/`HOLD`/`WORKING_HYPOTHESIS`/`WORKING_ANALOGY`/`CHALLENGED`/`SUPPORTED` (173-174, 187, 323), freshness classes `FAST`/`LIVE` (330-331, 399), verdict strings (75, 599, 629-634).
- `state["data"]` keys written here and read downstream: `lenses` (65), `cross_domain_analogies` (123), `gaps`/`queries` (332, 355), `research_allocation` (354, 419), `observations` (389), `sourcing_plan` (514), `sourcing_coverage` (549), `supplier_candidates` (577), `leads` (620), `utilization` (640).
- Removing the `_MOQ` alias breaks importers of the old name — adapters/ecommerce/python/executors.py:440.
- Import-time reads of the channel table (249, 482, 484) mean the file must exist before this module imports; moving them lazy changes first-failure timing.

## VERIFY
```verify
grep -Fq 'No LLM calls, ever' adapters/ecommerce/python/executors.py
grep -Fq 'NO_GENERATIVE_SIGNAL' adapters/ecommerce/python/executors.py
grep -Fq 'max_research_ready", 3' adapters/ecommerce/python/executors.py
grep -Fq 'agent_reach_plan.v1' adapters/ecommerce/python/executors.py
grep -Fq 'kept for callers that imported the old name' adapters/ecommerce/python/executors.py
test "$(grep -c -F 'load_snapshot' adapters/ecommerce/python/executors.py)" -ge 3
! grep -Fq 'import requests' adapters/ecommerce/python/executors.py
```
