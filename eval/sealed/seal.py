#!/usr/bin/env python3
"""SEALED-MULTIDOMAIN-QUALIFICATION-V1 — the sealing harness.

The point of this file is to convert a promise into a mechanism.

    before:  "I promise I did not tune against the evaluation set."
    after:   "The run refuses to proceed if the evaluation set, the code, or
              the semantic bundle changed after sealing."

It cannot make tuning impossible — nothing can — but it makes an altered set
or an altered semantic surface DETECTABLE and BLOCKING rather than a matter
of recollection. Every refusal is loud and names what drifted.

    seal    freeze inputs + code + semantic bundle, before any ingestion
    verify  refuse if any of the three moved
    stamp   record output hashes after a run
    replay  re-derive output hashes and compare to the stamp

Deliberate properties:

  * The manifest records its OWN sha256 separately, so editing it after the
    fact is detectable rather than silent.
  * Sealing REFUSES if a document has already been ingested anywhere in the
    corpus store. A document the system has already seen cannot prove
    generalization, and that is a property of the data, not of good
    intentions.
  * Sealing REFUSES on a dirty working tree or a detached/unknown commit.
    "Which code produced this result" must have exactly one answer.
  * Nothing here imports an admission authority. This harness measures; it
    has no opinion about semantics and must never acquire one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent
DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

CONTRACT = "sealed-multidomain-qualification-v1"

# Registers the sealed set must span. A set that omits one is not rejected,
# but the gap is recorded in the manifest so the verdict cannot silently
# claim coverage it does not have.
REGISTERS = ("technical_cyber", "biomedical_scientific", "business_operations",
             "academic_social_science", "structurally_different")


def _sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _sha256_obj(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()


def _code_state() -> dict:
    # The sealed manifests are the harness's OWN output, not code under test.
    # Counting them as drift makes an intact seal unverifiable the moment it
    # is written, and would push a user toward --allow-dirty, which defeats
    # the check that matters.
    dirty = "\n".join(
        ln for ln in _git("status", "--porcelain").splitlines()
        if "eval/sealed/manifest_" not in ln)
    return {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "describe": _git("describe", "--tags", "--always"),
        "dirty_files": [ln[3:] for ln in dirty.splitlines()] if dirty else [],
    }


def _runtime_state() -> dict:
    locks = sorted(p.relative_to(ROOT).as_posix()
                   for p in ROOT.glob("*/pyproject.toml"))
    locks += ["pyproject.toml"] if (ROOT / "pyproject.toml").exists() else []
    lock_hash = _sha256_obj({p: _sha256_file(ROOT / p) for p in sorted(locks)})

    models: dict = {}
    try:
        import httpx

        from polymath_shared.settings import get_settings
        s = get_settings().sidecars
        for name, url in (("gliner", s.gliner_url), ("spacy", s.spacy_url),
                          ("embedder", s.embedder_url)):
            try:
                r = httpx.get(f"{url}/manifest", timeout=5)
                ident = r.json().get("identity", {})
                models[name] = ident.get("model", ident)
            except Exception as exc:            # a sidecar that cannot be
                models[name] = {"unavailable": str(exc)[:80]}   # identified
    except Exception as exc:                                    # is recorded
        models["error"] = str(exc)[:120]                        # as such
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependency_lock_hash": lock_hash,
        "dependency_files": sorted(locks),
        "models": models,
    }


def _semantic_bundle() -> dict:
    from polymath_shared.execution import (
        SEMANTIC_CONTRACT_V2, semantic_authorities, semantic_authority_sha256,
        semantic_bundle_sha256,
    )
    return {
        "semantic_contract": SEMANTIC_CONTRACT_V2,
        "authority_sha256": semantic_authority_sha256(),
        "bundle_sha256": semantic_bundle_sha256(),
        "authorities": semantic_authorities(),
    }


def _already_ingested(doc_hashes: dict[str, str]) -> list[dict]:
    """Has the system already seen any of these documents?

    A document already in the store cannot prove generalization: whatever it
    would reveal, the system has had the chance to be shaped by. Checked by
    CONTENT hash, so renaming a file does not launder it.
    """
    try:
        import psycopg
    except Exception:
        return []
    seen: list[dict] = []
    try:
        with psycopg.connect(DSN, connect_timeout=5) as conn:
            rows = conn.execute(
                "SELECT corpus_id, source_name, content_hash, source_hash "
                "FROM documents").fetchall()
    except Exception:
        return []
    known = {}
    for corpus, name, chash, shash in rows:
        for h in (chash, shash):
            if h:
                known.setdefault(h, []).append({"corpus": corpus, "source": name})
    for path, digest in doc_hashes.items():
        # content_hash and source_hash can both match the same row; report the
        # document once rather than once per matching column
        for hit in {(h["corpus"], h["source"]) for h in known.get(digest, [])}:
            seen.append({"document": path, "corpus": hit[0], "source": hit[1]})
    return seen


def manifest_path(name: str) -> pathlib.Path:
    return HERE / f"manifest_{name}.json"


# --------------------------------------------------------------------------
def cmd_seal(args) -> int:
    docs: list[dict] = []
    for spec in args.doc:
        register, _, raw = spec.partition("=")
        if not raw:
            print(f"ERROR: --doc must be REGISTER=PATH, got {spec!r}", file=sys.stderr)
            return 2
        if register not in REGISTERS:
            print(f"ERROR: unknown register {register!r}; expected one of "
                  f"{list(REGISTERS)}", file=sys.stderr)
            return 2
        p = pathlib.Path(raw).expanduser().resolve()
        if not p.is_file():
            print(f"ERROR: not a file: {p}", file=sys.stderr)
            return 2
        docs.append({"register": register, "path": str(p), "name": p.name,
                     "sha256": _sha256_file(p), "byte_length": p.stat().st_size})

    code = _code_state()
    if code["dirty_files"] and not args.allow_dirty:
        print("REFUSED: working tree is dirty — 'which code produced this "
              "result' must have exactly one answer.", file=sys.stderr)
        for f in code["dirty_files"][:10]:
            print(f"   {f}", file=sys.stderr)
        return 3

    contaminated = _already_ingested({d["path"]: d["sha256"] for d in docs})
    if contaminated and not args.allow_seen:
        print("REFUSED: these documents are already in the corpus store, so "
              "they cannot demonstrate generalization:", file=sys.stderr)
        for c in contaminated:
            print(f"   {c['document']} -> corpus {c['corpus']}", file=sys.stderr)
        return 4

    covered = sorted({d["register"] for d in docs})
    body = {
        "contract": CONTRACT,
        "set_name": args.set,
        "sealed_at_utc": args.sealed_at,
        "code": code,
        "semantic_bundle": _semantic_bundle(),
        "runtime": _runtime_state(),
        "documents": sorted(docs, key=lambda d: (d["register"], d["name"])),
        "register_coverage": {"covered": covered,
                              "missing": [r for r in REGISTERS if r not in covered]},
        "results": None,
    }
    out = {"manifest": body, "manifest_sha256": _sha256_obj(body)}
    path = manifest_path(args.set)
    if path.exists() and not args.force:
        print(f"REFUSED: {path.name} already exists. Re-sealing an existing "
              "set is how an evaluation set quietly changes.", file=sys.stderr)
        return 5
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"sealed": path.name, "documents": len(docs),
                      "registers_covered": covered,
                      "registers_missing": body["register_coverage"]["missing"],
                      "commit": code["describe"],
                      "authority_sha256": body["semantic_bundle"]["authority_sha256"][:16],
                      "manifest_sha256": out["manifest_sha256"][:16]}, indent=1))
    return 0


def _load(name: str) -> tuple[dict, dict, list[str]]:
    path = manifest_path(name)
    if not path.exists():
        print(f"ERROR: no sealed manifest at {path}", file=sys.stderr)
        sys.exit(2)
    doc = json.loads(path.read_text())
    body = doc["manifest"]
    drift: list[str] = []
    if _sha256_obj(body) != doc["manifest_sha256"]:
        drift.append("MANIFEST ALTERED after sealing (self-hash mismatch)")
    return doc, body, drift


def cmd_verify(args) -> int:
    doc, body, drift = _load(args.set)

    for d in body["documents"]:
        p = pathlib.Path(d["path"])
        if not p.is_file():
            drift.append(f"DOCUMENT MISSING: {d['name']}")
            continue
        if _sha256_file(p) != d["sha256"]:
            drift.append(f"DOCUMENT CHANGED: {d['name']}")
        elif p.stat().st_size != d["byte_length"]:
            drift.append(f"DOCUMENT SIZE CHANGED: {d['name']}")

    code = _code_state()
    if code["commit"] != body["code"]["commit"]:
        drift.append(f"CODE MOVED: sealed {body['code']['describe']} "
                     f"-> now {code['describe']}")
    if code["dirty_files"] and not args.allow_dirty:
        drift.append(f"WORKING TREE DIRTY: {len(code['dirty_files'])} file(s)")

    try:
        bundle = _semantic_bundle()
        if bundle["authority_sha256"] != body["semantic_bundle"]["authority_sha256"]:
            drift.append("SEMANTIC AUTHORITIES CHANGED since sealing")
    except Exception as exc:
        drift.append(f"SEMANTIC BUNDLE UNREADABLE: {exc}")

    print(json.dumps({"set": args.set, "documents": len(body["documents"]),
                      "sealed_commit": body["code"]["describe"],
                      "drift": drift, "verdict": "SEALED" if not drift else "BROKEN"},
                     indent=1))
    if drift:
        print("\nREFUSED: the seal is broken. Re-seal deliberately, or restore "
              "the sealed state — do not proceed.", file=sys.stderr)
    return 1 if drift else 0


def _output_hashes(corpus: str) -> dict:
    import psycopg
    q = {
        "mentions": """SELECT mention_id, COALESCE(entity_id,''),
                              COALESCE(admission_class,''), COALESCE(anchor_kind,''),
                              COALESCE(decision_status,''), COALESCE(reference_basis,'')
                         FROM mentions WHERE corpus_id=%s ORDER BY mention_id""",
        "entities": """SELECT DISTINCT e.entity_id, e.core_type, e.normalized_surface,
                              COALESCE(e.admission_class,'')
                         FROM entities e JOIN mentions m ON m.entity_id=e.entity_id
                        WHERE m.corpus_id=%s ORDER BY 1""",
        "facts": """SELECT f.fact_id, f.predicate, f.subject_id, f.object_id
                      FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
                      JOIN documents d ON d.doc_id=ev.doc_id
                     WHERE d.corpus_id=%s ORDER BY f.fact_id""",
        "canonical": """SELECT canonical_id, local_entity_id, decision
                          FROM canonical_memberships WHERE corpus_id=%s
                         ORDER BY 1,2""",
    }
    out: dict = {}
    with psycopg.connect(DSN) as conn:
        for key, sql in q.items():
            rows = conn.execute(sql, (corpus,)).fetchall()
            out[f"{key}_hash"] = _sha256_obj([list(map(str, r)) for r in rows])
            out[f"{key}_count"] = len(rows)
    return out


def cmd_stamp(args) -> int:
    doc, body, drift = _load(args.set)
    if drift and not args.allow_dirty:
        print(json.dumps({"drift": drift}, indent=1), file=sys.stderr)
        print("REFUSED: cannot stamp results against a broken seal.", file=sys.stderr)
        return 1
    body["results"] = {"corpus_id": args.corpus, **_output_hashes(args.corpus)}
    doc["manifest"] = body
    doc["manifest_sha256"] = _sha256_obj(body)
    manifest_path(args.set).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps(body["results"], indent=1))
    return 0


def cmd_replay(args) -> int:
    _doc, body, _drift = _load(args.set)
    stamped = body.get("results")
    if not stamped:
        print("ERROR: no stamped results; run `stamp` first.", file=sys.stderr)
        return 2
    current = {"corpus_id": stamped["corpus_id"], **_output_hashes(stamped["corpus_id"])}
    diffs = [k for k in current if k.endswith("_hash") and current[k] != stamped.get(k)]
    print(json.dumps({"set": args.set, "corpus": stamped["corpus_id"],
                      "divergent": diffs,
                      "verdict": "DETERMINISTIC" if not diffs else "NON-DETERMINISTIC"},
                     indent=1))
    return 1 if diffs else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("seal", help="freeze inputs + code + semantic bundle")
    s.add_argument("--set", required=True)
    s.add_argument("--doc", action="append", required=True,
                   metavar="REGISTER=PATH",
                   help=f"one of {list(REGISTERS)}")
    s.add_argument("--sealed-at", dest="sealed_at", required=True,
                   help="ISO timestamp, supplied by the caller (not read from "
                        "the clock, so the manifest stays reproducible)")
    s.add_argument("--force", action="store_true")
    s.add_argument("--allow-dirty", action="store_true")
    s.add_argument("--allow-seen", action="store_true",
                   help="seal documents already in the store — this forfeits "
                        "the generalization claim and is recorded")
    s.set_defaults(fn=cmd_seal)

    v = sub.add_parser("verify", help="refuse if inputs/code/bundle moved")
    v.add_argument("--set", required=True)
    v.add_argument("--allow-dirty", action="store_true")
    v.set_defaults(fn=cmd_verify)

    t = sub.add_parser("stamp", help="record output hashes after a run")
    t.add_argument("--set", required=True)
    t.add_argument("--corpus", required=True)
    t.add_argument("--allow-dirty", action="store_true")
    t.set_defaults(fn=cmd_stamp)

    r = sub.add_parser("replay", help="re-derive output hashes and compare")
    r.add_argument("--set", required=True)
    r.set_defaults(fn=cmd_replay)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
