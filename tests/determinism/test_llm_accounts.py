"""LLM-BACKEND L1 (register 11.465): the provider account registry.

The registry (`config/llm_accounts.yaml`) must compile to exactly the runtime files, name every lane under one account,
and its checks must surface the policy problems the owner asked to fix (gap L-01). Pure: files and dicts only; no
database, no network, and credential checks see booleans, never values.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import yaml
from polymath_shared.llm_extraction import accounts as A

REG = A.load_registry()


# ---- the real registry

def test_the_registry_compiles_to_the_runtime_files_with_no_drift():
    assert A.runtime_drift(REG) == []


def test_every_lane_sits_under_exactly_one_account_and_keeps_its_credentials():
    assert len(REG.lanes) == sum(len(a.lanes) for a in REG.accounts.values())
    providers, _ = A.compile_runtime(REG)
    for entry in providers["providers"]:
        acct = REG.accounts[REG.lanes[entry["name"]].account]
        assert entry["api_key_env"] == acct.key_env
        assert entry.get("account_id_env") == acct.account_id_env


def test_every_stage_pin_names_a_registry_lane():
    assert not [f for f in A.validate(REG, env={}) if f.level == "error"]


def test_groq_is_six_accounts_with_three_models_each():
    groq = [a for a in REG.accounts.values() if a.provider == "groq"]
    assert len(groq) == 6
    for a in groq:
        assert set(a.quota) == {"openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"}
        assert all(q["tpd"] == 200_000 and q["tpm"] == 8_000 for q in a.quota.values())


def test_the_real_registry_has_no_idle_groq_pair():
    # L1 (11.465) reported the audit's 7 idle pairs (key 1: 20b + qwen; keys 2-6: 120b) as the L3 worklist;
    # L3 (11.467) enables all 18 and gives each one owner.
    idle = [f.message for f in A.validate(REG, env={}) if f.code == "IDLE_PAIR" and f.message.startswith("groq_")]
    assert idle == []


# ---- the checks, on a small registry

def _registry(tmp_path: Path, body: str) -> A.Registry:
    p = tmp_path / "llm_accounts.yaml"
    p.write_text(textwrap.dedent(body))
    return A.load_registry(p)


FIXTURE = """
    version: 1
    slots: {doc_profile: {count: 2}}
    stage_pins: {doc_profile: [p1]}
    accounts:
      acme_1:
        provider: acme
        key_env: ACME_KEY_1
        quota: {m-big: {tpd: 1000}, m-small: {tpd: 1000}}
        lanes:
          p1: {model: m-big, url: https://x.invalid, dedicated: true, limiter: {kind: rate, family: acme}}
      acme_2:
        provider: acme
        key_env: ACME_KEY_2
        account_id_env: ACME_ACCOUNT_2
        lanes:
          x2: {model: m-big, url: https://x.invalid, limiter: {kind: rate, family: acme}}
    local_limiters: {}
    docs: []
"""


def test_the_checks_flag_shared_families_shared_pairs_idle_quota_and_missing_credentials(tmp_path):
    reg = _registry(tmp_path, FIXTURE)
    codes = {f.code for f in A.validate(reg, env={"ACME_KEY_1": "set"})}
    assert "FAMILY_SPANS_ACCOUNTS" in codes          # family acme covers acme_1 and acme_2
    assert "PAIR_SHARED_BY_SLOTS" in codes           # p1 is dedicated and doc_profile has 2 slots
    assert "IDLE_PAIR" in codes                      # acme_1 x m-small has quota and no lane
    assert "KEY_UNSET" in codes and "ACCOUNT_ID_UNSET" in codes


def test_a_parked_or_retired_account_is_not_flagged_for_missing_credentials(tmp_path):
    # register 11.469: credentials matter only while an account has an enabled lane (Cloudflare account 1 was retired)
    body = FIXTURE.replace("x2: {model: m-big, url: https://x.invalid, limiter",
                           "x2: {model: m-big, url: https://x.invalid, enabled: false, limiter")
    codes = {(f.code, f.message.split(":")[0]) for f in A.validate(_registry(tmp_path, body), env={})}
    assert ("KEY_UNSET", "acme_2") not in codes and ("ACCOUNT_ID_UNSET", "acme_2") not in codes
    assert ("KEY_UNSET", "acme_1") in codes                  # an account in use still is


def test_a_pin_to_an_unknown_lane_is_an_error(tmp_path):
    reg = _registry(tmp_path, FIXTURE.replace("doc_profile: [p1]", "doc_profile: [p1, ghost]"))
    errors = [f for f in A.validate(reg, env={}) if f.level == "error"]
    assert [f.code for f in errors] == ["PIN_UNKNOWN_LANE"]


def test_a_lane_declared_twice_is_refused(tmp_path):
    body = FIXTURE.replace("x2: {model: m-big", "p1: {model: m-big")
    try:
        _registry(tmp_path, body)
    except ValueError as exc:
        assert "two accounts" in str(exc)
    else:
        raise AssertionError("a duplicate lane must be refused")


def test_drift_is_reported_field_by_field(tmp_path):
    reg = _registry(tmp_path, FIXTURE)
    providers, limiter = A.compile_runtime(reg)
    providers["providers"][0]["dedicated"] = False
    (tmp_path / "p.json").write_text(json.dumps(providers))
    (tmp_path / "l.yaml").write_text(yaml.safe_dump(limiter))
    assert A.runtime_drift(reg, tmp_path / "p.json", tmp_path / "l.yaml") == ["provider p1: fields differ ['dedicated']"]


def test_the_report_shows_booleans_never_values(tmp_path):
    reg = _registry(tmp_path, FIXTURE)
    rows = A.ownership_rows(reg, env={"ACME_KEY_1": "SECRET-VALUE-123", "ACME_ACCOUNT_2": ""})
    assert "SECRET-VALUE-123" not in json.dumps(rows)
    by = {(r["account"], r["model"]): r for r in rows}
    assert by[("acme_1", "m-big")]["key_set"] is True
    assert by[("acme_2", "m-big")]["state"] == "parked"       # key and account id unset: the runtime parks it
    assert by[("acme_1", "m-small")]["state"] == "idle"
