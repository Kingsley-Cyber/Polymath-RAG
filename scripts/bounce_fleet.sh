#!/bin/bash
# One-supervisor fleet bounce (restart) for the LIVE fleet checkout — the owner runs it with one click.
# TERM the supervisor -> wait for 0 processes + 0 listeners -> boot -> wait for /ready + the expected healthy fleet on ONE bundle.
# Always boots from the fleet checkout (POLYMATH_FLEET_ROOT), never from the worktree the script was copied into.
# Exit: 0 READY · 1 the old fleet would not stop · 2 not ready within 6 minutes · 3 another bounce is already running.
set -u
ROOT="${POLYMATH_FLEET_ROOT:-/Users/king/Documents/polymath-rebuild/polymath-v4}"
EXPECT_WORKERS="${POLYMATH_EXPECT_WORKERS:-24}"
EXPECT_TYPES="${POLYMATH_EXPECT_TYPES:-13}"
cd "$ROOT" || { echo "fleet checkout not found: $ROOT"; exit 1; }
# One bounce at a time: a second click while one runs would find the fleet already stopped and boot a second copy.
mkdir -p /private/tmp/polymath_fleet
LOCK=/private/tmp/polymath_fleet/bounce.lock
if [ -d "$LOCK" ] && [ -n "$(find "$LOCK" -maxdepth 0 -mmin +10 2>/dev/null)" ]; then
  rmdir "$LOCK" 2>/dev/null        # a restart takes ~1 minute; a lock older than 10 minutes is left over from a killed run
fi
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "A restart is already running (started $(stat -f '%Sm' "$LOCK")). Wait for it to print READY; do not run it twice."
  exit 3
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
count() { ps -axo pid,command | grep -E "control\.process_supervisor|workers\.|uvicorn orchestrator" | grep -vE "grep|zsh -c|bash -c|bounce" | wc -l | tr -d ' '; }
listeners() { lsof -nP -iTCP:7200 -iTCP:8742 -iTCP:8743 -iTCP:8930 -sTCP:LISTEN 2>/dev/null | tail -n +2 | wc -l | tr -d ' '; }
echo "before: $(count) processes, $(listeners) listeners"
pgrep -f "control\.process_supervisor" | xargs kill -TERM 2>/dev/null
i=0
while [ $i -lt 90 ]; do
  [ "$(count)" = "0" ] && [ "$(listeners)" = "0" ] && break
  sleep 2; i=$((i+1))
done
echo "after TERM (~$((i*2))s): $(count) processes, $(listeners) listeners"
if [ "$(count)" != "0" ] || [ "$(listeners)" != "0" ]; then
  echo "ABORT: still alive"
  ps -axo pid,command | grep -E "control\.process_supervisor|workers\.|uvicorn orchestrator" | grep -vE "grep|zsh -c|bash -c|bounce" | cut -c1-120
  lsof -nP -iTCP:7200 -iTCP:8742 -iTCP:8743 -iTCP:8930 -sTCP:LISTEN 2>/dev/null
  exit 1
fi
nohup bash scripts/boot_polymath.sh > /private/tmp/polymath_fleet/boot.log 2>&1 &
disown
set -a; . ./.env; set +a
r=""; s=""
for i in $(seq 1 72); do
  sleep 5
  r=$(curl -s -m 3 127.0.0.1:7200/ready || true)
  s=$(.venv/bin/python -c "
import os,psycopg
c=psycopg.connect(os.environ['POLYMATH_PG_DSN']).cursor()
c.execute(\"select count(*),count(distinct worker_type),count(distinct left(execution_bundle_hash,12)) from worker_registrations where heartbeat_at>now()-interval '60 seconds' and status='healthy'\")
print(*c.fetchone())" 2>/dev/null)
  set -- $s
  if echo "$r" | grep -q '"ready":true' && [ "${1:-0}" = "$EXPECT_WORKERS" ] && [ "${2:-0}" = "$EXPECT_TYPES" ] && [ "${3:-0}" = "1" ]; then
    echo "READY after ~$((i*5))s: $r | healthy=$1 types=$2 bundles=$3"
    exit 0
  fi
done
echo "NOT READY after 360s: ready=$r | healthy/types/bundles=$s"
tail -25 /private/tmp/polymath_fleet/boot.log
exit 2
