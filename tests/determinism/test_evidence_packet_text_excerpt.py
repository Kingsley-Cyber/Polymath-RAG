"""RB5 — EvidencePacket text is a bounded VERBATIM EXCERPT of the retrieved chunk, never the 240-char UI preview.

Presentation only. The pins below say two things: (1) what the excerpt is (bounded, verbatim prefix, honest about truncation
and about the chunk's real length); (2) what it is NOT allowed to touch — supplying chunk text must never change which rows a
packet holds, their order, ids, roles, grades, lineage or provenance.
"""
import copy
import json
import pathlib
import sys

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import evidence_packet as EP  # noqa: E402
from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402

assert pathlib.Path(EP.__file__).resolve().is_relative_to(ROOT), EP.__file__      # executed path == this checkout

PLAN = [{"id": "q0", "type": "PRIMARY", "origin": "USER", "role": "direct"},
        {"id": "p0", "type": "ENTITY", "origin": "PROFILE", "role": "bridge", "inspired_by_profile": ["docB"], "target": "docB", "reason": "aspect:entity (bridge)"}]
CHUNK = ("Safety is a hundred percent the number one thing in our production. " * 30).strip()        # 2,069 chars
SHORT = "A short chunk that fits."
ROWS = [{"chunk_id": "c_long", "doc_id": "docA", "source_name": "Handbook", "text": CHUNK[:240], "query_ids": ["q0"], "role": "DIRECT"},
        {"chunk_id": "c_short", "doc_id": "docB", "source_name": "Book", "text": SHORT, "query_ids": ["p0"], "role": "LATENT", "latent_role": "COMPLEMENTARY"},
        {"chunk_id": "c_miss", "doc_id": "docC", "source_name": "Other", "text": ("x" * 239) + " ", "query_ids": ["q0"], "role": "RELATIONAL"}]
GRADES = {"c_long": "DIRECT", "c_short": "RELATED", "c_miss": "PARTIAL"}
FULL = {"c_long": CHUNK, "c_short": SHORT}                       # c_miss: the resolver found nothing
NON_TEXT = ("chunk_id", "document_id", "source", "origin", "query_ids", "lineage", "utility_role", "synthesis_role", "ca4_grade", "c4_valid", "provenance")


def _build(**kw):
    return EP.build_evidence_packet(q0="how do crews stay safe", retrieval_mode="HYBRID", plan_queries=PLAN, evidence_rows=copy.deepcopy(ROWS),
                                    ca4_grades=GRADES, receipts={"firing": {"requested": False}}, **kw).to_dict()


def test_excerpt_is_a_bounded_verbatim_prefix_cut_on_a_word_boundary():
    text, cut = EP.excerpt(CHUNK, 900)
    assert cut is True and 0.8 * 900 <= len(text) <= 900 and CHUNK.startswith(text) and not text.endswith(" ")
    assert CHUNK[len(text)] == " "                                            # the cut fell between words, nothing was appended
    assert EP.excerpt(SHORT, 900) == (SHORT, False) and EP.excerpt("", 900) == ("", False) and EP.excerpt(None, 900) == ("", False)
    assert EP.excerpt("x" * 5000, 900) == ("x" * 900, True)                    # no boundary nearby -> hard cut, still bounded
    assert EP.excerpt(CHUNK, 0) == ("", True) and len(EP.excerpt(CHUNK, 5)[0]) <= 5


def test_the_packet_carries_the_chunk_not_the_240_char_preview():
    assert EP.DEFAULT_MAX_TEXT == 900
    ev = {e["chunk_id"]: e for e in _build(full_texts=FULL)["evidence"]}
    long = ev["c_long"]
    assert 600 <= len(long["text"]) <= 900 and CHUNK.startswith(long["text"]) and long["text"].startswith(ROWS[0]["text"].rstrip())
    assert long["text_truncated"] is True and long["text_chars"] == len(CHUNK)
    assert ev["c_short"]["text"] == SHORT and ev["c_short"]["text_truncated"] is False and ev["c_short"]["text_chars"] == len(SHORT)


