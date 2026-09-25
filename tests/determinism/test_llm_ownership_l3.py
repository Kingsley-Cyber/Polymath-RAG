"""LLM-BACKEND L3 (register 11.467): ownership and wiring of the provider backend.

Gaps closed here: L-02 (7 of 18 Groq pairs idle), L-07 (six profile slots on one pair), L-14 (pMAP lane choice:
fallbacks rotated in as equals), L-15 (the extraction ring front-loaded its head lanes), L-20 (limiter families
spanning accounts). The runtime files are generated from `config/llm_accounts.yaml`.

Pure: config files, pure functions and monkeypatched endpoints. No database, no network, no model call.
"""
from __future__ import annotations

import json
import textwrap
from collections import Counter
from pathlib import Path

import pytest
from polymath_shared.llm_extraction import accounts as A
from polymath_shared.llm_extraction import pool

ROOT = Path(__file__).resolve().parents[2]
REG = A.load_registry()
PROVIDERS = json.loads((ROOT / "config" / "cloud_providers.json").read_text())
GROQ_MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b")


# ---- the real registry: all 18 Groq pairs used, one owner each (L-02, L-07) ----------------------------------------

def test_every_groq_pair_has_one_enabled_lane_owned_by_exactly_one_slot():
    owned = A.owned_lanes(REG)
    callers = A.lane_slots(REG)
    pairs = 0
    for acct in (a for a in REG.accounts.values() if a.provider == "groq"):
        for model in GROQ_MODELS:
            lanes = [lane for lane in acct.lanes if lane.model == model and lane.enabled]
            assert len(lanes) == 1, (acct.name, model)
            owners = [slot for by_lane in owned.values() for n, slot in by_lane.items() if n == lanes[0].name]
            assert len(owners) == 1, (lanes[0].name, owners)
            assert callers[lanes[0].name] == 1
            pairs += 1
    assert pairs == 18


def test_owned_groq_budgets_are_the_whole_pair_and_fit_the_quota():
    for acct in (a for a in REG.accounts.values() if a.provider == "groq"):
        for lane in acct.lanes:
            quota = acct.quota[lane.model]
            assert lane.limiter["tpd"] == 190_000 == int(0.95 * quota["tpd"])
            assert lane.limiter["rpd"] == 950 == int(0.95 * quota["rpd"])
            assert lane.limiter["tpm"] <= quota["tpm"]
    groq = [f for f in A.validate(REG, env={})
            if f.code in ("IDLE_PAIR", "PAIR_SHARED_BY_SLOTS", "BUDGET_EXCEEDS_QUOTA") and f.message.startswith("groq_")]
    assert groq == []


def test_no_limiter_family_spans_accounts_and_gemini_has_one_per_account_and_model():   # L-20
    assert not [f for f in A.validate(REG, env={}) if f.code == "FAMILY_SPANS_ACCOUNTS"]
    fams: dict[str, set] = {}
    for lane in REG.lanes.values():
        if lane.account.startswith("gemini_"):
            fams.setdefault(lane.limiter["family"], set()).add((lane.account, lane.model))
    assert all(len(pairs) == 1 for pairs in fams.values()), fams
    assert len(fams) == 12                                        # 6 accounts x 2 models


def test_the_registry_has_no_errors_and_no_unused_or_ownerless_lane():
    findings = A.validate(REG, env={})
    assert [f for f in findings if f.level == "error"] == []
    assert not [f for f in findings if f.code in ("LANE_UNUSED", "SLOT_WITHOUT_OWN_LANE", "OWNER_SPANS_ACCOUNTS")]


# ---- the runtime files are generated -----------------------------------------------------------------------------

def test_the_runtime_files_are_the_writers_output():
    assert A.runtime_drift(REG) == []
    assert A.runtime_not_generated(REG) == []
    assert PROVIDERS["stage_owners"] == {s: A.stage_owner_groups(REG, s) for s in ("doc_profile", "doc_parent_map")}
    assert "GENERATED" in PROVIDERS["_doc"][0]
    assert (ROOT / "config" / "extraction_models" / "limiter.yaml").read_text().startswith("# GENERATED")


