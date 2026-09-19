"""WLK2C C2 — bounded concept-bridge compiler (pure core; the ONE LLM call is injected / lives in the
orchestrator, flag-gated, proven live at C7).

ACTIVATION, not invention (owner-locked). The compiler derives a better RETRIEVAL QUESTION for a
GROUNDED corpus concept the corpus already nominated (Scout/profile/graph) — it may NOT invent new
concepts or search domains. This is enforced twice: the prompt instructs the model to use only the
listed concepts, AND `parse_and_validate` deterministically DROPS any bridge whose `derived_from` is not
one of the provided concepts. So even if the model free-associates, an ungrounded bridge never survives.

Metadata, not authority. `proposed_role` (COMPLEMENTARY/DIVERGENT) and `model_confidence` are
observability only — C5 decides the authoritative role from the cross-encoder scores; confidence never
gates admission. Real admission is layered: C1 structural gate (here) → C4 semantic scoring → C5
portfolio rules.

One bounded call per ELIGIBLE query (creative/synthesis intent with a nominated concept that has no
admissible existing bridge). FAST/simple-factual queries never reach the compiler. The `generate`
callable (the single structured Gemma JSON call, low temperature) is injected so this whole path is
deterministic + unit-testable with a fake.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from polymath_shared.bridge_admission import structural_bridge_admissibility
from polymath_shared.retrieval_lineage import DiscoveryPath

PROPOSED_ROLES = ("COMPLEMENTARY", "DIVERGENT")
#: intents that permit latent expansion (the compiler never runs for a simple factual/FAST turn).
LATENT_INTENTS = ("CREATIVE", "SYNTHESIS", "EXPLORE", "IDEATE", "DESIGN", "TRANSFORM")
MAX_BRIDGES = 4


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@dataclass
class Concept:
    """A nominated corpus concept — the GROUNDING set. `key` is stable (doc_id/slug); `label` is human."""
    key: str
    label: str
    source: str = ""                       # doc_id / profile id behind it (rides into inspired_by_profile)

    def to_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "source": self.source}


@dataclass
class BridgeCompilerInput:
    q0: str
    intent: str
    concepts: list = field(default_factory=list)             # [Concept] nominated corpus concepts
    existing_subqueries: list = field(default_factory=list)   # [str] already-compiled subqueries
    graph_relations: list = field(default_factory=list)       # [str] optional explicit relations


@dataclass
class CompiledBridge:
    bridge_id: str
    bridge_query: str
    derived_from: str                      # a provided concept key (enforced — activation not invention)
    relation_to_q0: str
    proposed_role: str = "COMPLEMENTARY"   # HINT only — C5 authoritative
    model_confidence: float | None = None  # observability only — NEVER gates admission

    def to_dict(self) -> dict:
        return {"bridge_id": self.bridge_id, "bridge_query": self.bridge_query,
                "derived_from": self.derived_from, "relation_to_q0": self.relation_to_q0,
                "proposed_role": self.proposed_role, "model_confidence": self.model_confidence}


def compiler_eligible(intent: str, concepts: list, admissible_existing_bridge_concepts) -> tuple[bool, str]:
    """Deterministic: run the compiler only when the task permits latent expansion AND ≥1 nominated
    concept has NO admissible existing bridge already covering it. `admissible_existing_bridge_concepts`
    = the set of concept keys already covered by a C1-admissible existing subquery/graph path.
    Returns (eligible, reason)."""
    if (intent or "").strip().upper() not in LATENT_INTENTS:
        return False, "intent_not_latent"
    covered = {str(k) for k in (admissible_existing_bridge_concepts or ())}
    uncovered = [c for c in concepts if str(getattr(c, "key", c)) not in covered]
    if not concepts:
        return False, "no_nominated_concepts"
    if not uncovered:
        return False, "all_concepts_have_admissible_bridge"
    return True, "eligible"


def build_prompt(inp: BridgeCompilerInput, *, max_bridges: int = MAX_BRIDGES) -> str:
    """Assemble the bounded, grounded prompt for the single structured call. Lists ONLY the nominated
    concepts as the allowed `derived_from` universe and forbids inventing new concepts/domains."""
    concepts = "\n".join(f"  - key={c.key!r} concept={c.label!r}" for c in inp.concepts)
    subs = "\n".join(f"  - {s!r}" for s in inp.existing_subqueries) or "  (none)"
    rels = "\n".join(f"  - {r!r}" for r in inp.graph_relations) or "  (none)"
    return (
        "You are a retrieval BRIDGE compiler. Your only job is ACTIVATION: for each listed corpus "
        "concept that could help answer the user's question, write ONE better retrieval question that "
        "would surface that concept's material from the library.\n\n"
        f"USER QUESTION (q0): {inp.q0!r}\n"
        f"TASK INTENT: {inp.intent!r}\n\n"
        "ALLOWED CORPUS CONCEPTS (you may ONLY derive bridges from these — do NOT invent new concepts, "
        "domains, books, or topics that are not listed):\n"
        f"{concepts}\n\n"
        f"EXISTING SUBQUERIES (do not duplicate these):\n{subs}\n\n"
        f"GRAPH RELATIONSHIPS (optional grounding):\n{rels}\n\n"
        f"Output a JSON array of AT MOST {max_bridges} objects, each:\n"
        '  {"bridge_id": "<short id>", "bridge_query": "<a specific retrieval question>", '
        '"derived_from": "<the key of one ALLOWED concept above>", '
        '"relation_to_q0": "<one short clause: how this concept helps answer q0>", '
        '"proposed_role": "COMPLEMENTARY" | "DIVERGENT", "model_confidence": <0..1>}\n\n'
        "Rules: derived_from MUST be one of the allowed concept keys. bridge_query must be a distinct "
        "information need, not a paraphrase of q0. Do not free-associate to unlisted domains. If no "
        "listed concept helps, return []. Output ONLY the JSON array."
    )


def _loads(raw) -> list:
    """Parse the model output to a list of dicts; tolerant of ```json fences and stray prose. Fail-open."""
    if isinstance(raw, (list, dict)):
        data = raw
    else:
        s = (raw or "").strip()
        m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
        if m:
            s = m.group(1).strip()
        if not s:
            return []
        try:
            data = json.loads(s)
        except Exception:
            m2 = re.search(r"\[.*\]", s, re.S)          # last resort: the first JSON array in the text
            if not m2:
                return []
            try:
                data = json.loads(m2.group(0))
            except Exception:
                return []
    if isinstance(data, dict):
        data = data.get("bridges") or data.get("results") or [data]
    return data if isinstance(data, list) else []


def parse_and_validate(raw, inp: BridgeCompilerInput, *, max_bridges: int = MAX_BRIDGES) -> tuple[list, dict]:
    """Parse the model's JSON and keep only ADMISSIBLE bridges. Deterministic. Drops a bridge that:
    invents a concept (derived_from ∉ provided keys — the activation-not-invention guard); has an empty
    query or no relation_to_q0; fails the C1 structural gate (paraphrase/boilerplate/duplicate). Role is
    sanitized to a hint; confidence is recorded but NEVER gates. Caps at `max_bridges`, dedups by query."""
    by_key = {_norm(c.key): c for c in inp.concepts}
    by_label = {_norm(c.label): c for c in inp.concepts}
    diag = {"generated": 0, "admitted": 0, "dropped_invented": 0, "dropped_no_relation": 0,
            "dropped_structural": 0, "dropped_empty": 0, "dropped_dup": 0}
    out: list[CompiledBridge] = []
    seen: set[str] = set()
    for i, obj in enumerate(_loads(raw)):
        if not isinstance(obj, dict):
            continue
        diag["generated"] += 1
        bq = str(obj.get("bridge_query") or "").strip()
        df = str(obj.get("derived_from") or "").strip()
        rel = str(obj.get("relation_to_q0") or "").strip()
        if not bq:
            diag["dropped_empty"] += 1; continue
        concept = by_key.get(_norm(df)) or by_label.get(_norm(df))
        if concept is None:                              # INVENTED concept — the activation guard
            diag["dropped_invented"] += 1; continue
        if not rel:
            diag["dropped_no_relation"] += 1; continue
        path = DiscoveryPath(origin_query=bq, origin="BRIDGE", query_id=f"bridge:{i}",
                             bridge_id=f"bridge:{i}", inspired_by_profile=[concept.source] if concept.source else [])
        if not structural_bridge_admissibility(path, inp.q0).admissible:
            diag["dropped_structural"] += 1; continue
        nq = _norm(bq)
        if nq in seen:
            diag["dropped_dup"] += 1; continue
        seen.add(nq)
        role = str(obj.get("proposed_role") or "").strip().upper()
        conf = obj.get("model_confidence")
        out.append(CompiledBridge(
            bridge_id=str(obj.get("bridge_id") or f"bridge:{i}"),
            bridge_query=bq, derived_from=concept.key, relation_to_q0=rel,
            proposed_role=(role if role in PROPOSED_ROLES else "COMPLEMENTARY"),
            model_confidence=(float(conf) if isinstance(conf, (int, float)) else None)))
        if len(out) >= max_bridges:
            break
    diag["admitted"] = len(out)
    return out, diag


def compile_bridges(inp: BridgeCompilerInput, *, generate, max_bridges: int = MAX_BRIDGES) -> tuple[list, dict]:
    """The pure orchestration: build the prompt → ONE injected structured call `generate(prompt)` →
    parse + validate. `generate` is the single low-temperature Gemma JSON call in production; a fake in
    tests. No concepts ⇒ no call. Never raises (a failed/garbage generation ⇒ [] + diag)."""
    if not inp.concepts:
        return [], {"generated": 0, "admitted": 0, "skipped": "no_concepts"}
    prompt = build_prompt(inp, max_bridges=max_bridges)
    try:
        raw = generate(prompt)
    except Exception as e:  # noqa: BLE001 — the compiler is additive; a model failure never breaks the turn
        return [], {"generated": 0, "admitted": 0, "error": f"{type(e).__name__}"}
    return parse_and_validate(raw, inp, max_bridges=max_bridges)
