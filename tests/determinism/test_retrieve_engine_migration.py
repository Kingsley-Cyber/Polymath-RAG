"""RETRIEVE-ENGINE-MIGRATION-V1 contract guard (provider-free, service-free).

Pins the reader-migration flag contract for `/retrieve` HYBRID:
  - default is the FINAL core (`v2`);
  - `v1` is an explicit rollback;
  - junk falls back to `v2` (never crashes the endpoint);
  - the final core entrypoint `chat_retrieve_mode` the migration routes to is importable.

Encodes no corpus ids or live counts — those live in the experiment artifact
(docs/wiki/experiments/retrieve-engine-migration-2026-09-10/).
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    _p = str(ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from orchestrator.api.retrieve import retrieve_engine_flag  # noqa: E402


def test_default_is_the_final_core():
    assert retrieve_engine_flag() == "v2"


def test_v1_is_an_explicit_rollback():
    assert retrieve_engine_flag("v1") == "v1"


def test_junk_falls_back_to_final_core():
    assert retrieve_engine_flag("garbage") == "v2"
    assert retrieve_engine_flag("") == "v2"


def test_env_override(monkeypatch):
    monkeypatch.setenv("POLYMATH_RETRIEVE_ENGINE", "v1")
    assert retrieve_engine_flag() == "v1"
    monkeypatch.setenv("POLYMATH_RETRIEVE_ENGINE", "v2")
    assert retrieve_engine_flag() == "v2"


def test_final_core_entrypoint_importable():
    from orchestrator.api.chat_retrieval import chat_retrieve_mode  # noqa: F401