def test_the_writer_is_idempotent_and_a_hand_edit_is_reported(tmp_path):
    p, lim = tmp_path / "p.json", tmp_path / "l.yaml"
    assert len(A.write_runtime(REG, p, lim)) == 2
    assert A.write_runtime(REG, p, lim) == []                      # nothing left to change
    assert A.runtime_drift(REG, p, lim) == [] and A.runtime_not_generated(REG, p, lim) == []
    lim.write_text(lim.read_text() + "# a hand edit\n")            # same data, different bytes
    assert A.runtime_drift(REG, p, lim) == []
    assert A.runtime_not_generated(REG, p, lim) == ["l.yaml is not the writer's output (run scripts/llm_accounts.py write)"]


# ---- the registry and the supervisor agree ------------------------------------------------------------------------

def test_registry_slot_counts_and_owner_names_match_the_supervisor_fleet():
    from control import process_supervisor as PS
    names = {e[0] for e in PS.FLEET if isinstance(e, tuple)}
    by_module = Counter(e[1] for e in PS.FLEET if isinstance(e, tuple))
    assert REG.slots["doc_profile"]["count"] == by_module["workers.doc_profile_worker"] == 6
    assert REG.slots["doc_parent_map"]["count"] == by_module["workers.doc_parent_map_stage_worker"] == 6
    assert REG.slots["extract"]["count"] == by_module["workers.extract_worker"] == 3
    assert REG.slots["parent_enrichment"]["count"] == by_module["workers.summary_worker"] == 2
    for stage in ("doc_profile", "doc_parent_map"):
        assert set(REG.slots[stage]["owners"]) <= names
        assert PS.LANE_OFFSET_ENV[stage] == REG.slots[stage]["lane_offset_env"]


def test_the_supervisor_gives_each_owning_slot_its_index():
    from control import process_supervisor as PS
    assert PS.lane_offset_env("doc_parent_map") == {"POLYMATH_DOC_PARENT_MAP_LANE_OFFSET": "1"}
    assert PS.lane_offset_env("doc_parent_map6") == {"POLYMATH_DOC_PARENT_MAP_LANE_OFFSET": "6"}
    assert PS.lane_offset_env("doc_profile2") == {"POLYMATH_DOC_PROFILE_LANE_OFFSET": "2"}
    for other in ("extract2", "summaries", "profile", "doc_parent_map_x", "orchestrator"):
        assert PS.lane_offset_env(other) == {}


# ---- an owning slot never reaches another slot's lanes (L-07, L-14) -----------------------------------------------

@pytest.mark.parametrize("stage", ["doc_profile", "doc_parent_map"])
def test_an_owning_slot_calls_its_own_lanes_then_the_shared_tier_and_nothing_else(stage):
    pin, owners = PROVIDERS["stage_pins"][stage], PROVIDERS["stage_owners"][stage]
    all_owned = {n for g in owners for n in g}
    shared = [n for n in pin if n not in all_owned]
    paid_last = [n for n in pin if "fallback" in n][-1]
    for k in range(1, len(owners) + 1):
        firsts = set()
        for i in range(30):
            order = pool.owned_lane_order(pin, owners, k, f"run_{i}")
            own = order[: len(owners[k - 1])]
            assert sorted(own) == sorted(owners[k - 1])                    # its own lanes first
            assert sorted(order[len(own):]) == sorted(shared)             # then the shared tier, nothing else
            assert not set(order) & (all_owned - set(owners[k - 1]))       # never another slot's lanes
            assert order[-1] == paid_last                                  # the OpenRouter fallback last
            firsts.add(order[0])
        assert firsts == set(owners[k - 1])                                # runs alternate the account's models
    assert set(pool.owned_lane_order(pin, owners, len(owners) + 1, "run")) == set(shared)   # owns nothing


