"""ENRICH-IDENTITY-V2: an enrichment's identity is content + contract,
never the lane. Measured 2026-09-02: with `<lane>:<model>` inside the
hash, adding two pin lanes re-sharded parents and the summaries worker
re-enriched the whole corpus (1,309 rows/day for 1,374 parents) while a
fresh upload waited. Also pins ENRICH-OWN-DOC-FIRST and the re-key
script's formula parity."""
import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers", "scripts"):
    sys.path.insert(0, str(ROOT / sub))

import psycopg
import pytest

from polymath_shared.latent.contract import PRODUCTION_BOUNDS, QUALIFICATION_BOUNDS
from polymath_shared.latent.runtime import enrichment_contract_id, input_hash_for

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"


def test_identity_ignores_the_lane_and_tracks_the_contract():
    sh = "sh_" + "a" * 20
    a = input_hash_for(sh, enrichment_contract_id(QUALIFICATION_BOUNDS))
    b = input_hash_for(sh, enrichment_contract_id(QUALIFICATION_BOUNDS))
    assert a == b                                       # deterministic
    # a different output contract IS a different identity
    assert a != input_hash_for(sh, enrichment_contract_id(PRODUCTION_BOUNDS))
    # a different source IS a different identity
    assert a != input_hash_for("sh_" + "b" * 20, enrichment_contract_id(QUALIFICATION_BOUNDS))
    assert enrichment_contract_id(QUALIFICATION_BOUNDS) == "parent-enrichment-v1|tokens=700"


def test_worker_no_longer_hashes_the_lane():
    src = (ROOT / "workers" / "workers" / "summary_worker_impl.py").read_text()
    assert 'f"{ep_p.name}:{ep_p.model}"' not in src, "lane back inside the enrichment identity"
    assert "input_hash_for(_sh(p.children), enrichment_contract_id(bounds))" in src


def test_migration_formula_matches_runtime():
    import migrate_enrichment_identity as mig
    sh = "sh_" + "c" * 20
    assert mig.lane_free_hash(sh, 700) == input_hash_for(sh, enrichment_contract_id(QUALIFICATION_BOUNDS))
    assert mig.lane_free_hash(sh, 900) == input_hash_for(sh, enrichment_contract_id(PRODUCTION_BOUNDS))


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=False) as c:
        yield c
        c.rollback()


def test_run_docs_puts_the_runs_own_document_first(conn):
    from workers.summary_worker_impl import _run_docs
    corpus = "probe-owndoc-" + uuid.uuid4().hex[:8]
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash, purpose) VALUES (%s,%s,'p','probe')",
                 (corpus, corpus))
    docs = []
    for i, name in enumerate(("older.md", "newer.md")):
        did = "doc_probe_" + uuid.uuid4().hex[:16]
        conn.execute(
            """INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length,
                                      content_hash, created_at)
               VALUES (%s,%s,%s,'text/markdown',10,%s, now() + make_interval(secs => %s))""",
            (did, corpus, name, "h" + uuid.uuid4().hex[:8], i))
        docs.append(did)
    run_id = "run_probe_" + uuid.uuid4().hex[:16]
    conn.execute("""INSERT INTO runs (run_id, corpus_id, status, metadata)
                    VALUES (%s,%s,'reconciling', '{"source_name": "newer.md"}'::jsonb)""",
                 (run_id, corpus))
    order = _run_docs(conn, run_id)
    assert order[0] == docs[1], "the run's own (newer) document must come first"
    assert set(order) == set(docs)


def test_rekey_is_idempotent_and_keeps_ids(conn):
    import migrate_enrichment_identity as mig
    corpus = "probe-rekey-" + uuid.uuid4().hex[:8]
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash, purpose) VALUES (%s,%s,'p','probe')",
                 (corpus, corpus))
    did = "doc_probe_" + uuid.uuid4().hex[:16]
    conn.execute("""INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length, content_hash)
                    VALUES (%s,%s,'x.md','text/markdown',10,%s)""", (did, corpus, "h" + uuid.uuid4().hex[:8]))
    pid = "chunk_probe_" + uuid.uuid4().hex[:16]; sh = "sh_" + uuid.uuid4().hex
    old_ih = "in_oldstyle_" + uuid.uuid4().hex[:12]
    eid = "penr_probe_" + uuid.uuid4().hex[:12]
    conn.execute("""INSERT INTO parent_enrichments (enrichment_id, parent_id, corpus_id, doc_id, source_child_ids,
                       source_hash, input_hash, compiler_contract, provider, model, prompt_version, summary, children,
                       abstraction, mechanisms, affordances, questions, gist_coverage, status)
                    VALUES (%s,%s,%s,%s,ARRAY[]::text[],%s,%s,'parent-enrichment-v1','llm:probe','m','v','s','[]'::jsonb,
                            'a','[]'::jsonb,'[]'::jsonb,'[]'::jsonb,1.0,'READY')""",
                 (eid, pid, corpus, did, sh, old_ih))
    out = mig.rekey(conn, max_tokens=700, execute=True)
    assert out["rekeyed"]["READY"] >= 1
    new_ih, kept_eid = conn.execute(
        "SELECT input_hash, enrichment_id FROM parent_enrichments WHERE parent_id=%s", (pid,)).fetchone()
    assert new_ih == mig.lane_free_hash(sh, 700) and kept_eid == eid
    again = mig.rekey(conn, max_tokens=700, execute=True)
    assert again["rekeyed"].get("READY", 0) == out["rekeyed"]["READY"] - 1 or again["already_lane_free"] >= 1
