#!/bin/sh
# Polymath pre-commit — deterministic contract-impact + changed-scope static security (no LLM).
#
# Install with `make hooks` (copies this to .git/hooks/pre-commit). It prints the change
# blast-radius (advisory) and blocks ONLY an out-of-scope DEFERRED-contract change. Any tooling
# hiccup (missing venv/deps) degrades to a warning — it never blocks a commit. Static security
# (ruff bandit S rules) on staged Python is advisory here; CI gates it. See AGENTS.md 5.3.
# Override the interpreter with POLYMATH_PY when there is no local .venv (e.g. in a worktree).
set -e
ROOT="$(git rev-parse --show-toplevel)"
PY="${POLYMATH_PY:-.venv/bin/python}"
if [ -x "$ROOT/$PY" ]; then PY="$ROOT/$PY"; elif [ -x "$PY" ]; then :; else PY=python3; fi

# 1. Contract impact: exit 3 = out-of-scope DEFERRED touch (block); other non-zero = tool problem
#    (warn, do not block); 0 = clean.
if "$PY" "$ROOT/scripts/contract_impact.py" --check --staged; then rc=0; else rc=$?; fi
if [ "$rc" = "3" ]; then
  echo "pre-commit BLOCKED: out-of-scope (deferred) contract changed — see above." >&2
  exit 1
elif [ "$rc" != "0" ]; then
  echo "pre-commit: contract_impact unavailable (rc=$rc) — skipping impact check (set POLYMATH_PY)." >&2
fi

# 2. Changed-scope static security (advisory): ruff bandit S rules on staged Python files.
FILES=$(git diff --cached --name-only --diff-filter=ACM -- '*.py')
if [ -n "$FILES" ]; then
  "$PY" -m ruff check --select S --ignore S101,S404,S603,S607 --quiet $FILES \
    || echo "pre-commit: ruff security (S) findings above — review before pushing (advisory)." >&2
fi
exit 0
