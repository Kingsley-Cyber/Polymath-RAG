#!/usr/bin/env python3
"""Reference corpus adapter for docs/18: Polymath -> contract rows.

The controller never talks to a corpus; the AGENT does, at `corpus_retrieve`
nodes. This helper is what the agent runs when the corpus is Polymath: it
queries the orchestrator, keeps only rows that satisfy the contract
({id, summary, source} — re-resolvable id, auditable origin), dedupes by id
across lanes, and prints the exact payload `controller.py submit --node corpus`
accepts. A dead or empty backend yields the docs/18 §6 capability_failure
payload instead — the run continues with an honest deficit, never a faked corpus.

EVIDENCE BOUNDARY (docs/22, v2.2.0): the native lane asks Polymath for EVIDENCE,
never for an answer. The run's ORIGINAL need goes to the evidence route once per
corpus (full planning + Corpus Explore -> EvidencePacket, synthesis_performed =
false) and the packet's rows carry text + utility_role + ca4_grade + origin +
provenance. θ reasons ONCE, over evidence — this adapter holds no synthesis
route at all (the only POST paths it can reach are in ALLOWED_POST_PATHS), and
every request is counted so a run can prove it (`polymath_chat_calls == 0`).

    python3 python/corpus_polymath.py --corpus ecom-meta-v1 \
        --query "customers complain reusable produce bags leak" --out rows.json
    python3 python/corpus_polymath.py --state candidates/run1.json --corpus ecom-meta-v1

Authority is unchanged (docs/18 §4): every row is corpus_evergreen knowledge
fuel; nothing here can establish demand.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ADAPTER_VERSION = "2.2.0"
DEFAULT_URL = os.environ.get("POLYMATH_URL", "http://127.0.0.1:7200")
_TITLE = re.compile(r'title:\s*"([^"]+)"')

EVIDENCE_PATH = "/chat/evidence"
PACKET_SCHEMA_VERSION = "evidence-packet-v1"
PACKET_AUTHORITY = "CORPUS_EVIDENCE_PACKET"      # a packet is EVIDENCE with roles and grades — never an answer
#: the ONLY paths this adapter may POST to. A Polymath synthesis route is not among them, so nesting a second
#: synthesis inside θ's reasoning is not a behaviour this file can have (pinned by tests/run_all.py §17).
ALLOWED_POST_PATHS = frozenset({EVIDENCE_PATH, "/retrieve", "/retrieve/plan"})
MAX_NEED_CHARS = 2000
DEFAULT_MAX_EVIDENCE_CALLS = 12                  # == policies lived_world.max_questions: one call per compiled question, capped
UTILITY_ROLES = ("DIRECT", "COMPLEMENTARY", "DIVERGENT", "RELATED")
CA4_GRADES = ("DIRECT", "PARTIAL", "RELATED")

#: request ledger of THIS invocation: "METHOD /path" -> count, and one timing row per request (docs/22 §4)
CALLS: collections.Counter = collections.Counter()
TIMINGS: list = []
_UA = {"value": f"opportunity-research/{ADAPTER_VERSION} corpus_polymath"}


def set_run_tag(run_id: str | None, node: str | None) -> None:
    """Make every request attributable in the backend's own query-receipt ledger (Polymath records the User-Agent)."""
    tag = " ".join(x for x in (f"run:{run_id}" if run_id else "", f"node:{node}" if node else "") if x)
    _UA["value"] = (f"opportunity-research/{ADAPTER_VERSION} corpus_polymath " + tag).strip()[:118]


def _route(path: str) -> str:
    return path.split("?", 1)[0]


def _open(req, method: str, path: str, timeout: float):
    CALLS[f"{method} {_route(path)}"] += 1
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    finally:
        TIMINGS.append({"request": f"{method} {_route(path)}", "ms": round((time.perf_counter() - t0) * 1000)})


