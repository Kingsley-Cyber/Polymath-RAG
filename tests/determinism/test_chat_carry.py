"""CARRY-V2 (CHAT-QUERY-COMPILER-PLAN §3.5, P0.e): used-only carry, hydrated,
reranked against the resolved request, admission floor, cap 8, carried items
in the legend. Live test replays the 3-turn probe against the orchestrator
(skips when unreachable)."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from orchestrator.api import ui  # noqa: E402


class _C:
    def __init__(self, locator, preview="", chunk_id=None):
        self.locator, self.preview, self.chunk_id = locator, preview, chunk_id


def _row(cid, text="some evidence text about the topic", doc="doc1"):
    return {"chunk_id": cid, "doc_id": doc, "text": text, "char_start": 0, "char_end": len(text), "heading_path": ["Ch 1", "Topic"]}


def test_candidates_normalise_dedupe_and_drop_freshly_retrieved():
    carry = [_C("chunk:c1@0:10", "p1"), {"locator": "chunk:c2@0:10", "preview": "p2"}, _C("chunk:c1@0:10", "dup"),
             _C("weird-locator"), _C("chunk:c3@5:9", chunk_id="c3"), _C("x", chunk_id="c4")]
    cands, acct = ui._carry_candidates(carry, exclude_ids={"c2"})
    assert [c["chunk_id"] for c in cands] == ["c1", "c3", "c4"]           # order kept, c1 once, c2 excluded, weird dropped
    assert acct == {"in": 6, "dropped_duplicate": 1, "dropped_already_retrieved": 1, "dropped_unparsed": 1}


def test_admission_hydrates_reranks_floors_and_caps_in_score_order():
    cands = [{"chunk_id": f"c{i}", "locator": f"chunk:c{i}@0:1", "preview": ""} for i in range(12)]
    rows = {f"c{i}": _row(f"c{i}") for i in range(12)}
    rows.pop("c11")                                                        # gone from the store
    scores = {f"c{i}": s for i, s in enumerate([0.9, 0.1, 0.8, 0.05, 0.7, 0.6, 0.5, 0.4, 0.3, 0.26, 0.24])}

    def scorer(q, texts):
        assert q == "how does making your own chroma keyer work in practice"
        return [scores[t.split("|")[0]] for t in texts]

    def resolve(cid):
        r = rows.get(cid)
        return dict(r, text=f"{cid}|" + r["text"]) if r else None

    items, acct = ui._admit_carry(cands, "how does making your own chroma keyer work in practice",
                                  resolve=resolve, scorer=scorer, resolve_document=lambda d: {"doc_id": d, "corpus_id": "cinema", "source_name": "Book"},
                                  floor=0.25, cap=8)
    assert acct["hydrated"] == 11 and acct["dropped_missing"] == 1
    assert acct["dropped_floor"] == 3                                      # 0.1, 0.05, 0.24
    assert acct["dropped_cap"] == 0 and acct["admitted"] == 8
    assert acct["admitted_ids"] == ["c0", "c2", "c4", "c5", "c6", "c7", "c8", "c9"]  # score order
    assert all(it["carried"] is True and it["lane"] == "carry" for it in items)
    assert items[0]["source_span"]["locator"].startswith("chunk:c0@") and items[0]["applicability"]["source_name"] == "Book"
    legend = ui._evidence_legend({"evidence_bundle": items})
    assert len(legend) == 8 and legend[0]["tag"] == "S1" and legend[0]["carried"] is True and legend[0]["carry_score"] == 0.9
    # cap applies after the floor
    _, acct2 = ui._admit_carry(cands[:10], "q", resolve=resolve, scorer=scorer, resolve_document=lambda d: None, floor=0.0, cap=3)
    assert acct2["admitted"] == 3 and acct2["dropped_cap"] == 7


def test_reranker_outage_degrades_to_cap_and_is_counted():
    cands = [{"chunk_id": f"c{i}", "locator": f"chunk:c{i}@0:1", "preview": ""} for i in range(10)]

    def scorer(q, texts):
        raise ConnectionError("sidecar down")

    items, acct = ui._admit_carry(cands, "q", resolve=lambda cid: _row(cid), scorer=scorer, resolve_document=lambda d: None, cap=8)
    assert acct["degraded"] == "carry_rerank_unavailable:ConnectionError"
    assert acct["admitted"] == 8 and acct["dropped_cap"] == 2 and acct["dropped_floor"] == 0
    assert acct["admitted_ids"] == [f"c{i}" for i in range(8)]            # newest-first order kept
    assert acct["scores"] == [None] * 8
    # nothing hydrated → nothing admitted, no scorer call
    items, acct = ui._admit_carry(cands[:2], "q", resolve=lambda cid: None, scorer=scorer, resolve_document=lambda d: None)
    assert items == [] and acct["dropped_missing"] == 2 and acct["degraded"] is None


def test_live_three_turn_probe_carries_used_only_and_drops_off_topic_turn_one():
    try:
        urllib.request.urlopen("http://127.0.0.1:7200/ready", timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"orchestrator not reachable: {exc}")
    base = ROOT / "docs" / "wiki" / "experiments" / "chat-carry-p0e-v1-baseline.json"
    baseline = json.loads(base.read_text())["summary"]["prompt_chars"] if base.exists() else None
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "chat_carry_probe.py"), "--policy", "v2", "--tag", "p0e-v2-test",
                           "--synthesizer", "deterministic-template-v3"], capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stderr[-800:]
    d = json.loads((ROOT / "docs" / "wiki" / "experiments" / "chat-carry-p0e-v2-test.json").read_text())
    s, turns = d["summary"], d["turns"]
    assert s["gate_no_leak"] is True, s
    assert all((t["carry"] or {}).get("admitted", 0) <= 8 for t in turns)
    assert s["carry_sent"][2] <= 8
    if baseline:
        # turn 1 carries nothing under either policy: its prompt differs only by the compiled
        # resolved-request wording (LLM compile, ±tens of chars); the carry-bearing turns must not grow
        # the deterministic synthesizer builds no LLM prompt, so prompt_chars is None there; the LLM
        # numbers are the probe receipts (chat-carry-p0e-v2.json) and this test then checks the carry law only
        for (a, b, sent) in zip(s["prompt_chars"], baseline, s["carry_sent"]):
            if a is not None and b is not None:
                assert a <= (b if sent else b * 1.02), (s["prompt_chars"], baseline)
    # backend law: every turn-3 candidate was either admitted, floor-dropped or already retrieved; nothing degraded
    t3 = turns[2]["carry"] or {}
    assert t3.get("degraded") is None
    assert t3.get("admitted", 0) + t3.get("dropped_floor", 0) + t3.get("dropped_cap", 0) + t3.get("dropped_missing", 0) == t3.get("candidates", 0)
    (ROOT / "docs" / "wiki" / "experiments" / "chat-carry-p0e-v2-test.json").unlink(missing_ok=True)
