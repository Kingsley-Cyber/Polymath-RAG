"""GNN-RETRIEVAL-V1 — M0 / M1: the deterministic graph-propagation baselines and the two causal CONTROLS (plan §7–§9, §21).

    h'_v = λ h_v + (1 − λ) Σ_{u∈N(v)} w_vu h_u        w_vu = s_vu / Σ_u' s_vu'        s_vu = β_r R_vu  (+ β_c C_vu when a confidence exists)

Interpreted literally in Polymath (§7): h = the current routing vector; N(v) = the accepted mapping / graph structure; w = bounded,
normalised per node; h' = the graph-enriched routing representation. The PARENT is the exported representation (two hops in):
    layer 1   entity' ← its related entities (R by predicate)          child' ← the entities it mentions
    layer 2   parent' ← its children (using child', which already carries the entities)
Every output is unit-normalised (cosine space, the query encoder unchanged). A node without a vector contributes nothing (weight 0).
No query enters the propagation (static, offline, §8). No learned parameter (M1 is the first-class control for "does propagation itself
help before any neural parameter?").

Controls (§21):  NOGRAPH  = the same pipeline with λ = 1 (no neighbourhood — projection / normalisation / collection effects only);
                 SHUFFLED = the same pipeline over DETERMINISTICALLY shuffled edges (destinations permuted per edge type; node and edge
                 counts, out-degrees and the weight normalisation preserved) — "any graph-shaped propagation" vs Polymath's topology.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping

import numpy as np

M1_CONTRACT = "m1-smooth-v1"
#: relation-type priors R (§8): the hierarchy and the mention are source-attested with certainty; an accepted relation is
#: a weaker, typed prior. `similar_to` is a similarity projection, not a fact — lowest. Unknown predicates take the default.
RELATION_PRIOR: dict[str, float] = {"belongs_to": 1.0, "contains": 1.0, "mentions": 1.0, "mentioned_in": 1.0, "similar_to": 0.25, "_default": 0.5}
DEFAULT_LAMBDA = 0.7


def _norm(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    return np.where(n > 0, x / np.maximum(n, 1e-12), 0.0).astype(np.float32)


def _present(x: np.ndarray) -> np.ndarray:
    return (np.abs(x).sum(axis=1) > 0).astype(np.float32)


def aggregate(dst_count: int, src_x: np.ndarray, edges: np.ndarray, weights: np.ndarray, *, src_col: int, dst_col: int) -> np.ndarray:
    """Σ_u w_vu h_u with w normalised per destination over the PRESENT sources (the neighbourhood mean the formula names)."""
    out = np.zeros((dst_count, src_x.shape[1]), dtype=np.float32)
    if len(edges) == 0:
        return out
    src, dst = edges[:, src_col], edges[:, dst_col]
    w = weights * _present(src_x)[src]
    denom = np.zeros(dst_count, dtype=np.float32)
    np.add.at(denom, dst, w)
    w_n = np.where(denom[dst] > 0, w / np.maximum(denom[dst], 1e-12), 0.0).astype(np.float32)
    np.add.at(out, dst, src_x[src] * w_n[:, None])
    return out


def relation_weights(predicates: list[str], prior: Mapping[str, float] = RELATION_PRIOR) -> np.ndarray:
    return np.asarray([float(prior.get(p, prior.get("_default", 0.5))) for p in predicates], dtype=np.float32)


def shuffle_edges(edges: np.ndarray, *, seed: int, dst_col: int = 1) -> np.ndarray:
    """Deterministic control: permute the DESTINATION endpoints (counts, sources / out-degrees preserved; the topology destroyed)."""
    if len(edges) == 0:
        return edges.copy()
    rng = np.random.default_rng(seed)
    out = edges.copy()
    out[:, dst_col] = out[rng.permutation(len(out)), dst_col]
    return out


def propagate(snap, *, lam: float = DEFAULT_LAMBDA, variant: str = "real", seed: int = 0, prior: Mapping[str, float] = RELATION_PRIOR) -> dict:
    """→ {"z_parent": (P, D) unit vectors, "z_child": (C, D), "z_entity": (E, D), "digest": model_digest, "params": {...}}."""
    ee, ec, cp = snap.ee, snap.ec, snap.cp
    if variant == "shuffled":
        ee, ec, cp = shuffle_edges(ee, seed=seed), shuffle_edges(ec, seed=seed + 1), shuffle_edges(cp, seed=seed + 2)
    elif variant == "nograph":
        lam = 1.0
    elif variant != "real":
        raise ValueError(f"unknown variant {variant!r}")
    he, hc, hp = _norm(snap.x_entity), _norm(snap.x_child), _norm(snap.x_parent)
    # layer 1: entities from related entities (both directions of an accepted relation carry the message); children from their entities
    ee_w = relation_weights(snap.ee_predicate, prior)
    ee_both = np.concatenate([ee, ee[:, ::-1]], axis=0) if len(ee) else ee
    ee_w_both = np.concatenate([ee_w, ee_w], axis=0) if len(ee) else ee_w
    m_e = aggregate(len(snap.entity_ids), he, ee_both, ee_w_both, src_col=0, dst_col=1)
    ze = _norm(lam * he + (1.0 - lam) * m_e) if lam < 1.0 else he
    m_c = aggregate(len(snap.child_ids), ze, ec, np.full(len(ec), float(prior.get("mentions", 1.0)), dtype=np.float32), src_col=0, dst_col=1)
    zc = _norm(lam * hc + (1.0 - lam) * m_c) if lam < 1.0 else hc
    # layer 2: the parent from its (entity-enriched) children — the exported representation
    m_p = aggregate(len(snap.parent_ids), zc, cp, np.full(len(cp), float(prior.get("belongs_to", 1.0)), dtype=np.float32), src_col=0, dst_col=1)
    present_p = _present(hp)[:, None]
    # a parent WITHOUT a map vector (recorded as missing) keeps only its children's message — its identity is the message, not a zero
    zp = np.where(present_p > 0, lam * hp + (1.0 - lam) * m_p, m_p) if lam < 1.0 else hp
    zp = _norm(zp)
    params = {"contract": M1_CONTRACT, "lambda": float(lam), "variant": variant, "seed": int(seed), "prior": dict(prior), "layers": 2,
              "graph_snapshot_id": snap.graph_snapshot_id}
    digest = "m1_" + hashlib.sha256((json.dumps(params, sort_keys=True) + "|" + hashlib.sha256(zp.tobytes()).hexdigest()).encode()).hexdigest()[:16]
    return {"z_parent": zp, "z_child": zc, "z_entity": ze, "digest": digest, "params": params,
            "anchor_cos_parent": float(np.mean(np.sum(zp * hp, axis=1)[present_p[:, 0] > 0])) if present_p.sum() else None}


def identity(snap) -> dict:
    """M0: h'_v = h_v — proves the projection / search plumbing before any propagation."""
    zp = _norm(snap.x_parent)
    params = {"contract": "m0-identity-v1", "lambda": 1.0, "variant": "real", "graph_snapshot_id": snap.graph_snapshot_id}
    return {"z_parent": zp, "digest": "m0_" + hashlib.sha256((json.dumps(params, sort_keys=True) + hashlib.sha256(zp.tobytes()).hexdigest()).encode()).hexdigest()[:16], "params": params, "anchor_cos_parent": 1.0}
