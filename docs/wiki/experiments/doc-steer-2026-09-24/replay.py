"""DOC-STEER-V1 replay ($0 — no LLM call; gap D-10, the owner's idea of 2026-09-24). The five stored questions of
RETRIEVAL-PATHWAYS-5Q, replayed through the candidate engine against the live stores + local embedder / reranker:
  base    — the chat config before the SEE ALSO changes (skeleton routes, the judge in WILDCARD, the probe gate), blend off
  blend   — the live config since 11.475: the question's documents' SEE ALSO lines (4), each blended with the question (0.7)
  steer   — blend + 4 more lines of the mode's document-level kinds from the same documents, ranked and blended the same way:
            HYBRID CONCEPT · GRAPH BRIDGE + ANCHOR · WILDCARD THEORY + CONCEPT + LATENT_PATTERN + TENSION + INVERSION
  steer60 — WILDCARD only: steer with the question weighted 0.6
No production code changes. The extra lines go through the production blend path: a wrapper around `search_atoms` answers
the blend's SEEALSO call with 4 SEEALSO lines + 4 lines of the mode's kinds (same documents, same question ranking), and
POLYMATH_CHAT_SEEALSO_BLEND_ITEMS=8 grows the lane cap by the same rule the engine uses. A wrapper around
`seealso_blend.blend_rows` records which line found each passage. One untimed warm-up pass runs first, so the first config
does not pay the cold caches. Each question runs in its own stored mode and in GRAPH. Run from the main checkout with the
main .env loaded. Writes replay.json next to this file.
Follow-up switches (all optional): DOC_STEER_WILDCARD_KINDS (comma list; replaces WILDCARD's extra kinds),
DOC_STEER_MODES (comma list; only these runs), DOC_STEER_CONFIGS (comma list), REPLAY_OUT (output file name)."""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = HERE.parent / "retrieval-pathways-2026-09-23" / "results.json"
_spec = importlib.util.spec_from_file_location("skeleton_replay", HERE.parent / "skeleton-routing-2026-09-23" / "replay.py")
SK = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SK)

#: the mode's document-level lines added on top of the SEE ALSO blend (CONTINUITY Next Action 0b)
EXTRA = {"HYBRID": ("CONCEPT",), "GRAPH": ("BRIDGE", "ANCHOR"),
         "WILDCARD": tuple(k for k in (os.environ.get("DOC_STEER_WILDCARD_KINDS")
                                       or "THEORY,CONCEPT,LATENT_PATTERN,TENSION,INVERSION").split(",") if k)}
MODES = tuple(m for m in (os.environ.get("DOC_STEER_MODES") or "").split(",") if m)
#: config → (blend flag, question weight, lines, the mode's extra lines on)
CONFIGS = {"base": ("0", "0.7", 4, False), "blend": ("1", "0.7", 4, False), "steer": ("1", "0.7", 8, True),
           "steer60": ("1", "0.6", 8, True)}
CONFIGS = {k: v for k, v in CONFIGS.items()
           if k in ("base", "blend") or not os.environ.get("DOC_STEER_CONFIGS")
           or k in os.environ["DOC_STEER_CONFIGS"].split(",")}
SEE_K, EXTRA_K = 4, 4
STATE: dict = {"extra": (), "lines": [], "found": {}}


def _install_wrappers() -> None:
    from polymath_shared import seealso_blend as _sb
    from polymath_shared.document_profile import profile_atom_projection as _pap
    orig_search, orig_rows = _pap.search_atoms, _sb.blend_rows

    def search_atoms(client, collection, query_vec, kinds, k=12, *, corpus_ids, doc_ids=None):
        if doc_ids is None or tuple(kinds) != ("SEEALSO",):
            return orig_search(client, collection, query_vec, kinds, k, corpus_ids=corpus_ids, doc_ids=doc_ids)
        see = orig_search(client, collection, query_vec, ("SEEALSO",), SEE_K, corpus_ids=corpus_ids, doc_ids=doc_ids)
        extra = (orig_search(client, collection, query_vec, STATE["extra"], EXTRA_K, corpus_ids=corpus_ids, doc_ids=doc_ids)
                 if STATE["extra"] else [])
        STATE["lines"] = [{"kind": a.get("atom_kind"), "text": a.get("text"), "doc_id": a.get("doc_id"),
                           "score": a.get("score")} for a in see + extra]
        return see + extra

    def blend_rows(items, item_vectors, **kw):
        rows, trace = orig_rows(items, item_vectors, **kw)
        for r in rows:
            STATE["found"].setdefault(str((r.get("payload") or {}).get("chunk_id") or ""), r.get("fanout_atom"))
        return rows, trace

    _pap.search_atoms, _sb.blend_rows = search_atoms, blend_rows


