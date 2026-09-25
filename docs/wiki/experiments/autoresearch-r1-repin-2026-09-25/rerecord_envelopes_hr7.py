"""Re-record tests/fixtures/trail_recorded_envelopes at the HR7 pin (ADR-070: two short-video comment source rows).

The repository owner AUTHORIZED this re-record on 2026-09-25 ("Yes, re-record": only the snapshot id and the new source rows
change; the recorded defects stay identical). So:
  * the REQUESTS change only where they carry the registry snapshot (its id and content hash -> the new snapshot's);
  * the responses are re-recorded from the embedded core at the SAME fixed clock;
  * a recorded ERROR (finding M1-02) must still be the same error, with the same message;
  * `hypotheses.judge` (findings M1-01 / M1-03: the challenge path, merge + weaken on one duplicate) must be IDENTICAL once the
    snapshot id / hash are normalised — the defects did not move. Other operations may differ beyond the snapshot only in what the
    new rows route (their kinds are recorded).
Run from the polymath-v4 worktree root AFTER the re-pin, with polymath's .venv python.
usage: rerecord_envelopes_hr7.py <new_trail_sha7> <previous_trail_sha7>"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "governance" / "trail"))
import embedded as E  # noqa: E402

SHA, PREVIOUS = sys.argv[1], sys.argv[2]
FIXTURES = ROOT / "tests" / "fixtures" / "trail_recorded_envelopes"
NOW = datetime(2026, 9, 15, 2, 0, tzinfo=timezone.utc)
ORDER = ("registry.project", "gaps.compile", "evidence.admit", "hypotheses.judge", "territory.project", "opportunity.qualify", "opportunity.score")
MUST_NOT_MOVE = ("hypotheses.judge",)
snap = E.compile_registry_snapshot(E.ROOT / "data", E.ROOT / "config", E.ROOT / "data" / "source_capabilities.csv", compiled_at=NOW)
NEW_ID, NEW_HASH = snap.snapshot_id, snap.content_hash


def _norm(obj, id_, hash_) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False).replace(hash_, "<SNAPSHOT_HASH>").replace(id_, "<SNAPSHOT_ID>")


def _swap(obj, old_id, old_hash):
    return json.loads(json.dumps(obj, ensure_ascii=False).replace(old_hash, NEW_HASH).replace(old_id, NEW_ID))


report = {}
for path in sorted(FIXTURES.glob("*.json")):
    raw = path.read_text(encoding="utf-8")
    rec = json.loads(raw)
    olds = sorted(set(re.findall(r"trs-[0-9a-f]{16}", raw)))
    assert len(olds) == 1, (path.name, olds)
    old_id = olds[0]
    hashes = sorted(set(re.findall(r"sha256:" + old_id[4:] + r"[0-9a-f]{48}", raw)))
    assert len(hashes) == 1, (path.name, hashes)
    old_hash = hashes[0]
    requests_before = _norm(rec["requests"], old_id, old_hash)
    rec["requests"] = _swap(rec["requests"], old_id, old_hash)
    assert _norm(rec["requests"], NEW_ID, NEW_HASH) == requests_before, "a request changed beyond the snapshot id / hash"
    service = E.build_service(clock=lambda: NOW)
    beyond_snapshot = []
    for kind in ORDER:
        if kind not in rec["requests"]:
            continue
        if rec["responses"].get(kind) is None:              # the recorded ERROR (M1-02) must still be the same error
            try:
                E.operate(service, kind, rec["requests"][kind])
            except Exception as exc:  # noqa: BLE001
                assert type(exc).__name__ == rec["judge_error"]["type"], (path.name, kind, type(exc).__name__)
                assert "admitted_evidence must carry exactly the admitted_evidence_ids" in str(exc), (path.name, kind, str(exc)[:200])
                continue
            raise AssertionError(f"{path.name}: {kind} no longer raises {rec['judge_error']['type']}")
        new = E.operate(service, kind, rec["requests"][kind])
        if _norm(new, NEW_ID, NEW_HASH) != _norm(rec["responses"][kind], old_id, old_hash):
            assert kind not in MUST_NOT_MOVE, f"{path.name}: {kind} moved beyond the snapshot id — a recorded defect changed"
            beyond_snapshot.append(kind)
        rec["responses"][kind] = new
    assert rec["trail_head"].startswith(PREVIOUS), (path.name, rec["trail_head"])
    rec["previous_trail_head"], rec["trail_head"] = rec["trail_head"], SHA
    rec["re_recorded"] = {"at_trail_head": SHA, "snapshot": {"from": old_id, "to": NEW_ID},
                          "responses_changed_beyond_the_snapshot_id": beyond_snapshot,
                          "note": ("HR7 re-pin (ADR-070: two short-video comment source rows). Authorized by the repository owner 2026-09-25: "
                                   "only the snapshot id / hash in the requests and what the new rows route change; the recorded defects "
                                   "(M1-01 challenge path, M1-02 error, M1-03 merge + weaken) are asserted unchanged.")}
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    report[path.name] = beyond_snapshot
print(json.dumps({"new_snapshot": NEW_ID, "changed_beyond_snapshot": report}, indent=1))
