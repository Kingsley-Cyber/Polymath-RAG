#!/usr/bin/env python
"""MCP PRINCIPALS — manage the hosted MCP surface's per-friend principals (owner decision 2026-09-21).

The registry is ONE JSON file OUTSIDE the repository (`--file`, else $POLYMATH_MCP_PRINCIPALS_FILE, else
~/PolymathRuntime/polymath-v4-mcp-principals.json): owner-only (0600), written atomically, holding key ids and sha256
digests — never a raw bearer. Server A re-reads it when it changes: add / revoke need no fleet bounce. (Server A must be
started with POLYMATH_MCP_PRINCIPALS_FILE pointing at the same file — a `.env` line, live after one bounce.)

A raw bearer exists exactly once: written to `--key-out`, a NEW owner-only file. It is not printed unless `--print-key`
is given explicitly. Hand that file's content to the friend over a channel you trust, then delete it.

    scripts/mcp_principals.py add --id prn_fred --name "Fred" --profile friend \\
        --corpus commerce-v1 --adapter ecommerce.product_research --key-out ~/PolymathRuntime/keys/prn_fred.key
    scripts/mcp_principals.py list
    scripts/mcp_principals.py rotate --id prn_fred --key-out ~/PolymathRuntime/keys/prn_fred.2.key --revoke-old
    scripts/mcp_principals.py revoke --id prn_fred            # the principal: every key stops authenticating
    scripts/mcp_principals.py revoke-key --key-id 3fa9c2d1e07b
    scripts/mcp_principals.py disable --id prn_fred | enable --id prn_fred

Profile `friend` = knowledge search / explore / answer + adapter list / start / next / submit / status / result. No upload,
no history, no admin. Extra scopes are explicit (`--scope adapter.cancel`); `upload.text` also needs `--writable-corpus`.
The admin scope cannot be granted: the owner key ($POLYMATH_MCP_API_KEY) is the only admin.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))

from orchestrator import mcp_principals as P  # noqa: E402

DEFAULT_FILE = "~/PolymathRuntime/polymath-v4-mcp-principals.json"


def _path(args) -> pathlib.Path:
    return pathlib.Path(args.file or os.environ.get("POLYMATH_MCP_PRINCIPALS_FILE") or DEFAULT_FILE).expanduser()


def _find(doc, pid):
    for rec in doc["principals"]:
        if rec["principal_id"] == pid:
            return rec
    raise SystemExit(f"no principal {pid!r}")


def _issue(args, rec) -> dict:
    if not args.key_out and not args.print_key:
        raise SystemExit("give --key-out <new file> (preferred) or --print-key: a raw bearer is never shown by default")
    raw, key = P.new_bearer()
    if args.key_out:
        P.write_secret_file(pathlib.Path(args.key_out).expanduser(), raw)      # refuses to overwrite; 0600
    rec.setdefault("keys", []).append(key)
    return {"key_id": key["key_id"], "key_out": args.key_out, **({"bearer": raw} if args.print_key else {})}


def cmd_add(args) -> dict:
    path = _path(args)
    doc = P.read_registry(path)
    if any(r["principal_id"] == args.id for r in doc["principals"]):
        raise SystemExit(f"principal {args.id!r} exists (rotate / enable / revoke it instead)")
    scopes = sorted({*P.PROFILES[args.profile], *args.scope})
    if P.UPLOAD_TEXT in scopes and not args.writable_corpus:
        raise SystemExit("upload.text needs at least one --writable-corpus")
    rec = {"principal_id": args.id, "name": args.name or "", "enabled": True, "revoked_at": None, "scopes": scopes,
           "corpus_ids": sorted(set(args.corpus)), "adapter_ids": sorted(set(args.adapter)),
           "writable_corpus_ids": sorted(set(args.writable_corpus)), "created_at": P._now_iso(), "expires_at": args.expires,
           "rate_per_minute": args.rate, "keys": []}
    P.principal_from_record(rec)                                   # validate BEFORE a key file is created
    issued = _issue(args, rec)
    doc["principals"].append(rec)
    P.write_registry(path, doc)
    return {"added": args.id, "registry": str(path), **issued, "scopes": scopes, "corpus_ids": rec["corpus_ids"], "adapter_ids": rec["adapter_ids"]}


def cmd_rotate(args) -> dict:
    path = _path(args)
    doc = P.read_registry(path)
    rec = _find(doc, args.id)
    if args.revoke_old:
        for key in rec.get("keys") or []:
            key["revoked_at"] = key.get("revoked_at") or P._now_iso()
    issued = _issue(args, rec)
    P.write_registry(path, doc)
    return {"rotated": args.id, **issued, "old_keys_revoked": bool(args.revoke_old)}


def cmd_state(args) -> dict:
    path = _path(args)
    doc = P.read_registry(path)
    rec = _find(doc, args.id)
    if args.cmd == "revoke":
        rec["revoked_at"] = rec.get("revoked_at") or P._now_iso()
    else:
        rec["enabled"] = args.cmd == "enable"
    P.write_registry(path, doc)
    return {args.cmd: args.id, "enabled": rec["enabled"], "revoked_at": rec["revoked_at"]}


def cmd_revoke_key(args) -> dict:
    path = _path(args)
    doc = P.read_registry(path)
    for rec in doc["principals"]:
        for key in rec.get("keys") or []:
            if key["key_id"] == args.key_id:
                key["revoked_at"] = key.get("revoked_at") or P._now_iso()
                P.write_registry(path, doc)
                return {"revoked_key": args.key_id, "principal_id": rec["principal_id"]}
    raise SystemExit(f"no key {args.key_id!r}")


def cmd_list(args) -> dict:
    doc = P.read_registry(_path(args))
    return {"registry": str(_path(args)), "principals": [
        {k: rec.get(k) for k in ("principal_id", "name", "enabled", "revoked_at", "expires_at", "rate_per_minute", "scopes", "corpus_ids",
                                 "adapter_ids", "writable_corpus_ids", "created_at")}
        | {"keys": [{"key_id": k["key_id"], "created_at": k.get("created_at"), "revoked_at": k.get("revoked_at")} for k in rec.get("keys") or []]}
        for rec in doc["principals"]]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", default=None, help=f"the registry (else $POLYMATH_MCP_PRINCIPALS_FILE, else {DEFAULT_FILE})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--id", required=True, help="stable principal id: prn_<lowercase>")
    a.add_argument("--name", default="")
    a.add_argument("--profile", choices=sorted(P.PROFILES), default="friend")
    a.add_argument("--scope", action="append", default=[], choices=[s for s in P.SCOPES if s != P.ADMIN], help="an extra scope (repeatable)")
    a.add_argument("--corpus", action="append", default=[], help="an allowed corpus id (repeatable)")
    a.add_argument("--adapter", action="append", default=[], help="an allowed adapter id (repeatable)")
    a.add_argument("--writable-corpus", action="append", default=[], help="a corpus upload_text may write to (repeatable)")
    a.add_argument("--expires", default=None, help="ISO-8601 instant after which the principal stops authenticating")
    a.add_argument("--rate", type=int, default=None, help="requests per minute")
    r = sub.add_parser("rotate")
    r.add_argument("--id", required=True)
    r.add_argument("--revoke-old", action="store_true")
    for p in (a, r):
        p.add_argument("--key-out", default=None, help="write the raw bearer to this NEW owner-only file")
        p.add_argument("--print-key", action="store_true", help="also print the raw bearer (off by default)")
    for name in ("revoke", "enable", "disable"):
        sub.add_parser(name).add_argument("--id", required=True)
    sub.add_parser("revoke-key").add_argument("--key-id", required=True)
    sub.add_parser("list")
    args = ap.parse_args(argv)
    out = {"add": cmd_add, "rotate": cmd_rotate, "revoke": cmd_state, "enable": cmd_state, "disable": cmd_state,
           "revoke-key": cmd_revoke_key, "list": cmd_list}[args.cmd](args)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
