#!/usr/bin/env python3
"""Reference corpus adapter for docs/18: Polymath -> contract rows.

The controller never talks to a corpus; the AGENT does, at `corpus_retrieve`
nodes. This helper is what the agent runs when the corpus is Polymath: it
queries the orchestrator's /retrieve, keeps only rows that satisfy the
contract ({id, summary, source} — re-resolvable id, auditable origin), dedupes
by id across queries, and prints the exact payload `controller.py submit
--node corpus` accepts. A dead or empty backend yields the docs/18 §6
capability_failure payload instead — the run continues with an honest
deficit, never a faked corpus.

    python3 python/corpus_polymath.py --corpus ecom-meta-v1 \
        --query "customers complain reusable produce bags leak" --out rows.json
    python3 python/corpus_polymath.py --state candidates/run1.json --corpus ecom-meta-v1

Authority is unchanged (docs/18 §4): every row is corpus_evergreen knowledge
fuel; nothing here can establish demand.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_URL = os.environ.get("POLYMATH_URL", "http://127.0.0.1:7200")
_TITLE = re.compile(r'title:\s*"([^"]+)"')


def _post(url: str, path: str, body: dict, bearer: str | None, timeout: float) -> dict:
    req = urllib.request.Request(url.rstrip("/") + path, data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json",
                                                         "User-Agent": "opportunity-research/corpus_polymath"})
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(url: str, path: str, bearer: str | None, timeout: float):
    req = urllib.request.Request(url.rstrip("/") + path, headers={"User-Agent": "opportunity-research/corpus_polymath"})
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def retrieve(url: str, corpus: str, query: str, limit: int = 12, bearer: str | None = None,
             timeout: float = 120.0, explore: bool = True) -> dict:
    """docs/19: ask for the contract-ready evidence rows (RETRIEVE-EVIDENCE-
    ROWS-V1) in EXPLORE mode — breadth across documents, timecodes, document
    summaries, attested graph facts. Older Polymath builds ignore the flags and
    the lane fallback below still applies."""
    body = {"query": query, "corpus_id": corpus, "limit": limit, "evidence": True}
    if explore:
        body["mode"] = "EXPLORE"
    return _post(url, "/retrieve", body, bearer, timeout)


def probe_capabilities(url: str, bearer: str | None = None, timeout: float = 15.0) -> dict | None:
    """docs/21 §2: ask the backend what it is. None = no capabilities endpoint
    (any docs/18 backend, or an older Polymath) -> generic mode. Never a hard
    failure: the lane must work against backends that have never heard of
    this skill."""
    req = urllib.request.Request(url.rstrip("/") + "/capabilities", headers={"Accept": "application/json", **({"Authorization": f"Bearer {bearer}"} if bearer else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
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
                  timeout: float, explore: bool = True) -> dict:
    """Polymath compiles the reformulations itself and returns rows stamped
    with the query ids that found them (corpus-plan-v1)."""
    body = {"signal": signal, "corpus_id": corpus, "limit": limit, "explore": explore, "communities": list(communities or [])}
    return _post(url, "/retrieve/plan", body, bearer, timeout)


def list_corpora(url: str, bearer: str | None = None, timeout: float = 30.0) -> list[dict]:
    """docs/22: corpora by id AND display name (`GET /corpora?all=true`)."""
    req = urllib.request.Request(url.rstrip("/") + "/corpora?all=true", headers={"Accept": "application/json", **({"Authorization": f"Bearer {bearer}"} if bearer else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (json.loads(resp.read().decode("utf-8")) or {}).get("corpora") or []
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


def ask_corpus(url: str, corpus: str, question: str, bearer: str | None, timeout: float, mode: str = "HYBRID",
               latent: bool = True) -> dict:
    """docs/22: the FULL RAG path — hybrid retrieval, rerank, graph + latent
    lanes, answer admission and synthesis with citations. `evidence: true`
    asks for the citations as RETRIEVE-EVIDENCE-ROWS-V1 rows as well."""
    body = {"message": question, "corpus_id": corpus, "mode": mode, "latent": latent, "evidence": True}
    return _post(url, "/chat", body, bearer, timeout)


def chat_question(q: dict) -> str:
    """docs/22 §1: the answer path admits only questions whose content terms the
    evidence covers. A compiled reformulation is a sentence of the signal
    (right for retrieval breadth, wrong for the gate: 14/15 abstained on the
    first live arm). Ask the RAG a SHORT, concrete question built from the
    reformulation's strongest terms instead; the full sentence still drives
    the EXPLORE rows."""
    _junk = {"already", "apply", "doing", "keep", "about", "enter", "group", "average", "beneath", "sense", "would", "could", "should",
             "their", "there", "these", "those", "which", "while", "where", "being", "other", "every", "still", "really", "things"}
    try:
        from corpus_queries import _keywords
        kws = [k for k in _keywords(q.get("query") or "", 10) if k not in _junk][:5]
    except Exception:  # noqa: BLE001
        kws = [w for w in re.findall(r"[a-z]{4,}", (q.get("query") or "").lower()) if w not in _junk][:5]
    if not kws:
        return (q.get("query") or "")[:160]
    frame = {"seed": "What do the sources say about {k}?", "tension": "What tension or difficulty do people describe around {k}?",
             "communities": "What do people in these communities do about {k}?", "invariant": "What do people want to regain or keep when it comes to {k}?",
             "contrast": "Why do people keep doing {k}?"}.get(q.get("kind") or "", "What do the sources say about {k}?")
    return frame.format(k=" ".join(kws[:5]))


def answer_record(resp: dict, question: dict, corpus: str, row_ids: list[str]) -> dict:
    meta = resp.get("meta") or {}
    return {"id": stable_id_local("ca", question.get("id") or question.get("query"), corpus),
            "query_id": question.get("id"), "kind": question.get("kind"), "question": question.get("query"), "asked_as": question.get("asked_as"), "corpus": corpus,
            "mode": meta.get("mode") or "HYBRID", "verdict": meta.get("verdict"), "abstained": bool(meta.get("abstained")),
            "uncovered_terms": meta.get("uncovered_query_terms") or [],
            "answer": resp.get("answer") or "", "claims": len(resp.get("claims") or []),
            "citations": row_ids, "authority": "CORPUS_SYNTHESIS",      # a synthesis is a reading of evidence, never evidence itself
            "synthesis_version": meta.get("synthesis_version")}


def stable_id_local(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]


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
            seen: set | None = None) -> tuple[list[dict], list[str]]:
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
            resp = retrieve(url, corpus, qtext, limit, bearer, timeout, explore=explore)
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
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            r["query_ids"] = [qid]
            r["query"] = qtext
            by_id[r["id"]] = r
            rows.append(r)
    return rows, errors


def main() -> int:
    ap = argparse.ArgumentParser(prog="corpus_polymath")
    ap.add_argument("--url", default=DEFAULT_URL, help="Polymath orchestrator (default $POLYMATH_URL or 127.0.0.1:7200)")
    ap.add_argument("--corpus", action="append", default=[], help="repeatable Polymath corpus_id(s) (default: from --state's corpus 'polymath:<id>[,<id>]')")
    ap.add_argument("--query", action="append", default=[], help="repeatable extra reformulations (default: the run's compiled corpus_queries, else its signal)")
    ap.add_argument("--no-explore", action="store_true", help="answer-precision retrieval instead of the EXPLORE ideation view")
    ap.add_argument("--generic", action="store_true", help="ignore the backend's capabilities and use the docs/18 generic path (control arm)")
    ap.add_argument("--no-field-evidence", action="store_true", help="do not add the backend's field-evidence corpus (control arm for step 3)")
    ap.add_argument("--via", choices=["chat", "chat-only", "plan"], default="chat", help="native lane: 'chat' = answers from the full RAG per reformulation PLUS the EXPLORE rows (docs/22, default); 'chat-only' = answers and their citations only; 'plan' = rows only")
    ap.add_argument("--state", default=None, help="run state JSON: supplies the signal and corpus identity")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--questions", action="store_true", help="docs/25 §6: ask the corpus the run's compiled friction/mechanism questions (auto at node corpus_mechanisms)")
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
    backend = backend_record(caps, args.url)
    field_corpus = (backend.get("contracts") or {}).get("field-evidence-corpus")
    if field_corpus and field_corpus not in corpora and not args.no_field_evidence and not _qmode:
        corpora.append(field_corpus)               # docs/21 step 3: past field evidence rides along (not for mechanism questions)
        backend["field_evidence_corpus"] = field_corpus
    server_plan = None
    answers = []
    _contracts = backend.get("contracts") or {}
    # docs/22: lanes follow CONTRACTS — chat when the backend serves chat-evidence,
    # else the plan endpoint when served, else the generic docs/18 path
    lane = "chat" if (args.via in ("chat", "chat-only") and _contracts.get("chat-evidence")) else ("plan" if _contracts.get("corpus-plan") else "retrieve")
    if _qmode and lane == "plan":
        lane = "retrieve"                      # a question is not a signal: retrieve per question, never re-plan the seed
    if backend["mode"] == "native" and args.state and lane == "chat":
        # docs/22: the full RAG answers each compiled reformulation; citations become contract rows,
        # the answer becomes a CORPUS_SYNTHESIS record (never evidence itself). Abstentions are kept.
        for corpus in corpora:
            n = 0
            for q in queries:
                asked = (q.get("asked_as") if isinstance(q, dict) and q.get("question_id") else (chat_question(q) if isinstance(q, dict) else str(q)))
                if isinstance(q, dict):
                    q = dict(q, asked_as=asked)
                try:
                    resp = ask_corpus(args.url, corpus, asked, bearer, args.timeout)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"chat/{corpus}/{(q.get('id') if isinstance(q, dict) else '?')}: {type(exc).__name__}: {exc}"); continue
                row_ids = []
                for r in rows_from_evidence_rows(resp, corpus):
                    qid = q.get("id") if isinstance(q, dict) else None
                    if r["id"] in seen:
                        ex = next((x for x in rows if x["id"] == r["id"]), None)
                        if ex is not None and qid and qid not in ex.setdefault("query_ids", []):
                            ex["query_ids"].append(qid)
                        row_ids.append(r["id"]); continue
                    seen.add(r["id"]); r["query_ids"] = [qid] if qid else []; r["query"] = q.get("query") if isinstance(q, dict) else str(q)
                    rows.append(r); row_ids.append(r["id"]); n += 1
                answers.append(answer_record(resp, q if isinstance(q, dict) else {"query": str(q)}, corpus, row_ids))
            per_corpus[corpus] = n
        backend["plan_source"] = "local"; backend["lane"] = "chat"
        if args.via == "chat" and _contracts.get("corpus-plan"):
            # breadth rides along: the seed's EXPLORE plan normally; in question mode the
            # per-question retrieve instead (a question is never re-planned as the seed)
            lane = "retrieve" if _qmode else "plan"
            backend["lane"] = "chat+questions" if _qmode else "chat+plan"
        elif not rows and errors:
            backend["mode"] = "generic"; backend["native_error"] = errors[-1]
    if backend["mode"] == "native" and args.state and lane == "plan":
        # docs/21 §2: Polymath owns the plan. One call per corpus; rows arrive with query_ids.
        signal = (state.get("data") or {}).get("signal") or " ".join(q.get("query", "") for q in queries)
        for corpus in corpora:
            try:
                resp = retrieve_plan(args.url, corpus, signal, (state.get("data") or {}).get("communities"), args.limit, bearer, args.timeout, explore=not args.no_explore)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"plan/{corpus}: {type(exc).__name__}: {exc}"); continue
            server_plan = server_plan or resp.get("plan")
            n = 0
            for r in rows_from_evidence_rows(resp, corpus):
                if r["id"] in seen:
                    continue
                seen.add(r["id"]); rows.append(r); n += 1
            per_corpus[corpus] = n
        backend["lane"] = backend.get("lane") if backend.get("lane") == "chat+plan" else "plan"
        local_ids = [q.get("id") for q in queries if isinstance(q, dict)]
        backend["plan_ids"] = [q.get("id") for q in server_plan or []]
        backend["plan_parity"] = (sorted(backend["plan_ids"]) == sorted(local_ids)) if local_ids and server_plan else None
        if not rows and errors:                      # native path failed outright: fall back, say so
            backend["mode"] = "generic"; backend["plan_source"] = "local"; backend["native_error"] = errors[-1]
    if backend["mode"] != "native" or lane == "retrieve":
        # generic per-query retrieve: the docs/18 path for non-native backends AND the
        # question lane on a native backend (a question is retrieved, never re-planned)
        if lane == "retrieve" and backend.get("lane") not in ("chat+questions",):
            backend["lane"] = "retrieve" if not _qmode else "questions"
        for corpus in corpora:
            r, e = collect(args.url, corpus, queries, args.limit, bearer, args.include_facts, args.timeout,
                           explore=not args.no_explore, seen=seen)
            rows += r; errors += e; per_corpus[corpus] = len(r)
    # docs/25 §6/§7: stamp question-level provenance and tag CORPUS_EXAMPLE rows (deterministic)
    _qmap = {q["id"]: q for q in queries if isinstance(q, dict) and q.get("question_id")}
    for r in rows:
        hit = [qid for qid in (r.get("query_ids") or []) if qid in _qmap]
        if hit:
            r["question_id"] = hit[0]; r["question_ids"] = hit; r["cluster_id"] = _qmap[hit[0]].get("cluster_id")
            r.setdefault("tags", []).append("question_level")
    try:
        import provenance as _prov
        _examples = _prov.tag_corpus_examples(rows, (state.get("data") or {}).get("example_terms") if args.state else None)
    except Exception as exc:  # noqa: BLE001 — tagging is a receipt, never a blocker
        _examples = f"tagging failed: {type(exc).__name__}"
    kinds = {k: sum(1 for x in rows if x.get("kind") == k) for k in ("chunk", "document", "graph_fact", "graph_hop")}
    if rows:
        payload = {"corpus_evidence": rows, "corpus_backend": backend}
        if answers:
            payload["corpus_answers"] = answers
        backend["corpus_names"] = corpus_names
        note = {"backend": "polymath", "mode": backend["mode"], "lane": backend.get("lane") or ("plan" if backend["mode"] == "native" else "retrieve"),
                "answers": len(answers), "answers_admitted": sum(1 for a in answers if not a["abstained"]),
                "plan_source": backend["plan_source"], "plan_parity": backend.get("plan_parity"),
                "url": args.url, "corpora": per_corpus, "queries": [q.get("kind") for q in queries],
                "rows": len(rows), "kinds": kinds, "corpus_example_rows": _examples,
                "question_level_rows": sum(1 for r in rows if r.get("question_id")), "errors": errors}
    else:
        payload = {"capability_failure": {"capability": "corpus",
                                          "detail": f"polymath/{','.join(corpora)}: no contract rows ({'; '.join(errors) or 'empty results'})"}}
        note = {"backend": "polymath", "url": args.url, "corpora": per_corpus, "queries": len(queries),
                "rows": 0, "errors": errors}
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
