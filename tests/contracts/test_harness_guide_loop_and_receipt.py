"""TRAIL-EXT-BUGHUNT-V1 batch C (2026-09-26): the operating guide says what the runtime really returns and accepts.
  * B-47: `adapter_next` answers `{kind: "status", status: AdapterRunStatusV1}`, an OBJECT; the run state is `status.status`. The
    guide showed `status: "running"`, so a harness written from it compared a dict with a string and misrouted its loop.
  * B-46: a receipt holds at most 100 sources and 50 limitations. The guide said to copy each read's `sources` and keep its
    `limitations`; five TikTok reads then give 105 sources and the receipt is refused. It now says to copy only the sources the
    observations cite, within `budget.max_sources` and the receipt's limits, and to merge repeated limitation lines.
The limits and the terminal states are read from the contract and the runtime, so the guide cannot drift from them unnoticed.
"""
import pathlib
import re
import sys
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.acquisition import service as S
from polymath_shared.adapter import contracts as C
from polymath_shared.adapter import harness_guide as HG
from polymath_shared.adapter import service as SVC

RECEIPT = C.schema("harness_receipt")
LIMITS = {k: RECEIPT["properties"][k]["maxItems"] for k in ("sources", "limitations", "observations")}


def test_the_code_under_test_is_this_checkout():
    for mod in (S, C, HG, SVC):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


def test_the_loop_reads_the_run_state_where_the_runtime_puts_it(monkeypatch):
    view = {"run_id": "adr_x", "status": "running", "current_step_id": "K_retrieve"}
    monkeypatch.setattr(SVC, "status", lambda conn, run_id, directory=None: view)
    reply = SVC.next_step(None, "adr_x")
    assert reply == {"kind": "status", "status": view}                     # an AdapterRunStatusV1 object, never a bare string
    loop = HG.GUIDE[HG.GUIDE.index("## 2. The loop"):HG.GUIDE.index("## 3.")]
    assert '`{kind: "status", status: "running"}`' not in loop and "`status.status`" in loop, loop
    assert reply["status"]["status"] == "running"                          # what the guide tells a harness to read
    named = set(re.findall(r"`([a-z_]+)`", loop[loop.index("terminal"):]))
    assert C.TERMINAL_RUN_STATUSES <= named, (sorted(C.TERMINAL_RUN_STATUSES), loop)


def test_the_guide_states_the_receipts_limits_and_what_to_copy():
    research = HG.GUIDE[HG.GUIDE.index("## 4."):HG.GUIDE.index("## 5.")]
    for name, n in LIMITS.items():
        assert f"{n} {name}" in research, (name, n)
    assert "your observations cite" in research and "`budget.max_sources`" in research and "merge repeated" in research.lower()


def test_five_reads_merged_as_the_guide_says_make_a_valid_receipt():
    """Five TikTok reads (a caption and 20 dated comments each): copied whole they give 105 sources (over the limit of 100); the receipt the
    guide now asks for cites only the sources its observations use and keeps each limitation line once."""
    run, t = "adr_" + "c0" * 16, S.resolve("comments", "https://www.tiktok.com/@creator/video/7400000000000000001")
    step = {"action_id": "hact_" + "e" * 24, "run_id": run, "budget": {"max_queries": 24, "max_sources": 20}, "search_intents": [{"intent_id": "si_x"}]}
    reads = []
    for v in range(5):
        base = datetime(2024, 6, 10, tzinfo=UTC).timestamp() + v * 100000
        raw = {"state": "ok", "page_url": t.url.replace("0001", f"000{v}"), "retrieved_at": "2026-09-26T10:00:00Z", "total": 400, "complete": False,
               "records": [{"kind": "caption", "ref": "caption", "text": "rain again", "precision": "exact", "published_at": "2024-06-01T00:00:00Z"}]
               + [{"kind": "comment", "ref": f"c{v}{i}", "text": f"the lens fogs, case {v}.{i}", "precision": "exact",
                   "published_at": datetime.fromtimestamp(base + i * 61, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")} for i in range(20)]}
        reads.append(S.shape(t, raw, action=step, search_intent_id="si_x", retrieved_at="2026-09-26T10:00:00Z", used=v + 1, cap=24, limit=20))
    everything = {s["source_id"]: s for r in reads for s in r["sources"]}
    assert len(everything) > LIMITS["sources"]                                            # the old instruction overflows
    cited = [i for r in reads for i in r["items"][:4] if i["source_id"]]                  # the observations the harness chose to write
    receipt = {"action_id": step["action_id"], "run_id": run, "harness_id": "any/1", "started_at": "2026-09-26T10:00:00Z",
               "completed_at": "2026-09-26T11:00:00Z",
               "sources": list({i["source_id"]: everything[i["source_id"]] for i in cited}.values()),
               "observations": [{"observation_id": f"o{n}", "source_id": i["source_id"], "claim": "the lens fogs in the rain",
                                 "paraphrase_or_excerpt": i["excerpt"], "metric_if_present": None, "context": "moment: during",
                                 "evidence_role_claimed": "friction", "hypothesis_ids": ["hyp_" + "a" * 12]} for n, i in enumerate(cited)],
               "tool_trace": [r["tool_trace"] for r in reads], "limitations": list(dict.fromkeys(x for r in reads for x in r["limitations"]))}
    assert C.validate("harness_receipt", receipt) == []
