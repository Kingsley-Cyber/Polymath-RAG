"""GLiNER two-pass runtime. See AGENTS.md, ADR-0001, ADR-0005.

Role: sidecar-gpu (mps/cpu on the Mac). One resident model serves the
entity and evidence proposal passes. GLiNER proposes spans; it never
decides predicates — the deterministic compiler owns semantics.

The /ready endpoint performs a REAL forward pass on every probe
(ISSUES_REPORT §4.1 fix): a sidecar that cannot infer reports not-ready,
never "up but broken".
"""
from __future__ import annotations

import hashlib
import logging
import os
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from polymath_shared.logging import configure_logging
from polymath_shared.metal import release as release_metal
from polymath_shared.metal import run_adaptive
from polymath_shared.rulepack import load_rule_pack

MANIFEST_PATH = Path(__file__).with_name("manifest.toml")
DIGEST_STATE_PATH = Path(__file__).with_name("weights.digest")
MODEL_CACHE_DIR = Path.home() / ".cache" / "polymath" / "gliner"

log = logging.getLogger("gliner-runtime")


class InferRequest(BaseModel):
    task: Literal["entity", "evidence"]
    text: str
    threshold: float = Field(default=0.5, ge=0, le=1)
    labels: list[str] = Field(default_factory=list)


class ProposalSpan(BaseModel):
    text: str
    start: int
    end: int
    label: str
    score: float


class InferResponse(BaseModel):
    task: Literal["entity", "evidence"]
    spans: list[ProposalSpan]
    model_release: str


class RescueItem(BaseModel):
    """One targeted rescue query (I4R): GLiNER is asked about EXACTLY
    the supplied phrase — the caller (deterministic alignment code)
    decides what to ask; the model decides what it is. Same resident
    model, same revision, threshold carried per request (frozen 0.5 in
    practice)."""

    text: str
    labels: list[str] = Field(min_length=1)
    threshold: float = Field(default=0.5, ge=0, le=1)


class RescueRequest(BaseModel):
    requests: list[RescueItem] = Field(min_length=1, max_length=256)


class RescueItemResult(BaseModel):
    text: str
    spans: list[ProposalSpan]


class RescueResponse(BaseModel):
    results: list[RescueItemResult]
    model_release: str


def load_manifest() -> dict:
    with MANIFEST_PATH.open("rb") as handle:
        return tomllib.load(handle)


def evidence_labels() -> list[str]:
    """Pass-2 labels generated from the rule pack evidence_classes —
    the rule pack is the single source of truth for the 18-class
    evidence inventory (docx §4)."""
    pack = load_rule_pack()
    return [f"{class_id}: {description}" for class_id, description in pack["evidence_classes"].items()]