def _post(url: str, path: str, body: dict, bearer: str | None, timeout: float) -> dict:
    if path not in ALLOWED_POST_PATHS:              # checked BEFORE any I/O
        raise ValueError(f"corpus_polymath may not POST to {path!r}; allowed: {', '.join(sorted(ALLOWED_POST_PATHS))}")
    req = urllib.request.Request(url.rstrip("/") + path, data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json", "User-Agent": _UA["value"]})
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    return _open(req, "POST", path, timeout)


def _get(url: str, path: str, bearer: str | None, timeout: float):
    req = urllib.request.Request(url.rstrip("/") + path, headers={"Accept": "application/json", "User-Agent": _UA["value"]})
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    return _open(req, "GET", path, timeout)


def call_ledger() -> dict:
    """What this invocation asked of the backend. `polymath_chat_calls` counts requests to a SYNTHESIS route; it is
    measured from the same ledger every request passes through, not asserted."""
    posts = {k.split(" ", 1)[1]: v for k, v in CALLS.items() if k.startswith("POST ")}
    return {"calls": dict(sorted(CALLS.items())),
            "polymath_chat_calls": sum(v for k, v in posts.items() if k not in ALLOWED_POST_PATHS),
            "polymath_evidence_calls": posts.get(EVIDENCE_PATH, 0),
            "timings_ms": {k: sum(t["ms"] for t in TIMINGS if t["request"] == k) for k in sorted({t["request"] for t in TIMINGS})}}


def retrieve(url: str, corpus: str, query: str, limit: int = 12, bearer: str | None = None,
             timeout: float = 120.0, explore: bool = True, document_ids: list | None = None) -> dict:
    """docs/19: ask for the contract-ready evidence rows (RETRIEVE-EVIDENCE-
    ROWS-V1) in EXPLORE mode — breadth across documents, timecodes, document
    summaries, attested graph facts. Older Polymath builds ignore the flags and
    the lane fallback below still applies."""
    body = {"query": query, "corpus_id": corpus, "limit": limit, "evidence": True}
    if document_ids:
        body["document_ids"] = list(document_ids)          # DOCUMENT-SCOPED-RETRIEVE-V1
    if explore:
        body["mode"] = "EXPLORE"
    return _post(url, "/retrieve", body, bearer, timeout)


def probe_capabilities(url: str, bearer: str | None = None, timeout: float = 15.0) -> dict | None:
    """docs/21 §2: ask the backend what it is. None = no capabilities endpoint
    (any docs/18 backend, or an older Polymath) -> generic mode. Never a hard
    failure: the lane must work against backends that have never heard of
    this skill."""
    try:
        data = _get(url, "/capabilities", bearer, timeout)
        return data if isinstance(data, dict) and data.get("contracts") is not None else None
    except Exception:  # noqa: BLE001 — absence of the endpoint is information, not an error
        return None


def backend_record(caps: dict | None, url: str) -> dict:
    if not caps:
        return {"name": "polymath", "url": url, "mode": "generic", "version": None, "contracts": {}, "plan_source": "local"}
    contracts = caps.get("contracts") or {}
    native = bool(contracts.get("corpus-plan")) and bool(contracts.get("retrieve-evidence-rows"))
    return {"name": caps.get("backend") or "polymath", "url": url, "mode": "native" if native else "generic",
            "version": caps.get("version"), "contracts": contracts, "plan_source": "polymath" if native else "local"}


def retrieve_plan(url: str, corpus: str, signal: str, communities: list | None, limit: int, bearer: str | None,
                  timeout: float, explore: bool = True, document_ids: list | None = None) -> dict:
    """Polymath compiles the reformulations itself and returns rows stamped
    with the query ids that found them (corpus-plan-v1)."""
    body = {"signal": signal, "corpus_id": corpus, "limit": limit, "explore": explore, "communities": list(communities or [])}
    if document_ids:
        body["document_ids"] = list(document_ids)          # DOCUMENT-SCOPED-RETRIEVE-V1
    return _post(url, "/retrieve/plan", body, bearer, timeout)


def list_corpora(url: str, bearer: str | None = None, timeout: float = 30.0) -> list[dict]:
    """docs/22: corpora by id AND display name (`GET /corpora?all=true`)."""
    try:
        return (_get(url, "/corpora?all=true", bearer, timeout) or {}).get("corpora") or []
    except Exception:  # noqa: BLE001
        return []


def resolve_corpora(url: str, wanted: list[str], bearer: str | None = None) -> tuple[list[str], dict]:
    """A run identity may name corpora by display NAME or by id; ids are
    immutable, names are the owner's. Case-insensitive name match first, then
    id; unknown entries pass through unchanged (the backend will say so)."""
    rows = list_corpora(url, bearer)
    by_name = {str(r.get("name") or "").strip().lower(): r["corpus_id"] for r in rows if r.get("corpus_id")}
    ids = {r["corpus_id"] for r in rows if r.get("corpus_id")}
    out, names = [], {}
    for w in wanted:
        key = w.strip()
        cid = by_name.get(key.lower()) if key.lower() in by_name else (key if key in ids or not rows else key)
        out.append(cid); names[cid] = next((r.get("name") for r in rows if r.get("corpus_id") == cid), key)
    return out, names


def explore_corpus(url: str, corpus: str, need: str, bearer: str | None, timeout: float, mode: str = "WILDCARD",
                   corpus_explorer: bool = True) -> dict:
    """docs/22 (v2.2.0): the EVIDENCE BOUNDARY. Polymath runs its FULL retrieval planning (compiler, grounded expansion,
    Corpus Explore, rerank, C4/C5 seating, CA4 grading) and returns an EvidencePacket — evidence with roles, grades and
    provenance, and NO answer (`synthesis_performed: false`). Submit the ORIGINAL need: Polymath owns retrieval planning,
    θ owns the reasoning. The body is exactly these four fields."""
    body = {"message": need, "corpus_id": corpus, "mode": mode, "corpus_explorer": bool(corpus_explorer)}
    return _post(url, EVIDENCE_PATH, body, bearer, timeout)


def packet_errors(resp) -> list[str]:
    """FAIL CLOSED: violations of the evidence-boundary response contract (empty = lawful). A packet of another version,
    one that reports a synthesis, or one that does not satisfy schemas/evidence_packet.json is never repaired, never
    partially consumed and never replaced by another lane — the caller records a capability_failure instead."""
    if not isinstance(resp, dict):
        return ["response is not an object"]
    packet = resp.get("evidence_packet")
    if not isinstance(packet, dict):
        return ["response carries no evidence_packet object"]
    errs = []
    if packet.get("schema_version") != PACKET_SCHEMA_VERSION:
        errs.append(f"schema_version is {packet.get('schema_version')!r}, expected {PACKET_SCHEMA_VERSION!r}")
    if packet.get("synthesis_performed") is not False:
        errs.append(f"packet.synthesis_performed is {packet.get('synthesis_performed')!r}, expected false")
    if "synthesis_performed" in resp and resp.get("synthesis_performed") is not False:
        errs.append(f"response.synthesis_performed is {resp.get('synthesis_performed')!r}, expected false")
    if errs:
        return errs
    import models as _models
    return _models.validate(packet, "evidence_packet")[:8]


def rows_from_packet(packet: dict, corpus: str, need_id: str | None = None, need: str | None = None) -> list[dict]:
    """EvidencePacket evidence -> docs/18 rows. Every row keeps what Polymath established about it: the verbatim text,
    utility_role (why it was seated), ca4_grade (how it supports the ORIGINAL need), c4_valid, origin + lineage (which
    compiled query reached it) and provenance. `query_ids` stays the SKILL's retrieval provenance (the need that asked);
    Polymath's own compiled-query ids travel as `packet_query_ids`. Ids share the retrieve lanes' id space, so a chunk
    found by both lanes is one row."""
    out = []
    for e in packet.get("evidence") or []:
        cid = str(e.get("chunk_id") or "")
        text = str(e.get("text") or "")
        if not cid or not text.strip():
            continue
        summary = re.sub(r"\s+", " ", _TS.sub("", text)).strip()
        if not summary:
            continue
        src = str(e.get("source") or "").strip()
        role = str(e.get("utility_role") or "").upper() or None
        grade = str(e.get("ca4_grade") or "").upper() or None
        row = {"id": f"polymath:chunk:{cid}", "summary": summary[:1200], "text": text,
               "source": f"polymath/{corpus} · {src or cid}", "title": src or None, "doc_id": e.get("document_id") or None,
               "corpus": corpus, "kind": "chunk", "tags": ["chunk", "corpus_evergreen", "evidence_packet"],
               "utility_role": role, "synthesis_role": e.get("synthesis_role") or None, "ca4_grade": grade,
               "c4_valid": bool(e.get("c4_valid")), "origin": e.get("origin") or None,
               "lineage": list(e.get("lineage") or [])[:8], "provenance": dict(e.get("provenance") or {}),
               "packet_query_ids": [str(q) for q in (e.get("query_ids") or [])][:8],
               # RB5 (polymath-v4): packet text is a bounded VERBATIM EXCERPT of the chunk and says so
               "text_truncated": e.get("text_truncated") if isinstance(e.get("text_truncated"), bool) else None,
               "text_chars": e.get("text_chars") if isinstance(e.get("text_chars"), int) else None,
               "can_establish": list(CAN_ESTABLISH), "cannot_establish": list(CANNOT_ESTABLISH)}
        if role:
            row["tags"].append(f"role:{role}")
        if grade:
            row["tags"].append(f"ca4:{grade}")
        if need_id:
            row["query_ids"] = [need_id]
        if need:
            row["query"] = need
        out.append({k: v for k, v in row.items() if v is not None})
    return out


def packet_record(packet: dict, need: dict, corpus: str, row_ids: list[str], rows: list[dict], wall_ms: int | None = None) -> dict:
    """One `corpus_packets` entry: what was asked, of which corpus, and what the evidence looked like. There is no
    `answer` field and no abstention flag — an empty packet (`n_evidence == 0`) is the corpus not supporting the need,
    and the CA4 grade distribution says how well it did when it answered."""
    plan = packet.get("plan") if isinstance(packet.get("plan"), dict) else {}
    firing = (packet.get("receipts") or {}).get("firing") if isinstance(packet.get("receipts"), dict) else None
    count = lambda key: dict(collections.Counter(str(r.get(key) or "UNGRADED") for r in rows))   # noqa: E731
    _lens = [len(str(r.get("text") or "")) for r in rows]
    rec = {"id": stable_id_local("cp", need.get("id") or need.get("query"), corpus), "need_id": need.get("id"), "kind": need.get("kind"),
           "need": need.get("query"), "corpus": corpus, "authority": PACKET_AUTHORITY,
           "schema_version": packet.get("schema_version"), "synthesis_performed": packet.get("synthesis_performed"),
           "mode": packet.get("retrieval_mode"), "n_evidence": len(row_ids), "row_ids": list(row_ids),
           "ca4_grades": count("ca4_grade"), "utility_roles": count("utility_role"), "origins": count("origin"),
           "compiled_queries": len(plan.get("compiled_queries") or []),
           # how much TEXT the packet actually delivered per row (a backend that ships previews shows up here, not in a guess)
           "text_chars": {"min": min(_lens), "max": max(_lens), "total": sum(_lens)} if _lens else {"min": 0, "max": 0, "total": 0},
           "corpus_explorer": {"requested": bool(plan.get("corpus_explorer_requested")), "used": bool(plan.get("corpus_explorer_used")),
                               **({"firing": {k: firing.get(k) for k in ("requested", "fired", "cause") if k in firing}} if isinstance(firing, dict) else {})}}
    if need.get("truncated"):
        rec["need_truncated"] = True
    if need.get("question_id"):
        rec["question_id"] = need["question_id"]; rec["cluster_id"] = need.get("cluster_id")
    if wall_ms is not None:
        rec["wall_ms"] = int(wall_ms)
    return rec


def _merge_row(existing: dict, incoming: dict) -> None:
    """The same chunk reached by two lanes is ONE row: packet fields (role, grade, provenance) are kept, the retrieve
    lane contributes what the packet does not carry (title, timecode, lanes, score, document frontmatter, a page-level
    source locator), and retrieval provenance is the union."""
    for k, v in incoming.items():
        if k == "query_ids":
            existing["query_ids"] = list(dict.fromkeys([*(existing.get("query_ids") or []), *(v or [])]))
        elif k == "tags":
            existing["tags"] = list(dict.fromkeys([*(existing.get("tags") or []), *(v or [])]))
        elif k == "source" and isinstance(v, str) and len(v) > len(str(existing.get("source") or "")):
            existing["source"] = v                                 # the longer locator names the page / timecode
        elif k in ("text", "summary") and isinstance(v, str) and len(v) > len(str(existing.get(k) or "")):
            existing[k] = v                                        # same chunk id: the fuller verbatim passage wins (a packet carries an excerpt)
            if k == "text" and isinstance(existing.get("text_chars"), int):
                existing["text_truncated"] = len(v) < existing["text_chars"]    # the indicator follows the text it describes
        elif existing.get(k) in (None, "", [], {}):
            existing[k] = v


def stable_id_local(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]


_HINT_STOP = {"what", "when", "this", "that", "with", "does", "people", "keep", "doing", "despite", "explains", "mechanism", "reduces",
              "analogous", "constraint", "exists", "elsewhere", "workaround", "which", "their", "there", "they", "from", "into", "than"}
CAN_ESTABLISH = ["behavioral_mechanism", "conceptual_pattern"]
CANNOT_ESTABLISH = ["current_demand", "current_purchase_intent", "current_supplier_availability"]


def rows_from_evidence_rows(resp: dict, corpus: str) -> list[dict]:
    """Map RETRIEVE-EVIDENCE-ROWS-V1 rows onto docs/18 rows. The backend
    already resolved titles, timecodes and provenance; this only renames,
    tags and stamps the authority hints every corpus row carries (docs/04)."""
    out = []
    for r in resp.get("evidence_rows") or []:
        kind = r.get("kind") or "chunk"
        rid = r.get("id") or ""
        if not rid or not (r.get("text_clean") or r.get("text")):
            continue
        if kind in ("graph_fact", "graph_hop") and not r.get("evidence"):
            continue                       # a fact without an attesting chunk is a note
        row = {"id": f"polymath:{kind}:{rid.split(':', 1)[-1]}",
               "summary": (r.get("text_clean") or r.get("text") or "")[:1200],
               "text": r.get("text") or "",
               "source": f"polymath/{corpus} · {r.get('source')}",
               "title": r.get("title"), "doc_id": r.get("doc_id"), "corpus": corpus, "kind": kind,
               "tags": [kind, "corpus_evergreen"], "lanes": r.get("lanes"), "score": r.get("score"),
               "can_establish": list(CAN_ESTABLISH), "cannot_establish": list(CANNOT_ESTABLISH)}
        if r.get("claim_kind"):                     # TYPED-CLAIMS-V1: a pre-labelled lived claim
            row["claim_kind"] = r["claim_kind"]
            row["tags"].append(f"typed:{r['claim_kind']}")
        if r.get("query_ids"):
            row["query_ids"] = list(r["query_ids"])
        if r.get("document"):
            row["document"] = {k: r["document"].get(k) for k in ("source_name", "frontmatter") if r["document"].get(k) is not None}
        fm = (r.get("document") or {}).get("frontmatter") or {}
        if fm.get("field_evidence") or "FIELD_OBS" in (r.get("text") or ""):
            row["tags"].append("field_evidence")
        if r.get("timecode"):
            row["timecode"] = r["timecode"]
        if r.get("fact"):
            row["fact"] = r["fact"]
        if r.get("via_fact"):
            row["via_fact"] = r["via_fact"]
        if r.get("evidence"):
            row["evidence"] = r["evidence"][:5]
        if r.get("summary") and kind == "document":
            row["document_summary"] = r["summary"]
        out.append(row)
    return out


def document_titles(url: str, corpus: str, bearer: str | None = None, timeout: float = 30.0) -> dict:
    """doc_id -> human title, best effort (any failure -> {} and rows fall
    back to the re-resolvable doc id)."""
    for path in (f"/corpora/{corpus}/documents", f"/documents?corpus_id={corpus}"):
        try:
            out = _get(url, path, bearer, timeout)
        except Exception:  # noqa: BLE001 — provenance nicety only
            continue
        rows = out.get("documents") if isinstance(out, dict) else out
        if isinstance(rows, list):
            titles = {}
            for d in rows:
                if isinstance(d, dict) and d.get("doc_id"):
                    titles[d["doc_id"]] = d.get("title") or d.get("source_name") or d["doc_id"]
            if titles:
                return titles
    return {}


_TS = re.compile(r"\*\*\[\d+:\d+(?::\d+)?\]\*\*\s*")          # transcript timestamps
_META_LINE = re.compile(r"^(?:title|video_id|url|channel|upload_date|duration(?:_seconds)?|view_count|"
                        r"like_count|source_file|source_type|tags?):.*$", re.M)
_URL_LINE = re.compile(r"^.*https?://\S+.*$", re.M)          # any line carrying a link (descriptions, CTAs)
_HEADING_LINE = re.compile(r"^\s*#{1,6}\s+.*$", re.M)        # markdown headings ("## Description", "## Transcript")


def _title_from_summary(summary: str) -> str | None:
    m = _TITLE.search(summary or "")
    return m.group(1).strip() if m else None


def _display_title(title: str | None, summary: str, doc_id: str) -> str:
    """A human title: frontmatter title beats a filesystem path beats the id.
    Polymath's document listing returns source_name, which for transcripts
    is the absolute path of the markdown file."""
    fm = _title_from_summary(summary)
    if fm:
        return fm
    if title and ("/" in title or "\\" in title):
        base = title.replace("\\", "/").rsplit("/", 1)[-1]
        return re.sub(r"\.(md|txt|pdf|epub|html?)$", "", base, flags=re.I) or doc_id
    return title or doc_id


def _clean_profile(summary: str) -> str:
    """A document-profile row should read as what the document SAYS, not its
    frontmatter and description links (measured 2026-09-03: transcript
    profiles arrived as `title: … video_id: … ## Description Apply for my
    mentorship …`). Strip metadata lines, bare URLs and timestamps."""
    text = summary.replace("---", "\n")
    text = _META_LINE.sub("", text)
    text = _URL_LINE.sub("", text)
    text = _HEADING_LINE.sub("", text)
    text = _TS.sub("", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"\s+", " ", text).strip()


def rows_from_response(resp: dict, corpus: str, titles: dict | None = None,
                       include_facts: bool = False) -> list[dict]:
    """Pure mapping of one /retrieve response onto contract rows.
    document profiles -> id polymath:doc:<doc_id>; child chunks -> id
    polymath:chunk:<chunk_id> (verbatim text kept); graph facts only on
    request (they carry no per-row document origin in the response)."""
    titles = dict(titles or {})
    rows: list[dict] = []
    for d in resp.get("selected_documents") or []:
        doc, summ = d.get("doc_id"), (d.get("semantic_summary") or "").strip()
        if not doc or not summ:
            continue
        titles[doc] = _display_title(titles.get(doc), summ, doc)
        body = _clean_profile(summ)
        if len(body.split()) < 12:       # frontmatter only: nothing the document says yet
            continue
        rows.append({"id": f"polymath:doc:{doc}", "summary": body[:1200],
                     "source": f"polymath/{corpus} · {titles[doc]} · document profile",
                     "tags": ["document_profile", "corpus_evergreen"], "doc_id": doc})
    for c in resp.get("child_evidence") or []:
        cid, text, doc = c.get("chunk_id"), (c.get("text") or "").strip(), c.get("doc_id")
        if not cid or not text:
            continue
        title = titles.get(doc)
        if title is None or "/" in title or "\\" in title:
            title = _display_title(title, "", doc) if title else doc
            titles[doc] = title
        summary = re.sub(r"\s+", " ", _TS.sub("", text)).strip()   # timestamps out of the summary, verbatim text kept
        if not summary:
            continue
        rows.append({"id": f"polymath:chunk:{cid}", "summary": summary[:1200], "text": text,
                     "source": f"polymath/{corpus} · {title} · chunk {str(cid)[:18]}",
                     "tags": ["child_chunk", "corpus_evergreen"], "doc_id": doc,
                     "score": c.get("rerank_score")})
    if include_facts:
        for f in resp.get("graph_facts") or []:
            fid = f.get("fact_id")
            if not fid:
                continue
            rows.append({"id": f"polymath:fact:{fid}",
                         "summary": f"{f.get('subject')} —{f.get('predicate')}→ {f.get('object')}",
                         "source": f"polymath/{corpus} · graph fact (resolve by id for its evidence)",
                         "tags": ["graph_fact", "corpus_evergreen"]})
    seen, out = set(), []
    for r in rows:
        if r["id"] in seen or not r.get("summary") or not r.get("source"):
            continue
        seen.add(r["id"])
        out.append(r)
    return out


def collect(url: str, corpus: str, queries: list, limit: int, bearer: str | None,
            include_facts: bool, timeout: float, explore: bool = True,
            seen: set | None = None, document_ids: list | None = None, merge_into: dict | None = None) -> tuple[list[dict], list[str]]:
    """Run every query against one corpus; rows are deduped by id ACROSS
    queries and corpora (pass the same `seen`), and each row records the
    query ids that produced it (`query_ids`) — retrieval provenance (docs/19).
    `queries` items are strings or {id, query, kind} dicts."""
    titles = None
    rows, errors = [], []
    seen = seen if seen is not None else set()
    by_id: dict[str, dict] = {}
    for q in queries:
        qid, qtext = (q.get("id"), q.get("query")) if isinstance(q, dict) else (None, str(q))
        qid = qid or ("q_" + hashlib.sha1(qtext.encode("utf-8")).hexdigest()[:10])
        try:
            resp = retrieve(url, corpus, qtext, limit, bearer, timeout, explore=explore, document_ids=document_ids)
        except urllib.error.HTTPError as exc:
            errors.append(f"{qtext[:60]!r}: HTTP {exc.code} {exc.read()[:160].decode(errors='replace')}")
            continue
        except Exception as exc:  # noqa: BLE001 — reported as a deficit, never hidden
            errors.append(f"{qtext[:60]!r}: {type(exc).__name__}: {exc}")
            continue
        if resp.get("evidence_rows") is not None:
            mapped = rows_from_evidence_rows(resp, corpus)
        else:                                   # older backend: lane mapping
            if titles is None:
                titles = document_titles(url, corpus, bearer)
            mapped = rows_from_response(resp, corpus, titles, include_facts)
        for r in mapped:
            if r["id"] in by_id:
                if qid not in by_id[r["id"]].setdefault("query_ids", []):
                    by_id[r["id"]]["query_ids"].append(qid)
                continue
            if merge_into is not None and r["id"] in merge_into:
                _merge_row(merge_into[r["id"]], dict(r, query_ids=[qid])); continue   # the evidence lane holds this row already
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            r["query_ids"] = [qid]
            r["query"] = qtext
            by_id[r["id"]] = r
            rows.append(r)
    return rows, errors


def presence_audit(url: str, corpora: list, concepts: list, state: dict, bearer: str | None, timeout: float, limit: int = 40) -> list[dict]:
    """Final-pass item 3: CorpusPresenceReceipt per final ProductConcept, with the
    backend's EXISTING calls only — GET /documents (documents_checked) and POST
    /retrieve for the concept's own normalized phrase (the default lane's in-memory
    lexical scan surfaces exact and multi-token hits corpus-wide). Never the
    opportunity retrieval path: no evidence call, no plan, no new index."""
    import provenance as _prov
    docs_checked, doc_notes = 0, []
    for corpus in corpora:
        try:
            out = _get(url, f"/documents?corpus_id={corpus}", bearer, max(timeout, 300.0))
            docs_checked += len(out.get("documents") or []) if isinstance(out, dict) else 0
        except Exception as exc:  # noqa: BLE001
            doc_notes.append(f"{corpus}: {type(exc).__name__}: {exc}")
    receipts = []
    for c in concepts:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        phrase = _prov.normalize_phrase(c.get("name"))
        rows, errors = [], []
        for corpus in corpora:
            try:
                resp = retrieve(url, corpus, phrase, limit, bearer, timeout, explore=False)
                rows += rows_from_evidence_rows(resp, corpus)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{corpus}: {type(exc).__name__}: {exc}")
        rc = _prov.corpus_presence(c, ",".join(corpora), rows, state, documents_checked=docs_checked or None,
                                   method_version=f"{_prov.PRESENCE_METHOD}:retrieve-lexical")
        rc["backend_rows"] = len(rows)
        if errors:
            rc["errors"] = errors
        if doc_notes:
            rc["documents_note"] = "; ".join(doc_notes)
        receipts.append(rc)
    return receipts


def main() -> int:
    ap = argparse.ArgumentParser(prog="corpus_polymath")
    ap.add_argument("--url", default=DEFAULT_URL, help="Polymath orchestrator (default $POLYMATH_URL or 127.0.0.1:7200)")
    ap.add_argument("--corpus", action="append", default=[], help="repeatable Polymath corpus_id(s) (default: from --state's corpus 'polymath:<id>[,<id>]')")
    ap.add_argument("--query", action="append", default=[], help="repeatable extra reformulations (default: the run's compiled corpus_queries, else its signal)")
    ap.add_argument("--no-explore", action="store_true", help="answer-precision retrieval instead of the EXPLORE ideation view")
    ap.add_argument("--generic", action="store_true", help="ignore the backend's capabilities and use the docs/18 generic path (control arm)")
    ap.add_argument("--no-field-evidence", action="store_true", help="do not add the backend's field-evidence corpus (control arm for step 3)")
    ap.add_argument("--via", choices=["evidence", "plan"], default="evidence", help="native lane: 'evidence' = ONE evidence-boundary call per corpus with the run's ORIGINAL need (EvidencePacket: roles, CA4 grades, provenance, NO synthesis) PLUS the EXPLORE plan rows (docs/22, default); 'plan' = plan rows only (rollback arm)")
    ap.add_argument("--max-evidence-calls", type=int, default=DEFAULT_MAX_EVIDENCE_CALLS, help="upper bound on evidence-boundary calls per invocation (question mode asks one per compiled question); what is skipped is recorded")
    ap.add_argument("--state", default=None, help="run state JSON: supplies the signal and corpus identity")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--document-id", action="append", default=None, help="docs/26 §8: restrict retrieve + plan to these document ids (repeatable; unioned with the run's document_scope). The evidence route cannot be scoped to documents and is skipped while a scope is active; a backend that does not advertise document_ids yields a capability_failure (fail closed)")
    ap.add_argument("--questions", action="store_true", help="docs/25 §6: ask the corpus the run's compiled friction/mechanism questions (auto at node corpus_mechanisms)")
    ap.add_argument("--presence", action="store_true", help="final presence audit: one CorpusPresenceReceipt per product_concept in --state (GET /documents + POST /retrieve for the concept phrase); writes {corpus_presence:[...]} for tests/calibration_acceptance.py --presence")
    ap.add_argument("--include-facts", action="store_true")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--out", default=None, help="write the submit payload here (default stdout)")
    args = ap.parse_args()
    bearer = os.environ.get("POLYMATH_API_KEY") or None
    corpora = list(args.corpus)
    queries = [{"id": f"cli_{i}", "query": q, "kind": "cli"} for i, q in enumerate(args.query)]
    if args.state:
        with open(args.state, encoding="utf-8") as f:
            state = json.load(f)
        set_run_tag(state.get("run_id"), state.get("node"))      # requests become attributable in the backend's receipt ledger
        ident = str(state.get("corpus") or "")
        if not corpora and ident.startswith("polymath:"):
            corpora = [c for c in ident.split(":", 1)[1].split(",") if c]
        compiled = (state.get("data") or {}).get("corpus_queries") or []
        if compiled:
            queries = compiled + queries           # docs/19: the compiled plan first, extras after
        elif not queries and (state.get("data") or {}).get("signal"):
            queries = [{"id": "signal", "query": state["data"]["signal"], "kind": "signal"}]
    if corpora and not args.generic:
        corpora, corpus_names = resolve_corpora(args.url, corpora, bearer)      # docs/22: names or ids
    else:
        corpus_names = {c: c for c in corpora}
    # docs/26 §8: document scope = CLI ids ∪ the run's document_scope (set at init)
    _scope = list(dict.fromkeys([*(args.document_id or []), *((state.get("document_scope") or []) if args.state else [])]))
    if args.presence:
        if not args.state or not corpora:
            print("usage: --presence needs --state (product_concepts) and a Polymath corpus", file=sys.stderr)
            return 2
        _concepts = (state.get("data") or {}).get("product_concepts") or []
        _receipts = presence_audit(args.url, corpora, _concepts, state, bearer, args.timeout, limit=max(int(args.limit or 12), 40))
        payload = {"corpus_presence": _receipts}
        text = json.dumps(payload, indent=1, ensure_ascii=False)
        (open(args.out, "w", encoding="utf-8").write(text) if args.out else print(text))
        print(json.dumps({"backend": "polymath", "mode": "presence", "concepts": len(_receipts), "named": sum(1 for r in _receipts if r.get("named")),
                          "documents_checked": (_receipts[0].get("documents_checked") if _receipts else None), "corpora": corpora}), file=sys.stderr)
        return 0
    # docs/25 §6: at corpus_mechanisms the run asks friction / mechanism / question-level
    # asks compiled from lived clusters — never per person, never the seed plan again
    _qmode = bool(args.state) and (args.questions or (state.get("node") == "corpus_mechanisms"))
    if _qmode:
        _qs = (state.get("data") or {}).get("corpus_questions") or []
        queries = [{"id": q["id"], "query": q["question"], "kind": q.get("kind") or "question", "question_id": q["id"],
                    "asked_as": q["question"], "cluster_id": q.get("cluster_id")} for q in _qs if q.get("question")]
        if not queries:
            payload = {"capability_failure": {"capability": "corpus_questions", "detail": "no corpus questions compiled (no lived clusters with frictions)"}}
            text = json.dumps(payload, indent=1)
            (open(args.out, "w", encoding="utf-8").write(text) if args.out else print(text))
            print(json.dumps({"backend": "polymath", "mode": "questions", "rows": 0, "questions": 0}), file=sys.stderr)
            return 0
    if not corpora or not queries:
        print("usage: --corpus <id> (repeatable) and at least one --query (or --state with corpus_queries/signal)", file=sys.stderr)
        return 2
    rows, errors, seen, per_corpus = [], [], set(), {}
    caps = None if args.generic else probe_capabilities(args.url, bearer)
    if _scope:
        # FAIL CLOSED (final pass item 5): a document scope is a guarantee, not a preference. If the backend
        # does not ADVERTISE document_ids (capabilities.contracts.document_ids) the scope cannot be honoured —
        # no retrieve / plan / chat request leaves this process; the run records a coverage deficit instead.
        # --generic does not bypass the check: the control arm still needs the guarantee.
        _scope_caps = caps if caps is not None else probe_capabilities(args.url, bearer)
        if not ((_scope_caps or {}).get("contracts") or {}).get("document_ids"):
            payload = {"capability_failure": {"capability": "document_scoped_corpus_retrieval", "blocked": "BLOCKED_CAPABILITY_UNAVAILABLE",
                                              "detail": f"document scope {list(_scope)} requested but the backend at {args.url} does not advertise "
                                                        f"capabilities.contracts.document_ids — scope cannot be guaranteed; no unscoped request was issued",
                                              "document_scope": list(_scope)}}
            text = json.dumps(payload, indent=1)
            (open(args.out, "w", encoding="utf-8").write(text) if args.out else print(text))
            print(json.dumps({"backend": "polymath", "mode": "blocked", "blocked": "BLOCKED_CAPABILITY_UNAVAILABLE", "document_scope": list(_scope), "rows": 0}), file=sys.stderr)
            return 0
    backend = backend_record(caps, args.url)
    field_corpus = (backend.get("contracts") or {}).get("field-evidence-corpus")
    if field_corpus and field_corpus not in corpora and not args.no_field_evidence and not _qmode:
        corpora.append(field_corpus)               # docs/21 step 3: past field evidence rides along (not for mechanism questions)
        backend["field_evidence_corpus"] = field_corpus
    server_plan = None
    packets = []
    by_row_id: dict = {}
    _contracts = backend.get("contracts") or {}
    # docs/22: lanes follow CONTRACTS — the evidence boundary when the backend serves evidence-packet,
    # else the plan endpoint when served, else the generic docs/18 path
    lane = "evidence" if (args.via == "evidence" and _contracts.get("evidence-packet")) else ("plan" if _contracts.get("corpus-plan") else "retrieve")
    if _scope:
        # POLICY B (docs/26 §8): the evidence route cannot be scoped to documents, so while a scope is active
        # the run uses retrieve/plan rows only — never an unscoped evidence call
        backend["document_scope"] = list(_scope)
        if lane == "evidence":
            backend["evidence_skipped"] = "document scope active: the evidence route is unscoped (policy B)"
            lane = "plan" if _contracts.get("corpus-plan") else "retrieve"
        backend["document_scope_guaranteed"] = True      # advertised document_ids (checked fail-closed above)
    if _qmode and lane == "plan":
        lane = "retrieve"                      # a question is not a signal: retrieve per question, never re-plan the seed
    if backend["mode"] == "native" and args.state and lane == "evidence":
        # docs/22 (v2.2.0): the ORIGINAL need, once per corpus — the run's signal at `corpus`, each compiled
        # friction/mechanism question at `corpus_mechanisms` (distinct needs derived from field clusters). NEVER the
        # 3–5 reformulations: Polymath owns retrieval planning. The packet is evidence; θ reasons over it ONCE.
        if _qmode:
            needs = [dict(q) for q in queries if isinstance(q, dict) and q.get("query")]
        else:
            _signal = str((state.get("data") or {}).get("signal") or "").strip()
            needs = [{"id": "signal", "kind": "signal", "query": _signal}] if _signal else []
        for nd in needs:
            _text = " ".join(str(nd["query"]).split())
            if len(_text) > MAX_NEED_CHARS:
                nd["truncated"] = True
            nd["query"] = _text[:MAX_NEED_CHARS]
        _pairs = [(corpus, nd) for corpus in corpora for nd in needs]
        _cap = max(1, int(args.max_evidence_calls))
        if len(_pairs) > _cap:
            backend["evidence_truncated"] = [{"corpus": c, "need_id": nd.get("id"), "reason": "max_evidence_calls"} for c, nd in _pairs[_cap:]]
        _mismatch = None
        for corpus, nd in _pairs[:_cap]:
            _t0 = time.perf_counter()
            try:
                resp = explore_corpus(args.url, corpus, nd["query"], bearer, args.timeout)
            except Exception as exc:  # noqa: BLE001 — an unreachable evidence route is a recorded deficit; the row lanes still run
                errors.append(f"evidence/{corpus}/{nd.get('id')}: {type(exc).__name__}: {exc}"); continue
            _perr = packet_errors(resp)
            if _perr:
                _mismatch = {"corpus": corpus, "need_id": nd.get("id"), "errors": _perr}
                break
            packet = resp["evidence_packet"]
            mapped = rows_from_packet(packet, corpus, need_id=nd.get("id"), need=nd.get("query"))
            row_ids = []
            for r in mapped:
                row_ids.append(r["id"])
                if r["id"] in by_row_id:
                    _merge_row(by_row_id[r["id"]], r); continue
                seen.add(r["id"]); by_row_id[r["id"]] = r; rows.append(r)
                per_corpus[corpus] = per_corpus.get(corpus, 0) + 1
            packets.append(packet_record(packet, nd, corpus, row_ids, mapped, wall_ms=round((time.perf_counter() - _t0) * 1000)))
        if _mismatch:
            # FAIL CLOSED: a packet that breaks the contract is never repaired, partially used, or papered over by
            # another lane. No further request leaves this process; the run records an honest coverage deficit.
            payload = {"capability_failure": {"capability": "corpus_evidence_packet", "blocked": "EVIDENCE_CONTRACT_MISMATCH",
                                              "detail": f"polymath/{_mismatch['corpus']} need {_mismatch['need_id']!r}: " + "; ".join(_mismatch["errors"][:5]),
                                              "expected_schema_version": PACKET_SCHEMA_VERSION, **call_ledger()}}
            text = json.dumps(payload, indent=1, ensure_ascii=False)
            (open(args.out, "w", encoding="utf-8").write(text) if args.out else print(text))
            print(json.dumps({"backend": "polymath", "mode": "blocked", "blocked": "EVIDENCE_CONTRACT_MISMATCH", "rows": 0, **call_ledger()}), file=sys.stderr)
            return 0
        backend["plan_source"] = "local"; backend["lane"] = "evidence"
        if _contracts.get("corpus-plan") or _qmode:
            # breadth rides along: the seed's EXPLORE plan normally; in question mode the
            # per-question retrieve instead (a question is never re-planned as the seed)
            lane = "retrieve" if _qmode else "plan"
            backend["lane"] = "evidence+questions" if _qmode else "evidence+plan"
        elif not rows and errors:
            backend["mode"] = "generic"; backend["native_error"] = errors[-1]
    if backend["mode"] == "native" and args.state and lane == "plan":
        # docs/21 §2: Polymath owns the plan. One call per corpus; rows arrive with query_ids.
        signal = (state.get("data") or {}).get("signal") or " ".join(q.get("query", "") for q in queries)
        for corpus in corpora:
            try:
                resp = retrieve_plan(args.url, corpus, signal, (state.get("data") or {}).get("communities"), args.limit, bearer, args.timeout, explore=not args.no_explore, document_ids=_scope or None)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"plan/{corpus}: {type(exc).__name__}: {exc}"); continue
            server_plan = server_plan or resp.get("plan")
            n = 0
            for r in rows_from_evidence_rows(resp, corpus):
                if r["id"] in by_row_id:
                    _merge_row(by_row_id[r["id"]], r); continue      # the evidence lane found it first: one row, both lanes' fields
                if r["id"] in seen:
                    continue
                seen.add(r["id"]); rows.append(r); n += 1
            per_corpus[corpus] = per_corpus.get(corpus, 0) + n
        backend["lane"] = backend.get("lane") if backend.get("lane") == "evidence+plan" else "plan"
        local_ids = [q.get("id") for q in queries if isinstance(q, dict)]
        backend["plan_ids"] = [q.get("id") for q in server_plan or []]
        backend["plan_parity"] = (sorted(backend["plan_ids"]) == sorted(local_ids)) if local_ids and server_plan else None
        if not rows and errors:                      # native path failed outright: fall back, say so
            backend["mode"] = "generic"; backend["plan_source"] = "local"; backend["native_error"] = errors[-1]
    if backend["mode"] != "native" or lane == "retrieve":
        # generic per-query retrieve: the docs/18 path for non-native backends AND the
        # question lane on a native backend (a question is retrieved, never re-planned)
        if lane == "retrieve" and backend.get("lane") not in ("evidence+questions",):
            backend["lane"] = "retrieve" if not _qmode else "questions"
        for corpus in corpora:
            r, e = collect(args.url, corpus, queries, args.limit, bearer, args.include_facts, args.timeout,
                           explore=not args.no_explore, seen=seen, document_ids=_scope or None, merge_into=by_row_id)
            rows += r; errors += e; per_corpus[corpus] = per_corpus.get(corpus, 0) + len(r)
    # docs/25 §6/§7: stamp question-level provenance and tag CORPUS_EXAMPLE rows (deterministic)
    _qmap = {q["id"]: q for q in queries if isinstance(q, dict) and q.get("question_id")}
    for r in rows:
        hit = [qid for qid in (r.get("query_ids") or []) if qid in _qmap]
        if hit:
            r["question_id"] = hit[0]; r["question_ids"] = hit; r["cluster_id"] = _qmap[hit[0]].get("cluster_id")
            r.setdefault("tags", []).append("question_level")
            # docs/26 §2: a deterministic HINT for θ's relevance call — which content words the row
            # actually shares with the question (none = semantic retrieval, one = the lexical trap)
            _qt = {w for w in re.findall(r"[a-z]{4,}", (_qmap[hit[0]].get("query") or "").lower()) if w not in _HINT_STOP}
            _rt = {w for w in re.findall(r"[a-z]{4,}", (r.get("summary") or "").lower())}
            _ov = sorted(_qt & _rt)
            r["lexical_overlap"] = _ov
            if not _ov:
                r["relevance_hint"] = "NO_LEXICAL_OVERLAP"      # reached by embedding / rerank only — judge the structure
            elif len(_ov) == 1:
                r["relevance_hint"] = "SINGLE_WORD_OVERLAP"     # one shared content word ("hold") — the classic lexical trap
    try:
        import provenance as _prov
        _examples = _prov.tag_corpus_examples(rows, (state.get("data") or {}).get("example_terms") if args.state else None)
    except Exception as exc:  # noqa: BLE001 — tagging is a receipt, never a blocker
        _examples = f"tagging failed: {type(exc).__name__}"
    kinds = {k: sum(1 for x in rows if x.get("kind") == k) for k in ("chunk", "document", "graph_fact", "graph_hop")}
    _ledger = call_ledger()
    if rows:
        backend.update(_ledger)                      # docs/22 §4: what this invocation asked of the backend, by route
        payload = {"corpus_evidence": rows, "corpus_backend": backend}
        if packets:
            payload["corpus_packets"] = packets
        backend["corpus_names"] = corpus_names
        note = {"backend": "polymath", "mode": backend["mode"], "lane": backend.get("lane") or ("plan" if backend["mode"] == "native" else "retrieve"),
                "packets": len(packets), "packets_with_evidence": sum(1 for x in packets if x["n_evidence"]),
                "packet_rows": sum(1 for r in rows if "evidence_packet" in (r.get("tags") or [])),
                "polymath_chat_calls": _ledger["polymath_chat_calls"], "polymath_evidence_calls": _ledger["polymath_evidence_calls"],
                "calls": _ledger["calls"], "timings_ms": _ledger["timings_ms"],
                "plan_source": backend["plan_source"], "plan_parity": backend.get("plan_parity"),
                "url": args.url, "corpora": per_corpus, "queries": [q.get("kind") for q in queries],
                "rows": len(rows), "kinds": kinds, "corpus_example_rows": _examples, "document_scope": _scope or None, "evidence_skipped": backend.get("evidence_skipped"),
                "question_level_rows": sum(1 for r in rows if r.get("question_id")), "errors": errors}
    else:
        _empty = f"{len(packets)} evidence packet(s), all empty; " if packets else ""
        payload = {"capability_failure": {"capability": "corpus",
                                          "detail": f"polymath/{','.join(corpora)}: no contract rows ({_empty}{'; '.join(errors) or 'empty results'})"}}
        note = {"backend": "polymath", "url": args.url, "corpora": per_corpus, "queries": len(queries),
                "rows": 0, "errors": errors, **_ledger}
    text = json.dumps(payload, indent=1, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
    print(json.dumps(note), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
