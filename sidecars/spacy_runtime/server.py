"""spaCy syntax runtime (syntax-evidence-v1). See AGENTS.md, ADR-0005.

Role: sidecar-cpu. One resident en_core_web_sm pipeline (NER DISABLED —
GLiNER is Polymath's only entity model) serves batched syntax
annotation for the extract worker's existing sentence slices. spaCy
never redefines sentence boundaries, never proposes entities, and never
decides predicates; it only returns deterministic token/noun-chunk
evidence with offsets relative to the supplied sentence text.

Isolation: this runtime owns its venv (sidecars/spacy_runtime/.venv);
spaCy/Thinc never enter the root venv that hosts GLiNER/PyTorch/MPS.
The Apple acceleration extra (thinc-apple-ops) is allowed by default;
SPACY_BACKEND=cpu blocks it before thinc loads for byte-level
determinism comparison. Backend selection is reported in /health and
never changes silently.

/ready performs a REAL nlp.pipe forward pass on every probe (same
discipline as the other sidecars).
"""
from __future__ import annotations

import hashlib
import logging
import os
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from polymath_shared.logging import configure_logging

MANIFEST_PATH = Path(__file__).with_name("manifest.toml")
DIGEST_STATE_PATH = Path(__file__).with_name("weights.digest")

RELEASE = "syntax-evidence-v1"
CONTRACT_ID = "syntax-evidence-v1"
DISABLED_COMPONENTS = ["ner", "senter"]
REQUIRED_COMPONENTS = ["tok2vec", "tagger", "parser", "attribute_ruler", "lemmatizer"]

log = logging.getLogger("spacy-syntax-runtime")


class SentenceIn(BaseModel):
    sentence_id: str = Field(min_length=1)
    text: str


class SyntaxRequest(BaseModel):
    sentences: list[SentenceIn] = Field(min_length=1, max_length=512)


class TokenOut(BaseModel):
    i: int
    text: str
    char_start: int
    char_end: int
    lemma: str
    pos: str
    tag: str
    dep: str
    head_i: int


class NounChunkOut(BaseModel):
    char_start: int
    char_end: int
    text: str
    root_i: int


class SentenceOut(BaseModel):
    sentence_id: str
    tokens: list[TokenOut]
    noun_chunks: list[NounChunkOut]


class SyntaxResponse(BaseModel):
    contract: str
    results: list[SentenceOut]
    model_release: str
    runtime: dict


def load_manifest() -> dict:
    with MANIFEST_PATH.open("rb") as handle:
        return tomllib.load(handle)


