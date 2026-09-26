#!/usr/bin/env bash
# FRIENDS-ACCESS-V1 F6 — the owner's ONE Run button: friends get their own sign-in on rag.kingsleylab.xyz.
#   1 merge feat/friends-access into production (fast-forward only)
#   2 the web session secret in .env (generated once, never printed)
#   3 build the web UI
#   4 restart the fleet (waits until READY)
#   5 King's password (asked at a hidden prompt; skipped when already set)
#   6 Caddy: drop the shared basic-auth, strip any principal header a browser sends; restart the Caddy service
# Safe to re-run: the merge, secret, password and Caddy steps say when they are already done (the build and restart run again).
# Stops at the first failure (nothing later runs).
set -euo pipefail
ROOT=/Users/king/Documents/polymath-rebuild/polymath-v4
CADDYFILE="${CADDYFILE:-$HOME/.hermes/rag-proxy/Caddyfile}"
CADDY_LABEL=com.hermes.rag-caddy
PY="$ROOT/.venv/bin/python"
cd "$ROOT"
# the accounts file the orchestrator reads (from .env), so King's password lands where the server looks
REG="$(grep -m1 '^POLYMATH_MCP_PRINCIPALS_FILE=' .env | cut -d= -f2- || true)"
REG="${REG:-$HOME/PolymathRuntime/polymath-v4-mcp-principals.json}"
say() { printf '\n== %s\n' "$*"; }

say "1/6 merge feat/friends-access into production"
[ "$(git branch --show-current)" = production ] || { echo "the main checkout is not on production: stopping"; exit 2; }
git merge --ff-only feat/friends-access

say "2/6 the web session secret"
if grep -q '^POLYMATH_WEB_SESSION_SECRET=.\{32,\}' .env; then
  echo "already set"
else
  printf '\nPOLYMATH_WEB_SESSION_SECRET=%s\n' "$("$PY" -c 'import secrets; print(secrets.token_urlsafe(48))')" >> .env
  echo "added to .env (not shown)"
fi

say "3/6 build the web UI"
(cd frontend-v2 && npm run build >/dev/null) && echo "built"

say "4/6 restart the fleet"
bash scripts/bounce_fleet.sh

say "5/6 King's password"
if "$PY" scripts/web_accounts.py --file "$REG" list | grep '"owner_login": "set"' >/dev/null; then
  echo "already set"
elif [ -t 0 ]; then
  "$PY" scripts/web_accounts.py --file "$REG" set-owner-password
else
  echo "not set, and there is no terminal to ask in. Run this, then run this script again:"
  echo "  cd $ROOT && .venv/bin/python scripts/web_accounts.py --file $REG set-owner-password"
  exit 3
fi

say "6/6 Caddy"
out="$("$PY" scripts/friends_access_caddy.py --caddyfile "$CADDYFILE" --apply)"
echo "$out"
case "$out" in
  changed:*) launchctl kickstart -k "gui/$(id -u)/$CADDY_LABEL" && echo "Caddy restarted" ;;
esac

say "done. Check it:  cd $ROOT && .venv/bin/python docs/wiki/experiments/friends-access-2026-09-26/live_check.py"
