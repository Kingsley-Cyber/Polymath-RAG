---
change_id: FACET-RETRIEVAL-V1-F4
owner: "@king"
date: 2026-09-27
status: complete
status_note: "Slice F4 of FACET-RETRIEVAL-V1 (register 11.545, plan §3.4): section profiles for giant documents (> 300 parents), the document profile of a giant rebuilt from a stratified sample across ALL sections, the read-only coverage audit, and the one-document rebuild path. Unit and worktree proven on feat/giant-profiles; the live rebuild of handbook.html and the VES handbook is the orchestrating session's, after the deploy. Not merged, not deployed, no live write."
architecture_impact: "shared/polymath_shared/document_profile/giant_profile.py (NEW: section plan, stratified giant input, section input); shared/polymath_shared/document_profile/profile_coverage.py (NEW: the audit scorer); shared/polymath_shared/document_profile/projection.py (section points `scope: section` + `parent_ids`, `section_point_id`, two-stage `profile_nominate`, `fetch_existing_point`, `list_section_points`, `purge_section_points`); shared/polymath_shared/document_profile/profile_atom.py (the `section` family, `ProfileAtom.scope/section_key/parent_ids`, section-scoped supersession); shared/polymath_shared/document_profile/profile_atom_projection.py (`ingest_section_atoms`, `purge_section_atoms`, section payload); workers/workers/doc_profile_worker.py (`build_section_profiles`, the giant document input, per-pass hold, `POLYMATH_DOC_PROFILE_GIANT` / `_SECTIONS_PER_PASS` / `_FORCE_SECTIONS`); scripts/profile_audit.py + scripts/rebuild_profile.py (NEW); tests/determinism/test_giant_profile.py + test_section_profile_lanes.py (NEW); scaffold TREE, scripts/README.md, architecture/contract-dependencies.yaml (PROFILE_PROJECTION paths + tests, PROFILE_ATOM tests)."
last_reviewed: 2026-09-27
---

# FACET-RETRIEVAL-V1 F4 — profiles that match giant documents

## Contract
- **The finding (plan §1.2, receipt `q_e09925df009649c6be872299`).** `handbook.html` in `cinema` (802 parents, 2.47 MB of
  parent text, 22 top-level headings) had a document profile built from a 500-token fingerprint: `coverage_samples: 5`
  of 802 sections, `framing` = the front matter. Its compiled profile (2026-09-08, `profile_groq3`, quality 0.823) holds
  ONE question ("What is the CPCS Domain Handbook and what topics does it cover?"), ONE search ("CPCS Domain Handbook"),
  one topic, one comma-joined TERM line — nothing about motion, camera, prompting or performance. The deterministic
  `documents.retrieval_profile` names `cpcs, cpcs-mx, compiler, yaml, facs, adrg, json…` and "how to HAS PROPERTY". The
  VES Handbook (1,322 parents) is the same: `coverage_samples: 3`. The profile lanes (dualread, the scout's probes, the
  see-also blend, the atom fan-out) nominate through these points and atoms, so they never route to either book.
- **The owner's decision (plan §3.4).** A document with more than 300 sections gets one **section profile** per top-level
  heading, the same surfaces a document profile has, indexed beside document profiles and read by the same lanes; the
  document profile itself is rebuilt from a stratified sample across ALL sections, never the first pages; an audit scores
  every profile against its document and lists the worst; `handbook.html` and the VES handbook are rebuilt first.
- **Acceptance (this slice).** (1) `section_groups` cuts a giant into sections covering every eligible parent exactly
  once; (2) the stratified document sampler represents every section; (3) a section's input is that section's own text;
  (4) a giant gets section profiles, a small document does not, the stored shape is what the lanes read; (5) the audit
  scores a blank profile low and a good one high and flags giants without section profiles; (6) a rebuild path for one
  document through the worker's own lanes, limiter and receipts, with a dry run that shows the exact input windows.
