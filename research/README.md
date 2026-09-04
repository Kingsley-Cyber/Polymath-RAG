# TRAIL_AGENT_AUTORESEARCH

Graph-run product-opportunity research for an agent. A signal — a transcript,
a niche, a market, a product idea — goes in; qualified, evidence-backed
product leads come out. The agent (θ) supplies reasoning only at the nodes
that ask for it; deterministic Python (φ) decides what runs next, constrains
every submission against JSON schemas, and records the run as a Work Graph.
Forcing a product is the failure mode: `NO_DEFENSIBLE_BRIDGE` is a success
outcome.

**The invariant:** evidence before supply. Alibaba establishes price/MOQ/
suppliers only after a plausible demand mechanism survives evidence testing —
never first.

Full operating contract: [SKILL.md](SKILL.md). Design history: [docs/](docs/)
and [WORKLOG.md](WORKLOG.md).

## Quickstart

Python ≥ 3.9. One third-party dependency (PyYAML).

```
pip install -r requirements.txt
python3 tests/run_all.py            # full check suite, dependency-free harness (RUN_ALL_CONTINUE=1 to see every failure)
python3 python/controller.py doctor # fail-closed lint of graphs/policies/schemas/prompts
```

A fresh clone is runnable immediately: `registry/compiled/` is a gitignored
build cache that self-compiles from the authoritative CSVs in
`registry/trailsignal/` on first use. After editing registry CSVs, rebuild
explicitly with `python3 python/registry.py build` — live CSV edits never
silently change runtime behavior (docs/06).

## Driving a run

```
python3 python/controller.py init   --state candidates/run1.json --signal "<seed text>" --corpus "polymath-mcp"
python3 python/controller.py status --state candidates/run1.json
python3 python/controller.py submit --state candidates/run1.json --node <node> --file out.json
python3 python/controller.py step   --state candidates/run1.json
python3 python/controller.py triage-run --state candidates/run1.json --markdown   # lay out the run's bugs (read-only)
python3 python/corpus_polymath.py --state candidates/run1.json --corpus <polymath corpus_id> --out rows.json  # docs/18 adapter
```

The retrieval seam is corpus-agnostic (docs/18): Polymath MCP, any RAG
stack, vector store, or file corpus can fuel a run — retrieve nodes need
rows of `{id, summary, source}`, and `--corpus` records which backend fed
this run (provenance in every envelope and the report header). Corpus rows
are knowledge fuel only — they can never establish demand; live communities
stay the demand truth. No corpus available = an honest recorded
`capability_failure`, never fake grounding.

Loop: `status` → do exactly what `needs` says (reason nodes name their prompt
file under `prompts/`; agent nodes use your web stack; transform/gate nodes
just need `step`) → `submit` → `step` → repeat until `node: stop`. The
controller rejects out-of-order submissions, schema violations, and illegal
transitions — fix the input, never bypass it.

## Four modes, one spine

| graph | mode | direction |
|---|---|---|
| `control_graph.yaml` | OPPORTUNITY_RESEARCH | opportunity → evidence → product |
| `loadout_graph.yaml` | NICHE_LOADOUT | niche → lived world → 3–6 products |
| `market_discovery_graph.yaml` | MARKET_DISCOVERY | market → niches → whitespace → 3–8 scopes |
| `product_anchored_graph.yaml` | PRODUCT_ANCHORED | product → meanings → defensible markets |

Same controller, memory, context compiler, evidence authority, and report
layer under all four. Preferences ("keep digging until 15, best 5 final")
compile into validated settings — `python3 python/settings.py describe
--mode niche_loadout` lists the levers; presets via `settings.py presets`.

## Repo map

- `graph/` — control graphs + policies + settings schema (YAML, doctor-linted)
- `python/` — controller, executors, verifiers, context compiler, reports
- `prompts/` — per-node reasoning contracts for the agent
- `schemas/` — JSON schemas every submission is validated against
- `registry/` — curated TrailSignal CSVs (authoritative) + compiled snapshot (cache)
- `candidates/` — run states (Work Graph JSON, never committed)
- `docs/` — numbered design docs; architecture frozen at v1 (docs/15)
- `tests/run_all.py` — the whole suite; exits non-zero on first failure

## Deployment

Runs standalone from any checkout. In Hermes it lives at
`~/.hermes/skills/business/opportunity-research` (this same repo, pulled) and
fires per SKILL.md. CI runs the suite + doctor on every push.
