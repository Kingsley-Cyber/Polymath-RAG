"""GNN-RETRIEVAL-V1 — M2: a SHALLOW relation-aware heterogeneous GraphSAGE (plan §9 M2, §10 anchoring, §11 training).

Two propagation layers, one per hop the parent needs (entity → child → parent), relation-specific mean aggregation:
    layer 1   m_e = mean_{u∈N_rel(e)} W_rel h_u                       m_c = mean_{u∈N_mention(c)} W_men h_u
              z_e = norm(h_e + γ tanh(m_e))                            z_c = norm(h_c + γ tanh(m_c))
    layer 2   m_p = mean_{c∈children(p)} W_child z_c                   z_p = norm(h_p + γ tanh(m_p))         (h_p missing ⇒ z_p = norm(tanh(m_p)))
Residual anchoring keeps every output in the ORIGINAL semantic space (§10): the query encoder is unchanged, so `z_p` must stay searchable
by `q`. Training (§11): link prediction over the graph's OWN positives (E–E accepted relation, E–C mention, C–P hierarchy) with in-batch,
type-compatible negatives (InfoNCE, seeded), plus the anchor loss  L = L_graph + η · mean(1 − cos(z_v, h_v)).  The frozen retrieval gold is
NEVER used (§11). Controls: NOGRAPH trains the same model with NO edges (m = 0 ⇒ the residual path alone — the projection / normalisation
effect); SHUFFLED trains it over the deterministically shuffled edges (propagate.shuffle_edges).
"""
from __future__ import annotations

import hashlib
import json
import time

import numpy as np

M2_CONTRACT = "m2-hsage-v1"


def _torch():
    import torch
    return torch


def _mean_aggregate(torch, src_h, edges: np.ndarray, dst_count: int, src_col: int, dst_col: int, device):
    """mean_{u∈N(v)} h_u over PRESENT sources — a sparse (dst × src) row-normalised matmul; empty edge sets give zeros."""
    if len(edges) == 0:
        return torch.zeros((dst_count, src_h.shape[1]), device=device)
    src = torch.as_tensor(edges[:, src_col], dtype=torch.long, device=device)
    dst = torch.as_tensor(edges[:, dst_col], dtype=torch.long, device=device)
    present = (src_h.detach().abs().sum(dim=1) > 0).float()
    w = present[src]
    denom = torch.zeros(dst_count, device=device).index_add_(0, dst, w)
    w = torch.where(denom[dst] > 0, w / denom[dst].clamp_min(1e-12), torch.zeros_like(w))
    out = torch.zeros((dst_count, src_h.shape[1]), device=device)
    out.index_add_(0, dst, src_h[src] * w[:, None])
    return out


class HeteroSAGE:
    def __init__(self, dim: int, *, gamma: float = 0.5, seed: int = 0, device: str | None = None) -> None:
        torch = _torch()
        torch.manual_seed(seed)
        self.torch, self.dim, self.gamma, self.seed = torch, dim, float(gamma), int(seed)
        self.device = torch.device(device or ("mps" if torch.backends.mps.is_available() else "cpu"))
        # relation-specific transforms, initialised near identity so training starts AT the original semantic space
        def near_identity():
            w = torch.eye(dim) + 0.01 * torch.randn(dim, dim)
            return torch.nn.Parameter(w.to(self.device))
        self.w_rel, self.w_men, self.w_child = near_identity(), near_identity(), near_identity()
        self.params = [self.w_rel, self.w_men, self.w_child]

    def forward(self, he, hc, hp, ee: np.ndarray, ec: np.ndarray, cp: np.ndarray):
        torch, g = self.torch, self.gamma
        n = lambda x: torch.nn.functional.normalize(x, dim=1)  # noqa: E731
        ee_both = np.concatenate([ee, ee[:, ::-1]], axis=0) if len(ee) else ee
        m_e = _mean_aggregate(torch, he @ self.w_rel, ee_both, he.shape[0], 0, 1, self.device)
        z_e = n(he + g * torch.tanh(m_e))
        m_c = _mean_aggregate(torch, z_e @ self.w_men, ec, hc.shape[0], 0, 1, self.device)
        z_c = n(hc + g * torch.tanh(m_c))
        m_p = _mean_aggregate(torch, z_c @ self.w_child, cp, hp.shape[0], 0, 1, self.device)
        present_p = (hp.abs().sum(dim=1) > 0).float()[:, None]
        z_p = n(torch.where(present_p > 0, hp + g * torch.tanh(m_p), torch.tanh(m_p)))
        return z_e, z_c, z_p

    def state_digest(self) -> str:
        h = hashlib.sha256()
        for p in self.params:
            h.update(p.detach().cpu().numpy().astype(np.float32).tobytes())
        return h.hexdigest()[:16]


