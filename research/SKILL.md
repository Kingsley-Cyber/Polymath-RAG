---
name: opportunity-research
description: "USE THIS whenever the user asks for product leads, product ideas/ideation, opportunities, niches, what to sell, or a research run over Polymath/the corpus. Run the controller (init → step → submit …); NEVER improvise a brief by querying Polymath directly — the corpus is one evidence lane, the graph enforces evidence, allocation and a 3–6 product portfolio."
version: 1.6.0
platforms: [macos, linux]
metadata:
  hermes:
    tags: [ecommerce, research, alibaba, graph, polymath, rag, corpus, opportunity, leads]
    category: business
---

# Opportunity Research — the semantic constitution

> **When you are asked for leads, product ideas, niches, "what could we sell", or a
> research run: run THIS controller. Do not call Polymath's chat/retrieve yourself
> and summarize — that returns the corpus's own examples (a marketing transcript
> yields the marketer's five case studies) and nothing enforces evidence,
> independence, allocation across hypotheses or the product portfolio. The
> controller calls Polymath for you (its receipts show client
> `opportunity-research/corpus_polymath`); a brief written from direct calls is
> not a run and must not be presented as evidence-backed.**


Turn abstract knowledge into qualified, evidence-backed product leads by walking
an explicit control graph. You do not improvise the process; the graph and the
Python controller decide what runs next. You supply reasoning at the nodes that
ask for it.

## The invariant (never violated)

> The corpus knows (Polymath or any backend meeting docs/18). The registry
> gives you reusable reasoning coordinates. The
> Control Graph decides how this skill operates. You (θ) construct latent
> bridges. Python (φ) constrains and validates them. The Work Graph records the
> current investigation. Your existing web stack tests the unknowns against
> real people. **Alibaba is searched only after a plausible mechanism survives
> evidence testing.** Validated discoveries may PROPOSE registry additions;
> only reviewed promotion changes the curated registry.

