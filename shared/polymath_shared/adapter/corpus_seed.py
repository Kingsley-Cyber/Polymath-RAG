"""PRODUCT-SEARCH-E2E — a run's CORPUS SCOPE and, when the requester gives no seed, its CORPUS SEED.

The owner, 2026-11-01: "a product search asks the users for a product but essentially it shouldnt really expect a niche it uses a
corpus to find products"; "the corpus it uses it should be able to use any corpus". So, at `service.start`, driven by the entry step's
config (manifest data; the runtime names no domain):

  * corpus scope (`config.corpus_scope`): named corpora are validated NOW (they exist and are searchable — a run never dies later with
    INPUT_SCOPE_MISSING); none named = every library the caller may use that is in "all libraries" (the platform's one rule,
    `query_scope.ALL_LIBRARIES_SQL`, narrowed by the caller's own view), ranked deterministically and capped at the adapter's limit;
  * corpus seed (`config.corpus_seed`): no seed = one derived deterministically from what the corpora's documents are about — the
    document-profile topics and questions, the active TENSION / LATENT_PATTERN profile atoms, the corpus summaries' research topics —
    with its lineage (doc ids + fields) in the start receipt.

Skeleton law (docs/wiki/plans/DOCUMENT-SKELETON-V1.md §1-3): profile and atom text may ROUTE (become a retrieval need), never be
hydrated into synthesis as evidence. The corpus seed is exactly a routing need: it is the run's search seed, never an evidence row,
never citable; the agent reasons only over the evidence the seed retrieves.

Pure: the corpus readers are the store's (`catalog`).
"""
from __future__ import annotations

import collections
import hashlib
import re
from typing import Any, Callable, Iterable, Mapping, Sequence

DERIVATION = "corpus-seed-v1"
MAX_TOPICS, MAX_QUESTIONS, MAX_TENSIONS = 3, 1, 1
SEED_MAX_CHARS = 600
MAX_LINEAGE_DOCS = 50
SEED_ATOM_KINDS = ("TENSION", "LATENT_PATTERN")
#: the request contract's own bound (adapter_run_request.request_options.corpus_ids maxItems)
REQUEST_MAX_CORPORA = 32
_STOP = frozenset("""a an the and or of to in on for with without by from into onto at as is are was were be been being it its this that these
those their there what which who whom whose when where why how do does did can could should would will may might must not no
nor than then so such very more most less least also just about over under up down out off again further once all any both each few
other some own same too only per via vs versus using use used document documents chapter section page pages""".split())


class StartRefused(ValueError):
    """A start that cannot lawfully begin: a typed code, a plain message and the next step the requester can take."""

    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.hint = code, message, hint
        self.errors = [f"{code}: {message}" + (f" — {hint}" if hint else "")]

    def detail(self) -> dict[str, Any]:
        return {"error_code": self.code, "message": self.message, "hint": self.hint, "errors": list(self.errors)}


# ─────────────────────────────────────────────────────────── readers
#: The corpus readers (`corpora`, `profiles`, `atoms`, `summaries`, `corpus_generation`) are the STORE's (store.py, read-only SQL): the
#: functions below take `catalog` — the store module in production, its in-memory double in tests — so the derivation stays pure.


# ─────────────────────────────────────────────────────────── corpus scope
def _named(input_payload: Mapping[str, Any], options: Mapping[str, Any]) -> list[str]:
    ids = input_payload.get("corpus_ids") or options.get("corpus_ids") or []
    return list(dict.fromkeys(str(c).strip() for c in ids if isinstance(c, str) and c.strip()))


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", str(text or "").lower()) if len(w) >= 3 and w not in _STOP}


def rank_corpora(candidates: Sequence[Mapping[str, Any]], profiles: Sequence[Mapping[str, Any]], seed: str | None) -> list[str]:
    """Deterministic order of candidate corpora: with a seed, by how many of the seed's words the corpus's document profiles carry
    (topics, terms) — then by size (query-ready documents), then by id; without one, by size, then by id."""
    words = _tokens(seed or "")
    vocab: dict[str, set[str]] = collections.defaultdict(set)
    for p in profiles:
        for t in list(p.get("topics") or []) + list(p.get("terms") or []):
            vocab[str(p.get("corpus_id"))] |= _tokens(t)
    def key(c: Mapping[str, Any]) -> tuple:
        cid = str(c["corpus_id"])
        return (-len(words & vocab.get(cid, set())) if words else 0, -int(c.get("documents") or 0), cid)
    return [str(c["corpus_id"]) for c in sorted(candidates, key=key)]