def _once(mode: str, question: str, cp: dict, cfg: str) -> dict:
    flag, alpha, items, extra = CONFIGS[cfg]
    os.environ.update({"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_CONTEXTUAL_JUDGE": "wildcard",
                       "POLYMATH_CHAT_SKELETON_PROBES": "0", "POLYMATH_CHAT_PROBE_GATE": "1",
                       "POLYMATH_CHAT_SEEALSO_BLEND": flag, "POLYMATH_CHAT_SEEALSO_BLEND_ALPHA": alpha,
                       "POLYMATH_CHAT_SEEALSO_BLEND_ITEMS": str(items)})
    os.environ.pop("POLYMATH_CHAT_SEEALSO_HOP", None)
    STATE.update({"extra": EXTRA[mode] if extra else (), "lines": [], "found": {}})
    from orchestrator.api import chat_retrieval as _cr
    from orchestrator.api.chat_retrieval import chat_retrieve_mode, default_budget, intent_policy_enabled
    from polymath_shared.probe_gate import gate_probes
    from polymath_shared.query_intent import apply_intent_policy, policy_for
    from polymath_shared.skeleton_routes import apply_skeleton_routes
    plan = SK._plan(cp)
    ip = bool(intent_policy_enabled() and plan.intent)
    budget = apply_intent_policy(plan.intent, default_budget()) if ip else default_budget()
    budget = apply_skeleton_routes(budget, mode=mode, plan=plan)
    gated_out = set()
    if getattr(budget, "probe_gate_floor", 0.0) > 0:
        gated_out, _ = gate_probes((cp.get("resolved_request") or question).strip(),
                                   [(q.id, q.origin, q.query) for q in plan.queries if q.type != "PRIMARY"],
                                   _cr._rerank_children, floor=budget.probe_gate_floor)
    t0 = time.perf_counter()
    out = chat_retrieve_mode(
        "HYBRID" if mode == "WILDCARD" else mode, cp.get("retrieval_query") or question, "cinema",
        graph_useful=True if mode == "GRAPH" else bool(plan.graph_useful),
        graph_assist=(policy_for(plan.intent).graph if ip else "off"), keep_latent=False, budget=budget,
        exact_terms=plan.exact_terms,
        subqueries=tuple((q.id, q.type, q.query, q.weight, q.origin, q.derived_from) for q in plan.queries
                         if q.type != "PRIMARY" and q.id not in gated_out),
        latent_bridge_ids=tuple(q.id for q in plan.queries if q.origin in ("BRIDGE", "CORPUS_EXPLORE") and q.id not in gated_out))
    wall = round((time.perf_counter() - t0) * 1000, 1)
    ev = out.get("evidence") or []
    fan = (out.get("trace") or {}).get("seealso_fanout") or {}
    kind_of = {ln["text"]: ln["kind"] for ln in STATE["lines"]}
    found = dict(STATE["found"])
    return {"wall_ms": wall, "lane_g_ms": fan.get("lane_ms"), "alpha": budget.seealso_blend_alpha,
            "items": budget.seealso_blend_items, "blend_on": bool(budget.seealso_blend_enabled), "lines": STATE["lines"],
            "final_chunks": [r.get("chunk_id") for r in ev],
            "direct_final": sum(1 for r in ev if "q0" in (r.get("query_ids") or [])),
            "rows": {r.get("chunk_id"): {"source": r.get("source_name"), "arrivals": r.get("arrivals"),
                                         "rerank": r.get("rerank_score"), "line": found.get(str(r.get("chunk_id"))),
                                         "line_kind": kind_of.get(found.get(str(r.get("chunk_id")))),
                                         "text": (r.get("text") or "")[:260]} for r in ev},
            "fanout": {k: fan.get(k) for k in ("enabled", "candidates", "blends", "blend_candidates", "lane_ms", "degraded")}}


def main() -> int:
    _install_wrappers()
    turns = json.loads(RESULTS.read_text())
    runs, seen = [], set()
    for t in turns:
        cp = ((t.get("receipt") or {}).get("meta") or {}).get("chat_plan") or {}
        for mode in dict.fromkeys((t["mode"], "GRAPH")):
            if (t["question"], mode) not in seen and (not MODES or mode in MODES):
                seen.add((t["question"], mode))
                runs.append((t["turn"], mode, t["question"], cp))
    for _turn, mode, q, cp in runs:                      # warm-up: caches, sidecar models, Qdrant segments
        try:
            _once(mode, q, cp, "base")
        except Exception:  # noqa: BLE001, S110 — a warm-up failure repeats in the timed pass, which records it
            pass
    out = []
    for turn, mode, q, cp in runs:
        rec = {"turn": turn, "mode": mode, "question": q}
        for cfg in CONFIGS:
            if cfg == "steer60" and mode != "WILDCARD":
                continue
            try:
                rec[cfg] = _once(mode, q, cp, cfg)
            except Exception as exc:  # noqa: BLE001 — a failed replay is a finding
                rec[cfg] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        base, blend = rec["base"], rec["blend"]
        for cfg in ("blend", "steer", "steer60"):
            b = rec.get(cfg)
            if not b or "error" in b or "error" in base:
                continue
            rec[f"delta_{cfg}"] = {"new_vs_base": [c for c in b["final_chunks"] if c not in base["final_chunks"]],
                                   "new_vs_blend": ([c for c in b["final_chunks"] if c not in blend["final_chunks"]]
                                                    if cfg != "blend" and "error" not in blend else None),
                                   "displaced_vs_base": [c for c in base["final_chunks"] if c not in b["final_chunks"]],
                                   "direct": (base["direct_final"], b["direct_final"]),
                                   "lane_g_ms": (base.get("lane_g_ms"), b.get("lane_g_ms")),
                                   "wall_delta_ms": round(b["wall_ms"] - base["wall_ms"], 1)}
        out.append(rec)
        line = [f"turn {turn} {mode:8s}"]
        for cfg in ("blend", "steer", "steer60"):
            d = rec.get(f"delta_{cfg}")
            if d:
                line.append(f"{cfg}: new_vs_base={len(d['new_vs_base'])} new_vs_blend="
                            f"{'-' if d['new_vs_blend'] is None else len(d['new_vs_blend'])} direct={d['direct']} "
                            f"laneG_ms={d['lane_g_ms']} wallΔ={d['wall_delta_ms']}")
        print(" | ".join(line), f"err={base.get('error')}", flush=True)
    (HERE / (os.environ.get("REPLAY_OUT") or "replay.json")).write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
