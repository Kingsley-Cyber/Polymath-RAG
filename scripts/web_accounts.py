#!/usr/bin/env python
"""WEB ACCOUNTS — logins for the public web UI (FRIENDS-ACCESS-V1, the owner 2026-09-26).

The same registry as scripts/mcp_principals.py (--file, else $POLYMATH_MCP_PRINCIPALS_FILE, else
~/PolymathRuntime/polymath-v4-mcp-principals.json). A password is never printed and never taken as an argument: the owner's is
typed at a hidden prompt; a friend's first password is generated and written to a NEW owner-only file (--password-out), unless
--print-password is given explicitly. The friend must change it at first login.

    scripts/web_accounts.py set-owner-password
    scripts/web_accounts.py add-friend --username fred --name "Fred" --corpus cinema --corpus commerce-v1 \\
        --adapter ecommerce.product_research --password-out ~/PolymathRuntime/keys/fred.password
    scripts/web_accounts.py reset-password --username fred --password-out ~/PolymathRuntime/keys/fred.2.password
    scripts/web_accounts.py disable --username fred | enable --username fred
    scripts/web_accounts.py list
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import pathlib
import secrets
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))

from orchestrator import mcp_principals as P
from orchestrator import web_accounts as W

DEFAULT_FILE = "~/PolymathRuntime/polymath-v4-mcp-principals.json"


def _path(args) -> pathlib.Path:
    return pathlib.Path(args.file or os.environ.get("POLYMATH_MCP_PRINCIPALS_FILE") or DEFAULT_FILE).expanduser()


def _generated_password(args) -> tuple[str, dict]:
    if not args.password_out and not args.print_password:
        raise SystemExit("give --password-out <new file> (preferred) or --print-password: a password is never shown by default")
    pw = secrets.token_urlsafe(12)
    if args.password_out:
        P.write_secret_file(pathlib.Path(args.password_out).expanduser(), pw)      # refuses to overwrite; 0600
    return pw, {"password_out": args.password_out, **({"password": pw} if args.print_password else {})}


def cmd_set_owner_password(args) -> dict:
    first = getpass.getpass("New password for King (hidden): ")
    if first != getpass.getpass("Again: "):
        raise SystemExit("the two entries differ; nothing changed")
    W.set_owner_password(_path(args), first)
    return {"owner_password": "set", "username": W.OWNER_USERNAME, "registry": str(_path(args))}


def cmd_add_friend(args) -> dict:
    pw, shown = _generated_password(args)
    rec = W.add_friend(_path(args), args.username, pw, display_name=args.name, corpus_ids=args.corpus, adapter_ids=args.adapter)
    return {"added": rec, **shown}


def cmd_reset_password(args) -> dict:
    pw, shown = _generated_password(args)
    W.reset_friend_password(_path(args), args.username, pw)
    return {"reset": W.normalize_username(args.username), **shown}


def cmd_state(args) -> dict:
    W.set_friend_enabled(_path(args), args.username, args.cmd == "enable")
    return {args.cmd: W.normalize_username(args.username)}


def cmd_list(args) -> dict:
    doc = W.read_registry(_path(args))
    owner = doc.get("owner_web") or {}
    return {"registry": str(_path(args)), "owner_login": "set" if owner.get("password_hash") else "NOT SET",
            "friends": W.list_friends(doc)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", default=None, help=f"the registry (else $POLYMATH_MCP_PRINCIPALS_FILE, else {DEFAULT_FILE})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("set-owner-password")
    a = sub.add_parser("add-friend")
    a.add_argument("--username", required=True)
    a.add_argument("--name", default="")
    a.add_argument("--corpus", action="append", default=[], help="a library the friend may read (repeatable); fr-<username> is added")
    a.add_argument("--adapter", action="append", default=[], help="an adapter the friend may run (repeatable)")
    r = sub.add_parser("reset-password")
    r.add_argument("--username", required=True)
    for p in (a, r):
        p.add_argument("--password-out", default=None, help="write the first password to this NEW owner-only file")
        p.add_argument("--print-password", action="store_true", help="also print it (off by default)")
    for name in ("enable", "disable"):
        sub.add_parser(name).add_argument("--username", required=True)
    sub.add_parser("list")
    args = ap.parse_args(argv)
    try:
        out = {"set-owner-password": cmd_set_owner_password, "add-friend": cmd_add_friend, "reset-password": cmd_reset_password,
               "enable": cmd_state, "disable": cmd_state, "list": cmd_list}[args.cmd](args)
    except W.AccountError as exc:
        raise SystemExit(f"{exc.code}: {exc}")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