def resolve_scope(conn, catalog: Any, input_payload: Mapping[str, Any], options: Mapping[str, Any], *, config: Mapping[str, Any] | None,
                  corpus_view: Callable[[list[str]], Iterable[str]] | None, seed: str | None) -> dict[str, Any]:
    """-> {"corpus_ids": [...], "origin": "named" | "default", "candidates": n, "ranked_by": ...}. Named corpora are validated (they exist
    and are query-ready); none named = the caller's share of "all libraries", ranked, capped at `config.max_corpora`. Raises StartRefused."""
    cfg = dict(config or {})
    named = _named(input_payload, options)
    if named:
        rows = {r["corpus_id"]: r for r in catalog.corpora(conn, named)}
        unknown = [c for c in named if c not in rows]
        if unknown:
            raise StartRefused("CORPUS_UNKNOWN", f"no corpus named {', '.join(unknown[:5])}",
                               "list the corpora (list_corpora) and name one that exists, or leave corpus_ids out to use every library you may use")
        not_ready = [c for c in named if not rows[c]["query_ready"]]
        if not_ready:
            raise StartRefused("CORPUS_NOT_READY", f"{', '.join(not_ready[:5])} has no searchable document yet",
                               "wait until document_status shows query_ready for at least one document, or leave corpus_ids out")
        return {"corpus_ids": named, "origin": "named", "candidates": len(named), "ranked_by": None}
    pool = [r for r in catalog.corpora(conn) if r["in_all_libraries"]]
    if corpus_view is not None:
        allowed = set(corpus_view([r["corpus_id"] for r in pool]))
        pool = [r for r in pool if r["corpus_id"] in allowed]
    if not pool:
        raise StartRefused("QUERY_SCOPE_EMPTY", "there is no library to research: none of the libraries open to this account is searchable now "
                           "and included in all-library searches",
                           "name a library with corpus_ids (list_corpora shows them), or upload a document and wait until it is query_ready")
    cap = max(1, min(int(cfg.get("max_corpora") or REQUEST_MAX_CORPORA), REQUEST_MAX_CORPORA))
    profiles = catalog.profiles(conn, [r["corpus_id"] for r in pool]) if seed and len(pool) > cap else []
    ranked = rank_corpora(pool, profiles, seed)
    return {"corpus_ids": ranked[:cap], "origin": "default", "candidates": len(pool),
            "ranked_by": ("seed words in document profiles, then size" if seed and len(pool) > cap else "size") if len(pool) > cap else None}


