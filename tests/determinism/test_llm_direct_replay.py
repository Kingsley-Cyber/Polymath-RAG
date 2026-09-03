"""LLM-DIRECT-REPLAY-V1 + RECEIPT-COMPLETENESS-V1 (LLM-DIRECT-CANON P3,
ADR-0017): replay from the raw-response ledger needs (a) every response
receipted, reissues included, (b) each receipt's batch recoverable from the
provider's own key rule, (c) a capturing connection that turns materialize
into a pure fact-id function. Measured 2026-09-03: 5 of 14 responses on the
canary document were never stored because reissues bypassed the ledger."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers", "eval/v5"):
    sys.path.insert(0, str(ROOT / sub))

from polymath_shared.identity import content_hash
from workers import llm_provider as lp
import replay_llm_direct as R


def _nb(nid, text):
    return lp.Neighborhood(nid=nid, chunks=[(f"chunk_{nid}", text)])


def test_batches_are_recovered_from_contiguous_window_keys():
    nbs = [_nb(f"p{i}:{i}", f"text {i}") for i in range(6)]
    ident = content_hash({"contract": lp.contract_identity()})
    key = lambda batch: "ecr_" + content_hash({"ident": ident, "batch": [(n.nid, n.chunks) for n in batch]})[:40]
    receipts = {key(nbs[0:4]), key(nbs[4:6]), key(nbs[2:3])}          # first pass ×2 + one single-neighborhood reissue
    found = R._recover_batches(nbs, receipts)
    assert {tuple(n.nid for n in b) for b in found.values()} == {
        ("p0:0", "p1:1", "p2:2", "p3:3"), ("p4:4", "p5:5"), ("p2:2",)}
    assert R._recover_batches(nbs, {"ecr_nope"}) == {}


def test_capturing_connection_records_fact_ids_without_a_database():
    cap = R._CaptureConn()
    with cap.cursor() as cur:
        cur.execute("INSERT INTO facts (fact_id, predicate) VALUES (%s,%s) ON CONFLICT DO NOTHING", ("fact_1", "IS_A"))
        cur.execute("INSERT INTO entities (entity_id) VALUES (%s)", ("ent_1",))
        cur.execute("INSERT INTO evidence (evidence_id) VALUES (%s)", ("ev_1",))
    assert cap.sink == {"facts": {"fact_1"}, "entities": {"ent_1"}, "evidence": {"ev_1"}}


def test_reissue_responses_are_receipted_under_the_same_key_rule():
    src = (ROOT / "workers" / "workers" / "llm_provider.py").read_text()
    i = src.index("_raise_if_refused(reissue_results, lane)")
    after = src[i:i + 1500]
    assert "for r in reissue_results:" in after and "_cp(_kf(batch)" in after and "RECEIPT-COMPLETENESS-V1" in after, \
        "reissue results must be written to the receipt ledger with the provider's key rule"