def _package_version(name: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _snapshot_digest(model_dir: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(model_dir.rglob("*")):
        if path.is_file():
            hasher.update(str(path.relative_to(model_dir)).encode())
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def verify_weights(model_dir: Path, declared_sha: str) -> dict:
    """Same three-state discipline as gliner-runtime/embedder: declared
    digest -> verify; unpinned + recorded -> TOFU verify; nothing
    recorded -> record (TOFU)."""
    require_pinned = os.environ.get("POLYMATH_REQUIRE_PINNED", "0") == "1"
    declared_pinned = not declared_sha.startswith("__PIN_")
    if not model_dir.exists():
        return {"verified": False, "mode": "missing_model"}
    digest = _snapshot_digest(model_dir)
    if declared_pinned:
        return {"verified": digest == declared_sha, "mode": "declared", "digest": digest[:16]}
    if require_pinned:
        return {"verified": False, "mode": "unpinned_refused", "digest": digest[:16]}
    if DIGEST_STATE_PATH.exists():
        recorded = DIGEST_STATE_PATH.read_text().strip()
        return {"verified": digest == recorded, "mode": "tofu", "digest": digest[:16]}
    DIGEST_STATE_PATH.write_text(digest)
    return {"verified": True, "mode": "tofu_recorded", "digest": digest[:16]}


def _load_pipeline(model_name: str, backend: str):
    """Load spaCy with the requested float backend.

    thinc's get_ops("cpu") prefers the Apple Accelerate ops whenever
    thinc-apple-ops is installed, and layers bake in the ops that are
    current at construction. SPACY_BACKEND=cpu therefore forces stock
    NumpyOps as the process-wide ops BEFORE the pipeline is built: an
    explicit, inspectable CPU path, never a silent switch (the active
    ops name is reported in /health)."""
    import spacy
    from thinc.backends import NumpyOps, set_current_ops

    if backend == "cpu":
        set_current_ops(NumpyOps())

    nlp = spacy.load(model_name, disable=DISABLED_COMPONENTS)

    active = list(nlp.pipe_names)
    missing = [c for c in REQUIRED_COMPONENTS if c not in active]
    if missing:
        raise RuntimeError(f"syntax pipeline missing required components: {missing}")
    if "ner" in active:
        raise RuntimeError("ner must be disabled in the syntax runtime")
    return nlp


def _runtime_identity(nlp, backend: str, batch_size: int) -> dict:
    from thinc.backends import get_current_ops

    ops_name = get_current_ops().name
    apple_active = ops_name == "apple"
    return {
        "spacy_version": _package_version("spacy"),
        "model": nlp.meta.get("lang", "") + "_" + nlp.meta.get("name", ""),
        "model_version": nlp.meta.get("version", ""),
        "thinc_version": _package_version("thinc"),
        "apple_ops_version": _package_version("thinc-apple-ops") if apple_active else None,
        "apple_ops_active": apple_active,
        "ops": ops_name,
        "backend": backend,
        "batch_size": batch_size,
        "ner_disabled": True,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("sidecar-spacy-syntax")
    manifest = load_manifest()
    model_cfg = manifest["identity"]["model"]
    backend = os.environ.get("SPACY_BACKEND", manifest.get("runtime", {}).get("backend", "apple"))
    if backend not in ("apple", "cpu"):
        raise RuntimeError(f"unknown SPACY_BACKEND: {backend}")
    batch_size = int(os.environ.get("SPACY_BATCH_SIZE", manifest.get("runtime", {}).get("batch_size", 128)))
    model_name = os.environ.get("SPACY_MODEL", model_cfg["id"])

    nlp = _load_pipeline(model_name, backend)

    import en_core_web_sm

    model_dir = Path(en_core_web_sm.__file__).resolve().parent
    app.state.nlp = nlp
    app.state.manifest = manifest
    app.state.backend = backend
    app.state.batch_size = batch_size
    app.state.runtime = _runtime_identity(nlp, backend, batch_size)
    app.state.weights = verify_weights(model_dir, model_cfg.get("weights_sha256", ""))
    if not app.state.weights["verified"]:
        log.error("weights verification failed: %s", app.state.weights)
    yield


app = FastAPI(title="Polymath spaCy Syntax Runtime", lifespan=lifespan)


@app.get("/manifest")
async def manifest() -> dict:
    out = dict(app.state.manifest)
    out["weights_verification"] = app.state.weights
    out["runtime_identity"] = app.state.runtime
    return out


@app.get("/health")
async def health() -> dict:
    nlp = getattr(app.state, "nlp", None)
    return {
        "status": "ok" if nlp is not None else "loading",
        "release": RELEASE,
        "contract": CONTRACT_ID,
        "pipeline_components": {
            "active": list(nlp.pipe_names) if nlp else [],
            "disabled": DISABLED_COMPONENTS,
        },
        "ner_disabled": True,
        **getattr(app.state, "runtime", {}),
    }


@app.get("/ready")
async def ready(response: Response) -> dict:
    """READINESS, not liveness (P0-B).

    Returns 503 when the inference path is not usable, so a process that
    is alive but whose model has wedged stops being dispatched to. A
    wedged forward pass hangs here and the caller's timeout converts that
    into a probe failure — which is the intended signal. `/manifest` and
    `/health` remain pure liveness.
    """
    nlp = getattr(app.state, "nlp", None)
    if nlp is None:
        response.status_code = 503
        return {"ready": False, "reason": "model not loaded"}
    if not getattr(app.state, "weights", {}).get("verified", False):
        response.status_code = 503
        return {"ready": False, "reason": f"weights unverified: {app.state.weights}"}
    if "ner" in nlp.pipe_names:
        response.status_code = 503
        return {"ready": False, "reason": "ner must stay disabled"}
    try:
        # REAL forward pass through the same batched path as /infer.
        (doc,) = nlp.pipe(["readiness probe sentence."], batch_size=app.state.batch_size)
        if not doc or not doc[0].text:
            response.status_code = 503
        return {"ready": False, "reason": "forward pass produced no tokens"}
    except Exception as exc:
        response.status_code = 503
        return {"ready": False, "reason": f"forward pass failed: {exc}"}
    return {"ready": True}


@app.post("/infer", response_model=SyntaxResponse)
async def infer(request: SyntaxRequest) -> SyntaxResponse:
    nlp = getattr(app.state, "nlp", None)
    if nlp is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    if not getattr(app.state, "weights", {}).get("verified", False):
        raise HTTPException(status_code=503, detail="weights verification failed")
    if "ner" in nlp.pipe_names:
        raise HTTPException(status_code=503, detail="ner must stay disabled")

    texts = [s.text for s in request.sentences]
    # One batched pass over the whole request; order is preserved.
    docs = nlp.pipe(texts, batch_size=app.state.batch_size)
    results: list[SentenceOut] = []
    for sentence, doc in zip(request.sentences, docs):
        tokens: list[TokenOut] = []
        for tok in doc:
            token = TokenOut(
                i=tok.i,
                text=tok.text,
                char_start=tok.idx,
                char_end=tok.idx + len(tok.text),
                lemma=tok.lemma_,
                pos=tok.pos_,
                tag=tok.tag_,
                dep=tok.dep_,
                head_i=tok.head.i,
            )
            if sentence.text[token.char_start:token.char_end] != token.text:
                raise HTTPException(status_code=500, detail=f"token offset invariant violated for {sentence.sentence_id}")
            tokens.append(token)
        chunks: list[NounChunkOut] = []
        for chunk in doc.noun_chunks:
            out = NounChunkOut(
                char_start=chunk.start_char,
                char_end=chunk.end_char,
                text=chunk.text,
                root_i=chunk.root.i,
            )
            if sentence.text[out.char_start:out.char_end] != out.text:
                raise HTTPException(status_code=500, detail=f"noun chunk offset invariant violated for {sentence.sentence_id}")
            chunks.append(out)
        results.append(SentenceOut(sentence_id=sentence.sentence_id, tokens=tokens, noun_chunks=chunks))

    return SyntaxResponse(
        contract=CONTRACT_ID,
        results=results,
        model_release=app.state.manifest["identity"]["version"],
        runtime=app.state.runtime,
    )
