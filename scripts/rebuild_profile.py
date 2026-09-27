#!/usr/bin/env python3
"""FACET-RETRIEVAL-V1 F4 — rebuild the profile(s) of ONE document by id, through the doc_profile worker itself.

  .venv/bin/python scripts/rebuild_profile.py --doc <doc_id> --dry-run            # the plan + the EXACT input windows
  .venv/bin/python scripts/rebuild_profile.py --doc <doc_id> --execute [--force] [--out receipt.json]

`--dry-run` (the default) reads Postgres only: it prints whether the document is a giant, its section plan
(one profile per top-level heading; big headings split, tiny ones folded), the lanes each call would try
(`config/cloud_providers.json` stage pins for `doc_profile`, in the worker's own attempt order — no key is
read or printed), and the exact prompt input the worker would send for the document profile and for every
section profile. No LLM call, no Qdrant, no write.

`--execute` runs `workers.doc_profile_worker.process_event` for the document's latest run — the SAME code path
the fleet's `doc_profile` slots run: the registered `doc_profile` lanes + their per-process limiter, the
compiler, the profile / atom projections, and the stage receipt + artifact under the run (stage `doc_profile`,
keys `doc_profile`, `doc_profile_sections`, `doc_profile_qdrant`, `doc_profile_atoms`). All sections are built in
ONE pass by default (`--sections-per-pass` bounds a pass; a pool hold is retried up to `--max-passes`). A section
whose input is unchanged under the live prompt is skipped unless `--force`. Load the fleet `.env` first
(`set -a; . ./.env; set +a`); the embedder sidecar and Qdrant must be up. Never run while a fleet slot holds
the same document's ticket.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "shared", ROOT / "workers", ROOT / "control", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from polymath_shared.document_profile import giant_profile as GP

STAGE = "doc_profile"


def _connect(read_only: bool):
    import psycopg
    dsn = os.environ.get("POLYMATH_PG_DSN")
    if not dsn:
        raise SystemExit("POLYMATH_PG_DSN is not set (load the fleet .env: set -a; . ./.env; set +a)")
    opts = "-c default_transaction_read_only=on" if read_only else None
    return psycopg.connect(dsn, options=opts)


def resolve_doc(conn, *, doc_id: str | None, corpus: str | None, source_name: str | None) -> tuple[str, str | None]:
    """(doc_id, latest run_id) for the document."""
    if doc_id:
        row = conn.execute("SELECT doc_id FROM documents WHERE doc_id=%s", (doc_id,)).fetchone()
    else:
        if not (corpus and source_name):
            raise SystemExit("give --doc <doc_id>, or --corpus and --source-name")
        row = conn.execute("SELECT doc_id FROM documents WHERE corpus_id=%s AND source_name=%s", (corpus, source_name)).fetchone()
    if not row:
        raise SystemExit("document not found")
    did = row[0]
    run = conn.execute(
        """SELECT r.run_id FROM runs r JOIN documents d ON d.corpus_id = r.corpus_id
                AND d.source_name = (r.metadata->'intake_payload'->>'source_name')
           WHERE d.doc_id = %s ORDER BY r.created_at DESC LIMIT 1""", (did,)).fetchone()
    return did, (run[0] if run else None)


def plan(conn, doc_id: str) -> dict:
    """The dry-run plan: the document, its parents, the section groups and the exact windows."""
    from workers import doc_profile_worker as W
    vnext = W._vnext_enabled()
    document, parents, _terms = W._load_inputs(conn, doc_id, want_terms=False)
    groups = GP.section_groups(parents)
    windows = []
    if groups:
        fp = GP.build_giant_fingerprint(document, parents, groups)
        system_prompt, user_prompt, prompt_ver, builder = W._prompt_for(fp, vnext=vnext)
        windows.append({"scope": "document", "title": fp.title, "builder": builder, "prompt_version": prompt_ver,
                        "budget_tokens": fp.budget_tokens, "used_tokens": fp.used_tokens, "used_total": fp.used_total,
                        "sections_sampled": fp.sources.get("sections_sampled"), "system_chars": len(system_prompt),
                        "user_chars": len(user_prompt), "user_prompt": user_prompt})
        for i, g in enumerate(groups, start=1):
            sfp = GP.build_section_fingerprint(document, g, ordinal=i, total=len(groups))
            system_prompt, user_prompt, prompt_ver, builder = W._prompt_for(sfp, vnext=vnext)
            windows.append({"scope": "section", "ordinal": i, "key": g.key, "title": g.title, "parents": g.parent_count,
                            "chars": g.chars, "builder": builder, "prompt_version": prompt_ver,
                            "input_hash": sfp.input_hash(g.content_hash()), "budget_tokens": sfp.budget_tokens,
                            "used_tokens": sfp.used_tokens, "used_total": sfp.used_total,
                            "system_chars": len(system_prompt), "user_chars": len(user_prompt), "user_prompt": user_prompt})
    else:
        from polymath_shared.document_profile import fingerprint as FP
        from polymath_shared.document_profile import profile_prompt_vnext as PP
        if vnext:
            fp = FP.build_fingerprint(document, parents)
            system_prompt, user_prompt = PP.build_vnext_profile_prompt(fp)
            builder, prompt_ver, used, title = FP.FINGERPRINT_BUILDER_VERSION, PP.PROFILE_VNEXT_PROMPT_VERSION, fp.used_tokens, fp.title
        else:
            from polymath_shared.document_profile import context as CX
            from polymath_shared.document_profile.prompt import (
                PROMPT_VERSION,
                SYSTEM,
                build_user_prompt,
            )
            ctx = CX.build_context(document, parents, budget_tokens=W.CONTEXT_BUDGET_TOKENS)
            system_prompt, user_prompt = SYSTEM, build_user_prompt(ctx.title, ctx.structure_block, ctx.excerpts_block)
            builder, prompt_ver, used, title = CX.BUILDER_VERSION, PROMPT_VERSION, ctx.used_tokens, ctx.title
        windows.append({"scope": "document", "title": title, "builder": builder, "prompt_version": prompt_ver,
                        "used_tokens": used, "system_chars": len(system_prompt), "user_chars": len(user_prompt),
                        "user_prompt": user_prompt})
    return {"doc_id": doc_id, "source_name": document.get("source_name"), "parents": len(parents),
            "giant": GP.is_giant(len(parents)), "threshold": GP.GIANT_PARENT_THRESHOLD, "vnext": vnext,
            "sections": [{"ordinal": g.ordinal, "key": g.key, "title": g.title, "parents": g.parent_count, "chars": g.chars}
                         for g in groups],
            "windows": windows, "calls": len(windows)}


def lanes_for(run_key: str) -> list[str]:
    """The worker's attempt order for one call (config only; no key read)."""
    from polymath_shared.llm_extraction.pool import stage_owners, stage_pin

    from workers import doc_profile_worker as W
    pin = stage_pin(STAGE) or []
    return W.attempt_lanes(pin, run_key, stage_owners(STAGE)) if pin else []


