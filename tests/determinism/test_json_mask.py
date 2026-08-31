"""JSON-GRAMMAR-MASK-V1 — state machine + mask legality tests (no model).

The mask makes malformed JSON unrepresentable at generation time on the
local lane (measured motivation: 37% of local calls needed salvage).
These tests pin the state machine's transitions and the permissive
legality patterns; the mlx runtime path is exercised live at the sidecar.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "json_mask", ROOT / "sidecars" / "local_extractor" / "json_mask.py")
json_mask = importlib.util.module_from_spec(_spec)
sys.modules["json_mask"] = json_mask
_spec.loader.exec_module(json_mask)

S = json_mask
_state_for = json_mask.JsonGrammarMask._state_for


def test_state_transitions():
    cases = [
        ("", S.S_START),
        ('{"', S.S_KEY_BODY),
        ('{"contract', S.S_KEY_BODY),
        ('{"contract"', S.S_COLON),
        ('{"contract":', S.S_VALUE),
        ('{"contract": "', S.S_STR_BODY),
        ('{"contract": "x"', S.S_OBJ),
        ('{"a": 1', S.S_NUM),
        ('{"a": [', S.S_VALUE),
        ('{"a": ["b"', S.S_ARR),
        ('{"a": true', S.S_LIT),
        ('{"a": false', S.S_LIT),
        ('{"a": null', S.S_LIT),
        ('{"a": 1e5', S.S_NUM),
        ('{"a": {"b"', S.S_COLON),
        ('{"a": 1, "b"', S.S_COLON),
        ('{"a": 1}', S.S_DONE),
        ('{"a": [1,2]', S.S_OBJ),
    ]
    for prefix, expected in cases:
        got = _state_for(prefix)
        assert got == expected, f"{prefix!r}: {got} != {expected}"


def test_nested_containers_track_phase():
    assert _state_for('{"a": {"b": [1, {"c": "d"') == S.S_OBJ
    assert _state_for('{"a": [1, {"b"') == S.S_COLON
    assert _state_for('{"a": [1, 2') == S.S_NUM


def test_legality_patterns_permissive_bias():
    import re
    # structural states admit whitespace-prefixed pieces (the BPE space
    # glyph lives in the piece, not the decoded text)
    assert S._PATTERNS[S.S_COLON].match(" :")
    assert S._PATTERNS[S.S_KEY].match('  "name"') or S._PATTERNS[S.S_KEY].match(' "x')
    assert S._PATTERNS[S.S_START].match("\n{")
    # prose is clearly illegal at structural states
    assert not S._PATTERNS[S.S_COLON].match("hello world")
    assert not S._PATTERNS[S.S_START].match("Here is the JSON:")
    # numbers/literals may continue or end (permissive)
    assert S._PATTERNS[S.S_NUM].match("123")
    assert S._PATTERNS[S.S_NUM].match(",")
    assert S._PATTERNS[S.S_LIT].match("rue")
    # free states allow everything by construction (no pattern consulted)
    assert S.S_STR_BODY in S._FREE_STATES


def test_mask_fail_open_on_bad_tokenizer():
    class BrokenTok:  # no len, no vocab — compile must raise -> None
        pass
    assert json_mask.make_json_mask(BrokenTok()) is None
