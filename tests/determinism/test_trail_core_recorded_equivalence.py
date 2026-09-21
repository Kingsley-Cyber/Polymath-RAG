"""Consolidation migration Phase 6, validation 3 — EQUIVALENCE by replay. The request / response envelopes under
`tests/fixtures/trail_recorded_envelopes/` were recorded from TrailSignal's OWN checkout (A41 @ de64d84, in-process service, fixed clock) during
the external-review M1 reproductions. Replayed through the EMBEDDED copy with the same clock they must produce the SAME envelopes — including the
recorded refusal. (The machine-local `trail_root` was removed from the fixtures on import; nothing else was changed.)

Needs `packageurl`: run with TrailSignal's interpreter until it is added to this repo's environment (see test_trail_core_embedded.py).
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

import pytest

pytest.importorskip("packageurl", reason="TrailSignal's platform contracts need `packageurl`; add it in the merge window (ADR-TRAIL-EMBEDDING) or run with TrailSignal's interpreter")

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "governance" / "trail"))
import embedded as E  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "trail_recorded_envelopes"
NOW = datetime(2026, 9, 15, 2, 0, tzinfo=timezone.utc)          # the instant the recordings pinned
ORDER = ("registry.project", "gaps.compile", "evidence.admit", "hypotheses.judge", "territory.project", "opportunity.qualify", "opportunity.score")


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("*.json")))
def test_the_embedded_core_reproduces_the_recorded_envelopes(name):
    rec = json.loads((FIXTURES / name).read_text())
    assert rec["trail_head"].startswith("de64d84")
    service = E.build_service(clock=lambda: NOW)
    replayed = 0
    for kind in ORDER:
        if kind not in rec["requests"]:
            continue
        if rec["responses"].get(kind) is not None:
            assert E.operate(service, kind, rec["requests"][kind]) == rec["responses"][kind], f"{name}: {kind} differs from the recording"
            replayed += 1
        else:                                                   # a null response = the recording holds the ERROR TrailSignal raised for this request (finding M1-02);
            with pytest.raises(Exception) as exc:               # the embedded copy must reproduce the DEFECT too — byte-identical code, identical behaviour
                E.operate(service, kind, rec["requests"][kind])
            assert type(exc.value).__name__ == rec["judge_error"]["type"]
            assert "admitted_evidence must carry exactly the admitted_evidence_ids" in str(exc.value) and "admitted_evidence must carry exactly the admitted_evidence_ids" in rec["judge_error"]["message"]
            replayed += 1
    assert replayed == len(rec["requests"])