def _info_nce(torch, a, b, temperature: float = 0.07):
    """In-batch contrastive link prediction: row i of `a` must prefer row i of `b` over the other rows (type-compatible negatives)."""
    logits = (a @ b.T) / temperature
    labels = torch.arange(a.shape[0], device=a.device)
    return 0.5 * (torch.nn.functional.cross_entropy(logits, labels) + torch.nn.functional.cross_entropy(logits.T, labels))


def train(snap, *, variant: str = "real", epochs: int = 20, batch: int = 2048, lr: float = 1e-3, gamma: float = 0.5, eta: float = 1.0, seed: int = 0,
          device: str | None = None, log=print) -> dict:
    from propagate import shuffle_edges, _norm

    torch = _torch()
    ee, ec, cp = snap.ee, snap.ec, snap.cp
    if variant == "shuffled":
        ee, ec, cp = shuffle_edges(ee, seed=seed), shuffle_edges(ec, seed=seed + 1), shuffle_edges(cp, seed=seed + 2)
    elif variant == "nograph":
        ee, ec, cp = ee[:0], ec[:0], cp[:0]
    elif variant != "real":
        raise ValueError(variant)
    model = HeteroSAGE(snap.dim, gamma=gamma, seed=seed, device=device)
    dev = model.device
    he = torch.as_tensor(_norm(snap.x_entity), device=dev); hc = torch.as_tensor(_norm(snap.x_child), device=dev); hp = torch.as_tensor(_norm(snap.x_parent), device=dev)
    opt = torch.optim.Adam(model.params, lr=lr)
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    history = []
    pairs = [("ee", ee, 0, 1), ("ec", ec, 0, 1), ("cp", cp, 0, 1)]
    for epoch in range(int(epochs)):
        opt.zero_grad()
        z_e, z_c, z_p = model.forward(he, hc, hp, ee, ec, cp)
        loss_graph = torch.zeros((), device=dev)
        n_terms = 0
        for name, edges, sc, dc in pairs:
            if len(edges) == 0:
                continue
            idx = rng.choice(len(edges), size=min(batch, len(edges)), replace=False)
            e = edges[idx]
            left = {"ee": z_e, "ec": z_e, "cp": z_c}[name][torch.as_tensor(e[:, sc], dtype=torch.long, device=dev)]
            right = {"ee": z_e, "ec": z_c, "cp": z_p}[name][torch.as_tensor(e[:, dc], dtype=torch.long, device=dev)]
            loss_graph = loss_graph + _info_nce(torch, left, right)
            n_terms += 1
        if n_terms:
            loss_graph = loss_graph / n_terms
        present_p = (hp.abs().sum(dim=1) > 0)
        anchor = (1 - (z_p[present_p] * hp[present_p]).sum(dim=1)).mean() + (1 - (z_c * hc).sum(dim=1)).mean() + (1 - (z_e * he).sum(dim=1)).mean()
        loss = loss_graph + eta * anchor
        if loss.requires_grad:              # NOGRAPH: no edge reaches a parameter ⇒ the residual path alone, nothing to step (recorded, not hidden)
            loss.backward()
            opt.step()
        history.append({"epoch": epoch, "loss": float(loss.detach()), "graph": float(loss_graph.detach()), "anchor": float(anchor.detach()), "stepped": bool(loss.requires_grad)})
        if epoch % max(1, epochs // 5) == 0 or epoch == epochs - 1:
            log(f"[m2:{variant}] epoch {epoch} loss={float(loss):.4f} graph={float(loss_graph):.4f} anchor={float(anchor):.4f} ({time.perf_counter() - t0:.0f}s)")
    with torch.no_grad():
        z_e, z_c, z_p = model.forward(he, hc, hp, ee, ec, cp)
        zp = z_p.cpu().numpy().astype(np.float32)
        present = (snap.x_parent != 0).any(axis=1)
        anchor_cos = float(np.mean(np.sum(zp[present] * _norm(snap.x_parent)[present], axis=1))) if present.any() else None
    params = {"contract": M2_CONTRACT, "variant": variant, "epochs": int(epochs), "batch": int(batch), "lr": lr, "gamma": gamma, "eta": eta, "seed": int(seed),
              "layers": 2, "loss": "InfoNCE link prediction (E-E, E-C, C-P; in-batch type-compatible negatives) + eta * anchor(1 - cos)", "device": str(dev),
              "graph_snapshot_id": snap.graph_snapshot_id, "weights_digest": model.state_digest()}
    digest = "m2_" + hashlib.sha256((json.dumps(params, sort_keys=True) + hashlib.sha256(zp.tobytes()).hexdigest()).encode()).hexdigest()[:16]
    return {"z_parent": zp, "digest": digest, "params": params, "history": history, "anchor_cos_parent": anchor_cos, "train_seconds": round(time.perf_counter() - t0, 1)}