def print_plan(p: dict, run_id: str | None, *, show_windows: int | None) -> None:
    from workers import doc_profile_worker as W
    print(f"document {p['doc_id']}  {p['source_name']}")
    print(f"parents {p['parents']}  giant {p['giant']} (threshold {p['threshold']})  vnext {p['vnext']}  run {run_id}")
    print(f"calls {p['calls']}: 1 document profile" + (f" + {len(p['sections'])} section profiles" if p["sections"] else ""))
    if p["sections"]:
        print(f"\nsection plan (one profile per top-level heading; > {GP.SECTION_SPLIT_PARENTS} parents split at the next "
              f"level, < {GP.MIN_SECTION_PARENTS} folded):")
        for s in p["sections"]:
            print(f"  {s['ordinal']:3d} {s['key']} {s['parents']:4d} parents {s['chars']:8d} chars  {s['title'][:90]}")
    lanes = lanes_for(run_id or p["doc_id"])
    print(f"\nlanes (stage pin `{STAGE}`, this process's attempt order, primaries rotate per call): {lanes or 'NO PIN'}")
    est_out = W.MAX_OUTPUT_TOKENS
    total_in = sum(int(w.get("used_total") or sum((w.get("used_tokens") or {}).values())) for w in p["windows"])
    print(f"expected tokens ≈ {total_in:,} input (+ ~{p['calls'] * 900:,} system prompt) + up to {p['calls'] * est_out:,} output "
          f"over {p['calls']} calls (max_tokens {est_out} each)")
    limit = len(p["windows"]) if show_windows is None else max(0, show_windows)
    for w in p["windows"][:limit]:
        head = (f"\n===== WINDOW {w['scope']}" + (f" #{w['ordinal']} {w['title']}" if w["scope"] == "section" else f" {w['title']}")
                + f" | builder {w['builder']} prompt {w['prompt_version']} | user {w['user_chars']} chars, "
                f"system {w['system_chars']} chars | used {w.get('used_tokens')}")
        print(head)
        print(w["user_prompt"])
    if limit < len(p["windows"]):
        print(f"\n… {len(p['windows']) - limit} more windows (pass --windows all)")


