#!/usr/bin/env python3
"""CODE-WIKI-V1 layer 3: check every page of docs/codewiki against the live code. No model, no network.

Two checks per page:
  1. Each line of a ```verify block is one SAFE assertion, run as an argument list (never through a shell):
       grep -Fq 'literal' path            grep -Eq 'regex' path            (flags from -F -E -q -R -r -i -w -x)
       ! grep -Fq 'literal' path          (the literal must NOT be there)
       test "$(grep -c -F 'literal' path)" -ge N      (-eq -ne -ge -gt -le -lt)
     A line in any other shape is refused (it counts as a failure): a page can never run a command.
  2. Each anchor `path:LINE` or `path:START-END` names a tracked file (missing file = failure) whose length covers the line
     (out of range = a warning: code moved; the page is stale, not wrong).

Usage: .venv/bin/python scripts/codewiki/verify.py [--json] [--strict-anchors] [PAGE ...]
Exit 0 = every assertion passed and every anchor names a real file.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WIKI = ROOT / "docs" / "codewiki"
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([A-Za-z0-9_-]*)\s*$")
GREP_FLAGS = re.compile(r"^-[FEqRriwxc]+$")
TEST_RE = re.compile(r'^test\s+"\$\((grep\s+[^)]*)\)"\s+(-eq|-ne|-ge|-gt|-le|-lt)\s+(\d+)$')
ANCHOR_RE = re.compile(r"(?<![\w/.-])((?:orchestrator|shared|workers|control|mcp_server|sidecars|adapters|frontend-v2|scripts|stores|"
                       r"tests|config|contracts|deployment|docs)/[\w./@+-]+\.[A-Za-z0-9]+|compose\.yaml|AGENTS\.md|ARCHITECTURE\.md)"
                       r":(\d+)(?:-(\d+))?")
OPS = {"-eq": int.__eq__, "-ne": int.__ne__, "-ge": int.__ge__, "-gt": int.__gt__, "-le": int.__le__, "-lt": int.__lt__}
_lines_cache: dict[str, int] = {}


def verify_lines(text: str) -> list[str]:
    out, inside, marker = [], False, ""
    for line in text.splitlines():
        m = FENCE.match(line)
        if m:
            if not inside and m.group(2).lower() == "verify":
                inside, marker = True, m.group(1)
                continue
            if inside and line.strip().startswith(marker[0] * 3):
                inside = False
                continue
        if inside and line.strip() and not line.strip().startswith("#"):
            out.append(line.strip())
    return out


def _safe_path(p: str) -> bool:
    return bool(p) and not p.startswith(("/", "~", "-")) and ".." not in Path(p).parts and (ROOT / p).exists()


def _grep_argv(tokens: list[str]) -> list[str] | None:
    """['grep', flags..., pattern, path] → a checked argv, or None when the shape is not the allowed one."""
    if not tokens or tokens[0] != "grep":
        return None
    flags, rest = [], tokens[1:]
    while rest and rest[0].startswith("-") and rest[0] != "--":
        if not GREP_FLAGS.match(rest[0]):
            return None
        flags.append(rest.pop(0))
    if rest and rest[0] == "--":
        rest = rest[1:]
    if len(rest) != 2 or not _safe_path(rest[1]):
        return None
    if (ROOT / rest[1]).is_dir() and not any(("R" in f or "r" in f) for f in flags):
        return None
    return ["grep", *flags, "--", rest[0], rest[1]]


def run_line(line: str, timeout: float = 20.0) -> tuple[bool, str]:
    """(passed, reason). Never uses a shell."""
    m = TEST_RE.match(line)
    try:
        if m:
            argv = _grep_argv(shlex.split(m.group(1)))
            if argv is None or not any("c" in f for f in argv[1:-3] if f.startswith("-")):
                return False, "refused: not an allowed test form"
            p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
            count = int((p.stdout.strip().splitlines() or ["0"])[-1].split(":")[-1] or 0)
            ok = OPS[m.group(2)](count, int(m.group(3)))
            return ok, "" if ok else f"count {count} fails {m.group(2)} {m.group(3)}"
        negate = line.startswith("! ")
        argv = _grep_argv(shlex.split(line[2:] if negate else line))
        if argv is None:
            return False, "refused: not an allowed assertion shape"
        p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
        if p.returncode > 1:
            return False, f"grep error: {p.stderr.strip()[:120]}"
        ok = (p.returncode == 0) != negate
        return ok, "" if ok else ("pattern present" if negate else "pattern not found")
    except (ValueError, subprocess.TimeoutExpired) as exc:
        return False, f"refused: {type(exc).__name__}"


def _line_count(path: str) -> int:
    if path not in _lines_cache:
        try:
            _lines_cache[path] = (ROOT / path).read_text(encoding="utf-8", errors="replace").count("\n") + 1
        except OSError:
            _lines_cache[path] = -1
    return _lines_cache[path]


def anchors(text: str) -> tuple[list[str], list[str]]:
    """(missing-file anchors, out-of-range anchors)."""
    missing, drift = [], []
    for m in ANCHOR_RE.finditer(text):
        path, start = m.group(1), int(m.group(2))
        end = int(m.group(3) or start)
        n = _line_count(path)
        if n < 0:
            missing.append(m.group(0))
        elif max(start, end) > n or start < 1:
            drift.append(m.group(0))
    return missing, drift


def check_page(page: Path, strict_anchors: bool = False) -> dict:
    text = page.read_text(encoding="utf-8", errors="replace")
    results = [(line, *run_line(line)) for line in verify_lines(text)]
    missing, drift = anchors(text)
    failed = [{"line": ln, "why": why} for ln, ok, why in results if not ok]
    fail_anchors = missing + (drift if strict_anchors else [])
    return {"page": page.relative_to(WIKI).as_posix(), "assertions": len(results), "failed": failed,
            "missing_anchors": missing, "drifted_anchors": drift,
            "ok": not failed and not fail_anchors, "invariants": len(re.findall(r"^\s*INVARIANT\s*:", text, re.MULTILINE))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pages", nargs="*", help="pages to check (default: all of docs/codewiki)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict-anchors", action="store_true", help="an out-of-range anchor fails too")
    args = ap.parse_args()
    pages = [Path(p).resolve() for p in args.pages] or sorted(WIKI.rglob("*.md"))
    reports = [check_page(p, args.strict_anchors) for p in pages]
    total = sum(r["assertions"] for r in reports)
    failed = sum(len(r["failed"]) for r in reports)
    missing = sum(len(r["missing_anchors"]) for r in reports)
    drift = sum(len(r["drifted_anchors"]) for r in reports)
    bad = [r for r in reports if not r["ok"]]
    summary = {"pages": len(reports), "assertions": total, "failed": failed, "missing_anchors": missing,
               "drifted_anchors": drift, "failing_pages": len(bad)}
    if args.json:
        print(json.dumps({"summary": summary, "pages": reports}, indent=1))
    else:
        for r in bad:
            for f in r["failed"]:
                print(f"  FAIL {r['page']}: {f['line']}  ({f['why']})")
            for a in r["missing_anchors"]:
                print(f"  MISSING FILE {r['page']}: {a}")
            if args.strict_anchors:
                for a in r["drifted_anchors"]:
                    print(f"  ANCHOR OUT OF RANGE {r['page']}: {a}")
        print(f"{total - failed}/{total} assertions passed on {len(reports)} pages; {missing} anchors name a missing file; "
              f"{drift} anchors past the end of their file (stale, run scripts/codewiki/pages.py refresh)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
