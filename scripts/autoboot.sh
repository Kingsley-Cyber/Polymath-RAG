#!/usr/bin/env bash
# AUTOBOOT — make the Polymath fleet start at login via launchd (com.polymath.v5),
# and PROVE it can. Idempotent; safe to re-run.
#
#   scripts/autoboot.sh            # probe → fix what can be fixed → kickstart → verify
#
# The one thing this script cannot do is grant macOS Full Disk Access: launchd-
# spawned processes are denied ~/Documents (TCC) and the checkout lives there.
# When the probe says BLOCKED it opens the exact System Settings pane and prints
# the three clicks; re-run afterwards and it finishes the job.
set -uo pipefail
LABEL="com.polymath.v5"
REPO="/Users/king/Documents/polymath-rebuild/polymath-v4"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
UID_="$(id -u)"

probe() {
  local p=/tmp/com.polymath.tccprobe.plist out=/tmp/polymath_tcc_probe.out
  rm -f "$out"
  cat > "$p" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.polymath.tccprobe</string>
<key>ProgramArguments</key><array><string>/bin/bash</string><string>-c</string>
<string>if head -c 1 ${REPO}/scripts/boot_polymath.sh >/dev/null 2>&1; then echo CAN_READ; else echo CANNOT_READ; fi > ${out} 2>&1</string></array>
<key>RunAtLoad</key><true/></dict></plist>
PL
  launchctl bootout "gui/${UID_}/com.polymath.tccprobe" 2>/dev/null
  launchctl bootstrap "gui/${UID_}" "$p" && sleep 2
  launchctl bootout "gui/${UID_}/com.polymath.tccprobe" 2>/dev/null; rm -f "$p"
  cat "$out" 2>/dev/null || echo NO_OUTPUT
}

echo "autoboot: probing whether a launchd-spawned bash can read the checkout…"
R="$(probe)"
if [ "$R" != "CAN_READ" ]; then
  echo "autoboot: BLOCKED — launchd bash cannot read ${REPO} (macOS TCC: $R)."
  echo "autoboot: opening System Settings → Privacy & Security → Full Disk Access."
  open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles" 2>/dev/null || true
  cat <<'MSG'
autoboot: do these three clicks, then re-run scripts/autoboot.sh:
  1. Click "+" under Full Disk Access.
  2. Press Cmd+Shift+G, type  /bin/bash  and press Return, then click Open.
  3. Make sure the new "bash" row's switch is ON (unlock with Touch ID if asked).
autoboot: alternative that needs no grant: move the checkout out of ~/Documents
  (e.g. ~/polymath-v4) — ask the executor to relocate it; it also rewrites this
  launcher's REPO path.
MSG
  exit 78
fi

echo "autoboot: TCC OK — launchd bash can read the checkout."
[ -r "$PLIST" ] || { echo "autoboot: FATAL — $PLIST missing"; exit 1; }
launchctl enable "gui/${UID_}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/${UID_}" "$PLIST" 2>/dev/null || true
if pgrep -f "control.process_supervisor" >/dev/null 2>&1; then
  echo "autoboot: a supervisor is already running (manual launch). launchd will own the fleet after"
  echo "autoboot: the next login/reboot; to hand over NOW: pkill -TERM -f control.process_supervisor && sleep 3 && launchctl kickstart -k gui/${UID_}/${LABEL}"
else
  launchctl kickstart -k "gui/${UID_}/${LABEL}"
  echo "autoboot: kickstarted ${LABEL}; waiting for the supervisor…"
  for _ in $(seq 1 30); do pgrep -f "control.process_supervisor" >/dev/null 2>&1 && break; sleep 2; done
fi
echo "autoboot: launchd job: $(launchctl print gui/${UID_}/${LABEL} 2>/dev/null | grep -E 'state =' | head -1 | tr -s ' ')"
echo "autoboot: supervisor: $(pgrep -f control.process_supervisor | head -1 || echo NOT RUNNING) | boot log: /tmp/polymath_boot.log"