def test_a_resolver_miss_presents_the_preview_and_claims_nothing():
    miss = {e["chunk_id"]: e for e in _build(full_texts=FULL)["evidence"]}["c_miss"]
    assert miss["text"] == ROWS[2]["text"] and miss["text_truncated"] is None and miss["text_chars"] is None     # never a false "complete"
    legacy_shape = _build()                                                      # a caller that supplies no chunk text at all
    assert all(e["text_truncated"] is None and e["text_chars"] is None for e in legacy_shape["evidence"])
    assert [e["text"] for e in legacy_shape["evidence"]] == [r["text"] for r in ROWS]


def test_supplying_chunk_text_changes_nothing_but_the_text_fields():
    a, b = _build(), _build(full_texts=FULL)
    assert [e["chunk_id"] for e in a["evidence"]] == [e["chunk_id"] for e in b["evidence"]] == ["c_long", "c_short", "c_miss"]     # membership + order
    for x, y in zip(a["evidence"], b["evidence"]):
        assert {k: x[k] for k in NON_TEXT} == {k: y[k] for k in NON_TEXT}
        assert set(x) == set(y) and set(x) - set(NON_TEXT) == {"text", "text_truncated", "text_chars"}
    assert {k: v for k, v in a.items() if k != "evidence"} == {k: v for k, v in b.items() if k != "evidence"}                        # plan, receipts, q0, mode, version
    assert b["evidence"][1]["utility_role"] == "COMPLEMENTARY" and b["evidence"][1]["provenance"]["origin"] == "PROFILE" and b["evidence"][0]["ca4_grade"] == "DIRECT"


def test_bounds_still_hold_and_extra_chunk_texts_never_add_rows():
    p = _build(full_texts={**FULL, "c_not_retrieved": "a chunk the turn never selected"}, max_rows=2, max_text=50)
    assert [e["chunk_id"] for e in p["evidence"]] == ["c_long", "c_short"] and all(len(e["text"]) <= 50 for e in p["evidence"])
    assert p["evidence"][0]["text_truncated"] is True and p["evidence"][0]["text_chars"] == len(CHUNK)
    assert _build(full_texts=FULL) == _build(full_texts=dict(FULL))                 # deterministic


def test_the_new_fields_are_lawful_on_the_wire_and_survive_the_adapter():
    schema = json.loads((ROOT / "contracts/evidence/v1/evidence_packet.schema.json").read_text())
    item = schema["$defs"]["evidence_item"]
    assert "text_truncated" in item["properties"] and "text_chars" in item["properties"]
    assert "text_truncated" not in item["required"] and "text_chars" not in item["required"]          # OPTIONAL: additive, older producers stay lawful
    packet = _build(full_texts=FULL)
    jsonschema.Draft202012Validator(schema).validate(packet)
    assert EB.check_response({"evidence_packet": packet, "synthesis_performed": False}) == []
    rows = {r["id"]: r for r in EB.rows_from_packet(packet, "cinema")}
    assert rows["c_long"]["text_truncated"] is True and rows["c_long"]["text_chars"] == len(CHUNK) and len(rows["c_long"]["text"]) <= EB.ROW_TEXT_CHARS
    assert rows["c_short"]["text_truncated"] is False and "text_truncated" not in rows["c_miss"]         # unknown stays unknown
    view = EB.hydrate([{"kind": "chunk", "id": "c_long"}, {"kind": "chunk", "id": "c_short"}], [{"step_id": "B_retrieve", "sequence": 3, "output": {"rows": list(rows.values())}}])
    by = {r["id"]: r for r in view["rows"]}
    assert len(by["c_long"]["text"]) == EB.HYDRATE_MAX_CHARS and by["c_long"]["text_truncated"] is True and by["c_long"]["text_chars"] == len(CHUNK)
    assert by["c_short"]["text"] == SHORT and by["c_short"]["text_truncated"] is False