Concretely:
- **Never begin with Alibaba.** Begin with evidence or an opportunity thesis.
- Corpus first — whatever backend the host exposes (Polymath MCP today; any
  RAG stack, vector store, or file corpus meeting docs/18), queried through
  the agent's tools only — never Mongo/Qdrant/Neo4j directly. Record the
  backend with `init --corpus "<id>"`; no corpus = capability_failure at the
  corpus node, an honest deficit, never a fake grounding.
  ENRICHED-TRANSCRIPT SHORTCUT: docs with `trail_signal: true` frontmatter
  carry a `## 10. Trail-Signal Layer` — a pre-structured opportunity_primitives
  yaml block, role-tagged verbatim evidence quotes (FRICTION_EVIDENCE /
  WORKAROUND_EVIDENCE / PURCHASE_INTENT ...), niche scopes, genesis +
  suggested_mode. LIFT these directly: the yaml block seeds the `primitives`
  submission; the tagged quotes become observation seeds (label their source
  identity from the doc's platform/author metadata); suggested_mode informs
  which graph to init. Never re-derive what the layer already states — but
  its quotes still pass the same evidence-authority gates as any other source.
- Interpret abstract material through the selected lenses.
- Generate MULTIPLE bridge hypotheses with every hop written out and an
  explicit evidence boundary (`first_inference_at`).
- Identify unsupported links; test them against real communities using your
  EXISTING web stack (scrape waterfall, camofox, agent-reach). No new browser layers.
- Prefer comments containing behavior, complaints, adaptations, comparisons,
  purchase seeking, workarounds (see prompts/evidence_judgment.md).
- Alibaba establishes SUPPLY (price/MOQ/variants/suppliers/pictures) — never demand.
- Return: evidence, inference boundaries, mechanism, candidate products,
  supplier data, unresolved risk. Abstention (`NO_DEFENSIBLE_BRIDGE`) is a
  SUCCESS outcome for weak signals — forcing a product is the failure mode.

## When this skill fires

King asks for opportunity research, product research from an idea/transcript/
corpus, "find product leads", "what could we sell to X", or invokes it by name.
NOT for direct "look up this product on Alibaba" asks (that's plain sourcing).

## How you drive it (the loop)

All commands use the Hermes venv python from this skill's directory:

```
PY=~/.hermes/hermes-agent/venv/bin/python
SKILL=~/.hermes/skills/business/opportunity-research

$PY $SKILL/python/controller.py init   --state $SKILL/candidates/<run>.json --signal "<seed text>"
$PY $SKILL/python/controller.py status --state $SKILL/candidates/<run>.json
$PY $SKILL/python/controller.py submit --state $SKILL/candidates/<run>.json --node <node> --file /tmp/out.json
$PY $SKILL/python/controller.py step   --state $SKILL/candidates/<run>.json
$PY $SKILL/python/controller.py context-export --state $SKILL/candidates/<run>.json   # working_context.md (debug/recovery projection)
```

Loop: `status` → do exactly what `needs` says (reason nodes name their prompt
file; agent nodes use your normal tools; transform/gate nodes just need `step`)
→ `submit` outputs → `step` → repeat until `node: stop`. The controller
rejects out-of-order submissions, schema violations, and illegal transitions —
when it rejects you, fix the input; never bypass it.

**Context law (docs/10):** every pending action ships a frozen
`context_envelope` — RunBrief + ActionContext compiled from each node's
ContextContract. That envelope IS your working context for the action: do not
rely on earlier conversation turns, and do not re-feed the whole run history
to the model. Crash-resume returns the same envelope. `working_context.md` is
a one-way human projection, never canonical state.

## Preference Control Plane (docs/16 — the user's levers)

When King expresses HOW he wants research done ("keep digging until 15,
heavy on comments, best 5 final, don't waste time on Alibaba"), you compile
it into settings — never edit config/code. Follow
prompts/preference_compiler.md:

```
$PY $SKILL/python/settings.py describe --mode niche_loadout   # discover levers
$PY $SKILL/python/settings.py explain --id community_strength # teach a lever
$PY $SKILL/python/settings.py presets                          # FAST_SCAN / DEEP_INSIDER / BLUE_OCEAN / ...
controller.py init ... --preset DEEP_INSIDER --settings /tmp/patch.json
$PY $SKILL/python/settings.py apply --state run.json --file /tmp/patch.json  # mid-run revision
```

Laws: user targets are DESIRED stopping conditions ("dig until N" attempts N
within round ceilings + stagnation detection — never forever); discovery
quantity ≠ final quantity (loadout final stays 3-6, always); SYSTEM_LOCKED
evidence laws refuse overrides — relay the reason, never work around it;
mid-run changes are versioned revisions, effective from the next action, and
show up in the report's Preference History.

## Qualification + lifecycle (docs/15 — architecture FROZEN at v1)

No new layers. Before trusting config changes: `controller.py doctor` (fail-
closed lint of every graph/policy/schema/prompt/executor/condition reference;
duplicate YAML keys are hard errors). Lifecycle controls: `pause` / `resume`
/ `abandon --reason` — never kill a process. When an external capability is
down (Trends, Alibaba, a site), submit
`{"capability_failure": {"capability": "...", "detail": "..."}}` at the
agent node — the run continues with an honest recorded deficit and downstream
gates produce honest verdicts (e.g. MECHANISM_WITHOUT_SUPPLY), never fake
success. Settings: `init --settings file.json` — USER_SAFE/ADVANCED_SAFE
knobs per graph/settings_schema.yaml; SYSTEM_LOCKED evidence laws refuse
overrides. Qualification report: `qualify.py --states <runs...>` — zero
invariant violations is the bar.

## Four modes, one spine (docs/12-14)

Four traversal directions through the same latent commerce space — same
controller, memory, context compiler, evidence authority, reports:

```
init --graph control_graph.yaml           # OPPORTUNITY_RESEARCH: opportunity -> evidence -> product
init --graph loadout_graph.yaml           # NICHE_LOADOUT: niche -> lived world -> 3-6 products
init --graph market_discovery_graph.yaml  # MARKET_DISCOVERY: market -> niches -> whitespace -> 3-8 scopes
init --graph product_anchored_graph.yaml  # PRODUCT_ANCHORED: product -> meanings -> defensible markets
```

Discovery-mode laws: the blind lanes (field / trends / corpus / supply) stay
isolated until merge — their ContextContracts exclude each other, so never
paste one lane's findings into another lane's action. Seller/user claims are
quarantined UNVERIFIED; Trends ≠ sales; supplier listings ≠ demand; a
reframe (NO_DEFENSIBLE_MARKET, PRODUCT_REFRAMED) is a success outcome.
Promoted results hand off via `controller.py handoff --state parent.json
--to-mode niche_loadout --scope <id> --out child.json` — a NEW child run
with a HandoffPacket; never re-type or continue the parent.

## Commercial intelligence (after a run terminates — docs/11)

The research verdict is frozen first; then you may project it into market /
product / style / ad intelligence. Never inside the run:

```
$PY $SKILL/python/intelligence.py packet --state <run>.json --out /tmp/packet.json
# reason over the packet with prompts/commercial_intelligence.md → /tmp/intel.json
$PY $SKILL/python/intelligence.py admit  --state <run>.json --file /tmp/intel.json
$PY $SKILL/python/report.py build  --state <run>.json --out /tmp/model.json
$PY $SKILL/python/report.py render --model /tmp/model.json --out report.html --layout COMMERCIAL
```

φ admission computes authority from evidence lineage (GROUNDED/PARTIAL/
SPECULATIVE), rejects duplicates and generic angles, and selects the angle
PORTFOLIO by hook-type coverage. Fabricated refs fail. Research keys are
refused — a qualified product is still qualified if this layer never runs.

Run states live in `candidates/` (the Work Graph — JSON, non-authoritative,
NEVER promoted into the corpus backend's stores). Registry discoveries become
`registry_candidates` entries in the state (schema registry_candidate.json),
reported to King for review — you never edit `registry/` yourself.

## Delegation shape

Run the whole investigation as an ASYNC delegated child (this is heavy link
work — the standing Codex-style rule applies): ack King in one bubble, child
walks the graph, you relay the lead report + state path when it wakes you.
The child inherits this SKILL.md; the controller keeps it honest.

## Node-by-node cheat sheet

| node | type | you do |
|---|---|---|
| understand | reason | prompts/latent_interpretation.md → submit `signal` |
| corpus | retrieve | `python3 python/corpus_polymath.py --state run.json --out payload.json` — probes `/capabilities`; a native Polymath ANSWERS each compiled reformulation through the full RAG (`/chat evidence=true`: rerank, graph + latent lanes, synthesis with citations) → `corpus_evidence` rows + `corpus_answers` (docs/22; `--via plan` = rows only, `--generic` = docs/18 control). Corpora may be named by display name. Submit `corpus_evidence` (+ `corpus_backend`, `corpus_answers`) |
| lenses | transform | just `step` (python selects lenses) |
| hypothesize | reason | prompts/bridge_hypothesis.md → submit `hypotheses` |
| challenge | reason | prompts/contradiction.md → submit `challenges` + updated `hypotheses`; REJECTED needs a contradicted gap or spent budget — a starved hypothesis stays CHALLENGED (docs/20 §1) |
| gaps | transform | just `step` (compiles gaps + research queries) |
| web_research | agent | first `python3 python/field_evidence.py --state run.json --out cands.json` (past field evidence for the open gaps, docs/21 step 3; review before submitting), then run compiled `queries` in `allocation_rank` order (starved hypotheses first, docs/20 §1) → submit `observations` per prompts/evidence_judgment.md; `status` shows threads per gap and per hypothesis |
| curate | transform | just `step` (dedupe, close/contradict gaps, count rounds) |
| mechanism | reason | prompts/mechanism_mapping.md → submit `mechanisms` + `product_candidates` |
| product_ideation | reason | prompts/product_ideation.md → submit `product_concepts`: 3–6 concepts on SUPPORTED mechanisms, distinct form factors, ≥2 variations each, `evidence_refs` = observation ids (docs/19 portfolio law) |
| supplier_search | agent | `data.sourcing_plan` = one search job PER CONCEPT (compiled on entry) → Alibaba per concept → submit `supplier_candidates` each with `concept_id` (price_raw, moq_raw, url, images); a concept with no candidate is reported UNSOURCED, never covered by another concept's listing (docs/20 §2) |
| normalize_supplier | transform | just `step` |
| qualify | gate | just `step` → verdict + `leads[]` + `data.utilization` (the evidence receipt, docs/21; also in `status`, `triage-run --markdown`, report) |

## Corpus lane + flywheel (docs/19)

- **Primitives and hops cite rows.** `primitives.evidence_refs` and
  `hypotheses[].hop_refs` name `corpus_evidence` ids; `bridge.require_hop_refs`
  (ON by default) makes the controller reject evidence-side hops without a known row —
  every hop before the evidence boundary must name the corpus rows or observations behind it.
- **Analogies from the corpus.** Graph-lane rows (`graph_fact` / `graph_hop`)
  that overlap the primitives become `CORPUS_FACT_HYPOTHESIS` analogies at
  `lenses` — hypotheses to test, never evidence.
- **Web queries are keyword forms** with `subreddit_hints` from the
  `communities` you may submit at `understand`. Stamp `query_id` /
  `query_used` on each observation; `status` shows `independent_threads` and
  `need_more` per gap while you research.
- **Registry growth.** A SUPPORTED bridge auto-proposes MECHANISM / FRICTION /
  ACTIVITY / QUERY_PATTERN candidates (`registry_candidates`, PROPOSED, cite
  observations). After a run: `python3 python/export_research_evidence.py
  --state run.json` appends curated observations to
  `registry/research_evidence.csv` (idempotent).

## Run triage — lay out the run's bugs (read-only)

When a run stalls, a verdict looks wrong, or before you report, run:

```bash
python3 python/controller.py triage-run --state candidates/run1.json --markdown
```

It lists every way the run is wrong, with a severity, a stable code, WHERE
it is and the FIX: BLOCKER (JSON and SQLite disagree, config drift, the
one-writer law broken), DEFECT (rows that today's validator would reject,
a gap closed on one voice, a source claiming a role it may not establish,
a currency-blind price), SMELL (starved gaps, stalled actions, exhausted
loops, recorded deficits and warnings). qualify.py's invariants ride along
as `QUALIFY`. Exit code 1 when a BLOCKER or DEFECT exists — gate on it. It
never mutates state: fix what it names, then `step`.

## Polymath as the corpus (docs/18 reference adapter)

At the `corpus` node, when the backend is Polymath:

```bash
python3 python/corpus_polymath.py --state candidates/run1.json --corpus ecom-meta-v1 \
    --query "<reformulation 1>" --query "<reformulation 2>" --out rows.json
python3 python/controller.py submit --state candidates/run1.json --node corpus --file rows.json
```

It queries the orchestrator's `/retrieve` (`$POLYMATH_URL`, default
`http://127.0.0.1:7200`; `$POLYMATH_API_KEY` for the gated remote), keeps
only contract rows (`id`, `summary`, `source` — document profiles and
verbatim chunks, titles as the auditable origin), dedupes across queries, and
writes the exact submit payload. Nothing back → it writes the docs/18 §6
`capability_failure` payload instead; submit that and the run continues with
an honest deficit. Pull a WIDE net: several reformulations, cross-domain on
purpose — recall beats precision here. Authority is unchanged: every row is
corpus_evergreen knowledge fuel; demand is proven only in the web lanes.

## Final report to King

Texting style, 1-2 bubbles + the file: verdict, top leads (name, price, MOQ,
supplier, evidence score), the strongest verbatim quote behind the winner, and
unresolved risks. Attach the state JSON path; save a digest to Mnemosyne.

## Registry flywheel (docs/17 — autonomous compounding)

Terminal gates auto-emit RegistryCandidates (query patterns that closed gaps,
sources that yielded, surviving whitespace/reroute/bridge/reasoning motifs,
negative motifs) — never ask King to run maintenance. Periodically (or after
several runs):

```
$PY $SKILL/python/maintenance_triggers.py evaluate [--create-run candidates/maint_N.json]   # then step the maintenance graph to human_approval (docs/23); patch, never a live edit
$PY $SKILL/python/gap_analysis.py --state <terminal-run>.json   # typed demand gaps, any mode
```

Cross-run recurrence fires the triggers; a fired trigger opens a Registry
Maintenance run (promotion still needs King's L5 approval — no autonomous
CSV edits, ever). Genesis tags (PROBLEM_LED … DEMAND_REROUTE) shape research
emphasis only. CaptureFeasibility (entry_surface → capture_gate) can exclude
HOSTILE-entry scopes: great demand can still be a hostile market.