def test_a_profile_slot_attempts_its_own_key_then_the_fallback(monkeypatch):
    from workers import doc_profile_worker as W
    pin, owners = PROVIDERS["stage_pins"]["doc_profile"], PROVIDERS["stage_owners"]["doc_profile"]
    for k in range(1, 7):
        monkeypatch.setenv("POLYMATH_DOC_PROFILE_LANE_OFFSET", str(k))
        assert W.attempt_lanes(pin, "run_a", owners) == [f"profile_groq{k}", "profile_fallback_openrouter"]
    monkeypatch.delenv("POLYMATH_DOC_PROFILE_LANE_OFFSET")
    # without the index (a single worker, tests): the pre-L3 rotation over every key
    assert {W.attempt_lanes(pin, f"run_{i}", owners)[0] for i in range(40)} == {f"profile_groq{k}" for k in range(1, 7)}


def _endpoints(names):
    return [pool.CloudEndpoint(name=n, url="https://example.invalid", model="m", dedicated=True) for n in names]


def test_a_pmap_slot_walks_its_own_account_then_the_cloudflare_tier_then_openrouter(monkeypatch):
    from workers import doc_parent_map_stage_worker as S
    pin = PROVIDERS["stage_pins"]["doc_parent_map"]
    cf = [n for n in pin if n.startswith("cloudflare_map")]       # cloudflare_map2 since account 1 retired (11.469)
    assert cf
    monkeypatch.setattr(pool, "cloud_endpoints", lambda: _endpoints(pin))
    for k in range(1, 7):
        monkeypatch.setenv("POLYMATH_DOC_PARENT_MAP_LANE_OFFSET", str(k))
        firsts = set()
        for i in range(20):
            names = [e.name for e in S._pmap_lanes(f"run_{i}")]
            assert set(names[:2]) == {f"map_groq{k}", f"map_groq{k}q"}
            assert set(names[2:2 + len(cf)]) == set(cf)
            assert names[2 + len(cf):] == ["map_fallback_openrouter"]
            firsts.add(names[0])
        assert firsts == {f"map_groq{k}", f"map_groq{k}q"}
    # slot 6's own account dark: it maps on the shared tier, never on another key
    monkeypatch.setattr(pool, "cloud_endpoints",
                        lambda: _endpoints([n for n in pin if n not in ("map_groq6", "map_groq6q")]))
    assert {e.name for e in S._pmap_lanes("run_x")} == set(cf) | {"map_fallback_openrouter"}
    # without the index: every active pin lane, rotated by run (pre-L3)
    monkeypatch.delenv("POLYMATH_DOC_PARENT_MAP_LANE_OFFSET")
    monkeypatch.setattr(pool, "cloud_endpoints", lambda: _endpoints(pin))
    assert sorted(e.name for e in S._pmap_lanes("run_x")) == sorted(pin)


# ---- extraction: a document's batches start on a lane chosen by the document (L-15) -------------------------------

def test_extraction_batches_start_on_a_lane_chosen_by_the_document():
    from workers.llm_provider import batch_lane_indices
    ring = list(range(20))                                  # a lone document's slice is the whole ring
    use: Counter = Counter()
    for d in range(600):
        lanes = batch_lane_indices(ring, 2, f"doc_{d}")
        assert lanes == batch_lane_indices(ring, 2, f"doc_{d}")          # replay-stable
        assert lanes[1] == (lanes[0] + 1) % 20                           # consecutive lanes of the slice
        use.update(lanes)
    assert set(use) == set(ring)                                         # every lane serves some document
    assert max(use.values()) < 3 * min(use.values())                     # no pile-up on the head of the ring
    for d in range(50):                                                  # a ranked slice keeps to its own lanes
        assert set(batch_lane_indices([8, 9, 10, 11], 7, f"doc_{d}")) <= {8, 9, 10, 11}
    assert batch_lane_indices([], 3, "d") == []


# ---- the ownership checks, on a small registry ---------------------------------------------------------------------