- Boundaries: worktree `pmv4-profiles`, branch `feat/giant-profiles` from `feat/fix-it-all` at `6837b8d4`. No edit to
  `chat_plan.py`, `candidate_engine.py`, `chat_retrieval.py` (the compiler / F2 agent's files). No live write, no LLM
  call, no restart, no push; the two live reads (the audit and the dry run) were read-only Postgres transactions.

## Changes
- **`giant_profile.py` (NEW, pure policy).**
  - `GIANT_PARENT_THRESHOLD = 300` (strictly more parents is a giant); `is_giant`.
  - `section_groups(parents)`: non-noisy, non-empty parents (`document_region.is_noisy`, the fingerprint's own
    eligibility) grouped by their cleaned top heading (`heading_key_path`: markdown links / emphasis / stray brackets
    stripped, file, page and furniture segments dropped — the fingerprint's furniture rules). A group over
    `SECTION_SPLIT_PARENTS = 150` splits at the next heading level (to depth 3), or into contiguous positional parts
    ("<title> (part i of n)") when it has no deeper headings, so a flat book still gets sections. Groups under
    `MIN_SECTION_PARENTS = 3` fold into their predecessor (the leading ones into the first real section). More than
    `MAX_SECTION_PROFILES = 72` merges the smallest group into its smaller neighbour ("A + B"). Every eligible parent lands
    in exactly one `SectionGroup(ordinal, key, title, heading_path, parents, parent_ids, chars)`; `key` = 16 hex chars of
    the lower-cased heading key path (stable across rebuilds, so a rebuilt section REPLACES its point);
    `content_hash()` = the section's own text.
  - `build_section_fingerprint(document, group, ordinal, total, budget_tokens=1000)`: the vNext `DocumentFingerprint`
    over the section's own parents (its heading stride, its even-stride salient coverage, its vocabulary), titled
    "<document> › <section>", identity "section i of n of “<document>”". Same prompt, same compiler.
  - `build_giant_fingerprint(document, parents, groups, budget_tokens=2000)`: identity ("N sections, M parts"),
    STRUCTURE = every section as "ordinal. title (parents)", COVERAGE = `stratified_samples`: pass 1 the opening of
    EVERY section's first parent, labelled "[ordinal]" (the label costs 3 tokens, so a long title can never eat a
    section's only sample; the per-sample ceiling shrinks with the section count, floor 12 tokens), passes 2–5 the salient
    sentence of the middle, last and quartile parents, round-robin until the budget is spent; FRAMING = the first content
    section's opening; SYNTHESIS = the last section's closing; VOCABULARY = the document-wide term ranking (bare-number
    identifiers dropped). `builder_version = "fingerprint-giant-v1"`; `sources.coverage_by_section` receipts the sample.
    `base_prompt_blocks(fp)` renders the same evidence for the base `doc-profile-v3.2` prompt (IDENTITY / OPENING /
    SAMPLE i / ENDING / KNOWN TERMS), so both prompt paths see the same sampled evidence.
- **`projection.py`.** `SCOPE_DOCUMENT` / `SCOPE_SECTION`; `section_point_id(doc_id, section_key)`;
  `project_profile(…, section={key, title, heading_path, parent_ids, parent_count, ordinal}, input_hash=…)` upserts a
  SECTION point in the SAME collection (`polymath_document_profiles_<contract>`) with the document's `doc_id` /
  `corpus_id` and the payload `scope: section, section_key, section_title, heading_path, parent_ids, parent_count,
  section_ordinal, input_hash` (+ `compiled`, the surfaces, via `payload_extra`); a document point now carries
  `scope: document` (a point without the field is a document point — every point before F4). `fetch_existing_point`,
  `fetch_existing_surfaces(…, section_key=)`, `list_section_points`, `purge_section_points(…, keep_keys=)`.
  - `profile_nominate` is two queries: the document points (`must_not scope=section`) exactly as before F4, then the
    section points alone, `NOMINATE_OVERFETCH (4) × k` deep, collapsed onto their documents; merged by fused RRF score,
    ties keep the document query's order. So a giant's sections cannot crowd other documents out of the top-k, a document
    votes once at its best section, and a collection without section points nominates byte-identically to pre-F4.
- **`profile_atom.py` / `profile_atom_projection.py`.** A third family, `section`: `source_tag("section", hash, key)` =
  `section:<key>:<hash>`; `family_of` / `section_key_of`; `ProfileAtom.scope / section_key / parent_ids` (defaults keep
  every existing constructor and id byte-identical); `atom_id(…, section_key)` mixes in the section (two sections may
  state the same idea); `persist_atoms(source=section:…)` supersedes ONLY that section's rows — base / vNext supersession
  never touches section rows and vice versa; `active_atoms` reads the section tag back. `build_payload` adds `scope`,
  `section_key`, `parent_ids` for section atoms (document atoms: the pre-F4 payload). `ingest_section_atoms` = extract →
  persist (section-scoped) → `purge_section_atoms` (the section's own points) → project. No schema change: the section
  tag lives in `source_profile_hash`, whose `family:hash` grammar already existed; `parent_ids` live on the profile point.
- **`doc_profile_worker.py`.** Resolve + load moved OUTSIDE the stage transaction (pMAP's rule §28: never a transaction
  across an LLM call). For a giant (`POLYMATH_DOC_PROFILE_GIANT`, default on, part of the stage contract hash):
  `build_section_profiles` runs FIRST — per section: input → `input_hash`; skip when the section's point already carries
  this hash under the live prompt (unless `POLYMATH_DOC_PROFILE_FORCE_SECTIONS=1`); else one pool call
  (`run_key = run:section_key`, so consecutive sections rotate keys), compile, validity, `project_profile(section=…)`,
  `ingest_section_atoms` in its own short `tx()`; at most `POLYMATH_DOC_PROFILE_SECTIONS_PER_PASS` (8) built per pass;
  a transient pool error stops the pass; the rest is `pending` → `TransientStageHold("DOC_PROFILE_SECTIONS_PENDING…")`
  BEFORE the document call, so a held pass wastes nothing and the next pass resumes. When every section is done, orphan
  section points (a re-cut document) are purged, then the document profile is built from `build_giant_fingerprint`
  (`builder_version fingerprint-giant-v1`, `doc_profile.giant: true, sections: N`) and the stage artifact carries
  `doc_profile_sections` {version, threshold, sections_total, built[], skipped[] (with their surfaces from the point),
  failed[], pending[], transient_error, orphans_purged}. Small documents and the switch-off path are byte-identical to
  pre-F4 (the same prompt, hashes and artifact keys; the parent SELECT additionally reads `chunk_id`).
- **`scripts/profile_audit.py` (NEW, read-only)** + **`profile_coverage.py`**: per document, the top-50 terms (tf over
  the parents × idf over the library's documents, the skeleton's tokenizer) and the top-level section titles; the share
  of each present in the profile's text (stem match; a title counts when ≥ 60 % of its content words appear); score =
  0.6 × terms + 0.4 × titles, for the LLM profile (compiled surfaces + section profiles from the artifact + active atoms)
  and for `documents.retrieval_profile`; the worst N; every giant flagged with its planned sections and whether it has
  section profiles. `--doc` prints one document's missing terms and titles; `--json` writes every row.
- **`scripts/rebuild_profile.py` (NEW).** `--dry-run` (default, read-only): the plan, the lanes each call would try
  (`attempt_lanes(stage_pin("doc_profile"), …)` from config, no key read), and the EXACT input windows. `--execute`:
  `workers.doc_profile_worker.process_event` for the document's latest run — the fleet's own code path, lanes, limiter,
  compiler, projections, receipts and artifact; all sections in one pass by default; a pool hold is retried with backoff
  (`--max-passes`); `--force`, `--vnext`, `--out`. Exit 3 = a section failed (the artifact says which).
- Paperwork: scaffold TREE (7 entries), `scripts/README.md` (2 rows), `architecture/contract-dependencies.yaml`
  (PROFILE_PROJECTION paths + tests, PROFILE_ATOM tests). No register / CONTINUITY / plan-row edits.

## Proof
- **Unit (fakes; the dead-DSN harness).** `tests/determinism/test_giant_profile.py` 15 + `test_section_profile_lanes.py`
  6 = 21 passed: a 1,047-parent synthetic document (30 headings, one of 200 parents under 5 sub-headings, one of 1 parent,
  6 table-of-contents parents; 1,041 eligible) → every eligible parent in exactly one section, the 200-parent heading split into 5 × 40,
  the 1-parent heading folded, furniture excluded, keys stable; 300 parents → no sections, 301 → sections; a flat
  423-parent document → 3 positional parts, two flat 200-parent chapters → 2 + 2; the cap merges neighbours and drops
  nothing; the stratified sample labels every section once (also at 40 tokens per section) and each section's own noun
  reaches its sample; a section's input holds its own vocabulary and not its neighbours'; the worker loop (fake pool,
  stub embedder, in-memory Qdrant + Postgres): 8 sections → 8 calls, 8 points with `scope: section`, the document's
  `doc_id`, the section's `parent_ids`, `input_hash` and `compiled`; atom rows keyed by section with `section:` sources
  and section atom points; a second run → 0 calls, 8 skipped with their surfaces; `force` rebuilds section 1 and leaves
  section 2's atoms untouched; a pass of 2 → 2 built, 4 pending, no orphan purge; HTTP_429 → `transient_error` + pending,
  HTTP_400 → failed and the pass goes on; a re-cut document purges 2 orphan points; `process_event` holds the ticket
  ("DOC_PROFILE_SECTIONS_PENDING: 2/5 done, 3 pending") with no document call and no artifact, then the next pass builds
  the 3 remaining sections + the document profile from the stratified sample (`[1] … [5]` samples, `5 sections`,
  `sections_sampled: 5`, `doc_profile.giant`, `doc_profile_sections` built 3 / skipped 2, the document point
  `scope: document`); a small document and `POLYMATH_DOC_PROFILE_GIANT=0` keep the pre-F4 prompt and artifact keys. The
  lanes: an index with a giant reachable only through 12 section points → `profile_nominate(k=3)` returns 3 distinct
  documents with the giant in the top 2 (the document query's limit stays k, the section pool 4k); with the section
  points removed the giant's CPCS document point no longer reaches the motion question; one point per document → the
  same documents in the same order as the pre-F4 single query; `search_atoms` returns the giant's section atoms under its
  `doc_id`, the scout fuses profile + atom votes, `search_parent_maps` filtered to the nominated document lands on the
  section's parents; `project_profile(section=…)` writes the section shape and the section helpers read / purge it;
  section atoms have their own ids, family and payload, document atoms the pre-F4 payload and ids. The audit: blank → 0,
  the wrong vocabulary ("CPCS YAML JSON compiler how to HAS PROPERTY") < 0.1, all terms + titles ≥ 0.95, half the terms
  0.25–0.35, stems ("cameras", "lighting") cover their base term; a giant without section profiles is flagged.
- **Existing suites.** `tests/contracts -k "not test_live_"` 799 passed, 0 failed; the profile / atom / scope /
  fingerprint / knowledge-scope suites (`test_document_profile_{compiler,context,projection,stage}`, `test_profile_atom*`,
  `test_profile_{prompt_vnext,scout,selection}`, `test_document_fingerprint`, `test_knowledge_scope`,
  `test_search_atoms_callers_scoped`) 112 passed, 3 skipped (the stage tests need the fleet's Postgres: skipped under
  the dead DSN by design). The impact tool's list (23 files, `contract_impact.py --staged`): 289 passed, 5 failed —
  the SAME 5 fail on the untouched base checkout `pmv4-fix` under the same harness
  (`test_chat_runtime::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes`,
  `test_query_receipts::test_all_three_query_handlers_and_read_surfaces_are_wired`, and three
  `test_adapter_product_discovery_loop` cases that open the dead DSN), so none is this slice's;
  `tests/integration/test_cross_domain_routing.py` needs the repo root on the path (collection error on both).
  Guards: `agent_preflight`, `repo_guard`, `wiki_worm --check` → 0. Ruff: the new files clean (incl. the bandit `S`
  set); the four edited files 17 pre-existing findings vs 18 on the base (none added).
- **The audit, live `cinema`, read-only (2026-09-27, before any rebuild).** `scripts/profile_audit.py --corpus cinema`:

  | # | score | llm terms | llm titles | det terms | det titles | parents | giant | document |
  |---|---|---|---|---|---|---|---|---|
  | 1 | 0.13 | 16.0 | 8.7 | 16.0 | 4.7 | 132 | | Manga in Theory and Practice.md |
  | 2 | 0.18 | 14.0 | 14.3 | 16.0 | 21.4 | 78 | | Sidney Lumet - Making Movies (1994).md |
  | 3 | 0.18 | 20.0 | 15.6 | 16.0 | 5.2 | 114 | | Save the Cat.md |
  | 4 | 0.19 | 24.0 | 11.7 | 24.0 | 2.0 | 256 | | The Adweek Copywriting Handbook.md |
  | 5 | 0.23 | 22.0 | 20.0 | 30.0 | 13.3 | 209 | | Grammar of the Edit.md |
  | 6 | 0.24 | 34.0 | 8.0 | 16.0 | 0.0 | 469 | GIANT | Hey Whipple Squeeze This.md |
  | 7 | 0.26 | 24.0 | 11.4 | 40.0 | 4.9 | 197 | | What the Face Reveals.md |
  | 8 | 0.26 | 30.0 | 20.0 | 24.0 | 20.0 | 255 | | Sound Design The Expressive Power of Music Voice and Sound Effects… |
  | 9 | 0.26 | 24.0 | 11.1 | 14.0 | 44.4 | 97 | | Facial Action coding 3.0.md |
  | 10 | 0.27 | 26.0 | 28.6 | 16.0 | 42.9 | 540 | GIANT | Digital Compositing for Film and Video.md |

  67 documents; 11 giants, ALL without section profiles (parents · planned sections · llm score): Bruce Block 303 · 11 ·
  0.43; Digital Compositing for Film and Video 540 · 17 · 0.27; FACS (Ekman, Friesen, Hager) 331 · 4 · 0.05; Fight
  Choreography 423 · 3 · 0.24; Hey Whipple 469 · 39 · 0.24; Ken Dancyger 431 · 3 · 0.54; Rabiger, Directing 670 · 41 ·
  0.31; Ekman FACS Manual 323 · 4 · 0.50; The Art and Science of Digital Compositing 389 · 20 · 0.35; **VES Handbook
  1322 · 72 · 0.43** (52 % terms, 30 % titles); **handbook.html 802 · 25 · 0.34** (38 % terms, 27 % titles). The
  handbook's missing terms: provider, canonical, verification, compiler, camera, schema, state, evidence, laban, control,
  identity, target, failure, causal, …, continuity, pose, frame, temporal, trajectory, timing; missing titles: 16 of 22
  (Control plane, Format/carrier/compiler, Canonical IR, **Motion core, Camera, Time and rhythm, Force and physics**,
  Continuity, World model, Failure-aware repair, Verification, Style, Capture and surface realism, Provider capability,
  Deconstruction). Its `retrieval_profile` scores 0.19 (missing 18 of 22 titles).
- **The dry run, live, read-only.** `scripts/rebuild_profile.py --doc doc_63ba98…580dab --dry-run`: 802 parents, giant,
  **26 calls** (1 document + 25 sections: 01 Control plane 15 · 02 Format 28 · 03 Canonical IR 7 · 04 Motion core 92 ·
  05 Performance › {FACS action units 5, VAD trajectories 3, Living performance realism 7, Behavior layer 3, Natural
  dialogue mode 7, Paper — From Action Units to Action Beats 129, FACS / Laban / Bartenieff closure 40} · 06 Interaction
  67 · 07 Camera 6 · 08 Time and rhythm 9 (+ 09 Force and physics folded) · 10 Continuity 20 · 11 MX grammar 92 ·
  12 Director reasoning 88 · 13 World model 11 · 14 Failure-aware repair 88 · 15 Verification 4 · 16 Style 6 · 17 Capture
  12 · 18 Provider capability 9 · 19 Deconstruction 48 · 20 Research protocol 6; "00. How to read this book" and the
  title parent folded into 01). Lanes for the run key: `profile_groq3, profile_groq4, profile_fallback_openrouter`
  (rotating per section). Tokens ≈ 22.4K input + ~23K system prompt + up to 62K output. The document window (7,785
  chars, `used {identity 12, structure 308, framing 47, coverage 1287, synthesis 44, vocabulary 279}`): STRUCTURE = the
  25 sections; SAMPLE 4 = "[4] ## Kinetic motion direction manual — Kinetic Motion Direction Prompting: Agent-Friendly
  Manual for AI Video Motion, Fight Choreography, and Realistic Movement", SAMPLE 5 = "[5] ## FACS action units 04 —
  FACS: Action Units, Intensity, and Temporal Curves", SAMPLE 13 = "[13] ## Camera grammar for action 09 — Camera Grammar
  for Motion and Action Scenes", SAMPLE 23 = "[23] ## AI video control surfaces 14 — AI Video Model Capabilities and
  Control Surfaces" … (28 samples, every section, 23 of 25 twice). Section window #1 (3,903 chars): its own headings,
  identity "section 1 of 25 of “handbook”", 10 samples from its 15 parents. VES (`--vnext`): 1,322 parents, **73 calls**
  (72 sections: ACQUISITION/SHOOTING 340 → 25 sub-sections, POST-PRODUCTION 210 → 16, DIGITAL ELEMENT CREATION 174 → 14,
  PERFORMANCE AND MOTION CAPTURE 144, STEREOSCOPIC 3D 112, …, GLOSSARY 59), tokens ≈ 57K input + ~66K system + up to
  175K output; the document window samples 34 of 72 sections in pass 1 ("sections_sampled" ≤ the budget's 28–34 samples
  at 2,000 tokens — every section still appears in STRUCTURE, and the 72 section profiles carry the rest).
- **Not proven here (the orchestrating session, after the deploy):** the live rebuild of the two giants and the audit's
  after-numbers (the handbook's profile naming motion, camera, prompting), one FACET question through dualread / the scout
  reaching `handbook.html` via a section point. The `.env` ships `POLYMATH_DOC_PROFILE_VNEXT=0`: a rebuild without
  `--vnext` uses the base prompt (no ANCHOR / BRIDGE / TENSION lines → no bridge atoms for the sections); the existing
  2026-09-08 profiles are vNext.

## Contract dispositions
- **PROFILE_PROJECTION — UPDATED.** Section points beside document points, `scope`, the two-stage `profile_nominate`
  (byte-identical without section points: `test_one_point_per_document_nominates_exactly_as_before_f4`), the section
  helpers; `test_document_profile_projection.py` unchanged and green.
- **PROFILE_ATOM — UPDATED.** The `section` family and the scope fields; every pre-F4 id, tag, payload and supersession
  unchanged (`test_profile_atom*.py`, `test_search_atoms_callers_scoped.py` green; `test_section_atoms_have_their_own_ids_family_and_payload`).
- **PROFILE_SCOUT_INPUT / PROFILE_SCOUT_FUSION / PROFILE_SCOUT_OUTPUT — TESTED_UNCHANGED.** No code change; a section
  nomination is a thin profile hit and section atoms are atom hits (`test_section_atoms_route_to_their_document_and_the_scout_fuses_both_projections`).
- **CANDIDATE_ENGINE / QUERY_PLANNER / PROFILE_SCOUT_WIRING — NOT_AFFECTED.** Not edited (the compiler / F2 agent's
  files); they consume `profile_nominate` / `search_atoms` / `search_parent_maps` whose contracts (ordered doc_ids ≤ k;
  atom rows; map rows) are unchanged.
- **PROFILE_COMPILER, SURFACE_REGISTRY, PROJECTION_LIFECYCLE — NOT_AFFECTED.** Read, not changed.
- **ACCEPTANCE, ADAPTER_RUNTIME, EVIDENCE_BOUNDARY_API, EVIDENCE_PACKET, MCP_SURFACE, PROFILE_YIELD_RECEIPT,
  RESOLUTION_STATE, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE — NOT_AFFECTED.** Transitive consumers (through
  CANDIDATE_ENGINE / QUERY_PLANNER) of the nomination and atom contracts, whose shapes did not move: ordered `doc_ids`
  ≤ k, atom rows `{doc_id, corpus_id, atom_kind, text, atom_id, score}`, map rows. The impact tool's full test list
  (`contract_impact.py --staged`: 23 files) ran green under the dead-DSN harness (see Proof).
- **The `doc_profile` stage (no contract entry; `test_document_profile_stage.py`) — UPDATED.** The stage contract hash
  moves with `POLYMATH_DOC_PROFILE_GIANT` on; the stage tests' assertions hold (skipped here: they need the fleet's
  Postgres — to run before the merge with the fleet DSN).

## Rejected claims
- "Over-fetch the one nomination query and dedupe by document": no. Measured on the fake index, 12 section points of one
  giant fill a 4k pool of 12 and other documents vanish; the section pool must be its own query, and only that keeps the
  document query byte-identical.
- "Add `scope` / `section_key` / `parent_ids` columns to `document_profile_atoms`": no. A migration the deploy could miss
  would break every document's atom ingest; the `family:hash` tag already carries provenance, and `parent_ids` belong to
  the section's profile point (one place). A dedicated column is an open gap, not a silent fallback.
- "Build the sections inside the stage transaction": no (pMAP §28). A 60-call section loop would hold a transaction for
  ~10 minutes and a hold would roll its work back; per-section commits + a pre-document hold resume for free.
- "One profile per top-level heading, literally": no for VES (ACQUISITION/SHOOTING = 340 parents) and for flat books
  (Fight Choreography, 423 parents, no headings); the split and positional rules keep "one per heading" where it is true.
- "Labels with the section title in the coverage samples": no. Measured on the handbook, long titles ate the per-sample
  budget and 2 of 25 sections went unsampled; the ordinal label costs 3 tokens and STRUCTURE maps it to the title.

## Open contract gaps
- The live rebuild and its after-audit; the receipt question's FACET path through a section point (F7).
- The base prompt (`POLYMATH_DOC_PROFILE_VNEXT=0` in the fleet `.env`) yields no research-index surfaces for sections;
  the rebuild takes `--vnext`. Whether the fleet's ingest path should flip the flag is the owner's.
- `parent_ids` of section ATOM points survive only until a document-level re-projection rebuilds the document's atom
  points from rows (the rows carry the section key, not the parents); the section PROFILE point keeps them. A column on
  `document_profile_atoms` would make it durable — deferred, not silent.
- Section budgets (1,000 tokens per section, 2,000 for the giant document) are unmeasured against quality; the section
  count per giant (≤ 72) is a cap, not a measurement. A 64-section giant costs 65 calls at ~3.5K tokens each.
- No new lane reads `parent_ids` yet: routing lands on the section through the pMAP search of the nominated document,
  as today; a future lane may jump straight to a section's parents from its point.
- `retrieval_profile` (document-summary-v1, `profile_worker.py`) is unchanged: it still names entities and predicates
  ("how to HAS PROPERTY"); the audit prints its score beside the LLM profile's.