def _snapshot_digest(cache_dir: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(cache_dir.rglob("*")):
        if path.is_file() and "blobs" not in path.parts and "refs" not in path.parts:
            hasher.update(str(path.relative_to(cache_dir)).encode())
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def verify_weights(cache_dir: Path, declared_sha: str) -> dict:
    """Weights verification. Three states:

      - declared digest present -> verify and refuse on mismatch;
      - declared digest unpinned and a recorded digest exists -> verify
        against the recorded one (TOFU), report weights_verified="tofu";
      - no digest anywhere -> record the snapshot digest (TOFU).
    """
    require_pinned = os.environ.get("POLYMATH_REQUIRE_PINNED", "0") == "1"
    declared_pinned = not declared_sha.startswith("__PIN_")

    if not cache_dir.exists():
        return {"verified": False, "mode": "missing_cache"}

    digest = _snapshot_digest(cache_dir)

    if declared_pinned:
        ok = digest == declared_sha
        return {"verified": ok, "mode": "declared", "digest": digest[:16]}
    if require_pinned:
        return {"verified": False, "mode": "unpinned_refused", "digest": digest[:16]}

    if DIGEST_STATE_PATH.exists():
        recorded = DIGEST_STATE_PATH.read_text().strip()
        return {"verified": digest == recorded, "mode": "tofu", "digest": digest[:16]}

    DIGEST_STATE_PATH.write_text(digest)
    return {"verified": True, "mode": "tofu_recorded", "digest": digest[:16]}


@asynccontextmanager
async def lifespan(app: FastAPI):
    from gliner import GLiNER

    configure_logging("sidecar-gliner-runtime")
    manifest = load_manifest()
    model_cfg = manifest["identity"]["model"]
    device = os.environ.get("POLYMATH_GLINER_DEVICE", manifest.get("runtime", {}).get("device", "cpu"))
    if device == "mps":
        try:
            import torch

            if not torch.backends.mps.is_available():
                log.warning("mps unavailable; explicit cpu fallback")
                device = "cpu"
        except Exception:
            device = "cpu"

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    model = GLiNER.from_pretrained(
        model_cfg["id"],
        revision=model_cfg["revision"],
        cache_dir=str(MODEL_CACHE_DIR),
    )
    app.state.model = model.to(device)
    app.state.manifest = manifest
    app.state.batch_mode = _probe_batch_equivalence(app.state.model)
    app.state.weights = verify_weights(MODEL_CACHE_DIR, model_cfg.get("weights_sha256", ""))
    if not app.state.weights["verified"]:
        log.error("weights verification failed: %s", app.state.weights)
    yield


app = FastAPI(title="Polymath GLiNER Runtime", lifespan=lifespan)


@app.get("/manifest")
async def manifest() -> dict:
    manifest = dict(app.state.manifest)
    manifest["weights_verification"] = app.state.weights
    return manifest


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready(response: Response) -> dict:
    """READINESS, not liveness (P0-B).

    Returns 503 when the inference path is not usable, so a process that
    is alive but whose model has wedged stops being dispatched to. A
    wedged forward pass hangs here and the caller's timeout converts that
    into a probe failure — which is the intended signal. `/manifest` and
    `/health` remain pure liveness.
    """
    model = getattr(app.state, "model", None)
    if model is None:
        response.status_code = 503
        return {"ready": False, "reason": "model not loaded"}
    if not getattr(app.state, "weights", {}).get("verified", False):
        response.status_code = 503
        return {"ready": False, "reason": f"weights unverified: {app.state.weights}"}
    try:
        # REAL forward pass on every probe (ISSUES_REPORT §4.1).
        model.predict_entities("readiness probe", ["readiness probe"], threshold=0.9)
    except Exception as exc:
        response.status_code = 503
        return {"ready": False, "reason": f"forward pass failed: {exc}"}
    return {"ready": True}


class InferBatchRequest(BaseModel):
    task: str = Field(default="entity")
    texts: list[str] = Field(min_length=1, max_length=256)
    labels: list[str] = Field(min_length=1)
    threshold: float = Field(default=0.5, ge=0, le=1)


class InferBatchResponse(BaseModel):
    task: str
    results: list[list[ProposalSpan]]
    mode: str            # model_batch | loop
    model_release: str


def _predict_many(model, texts: list[str], labels: list[str], threshold: float,
                  mode: str) -> list[list[dict]]:
    """PHASE B2 transport/batch execution. `mode` is fixed at startup by an
    EQUIVALENCE PROBE: `model_batch` is used only if batch_predict_entities
    reproduced per-text predict_entities EXACTLY (spans, labels, scores) on
    the probe inputs; otherwise `loop` — which still eliminates per-request
    HTTP/serialization overhead while keeping outputs bit-identical by
    construction. Batching must not alter output; when in doubt, loop.
    """
    if mode == "model_batch":
        return model.batch_predict_entities(texts, labels, threshold=threshold)
    return [model.predict_entities(t, labels, threshold=threshold) for t in texts]


def _probe_batch_equivalence(model) -> str:
    probe = ["Kubernetes orchestrates the Nimbus platform in Toledo.",
             "Dr Amara Osei founded the Riverside Clinic in 2015."]
    labels = ["Person", "Organization", "Technology", "Location"]
    try:
        batched = model.batch_predict_entities(probe, labels, threshold=0.3)
    except Exception:
        return "loop"
    looped = [model.predict_entities(t, labels, threshold=0.3) for t in probe]
    def norm(rs):
        return [sorted((r["text"], r["label"], int(r["start"]), int(r["end"]),
                        float(r["score"])) for r in row) for row in rs]
    return "model_batch" if norm(batched) == norm(looped) else "loop"


@app.post("/infer_batch", response_model=InferBatchResponse)
async def infer_batch(request: InferBatchRequest) -> InferBatchResponse:
    if not getattr(app.state, "weights", {}).get("verified", False):
        raise HTTPException(status_code=503, detail="weights verification failed")
    if request.task != "entity":
        raise HTTPException(status_code=422, detail="batch supports the entity task")
    mode = getattr(app.state, "batch_mode", "loop")
    # A Metal exhaustion must cost a retry of the batch, not the caller's
    # whole extract ticket. Splitting cannot change results: _predict_many
    # is per-text and order-preserving in both modes.
    try:
        raw_rows = run_adaptive(
            lambda chunk: _predict_many(app.state.model, list(chunk),
                                        request.labels, request.threshold, mode),
            request.texts, what="entity")
    finally:
        release_metal()
    return InferBatchResponse(
        task=request.task, mode=mode,
        results=[[ProposalSpan(text=i["text"], start=int(i["start"]),
                               end=int(i["end"]),
                               label=i["label"].split(":", 1)[0].strip(),
                               score=float(i["score"])) for i in row]
                 for row in raw_rows],
        model_release=app.state.manifest["identity"]["version"])


@app.post("/infer", response_model=InferResponse)
async def infer(request: InferRequest) -> InferResponse:
    if not getattr(app.state, "weights", {}).get("verified", False):
        raise HTTPException(status_code=503, detail="weights verification failed")
    if request.task == "entity":
        if not request.labels:
            raise HTTPException(status_code=422, detail="entity task requires labels")
        labels = request.labels
    else:
        labels = evidence_labels()

    raw = app.state.model.predict_entities(
        request.text,
        labels,
        threshold=request.threshold,
    )
    return InferResponse(
        task=request.task,
        spans=[
            ProposalSpan(
                text=item["text"],
                start=int(item["start"]),
                end=int(item["end"]),
                label=item["label"].split(":", 1)[0].strip(),
                score=float(item["score"]),
            )
            for item in raw
        ],
        model_release=app.state.manifest["identity"]["version"],
    )


@app.post("/rescue", response_model=RescueResponse)
async def rescue(request: RescueRequest) -> RescueResponse:
    """Batched targeted re-queries against the SAME resident model
    (I4R). Each item is an independent (text, labels, threshold)
    zero-shot query; results align 1:1 with request order. `/infer`
    behavior is unchanged."""
    if not getattr(app.state, "weights", {}).get("verified", False):
        raise HTTPException(status_code=503, detail="weights verification failed")
    # PHASE B2: group items sharing (labels, threshold) and execute each
    # group through the startup-probed batch mode. Order restored exactly;
    # per-item semantics identical to the previous per-item loop.
    mode = getattr(app.state, "batch_mode", "loop")
    groups: dict = {}
    for idx, item in enumerate(request.requests):
        groups.setdefault((tuple(item.labels), item.threshold), []).append(idx)
    raw_by_idx: dict = {}
    for (labels_t, thr), idxs in groups.items():
        rows = _predict_many(app.state.model,
                             [request.requests[i].text for i in idxs],
                             list(labels_t), thr, mode)
        for i, row in zip(idxs, rows):
            raw_by_idx[i] = row
    results = []
    for idx, item in enumerate(request.requests):
        raw = raw_by_idx[idx]
        results.append(RescueItemResult(
            text=item.text,
            spans=[
                ProposalSpan(
                    text=s["text"],
                    start=int(s["start"]),
                    end=int(s["end"]),
                    label=s["label"].split(":", 1)[0].strip(),
                    score=float(s["score"]),
                )
                for s in raw
            ],
        ))
    return RescueResponse(
        results=results,
        model_release=app.state.manifest["identity"]["version"],
    )
