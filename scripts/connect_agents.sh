#!/usr/bin/env bash
# CONNECT-AGENTS (ONE-PROFILE, the owner 2026-09-28: "copy and paste should work without creating a api, logging in should be
# good enough"). Connects this Mac's Claude Code and Codex to Polymath's MCP server with the owner's key, which it reads from the
# server's .env on this Mac. The key is never printed and goes nowhere but the two agents' own config files:
#   Claude Code: `claude mcp add -s user` (every project sees it);
#   Codex: ~/.codex/config.toml, the key as a fixed `http_headers` entry (the Codex app never sees a shell's exports, which is
#   why the old `bearer_token_env_var` setup showed "blocked").
# Safe to run again: the old "polymath" entry is replaced. It asks the server first whether the key is accepted.
# Exit: 0 connected · 1 nothing to connect (no key in .env, or neither agent installed) · 2 the server refused the key ·
#       3 a Codex config it could not safely edit · 4 an agent refused the new entry.
# Overrides (tests): POLYMATH_ENV_FILE, POLYMATH_CONNECT_URL, CODEX_HOME.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${POLYMATH_ENV_FILE:-$ROOT/.env}"
URL="${POLYMATH_CONNECT_URL:-http://127.0.0.1:8930/mcp}"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
CODEX_CONFIG="$CODEX_DIR/config.toml"

say() { printf '%s\n' "$*"; }

if [ ! -f "$ENV_FILE" ]; then
  say "No Polymath settings file at $ENV_FILE."
  exit 1
fi
KEY="$(grep -E '^[[:space:]]*(export[[:space:]]+)?POLYMATH_MCP_API_KEY=' "$ENV_FILE" | tail -n 1 \
  | sed -E "s/^[^=]*=//; s/^[[:space:]]+//; s/[[:space:]]+\$//; s/^\"(.*)\"\$/\\1/; s/^'(.*)'\$/\\1/")"
if [ -z "$KEY" ]; then
  say "Polymath has no POLYMATH_MCP_API_KEY in $ENV_FILE: add one, restart Polymath, then run this again."
  exit 1
fi
case "$KEY" in
  *[!A-Za-z0-9._~+/=-]*)
    say "POLYMATH_MCP_API_KEY holds characters this script will not write into a config file."
    exit 1 ;;
esac

HAVE_CLAUDE=0; command -v claude >/dev/null 2>&1 && HAVE_CLAUDE=1
HAVE_CODEX=0; command -v codex >/dev/null 2>&1 && HAVE_CODEX=1
if [ "$HAVE_CLAUDE" = 0 ] && [ "$HAVE_CODEX" = 0 ]; then
  say "Neither Claude Code (claude) nor Codex (codex) is installed on this Mac."
  exit 1
fi

# 1. Does Polymath accept the key? `initialize` is the first call every agent makes. The header goes through a file descriptor,
#    so the key is not in curl's command line.
INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"connect_agents","version":"1"}}}'
CODE="$(curl -s -o /dev/null -w '%{http_code}' -m 15 -X POST "$URL" \
  -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' \
  -H @<(printf 'Authorization: Bearer %s\n' "$KEY") -d "$INIT" 2>/dev/null)"
case "$CODE" in
  200) say "Polymath accepted the key at $URL." ;;
  401|403)
    say "Polymath refused the key at $URL (HTTP $CODE): check POLYMATH_MCP_API_KEY in $ENV_FILE. Nothing was changed."
    exit 2 ;;
  000|"") say "Polymath is not answering at $URL (is it running?). Connecting anyway: the agents reach it once it is up." ;;
  *) say "Polymath answered HTTP $CODE at $URL. Connecting anyway." ;;
esac

STATUS=0

# 2. Claude Code: user scope, the old entry replaced. Its output is dropped (it would echo the header).
if [ "$HAVE_CLAUDE" = 1 ]; then
  claude mcp remove polymath -s user >/dev/null 2>&1 || true
  if claude mcp add -s user -t http polymath "$URL" -H "Authorization: Bearer $KEY" >/dev/null 2>&1; then
    say "Claude Code: connected (every project)."
  else
    say "Claude Code: it refused the new entry (see: claude mcp list)."
    STATUS=4
  fi
else
  say "Claude Code: not installed, skipped."
fi

# 3. Codex: remove the old entry with Codex itself, then append the new section; never append a second [mcp_servers.polymath].
if [ "$HAVE_CODEX" = 1 ]; then
  codex mcp remove polymath >/dev/null 2>&1 || true
  mkdir -p "$CODEX_DIR"
  touch "$CODEX_CONFIG"
  if grep -Eq '^[[:space:]]*\[mcp_servers\.("polymath"|polymath)(\.[^]]*)?\]' "$CODEX_CONFIG"; then
    say "Codex: $CODEX_CONFIG still has a [mcp_servers.polymath] section; delete it by hand, then run this again."
    exit 3
  fi
  printf '\n[mcp_servers.polymath]\nurl = "%s"\nhttp_headers = { Authorization = "Bearer %s" }\n' "$URL" "$KEY" >> "$CODEX_CONFIG"
  chmod 600 "$CODEX_CONFIG"
  say "Codex: connected ($CODEX_CONFIG)."
else
  say "Codex: not installed, skipped."
fi

say ""
say "Done. Restart Claude Code and Codex (in Claude Code, /mcp shows polymath connected),"
say "then paste the prompt from Polymath's Settings into the agent."
exit "$STATUS"