# ─────────────────────────────────────────────────────────── corpus seed (pure derivation)
def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def derive_seed(profiles: Sequence[Mapping[str, Any]], atoms: Sequence[Mapping[str, Any]], summaries: Sequence[Mapping[str, Any]],
                corpus_ids: Sequence[str]) -> dict[str, Any] | None:
    """-> {"seed": text, "lineage": {...}} or None when the corpora carry no usable signal. Deterministic: topics rank by how many
    documents carry them (curated research topics first, the summaries' dominant concepts only when no profile has topics), ties by text;
    one open question from a document that carries the top topic; one tension (TENSION, else LATENT_PATTERN atom)."""
    fields: list[dict[str, Any]] = []
    topic_docs: dict[str, set[str]] = collections.defaultdict(set)
    shown: dict[str, str] = {}
    for p in sorted(profiles, key=lambda p: (str(p.get("corpus_id")), str(p.get("doc_id")))):
        for t in p.get("topics") or []:
            k = _norm(t)
            if k and len(k) <= 120:
                topic_docs[k].add(str(p["doc_id"]))
                shown.setdefault(k, " ".join(str(t).split()))
    curated = [(_norm(t), " ".join(str(t).split()), s["corpus_id"]) for s in sorted(summaries, key=lambda s: str(s.get("corpus_id")))
               for t in s.get("research_topics") or [] if _norm(t)]
    topics: list[tuple[str, str, list[str], str]] = []                    # (key, shown, doc ids, field)
    for k, text, cid in curated:
        if k not in {x[0] for x in topics}:
            topics.append((k, text, [], f"corpus_summaries.research_topics[{cid}]"))
    for k in sorted(topic_docs, key=lambda k: (-len(topic_docs[k]), k)):
        if k not in {x[0] for x in topics}:
            topics.append((k, shown[k], sorted(topic_docs[k]), "doc_profile.topics"))
    if not topic_docs:
        for s in sorted(summaries, key=lambda s: str(s.get("corpus_id"))):
            for t in s.get("dominant_concepts") or []:
                k = _norm(t)
                if k and k not in {x[0] for x in topics}:
                    topics.append((k, " ".join(str(t).split()), [], f"corpus_summaries.dominant_concepts[{s['corpus_id']}]"))
    topics = topics[:MAX_TOPICS]
    question = None
    if topics:
        lead_docs = set(topics[0][2])
        for p in sorted(profiles, key=lambda p: (str(p.get("doc_id")) not in lead_docs, str(p.get("corpus_id")), str(p.get("doc_id")))):
            q = next((" ".join(str(x).split()) for x in p.get("questions") or [] if str(x).strip() and len(str(x)) <= 300), None)
            if q:
                question = (q, str(p["doc_id"]))
                break
    tension = None
    for kind in SEED_ATOM_KINDS:
        hit = next((a for a in sorted(atoms, key=lambda a: (str(a.get("corpus_id")), str(a.get("doc_id")))) if a.get("kind") == kind
                    and 0 < len(str(a.get("text") or "").strip()) <= 300), None)
        if hit:
            tension = (" ".join(str(hit["text"]).split()), str(hit["doc_id"]), kind)
            break
    if not topics and not question and not tension:
        return None
    parts = []
    if topics:
        names = [t[1] for t in topics]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        parts.append(f"The problems, workarounds and situations people meet around {joined}.")
    if question:
        parts.append(f"Open question: {question[0].rstrip('?')}?")
    if tension:
        parts.append(f"Tension: {tension[0].rstrip('.')}.")
    seed = " ".join(parts)[:SEED_MAX_CHARS].strip()
    for k, text, docs, field in topics:
        fields.append({"field": field, "value": text, "doc_ids": docs[:5], "documents": len(docs)})
    if question:
        fields.append({"field": "doc_profile.questions", "value": question[0], "doc_ids": [question[1]], "documents": 1})
    if tension:
        fields.append({"field": f"document_profile_atoms.{tension[2]}", "value": tension[0], "doc_ids": [tension[1]], "documents": 1})
    doc_ids = sorted({d for f in fields for d in f["doc_ids"]})
    return {"seed": seed,
            "lineage": {"derivation": DERIVATION, "corpora": sorted(set(corpus_ids)), "fields": fields, "doc_ids": doc_ids[:MAX_LINEAGE_DOCS],
                        "signals_read": {"profiles": len(profiles), "atoms": len(atoms), "summaries": len(summaries)},
                        "authority": "ROUTING ONLY — the seed is a retrieval need derived from document profiles, never evidence",
                        "seed_sha256": hashlib.sha256(seed.encode("utf-8")).hexdigest()}}


def corpus_seed(conn, catalog: Any, corpus_ids: Sequence[str]) -> dict[str, Any]:
    """Read the corpora's signals and derive the seed. Raises StartRefused when nothing usable is there."""
    profiles, atoms, summaries = catalog.profiles(conn, corpus_ids), catalog.atoms(conn, corpus_ids), catalog.summaries(conn, corpus_ids)
    derived = derive_seed(profiles, atoms, summaries, corpus_ids)
    if derived is None:
        raise StartRefused("SEED_UNAVAILABLE", f"the corpora {', '.join(sorted(corpus_ids)[:5])} carry no document profile, profile atom or "
                           "research topic to derive a seed from", "give a seed: a problem, an audience or a situation")
    return derived
