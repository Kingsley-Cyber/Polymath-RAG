import hashlib, base64, os, sys, time
sys.path.insert(0, "shared"); sys.path.insert(0, "workers")
os.environ["POLYMATH_GLINER_URL"] = "http://127.0.0.1:9999"
from polymath_shared.settings import get_settings
get_settings.cache_clear()
from polymath_shared.db import tx
from polymath_shared.intake_submission import canonical_intake_payload, submit_intake
from workers.intake_worker import process_event as intake_event
from workers.extract_worker import process_event as extract_event
raw = open("eval/e3/corpus/docs/psych_monitoring.md", "rb").read() + ("\nfailure-probe %d" % time.time()).encode()
payload = canonical_intake_payload("e3-qualification-corpus", "fail_probe.md", "text/markdown", base64.b64encode(raw).decode())
with tx() as c:
    res = submit_intake(c, payload)
rid = res["run_id"]
with tx() as c:
    intake_event(c, {"run_id": rid, "payload": payload, "idempotency_key": hashlib.sha256(rid.encode()).hexdigest()[:16]})
    chunked = c.execute("SELECT payload FROM outbox_events WHERE run_id=%s AND event_type='chunked.v1' ORDER BY event_id DESC LIMIT 1", (rid,)).fetchone()
raised = False
try:
    with tx() as c:
        extract_event(c, {"run_id": rid, "payload": chunked[0], "idempotency_key": hashlib.sha256(rid.encode()).hexdigest()[:16]})
except Exception as exc:
    raised = True
    print("RAISED", type(exc).__name__)
with tx() as c:
    print("STATUS", c.execute("SELECT status FROM runs WHERE run_id=%s", (rid,)).fetchone()[0])
    print("ATTEMPT", c.execute("SELECT outcome FROM stage_attempts WHERE run_id=%s AND stage='extract'", (rid,)).fetchone()[0])
    c.execute("DELETE FROM stage_attempts WHERE run_id=%s", (rid,))
    c.execute("DELETE FROM receipts WHERE run_id=%s", (rid,))
    c.execute("DELETE FROM outbox_events WHERE run_id=%s", (rid,))
    c.execute("DELETE FROM runs WHERE run_id=%s", (rid,))
    c.execute("DELETE FROM documents WHERE doc_id IN (SELECT doc_id FROM documents d JOIN runs r ON r.corpus_id=d.corpus_id WHERE r.run_id=%s)", (rid,))
    print("CLEANED")
