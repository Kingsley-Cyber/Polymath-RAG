#!/usr/bin/env python
"""FRIENDS-ACCESS-V1 F5 — move rag.kingsleylab.xyz's sign-in from Caddy's shared basic-auth into the app.

In the Caddy site that proxies to the orchestrator (`:8794` by default): remove the `basic_auth { … }` block, and add
`request_header -X-Polymath-Principal` so a browser can never send a principal header (the app's web boundary drops it too).
Everything else in the file stays. `--apply` keeps a timestamped backup next to the file, validates the new text with
`caddy validate`, then writes it; without `--apply` it only prints what it would change. Idempotent.

    python3 scripts/friends_access_caddy.py --caddyfile ~/.hermes/rag-proxy/Caddyfile --apply
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

STRIP_LINE = "request_header -X-Polymath-Principal"


def _site_span(text: str, site: str) -> tuple[int, int] | None:
    """(start of the site's body, index of its closing brace) for `site {` … `}` with nested braces."""
    m = re.search(rf"(?m)^\s*{re.escape(site)}\s*\{{", text)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return (m.end(), i - 1) if depth == 0 else None


def transform(text: str, site: str = ":8794") -> tuple[str, list[str]]:
    """(new text, the changes made). Raises ValueError when the site is missing or its braces do not balance."""
    span = _site_span(text, site)
    if span is None:
        raise ValueError(f"no `{site} {{ … }}` site in the Caddyfile")
    start, end = span
    body, changes = text[start:end], []
    m = re.search(r"(?m)^[ \t]*basic_auth[^\n{]*\{", body)
    if m:
        depth, i = 1, m.end()
        while i < len(body) and depth:
            depth += {"{": 1, "}": -1}.get(body[i], 0)
            i += 1
        tail = body[i:]
        tail = tail.removeprefix("\n")
        body = body[:m.start()] + tail
        changes.append("removed basic_auth (sign-in moves into the app)")
    if STRIP_LINE not in body:
        indent = re.search(r"(?m)^([ \t]+)\S", body)
        pad = indent.group(1) if indent else "\t"
        body = (f"\n{pad}# FRIENDS-ACCESS-V1: each person signs in inside the app; a browser can never send a principal header"
                f"\n{pad}{STRIP_LINE}" + (body if body.startswith("\n") else "\n" + body))
        changes.append(f"added `{STRIP_LINE}`")
    return text[:start] + body + text[end:], changes


def _validate(text: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".Caddyfile", delete=False) as fh:
        fh.write(text)
        tmp = pathlib.Path(fh.name)
    try:
        out = subprocess.run(["caddy", "validate", "--config", str(tmp), "--adapter", "caddyfile"],
                             capture_output=True, text=True, timeout=60, check=False)
        if out.returncode != 0:
            raise SystemExit(f"caddy validate refused the new Caddyfile; nothing written:\n{out.stderr[-800:]}")
    finally:
        tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--caddyfile", default="~/.hermes/rag-proxy/Caddyfile")
    ap.add_argument("--site", default=":8794")
    ap.add_argument("--apply", action="store_true", help="back up, validate and write (else: only report)")
    args = ap.parse_args(argv)
    path = pathlib.Path(args.caddyfile).expanduser()
    new, changes = transform(path.read_text(), args.site)
    if not changes:
        print("unchanged: already signs in inside the app")
        return 0
    if not args.apply:
        print("would change:", "; ".join(changes))
        return 0
    _validate(new)
    backup = path.with_name(f"{path.name}.bak.{dt.datetime.now().astimezone():%Y%m%d-%H%M%S}")
    shutil.copy2(path, backup)
    path.write_text(new)
    print("changed:", "; ".join(changes), f"(backup: {backup})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
