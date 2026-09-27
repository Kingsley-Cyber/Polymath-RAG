#!/usr/bin/env python3
"""FACET-RETRIEVAL-V1 F4 — the profile-coverage audit (plan §3.4). READ-ONLY.

For every document of a library it scores how well each profile describes the document — the share of the
document's top-50 terms (tf × idf over the library) and of its top-level section titles that appear in the
profile's text — for the LLM profile (the latest `doc_profile` artifact's compiled surfaces + its section
profiles + the document's active profile atoms) and for the deterministic `documents.retrieval_profile`.
It prints the worst N with their parent counts and flags every giant (> 300 parents) without section profiles.

  .venv/bin/python scripts/profile_audit.py --corpus cinema                 # the table (worst 10)
  .venv/bin/python scripts/profile_audit.py --corpus cinema --worst 20 --json out.json
  .venv/bin/python scripts/profile_audit.py --corpus cinema --doc <doc_id>  # one document, with its missing terms

Reads Postgres only (a read-only transaction; the profile points in Qdrant are not consulted — the artifact
carries the same compiled surfaces). No LLM call, no write, no secret printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "shared", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from polymath_shared.document_profile import giant_profile as GP
from polymath_shared.document_profile import profile_coverage as PC


def _connect():
    import psycopg
    dsn = os.environ.get("POLYMATH_PG_DSN")
    if not dsn:
        raise SystemExit("POLYMATH_PG_DSN is not set (load the fleet .env: set -a; . ./.env; set +a)")
    return psycopg.connect(dsn, options="-c default_transaction_read_only=on")


def load_documents(conn, corpus_id: str, doc_id: str | None = None) -> list[dict]:
    q = "SELECT doc_id, source_name, retrieval_profile FROM documents WHERE corpus_id=%s"
    params: list = [corpus_id]
    if doc_id:
        q += " AND doc_id=%s"
        params.append(doc_id)
    rows = conn.execute(q + " ORDER BY source_name", tuple(params)).fetchall()
    out = []
    for did, name, rp in rows:
        rp = rp if isinstance(rp, dict) else (json.loads(rp) if rp else {})
        out.append({"doc_id": did, "source_name": name, "retrieval_profile": rp or {}})
    return out


def load_parents(conn, doc_id: str) -> list[dict]:
    return [{"chunk_id": r[0], "chunk_index": r[1], "heading_path": r[2], "text": r[3], "region_role": r[4]}
            for r in conn.execute("SELECT chunk_id, chunk_index, heading_path, text, region_role FROM chunks "
                                  "WHERE doc_id=%s AND tier='parent' ORDER BY chunk_index", (doc_id,)).fetchall()]


def load_llm_profile(conn, doc_id: str) -> tuple[dict, list[dict], dict | None]:
    """(compiled document profile, section entries [built + skipped], the artifact's doc_profile record) from the
    latest `doc_profile` artifact of the document's run."""
    row = conn.execute(
        """SELECT a.payload FROM artifacts a JOIN runs r ON r.run_id = a.run_id
            JOIN documents d ON d.corpus_id = r.corpus_id AND d.source_name = (r.metadata->'intake_payload'->>'source_name')
           WHERE d.doc_id = %s AND a.stage = 'doc_profile' ORDER BY a.created_at DESC LIMIT 1""", (doc_id,)).fetchone()
    if not row or not row[0]:
        return {}, [], None
    payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    dp = payload.get("doc_profile") or {}
    sec = payload.get("doc_profile_sections") or {}
    entries = list(sec.get("built") or []) + list(sec.get("skipped") or [])
    return (dp.get("compiled") or {}), entries, dp


def load_atom_texts(conn, doc_id: str) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT atom_text FROM document_profile_atoms WHERE doc_id=%s AND active ORDER BY atom_kind, ordinal", (doc_id,)).fetchall()]


def audit_corpus(conn, corpus_id: str, *, doc_id: str | None = None, top: int = PC.TOP_TERMS) -> list[dict]:
    docs = load_documents(conn, corpus_id, doc_id)
    parents_by_doc = {d["doc_id"]: load_parents(conn, d["doc_id"]) for d in docs}
    # idf over the LIBRARY's documents (every document, even when one is audited)
    if doc_id:
        all_ids = [r[0] for r in conn.execute("SELECT doc_id FROM documents WHERE corpus_id=%s", (corpus_id,)).fetchall()]
        texts_iter = ([str(p.get("text") or "") for p in (parents_by_doc.get(i) or load_parents(conn, i))] for i in all_ids)
    else:
        texts_iter = ([str(p.get("text") or "") for p in parents_by_doc[d["doc_id"]]] for d in docs)
    doc_freq, n_docs = PC.library_doc_freq(texts_iter)
    rows = []
    for d in docs:
        parents = parents_by_doc[d["doc_id"]]
        compiled, entries, dp = load_llm_profile(conn, d["doc_id"])
        section_texts = [PC.flatten_compiled(e.get("compiled")) for e in entries if e.get("compiled")]
        atom_texts = load_atom_texts(conn, d["doc_id"])
        llm_text = "\n".join([PC.flatten_compiled(compiled), *section_texts, *atom_texts])
        det_text = PC.flatten_retrieval_profile(d["retrieval_profile"])
        row = PC.audit_document(parents, profile_texts={"llm": llm_text, "det": det_text}, doc_freq=doc_freq,
                                n_docs=n_docs, top=top, section_profiles=len(entries))
        row.update({"doc_id": d["doc_id"], "source_name": d["source_name"],
                    "llm_builder": (dp or {}).get("builder_version"), "llm_quality": (dp or {}).get("quality"),
                    "has_llm_profile": bool(compiled), "atoms": len(atom_texts),
                    "sections_planned": len(GP.section_groups(parents))})
        rows.append(row)
    return rows


def _pct(x) -> str:
    return "  -  " if x is None else f"{100 * float(x):5.1f}"


def print_table(rows: list[dict], *, worst_n: int) -> None:
    worst = PC.worst(rows, n=worst_n)
    print(f"{'#':>2s} {'score':>5s} {'llm':>5s} {'llm-t':>5s} {'det':>5s} {'det-t':>5s} {'parents':>7s} {'giant':5s} "
          f"{'sect':>4s} document")
    for i, r in enumerate(worst, start=1):
        llm, det = r["reports"]["llm"], r["reports"]["det"]
        flag = "GIANT" if r["giant"] else ""
        print(f"{i:2d} {r['score']:5.2f} {_pct(llm['term_share'])} {_pct(llm['title_share'])} {_pct(det['term_share'])} "
              f"{_pct(det['title_share'])} {r['parents']:7d} {flag:5s} {r['section_profiles']:4d} {r['source_name'][:70]}")
    giants = [r for r in rows if r["giant"]]
    print(f"\n{len(rows)} documents; {len(giants)} giants (> {GP.GIANT_PARENT_THRESHOLD} parents)")
    for r in giants:
        state = ("NO SECTION PROFILES" if r["giant_without_sections"] else f"{r['section_profiles']} section profiles")
        llm = r["reports"]["llm"]
        print(f"  {r['parents']:5d} parents  {r['sections_planned']:3d} planned  {state:22s} llm {r['reports']['llm']['score']:.2f} "
              f"({_pct(llm['term_share']).strip()}% terms, {_pct(llm['title_share']).strip()}% titles)  {r['source_name'][:60]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--doc", default=None, help="audit one document (prints its missing terms and titles)")
    ap.add_argument("--worst", type=int, default=10)
    ap.add_argument("--top", type=int, default=PC.TOP_TERMS)
    ap.add_argument("--json", default=None, help="write every row (with the missing terms / titles) to this file")
    a = ap.parse_args()
    with _connect() as conn:
        rows = audit_corpus(conn, a.corpus, doc_id=a.doc, top=a.top)
    if not rows:
        print("no documents")
        return 1
    print_table(rows, worst_n=a.worst)
    if a.doc:
        r = rows[0]
        for name in ("llm", "det"):
            rep = r["reports"][name]
            print(f"\n[{name}] score {rep['score']:.2f}  missing terms ({len(rep['missing_terms'])}): "
                  f"{', '.join(rep['missing_terms'][:40])}")
            print(f"[{name}] missing titles ({len(rep['missing_titles'])}): {' | '.join(rep['missing_titles'][:30])}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1, default=str))
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
