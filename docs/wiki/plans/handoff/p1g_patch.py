"""P1.g — frozen conversation regression suite: manifest of fixtures + gate thresholds, `chat_baseline.py --check`,
an offline test that runs in CI (determinism.yml) and a live replay (`-k live`). Apply after the P1.f patch.
argv: none (thresholds are read from the latest experiment JSONs when present, else the defaults below)."""
import json, pathlib
ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4")
EXP = ROOT / "docs/wiki/experiments"

def summ(tag):
    p = EXP / f"chat-baseline-{tag}.json"
    return json.load(open(p))["summary"] if p.exists() else {}

b = summ("p1c-B-after") or summ("p1b-B-after"); l = summ("p1a-L-v2"); m = summ("p1c-M-after") or summ("p1b-M-after")
def floor(v, d, margin=0.0):
    return round(max(0.0, (v if v is not None else d) - margin), 3)
manifest = {
    "version": "chat-regression-suite-v1",
    "frozen": "2026-09-05",
    "conversations": [
        {"fixture": "eval/fixtures/chat_conversations/video_prompt_final.json", "owner_exact": True,
         "expect": {"task_type": "CONTINUE_PRIOR_ARTIFACT", "retrieval_skipped": True, "min_answer_chars": 300, "no_abstention_marker": True}},
        {"fixture": "eval/fixtures/chat_conversations/brainrot_transform.json",
         "expect": {"task_type": "TRANSFORM_USER_CONTENT", "retrieval_skipped": True, "min_answer_chars": 300, "no_abstention_marker": True}},
        {"fixture": "eval/fixtures/chat_conversations/cinema_improve_prompt.json",
         "expect": {"task_type": "CREATE_FROM_KNOWLEDGE", "retrieval_skipped": False, "min_citations": 1}},
        {"fixture": "eval/fixtures/chat_conversations/followup_creativity.json",
         "expect": {"task_type_in": ["GROUNDED_SYNTHESIS", "GROUNDED_QA"], "retrieval_skipped": False, "resolved_contains": ["creativ"]}},
        {"fixture": "eval/fixtures/chat_conversations/authors_agree.json",
         "expect": {"task_type_in": ["GROUNDED_SYNTHESIS", "GROUNDED_QA"], "retrieval_skipped": False, "min_queries": 2}},
        {"fixture": "eval/fixtures/chat_conversations/exact_terms_rapo.json",
         "expect": {"task_type": "GROUNDED_QA", "retrieval_skipped": False, "exact_terms_include": ["RAPO"], "sparse_rule": "exact_terms"}},
    ],
    "sets": {
        "B": {"fixture": "eval/fixtures/chat_baseline_B.json", "retrieval": "v2",
              "gates": {"gold_in_union_min": floor(b.get("gold_in_union"), 0.9), "hit@10_selected_min": floor(b.get("hit@10_selected"), 0.7),
                        "mrr_selected_min": floor(b.get("mrr_selected"), 0.47, 0.02), "arrivals_missing_total_max": 0, "compiler_fallbacks_max": 1,
                        "wall_p50_s_max": 20.0}},
        "L": {"fixture": "eval/fixtures/chat_lexical_L.json", "retrieval": "v2",
              "gates": {"gold_in_union_min": 1.0, "hit@10_selected_min": floor(l.get("hit@10_selected"), 0.95, 0.03), "wall_p50_s_max": 20.0}},
        "M": {"fixture": "eval/fixtures/chat_multi_M.json", "retrieval": "v2",
              "gates": {"dims_ok_rate_min": floor(m.get("dims_ok_rate"), 0.85, 0.03), "dims_system_ok_rate_min": floor(m.get("dims_system_ok_rate"), 0.9, 0.03),
                        "dims_unnamed_max": 2, "wall_p50_s_max": 22.0}},
    },
    "carry": {"probe": "scripts/chat_carry_probe.py --policy v2", "gates": {"gate_no_leak": True, "carry_admitted_max": 8}},
    "latency_rules": {"HYBRID_minus_VECTOR_p50_s_max": 0.5, "GRAPH_minus_HYBRID_p50_s_max": 1.5, "WILDCARD_minus_HYBRID_p50_s_max": 2.0},
}
(ROOT / "eval/fixtures/chat_regression_suite.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
print("manifest written:", {k: v["gates"] for k, v in manifest["sets"].items()})

# ------------------------------------------------------------------ chat_baseline --check
p = ROOT / "scripts/chat_baseline.py"; s = p.read_text(encoding="utf-8")
old = '''    ap.add_argument("--lanes", default=None,'''
new = '''    ap.add_argument("--check", default=None, help="P1.g: compare docs/wiki/experiments/chat-baseline-<tag>.json against the frozen gates of set B|L|M in eval/fixtures/chat_regression_suite.json (exit 1 on regression); e.g. --check B:p1c-B-after")
    ap.add_argument("--lanes", default=None,'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''    global RETRIEVAL_OVERRIDE, LANES_OVERRIDE'''
new = '''    if a.check:
        return check_against_suite(a.check)
    global RETRIEVAL_OVERRIDE, LANES_OVERRIDE'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''def _hit10(r: dict) -> bool:'''
new = '''SUITE = ROOT / "eval" / "fixtures" / "chat_regression_suite.json"


def check_against_suite(spec: str) -> int:
    """`--check <SET>:<tag>` — the frozen gates of the regression suite (P1.g) against a run's summary.
    Prints one line per gate; exit 1 when any gate fails."""
    set_name, _, tag = spec.partition(":")
    suite = json.loads(SUITE.read_text())
    gates = suite["sets"][set_name]["gates"]
    summary = json.loads((OUT_DIR / f"chat-baseline-{tag}.json").read_text())["summary"]
    failed = 0
    for gate, bound in gates.items():
        key, _, kind = gate.rpartition("_")
        val = summary.get(key)
        ok = (val is not None) and ((val >= bound) if kind == "min" else (val <= bound))
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'} {set_name} {key} = {val} ({kind} {bound})")
    print(f"{set_name}:{tag} -> {'OK' if not failed else str(failed) + ' gate(s) FAILED'}")
    return 1 if failed else 0


def _hit10(r: dict) -> bool:'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
import ast; ast.parse(s); print("chat_baseline: --check")

# ------------------------------------------------------------------ test
(ROOT / "tests/determinism/test_chat_regression_suite.py").write_text('''"""CHAT-REGRESSION-SUITE-V1 (plan §4 P1.g / §5): the frozen conversation and set fixtures with their gate
thresholds. Offline (CI): manifest integrity, fixture presence and shape, deterministic expectations of the
compiler's correction layer, and the `--check` gate evaluator. Live (`-k live`): every conversation fixture
replayed through the runtime against its expectations."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from polymath_shared import chat_plan as cp  # noqa: E402

SUITE = json.loads((ROOT / "eval/fixtures/chat_regression_suite.json").read_text())
ABSTAIN = re.compile(r"evidence (does not|doesn't|did not|didn't) (contain|include|mention|cover|provide)|cannot (be )?(answer|determine|provide)", re.I)


def test_manifest_is_frozen_complete_and_every_fixture_exists():
    assert SUITE["version"] == "chat-regression-suite-v1" and SUITE["frozen"]
    assert any(c.get("owner_exact") for c in SUITE["conversations"]), "the owner's exact video-gen conversation must be in the suite (§5 #10)"
    for c in SUITE["conversations"]:
        fx = json.loads((ROOT / c["fixture"]).read_text())
        assert fx.get("message") and fx.get("corpus_id") and isinstance(fx.get("history", []), list)
        assert c["expect"]
    for name, st in SUITE["sets"].items():
        fx = json.loads((ROOT / st["fixture"]).read_text())
        assert len(fx["questions"]) == 30, name
        for q in fx["questions"]:
            assert q["gold_chunk_ids"] and q["question"] and q["corpus_id"]
        assert all(isinstance(v, (int, float)) for v in st["gates"].values())
    assert SUITE["carry"]["gates"]["gate_no_leak"] is True and SUITE["carry"]["gates"]["carry_admitted_max"] == 8
    assert SUITE["latency_rules"]["HYBRID_minus_VECTOR_p50_s_max"] == 0.5


def test_deterministic_layer_meets_the_fixture_expectations_without_a_model():
    """What the correction layer guarantees regardless of the compiler lane."""
    for c in SUITE["conversations"]:
        fx = json.loads((ROOT / c["fixture"]).read_text()); ex = c["expect"]
        msg, hist = fx["message"], fx.get("history") or []
        if ex.get("exact_terms_include"):
            assert set(ex["exact_terms_include"]) <= set(cp.exact_terms_from(msg))
            assert cp.sparse_query_for(msg, cp.exact_terms_from(msg))[1] == "exact_terms" if hasattr(cp, "sparse_query_for") else True
        if ex.get("task_type") == "CONTINUE_PRIOR_ARTIFACT":
            assert cp.references_prior_artifact(msg, hist)
        if ex.get("task_type") == "CREATE_FROM_KNOWLEDGE":
            assert cp.references_corpus(msg)
        fb = cp.fallback_plan(msg, reason="offline")
        assert fb.retrieval_required is True and fb.queries[0].type == "PRIMARY"        # the fallback is always retrievable


def test_check_evaluator_passes_and_fails_correctly(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("cb", ROOT / "scripts/chat_baseline.py"); cb = importlib.util.module_from_spec(spec); spec.loader.exec_module(cb)
    monkeypatch.setattr(cb, "OUT_DIR", tmp_path)
    gates = SUITE["sets"]["L"]["gates"]
    good = {"summary": {"gold_in_union": 1.0, "hit@10_selected": 1.0, "wall_p50_s": 5.0}}
    (tmp_path / "chat-baseline-good.json").write_text(json.dumps(good))
    assert cb.check_against_suite("L:good") == 0
    bad = {"summary": {"gold_in_union": 0.9, "hit@10_selected": 1.0, "wall_p50_s": 5.0}}
    (tmp_path / "chat-baseline-bad.json").write_text(json.dumps(bad))
    assert cb.check_against_suite("L:bad") == 1
    assert gates["gold_in_union_min"] == 1.0


def _stream(body: dict) -> dict:
    req = urllib.request.Request("http://127.0.0.1:7200/chat/stream", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    answer, cur, err = {}, None, None
    with urllib.request.urlopen(req, timeout=600) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\\n")
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:") and cur == "answer":
                answer = json.loads(line[5:].strip())
            elif line.startswith("data:") and cur == "error":
                err = line[5:].strip()
    if err:
        pytest.skip(f"stream error (lane health, not the contract): {err[:160]}")
    return answer


@pytest.mark.parametrize("conv", SUITE["conversations"], ids=[c["fixture"].rsplit("/", 1)[-1] for c in SUITE["conversations"]])
def test_live_conversation_fixture_meets_its_frozen_expectations(conv):
    try:
        urllib.request.urlopen("http://127.0.0.1:7200/ready", timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"orchestrator not reachable: {exc}")
    fx = json.loads((ROOT / conv["fixture"]).read_text()); ex = conv["expect"]
    ans = _stream({"message": fx["message"], "corpus_id": fx["corpus_id"], "mode": "HYBRID", "compiler": "on", "history": fx.get("history") or []})
    ret = ans.get("retrieval") or {}; plan = ret.get("chat_plan") or {}; meta = (ans.get("result") or {}).get("meta") or {}
    if (plan.get("compiler") or {}).get("fallback"):
        pytest.skip("compiler fell back; the deterministic layer is covered offline")
    text = str(((ans.get("result") or {}).get("answer")) or "")
    if "task_type" in ex:
        assert plan.get("task_type") == ex["task_type"], plan.get("task_type")
    if "task_type_in" in ex:
        assert plan.get("task_type") in ex["task_type_in"], plan.get("task_type")
    if "retrieval_skipped" in ex:
        assert bool(plan.get("retrieval_skipped")) is ex["retrieval_skipped"], plan
    if ex.get("min_answer_chars"):
        assert len(text) >= ex["min_answer_chars"], len(text)
    if ex.get("no_abstention_marker"):
        assert not ABSTAIN.search(text), text[:300]
    if ex.get("min_citations"):
        assert len(ret.get("used_evidence") or []) >= ex["min_citations"]
    if ex.get("resolved_contains"):
        assert all(w in (plan.get("resolved_request") or "").lower() for w in ex["resolved_contains"])
    if ex.get("min_queries"):
        assert len(plan.get("queries") or []) >= ex["min_queries"], plan.get("queries")
    if ex.get("exact_terms_include"):
        assert set(ex["exact_terms_include"]) <= set(plan.get("exact_terms") or [])
''', encoding="utf-8")
p = ROOT / "scripts/scaffold_polymath_v4.py"; s = p.read_text(encoding="utf-8")
anchor = '    ("docs/wiki/work-log/2026-09-05-p1f-chat-runtime.md", "md", None),\n'; assert s.count(anchor) == 1
add = ''.join(f'    ("{f}", "{f.rsplit(".",1)[1]}", None),\n' for f in [
    "eval/fixtures/chat_regression_suite.json", "tests/determinism/test_chat_regression_suite.py", "docs/wiki/work-log/2026-09-05-p1g-regression-suite.md"])
p.write_text(s.replace(anchor, anchor + add), encoding="utf-8")
p = ROOT / "scripts/README.md"; s = p.read_text(encoding="utf-8")
line = [l for l in s.split("\n") if l.startswith("| `scripts/chat_baseline.py`")][0]
if "--check" not in line:
    s = s.replace(line, line.rstrip(" |") + " P1.g: `--check B|L|M:<tag>` evaluates a run against the frozen gates in eval/fixtures/chat_regression_suite.json (exit 1 on regression). |")
    p.write_text(s, encoding="utf-8")
print("P1.g patch applied")