def execute(doc_id: str, run_id: str, *, force: bool, per_pass: int | None, max_passes: int, out: str | None) -> int:
    from polymath_shared.db import tx
    from polymath_shared.receipts import StageFailed
    from polymath_shared.worker_runtime import TransientStageHold, _is_transient_hold

    from workers import doc_profile_worker as W
    # the worker reads its switches from the environment (the same names the fleet's slots read)
    os.environ.update({
        "POLYMATH_DOC_PROFILE_GIANT": "1",
        "POLYMATH_DOC_PROFILE_SECTIONS_PER_PASS": str(per_pass) if per_pass else "100000",   # every section in one pass
        "POLYMATH_DOC_PROFILE_FORCE_SECTIONS": "1" if force else "0",
    })
    event = {"run_id": run_id, "payload": {"run_id": run_id, "rebuild": "scripts/rebuild_profile.py", "doc_id": doc_id}}
    backoff = 30.0
    for n in range(1, max_passes + 1):
        t0 = time.time()
        try:
            with tx() as conn:
                W.process_event(conn, event)
            print(f"pass {n}: done in {time.time() - t0:.0f}s")
            break
        except (StageFailed, TransientStageHold, RuntimeError) as exc:
            cause = exc.__cause__ if isinstance(exc, StageFailed) else exc
            if _is_transient_hold(exc):
                print(f"pass {n}: hold after {time.time() - t0:.0f}s — {cause}; retrying in {backoff:.0f}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 300.0)
                continue
            print(f"pass {n}: FAILED — {cause}")
            return 1
    else:
        print("gave up: passes exhausted while the pool held")
        return 2
    with tx() as conn:
        row = conn.execute("SELECT payload FROM artifacts WHERE run_id=%s AND stage=%s AND contract_hash=%s",
                           (run_id, STAGE, W.contract())).fetchone()
    payload = (row[0] if isinstance(row[0], dict) else json.loads(row[0])) if row else {}
    dp, sec, pq = payload.get("doc_profile") or {}, payload.get("doc_profile_sections") or {}, payload.get("doc_profile_qdrant") or {}
    summary = {"doc_id": doc_id, "run_id": run_id, "contract_hash": W.contract(),
               "document": {k: dp.get(k) for k in ("builder_version", "prompt_version", "quality", "valid", "lane", "model",
                                                    "compiled_hash", "giant", "sections")},
               "document_surfaces": {k: (len(v) if isinstance(v, list) else 1) for k, v in (dp.get("compiled") or {}).items() if v},
               "projection": {k: pq.get(k) for k in ("point_id", "vectors", "kept_last_known_good", "valid")},
               "sections": {"total": sec.get("sections_total"), "built": len(sec.get("built") or []),
                            "skipped": len(sec.get("skipped") or []), "failed": len(sec.get("failed") or []),
                            "pending": len(sec.get("pending") or []), "orphans_purged": sec.get("orphans_purged"),
                            "lanes": sorted({str(b.get("lane")) for b in (sec.get("built") or [])}),
                            "quality": [b.get("quality") for b in (sec.get("built") or [])]}}
    print(json.dumps(summary, indent=1, default=str))
    if out:
        Path(out).write_text(json.dumps(payload, indent=1, default=str))
        print(f"wrote {out}")
    failed = summary["sections"]["failed"] or 0
    return 3 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--doc", default=None, help="document id")
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--source-name", default=None)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="print the plan and the exact input windows (default)")
    g.add_argument("--execute", action="store_true", help="rebuild through the worker's code path (LLM calls, writes)")
    ap.add_argument("--force", action="store_true", help="rebuild sections whose input is unchanged, too")
    ap.add_argument("--vnext", action="store_true",
                    help="use the vNext prompt (research-index surfaces: anchor, bridge, tension, …) for this run, "
                         "whatever the fleet .env says (sets POLYMATH_DOC_PROFILE_VNEXT=1 for the process)")
    ap.add_argument("--sections-per-pass", type=int, default=None, help="bound a pass (default: every section)")
    ap.add_argument("--max-passes", type=int, default=12)
    ap.add_argument("--windows", default="all", help="how many input windows to print in the dry run (all | N)")
    ap.add_argument("--out", default=None, help="--execute: write the full artifact payload here")
    a = ap.parse_args()
    if a.vnext:
        os.environ["POLYMATH_DOC_PROFILE_VNEXT"] = "1"
    with _connect(read_only=True) as conn:
        doc_id, run_id = resolve_doc(conn, doc_id=a.doc, corpus=a.corpus, source_name=a.source_name)
        if not a.execute:
            p = plan(conn, doc_id)
    if not a.execute:
        show = None if str(a.windows).lower() == "all" else int(a.windows)
        print_plan(p, run_id, show_windows=show)
        print("\nDRY RUN — nothing was called or written. Pass --execute to rebuild.")
        return 0
    if not run_id:
        raise SystemExit("the document has no run (the worker keys its receipt on the run)")
    return execute(doc_id, run_id, force=a.force, per_pass=a.sections_per_pass, max_passes=a.max_passes, out=a.out)


if __name__ == "__main__":
    raise SystemExit(main())