FIXTURE = """
    version: 1
    slots:
      doc_profile:
        count: 2
        lane_offset_env: X_OFFSET
        owners: {doc_profile: [p1], doc_profile2: [p2]}
    stage_pins: {doc_profile: [p1, p2, p_fallback]}
    accounts:
      acme_1:
        provider: acme
        key_env: K1
        quota: {m: {tpd: 1000, tpm: 100}}
        lanes:
          p1: {model: m, url: https://x.invalid, dedicated: true, limiter: {kind: rate, family: a1, tpm: 100, tpd: 950}}
      acme_2:
        provider: acme
        key_env: K2
        quota: {m: {tpd: 1000, tpm: 100}}
        lanes:
          p2: {model: m, url: https://x.invalid, dedicated: true, limiter: {kind: rate, family: a2, tpm: 100, tpd: 950}}
      acme_3:
        provider: acme
        key_env: K3
        lanes:
          p_fallback: {model: m, url: https://x.invalid, dedicated: true, limiter: {kind: rate, family: a3}}
    local_limiters: {}
    docs: []
"""


def _registry(tmp_path: Path, body: str) -> A.Registry:
    p = tmp_path / "llm_accounts.yaml"
    p.write_text(textwrap.dedent(body))
    return A.load_registry(p)


def test_an_owned_pair_has_one_caller_and_its_whole_budget_fits(tmp_path):
    reg = _registry(tmp_path, FIXTURE)
    findings = A.validate(reg, env={"K1": "x", "K2": "x", "K3": "x"})
    assert [f.message for f in findings if f.code == "PAIR_SHARED_BY_SLOTS"] == [
        "acme_3 × m: up to 2 worker slots (doc_profile) share one quota"]          # only the unowned fallback
    assert not [f for f in findings if f.code == "BUDGET_EXCEEDS_QUOTA"]
    assert A.lane_slots(reg) == {"p1": 1, "p2": 1, "p_fallback": 2}
    assert A.compile_runtime(reg)[0]["stage_owners"] == {"doc_profile": [["p1"], ["p2"]]}
    # the same budgets WITHOUT ownership: two callers per pair overshoot the quota
    reg2 = _registry(tmp_path, FIXTURE.replace("owners: {doc_profile: [p1], doc_profile2: [p2]}", "owners: {}"))
    over = [f.message for f in A.validate(reg2, env={}) if f.code == "BUDGET_EXCEEDS_QUOTA"]
    assert "acme_1 × m: tpd budgets reach 1,900 against a quota of 1,000" in over


@pytest.mark.parametrize("old, new, code", [
    ("[p1], doc_profile2: [p2]}", "[ghost], doc_profile2: [p2]}", "OWNER_UNKNOWN_LANE"),
    ("{doc_profile: [p1, p2, p_fallback]}", "{doc_profile: [p2, p_fallback]}", "OWNER_NOT_PINNED"),
    ("doc_profile2: [p2]}", "doc_profile2: [p1]}", "OWNED_TWICE"),
    ("doc_profile2: [p2]}", "doc_profile3: [p2]}", "OWNER_BAD_SLOT"),
    ("{doc_profile: [p1], doc_profile2", "{doc_profile1: [p1], doc_profile2", "OWNER_BAD_SLOT"),
    ("        lane_offset_env: X_OFFSET\n", "", "OWNER_WITHOUT_OFFSET"),
])
def test_ownership_mistakes_are_errors(tmp_path, old, new, code):
    assert FIXTURE.count(old) == 1
    reg = _registry(tmp_path, FIXTURE.replace(old, new))
    assert code in {f.code for f in A.validate(reg, env={}) if f.level == "error"}


def test_a_slot_with_no_own_lane_and_a_group_across_accounts_are_warnings(tmp_path):
    reg = _registry(tmp_path, FIXTURE.replace("owners: {doc_profile: [p1], doc_profile2: [p2]}",
                                              "owners: {doc_profile: [p1, p2], doc_profile2: []}"))
    findings = A.validate(reg, env={})
    assert not [f for f in findings if f.level == "error"]
    assert {"SLOT_WITHOUT_OWN_LANE", "OWNER_SPANS_ACCOUNTS"} <= {f.code for f in findings}
