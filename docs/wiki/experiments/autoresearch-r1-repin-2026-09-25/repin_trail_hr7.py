"""Re-pin polymath-v4's embedded Trail core to a Trail commit through the EXISTING deterministic process recorded in PROVENANCE.json:
`git archive <commit> <pinned paths> | tar -x` — tracked files only, no edits; PROVENANCE.json rewritten with the new hashes.
Run from the polymath-v4 worktree root. usage: repin_trail.py <trail_worktree> <trail_commit_sha>"""
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path.cwd()
TRAIL_WT, SHA = Path(sys.argv[1]), sys.argv[2]
DEST = ROOT / "governance" / "trail"
prov_path = DEST / "PROVENANCE.json"
prov = json.loads(prov_path.read_text(encoding="utf-8"))
paths = sorted(prov["files"])
full = subprocess.run(["git", "rev-parse", SHA], cwd=TRAIL_WT, capture_output=True, text=True, check=True).stdout.strip()
short = full[:7]
# byte-exact extraction of exactly the pinned tracked files at the commit
archive = subprocess.run(["git", "archive", full, *paths], cwd=TRAIL_WT, capture_output=True, check=True).stdout
subprocess.run(["tar", "-x", "-C", str(DEST)], input=archive, check=True)
files = {p: hashlib.sha256((DEST / p).read_bytes()).hexdigest() for p in paths}
# the hashes must equal the commit's blobs (never a working-tree edit)
for p in paths:
    blob = subprocess.run(["git", "show", f"{full}:{p}"], cwd=TRAIL_WT, capture_output=True, check=True).stdout
    assert hashlib.sha256(blob).hexdigest() == files[p], p
changed = [p for p in paths if files[p] != prov["files"][p]]
prov.update({"source_repository": f"TrailSignal OS (trail-signal-os), worktree {TRAIL_WT.name} (branch agent/HR7, HR7 admitted under ADR-070)",
             "source_commit": short, "source_commit_full": full, "imported_at": date.today().isoformat(),
             "method": f"git archive {short} <paths> | tar -x — tracked files only, no edits",
             "previous_pin": {"source_commit": prov.get("source_commit"), "files_changed_by_this_pin": changed}, "files": files})
prov_path.write_text(json.dumps(prov, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("pinned", short, "| files changed by the re-pin:", len(changed)); print("\n".join(changed))
