"""SQLite loop-memory adapter — the ONLY module allowed to know SQLite exists.

Laws (docs/03): SQLite = workflow memory, not agent memory, not knowledge.
DB lives OUTSIDE the skill dir (skill reinstall must never destroy state).
Actions persist BEFORE Hermes sees them; submit is idempotent; transitions
commit atomically; config hashes pin each run — drift blocks, never silently
resumes. controller.py stays the sole transition authority: this module
persists, it never decides.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3

from models import now

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_SQL = os.path.join(SKILL_ROOT, "sql", "001_initial.sql")
MIGRATIONS = [("2", os.path.join(SKILL_ROOT, "sql", "002_context.sql"))]
SCHEMA_VERSION = "2"


def db_path() -> str:
    p = os.environ.get("OPPORTUNITY_RESEARCH_DB")
    if p:
        return p
    return os.path.expanduser("~/.hermes/state/opportunity-research/opportunity.sqlite3")


_SCHEMA_READY: set = set()   # db paths whose schema this process has verified


def connect() -> sqlite3.Connection:
    path = db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if path not in _SCHEMA_READY:
        # journal/synchronous are durable database settings; set them once
        # per process together with the schema check (a step issues dozens
        # of connects — re-running migrations + four PRAGMAs each time was
        # pure overhead).
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
        _ensure_schema(conn)
        _SCHEMA_READY.add(path)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    have = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'").fetchone()
    if not have:
        with open(SCHEMA_SQL, encoding="utf-8") as f:
            conn.executescript(f.read())
        for _, path in MIGRATIONS:
            with open(path, encoding="utf-8") as f:
                conn.executescript(f.read())
        conn.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES('schema_version',?)",
                     (SCHEMA_VERSION,))
        conn.commit()
        return
    ver = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    current = ver["value"] if ver else "1"
    for target, path in MIGRATIONS:  # additive, ordered, idempotent DDL
        if current < target:
            with open(path, encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES('schema_version',?)",
                         (target,))
            conn.commit()
            current = target
    if current != SCHEMA_VERSION:
        raise RuntimeError(f"unsupported schema_version {current} (supported {SCHEMA_VERSION})")


def _h(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()
                          if not isinstance(data, (bytes, str))
                          else (data.encode() if isinstance(data, str) else data)).hexdigest()[:16]


def _file_hash(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return "missing"


def _dir_hash(path: str) -> str:
    parts = []
    try:
        for name in sorted(os.listdir(path)):
            fp = os.path.join(path, name)
            if os.path.isfile(fp):
                parts.append(name + ":" + _file_hash(fp))
    except OSError:
        return "missing"
    return _h("|".join(parts))


def config_hashes() -> dict:
    reg_build = None
    try:
        import registry
        snap = registry.load_snapshot()
        reg_build = snap and snap.get("build_id")
    except Exception:
        pass
    return {
        "control_graph_hash": _file_hash(os.path.join(SKILL_ROOT, "graph", "control_graph.yaml")),
        "loop_spec_hash": _file_hash(os.path.join(SKILL_ROOT, "loop.yaml")),
        "policy_hash": _file_hash(os.path.join(SKILL_ROOT, "graph", "policies.yaml")),
        "schemas_hash": _dir_hash(os.path.join(SKILL_ROOT, "schemas")),
        "prompts_hash": _dir_hash(os.path.join(SKILL_ROOT, "prompts")),
        "registry_build": reg_build or "none",
    }


DRIFT_FIELDS = ["control_graph_hash", "loop_spec_hash", "policy_hash",
                "schemas_hash", "prompts_hash"]


# ------------------------------------------------------------------- runs --
def create_run(run_id: str, objective: str, node: str) -> None:
    h = config_hashes()
    with connect() as conn:
        conn.execute("""INSERT OR IGNORE INTO runs
            (run_id,status,current_graph_node,objective,control_graph_hash,
             loop_spec_hash,policy_hash,schemas_hash,prompts_hash,registry_build,
             created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, "running", node, objective, h["control_graph_hash"],
             h["loop_spec_hash"], h["policy_hash"], h["schemas_hash"],
             h["prompts_hash"], h["registry_build"], now(), now()))
        _event(conn, run_id, "RUN_CREATED", {"objective": objective, "hashes": h})


def get_run(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None


def check_drift(run: dict) -> list[str]:
    current = config_hashes()
    return [f for f in DRIFT_FIELDS if run.get(f) and run[f] != current[f]]


def update_run(run_id: str, *, node=None, status=None, verdict=None,
               terminal_reason=None, cycle=None, bump_revision=False) -> None:
    sets, vals = ["updated_at=?"], [now()]
    if node is not None:
        sets.append("current_graph_node=?"); vals.append(node)
    if status is not None:
        sets.append("status=?"); vals.append(status)
        if status == "stopped":
            sets.append("terminal_at=?"); vals.append(now())
    if verdict is not None:
        sets.append("verdict=?"); vals.append(verdict)
    if terminal_reason is not None:
        sets.append("terminal_reason=?"); vals.append(terminal_reason)
    if cycle is not None:
        sets.append("cycle=?"); vals.append(cycle)
    if bump_revision:
        sets.append("revision=revision+1")
    vals.append(run_id)
    with connect() as conn:
        conn.execute(f"UPDATE runs SET {', '.join(sets)} WHERE run_id=?", vals)


# ---------------------------------------------------------------- actions --
def pending_action(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM actions WHERE run_id=? AND status IN ('PENDING','RUNNING')",
            (run_id,)).fetchone()
        return dict(row) if row else None


def create_action(run_id: str, node: str, action_type: str, request: dict) -> dict:
    """Persist PENDING before the agent ever sees the directive. If a live
    action already exists (crash/retry), return THAT one — never a duplicate."""
    existing = pending_action(run_id)
    if existing:
        with connect() as conn:
            conn.execute("UPDATE actions SET attempt_count=attempt_count+1 WHERE action_id=?",
                         (existing["action_id"],))
        existing["attempt_count"] += 1
        return existing
    run = get_run(run_id) or {}
    key = _h({"run": run_id, "node": node, "type": action_type,
              "revision": run.get("revision", 0)})
    action_id = "act_" + key
    with connect() as conn:
        conn.execute("""INSERT INTO actions
            (action_id,run_id,graph_node,action_type,idempotency_key,status,
             request_json,attempt_count,created_at)
            VALUES (?,?,?,?,?,'PENDING',?,1,?)""",
            (action_id, run_id, node, action_type, key,
             json.dumps(request, ensure_ascii=False), now()))
        _event(conn, run_id, "ACTION_CREATED",
               {"action_type": action_type, "node": node}, action_id=action_id)
    return {"action_id": action_id, "run_id": run_id, "graph_node": node,
            "action_type": action_type, "status": "PENDING",
            "request_json": json.dumps(request), "attempt_count": 1}


def apply_submission(run_id: str, node: str, payload: dict) -> tuple[str, str]:
    """Idempotent submission gate. Returns (disposition, detail):
       APPLY            first time this payload lands for this node
       ALREADY_APPLIED  exact same payload re-submitted (safe retry)
       CONFLICT         a different payload for an already-answered action
                        while the run has not advanced past the node
    """
    payload_hash = _h(payload)
    with connect() as conn:
        # ONE-WRITER LAW enforced, not assumed: take the write lock before
        # the SELECTs so two submitters cannot both read "no prior answer"
        # and both apply.
        conn.execute("BEGIN IMMEDIATE")
        exact = conn.execute(
            "SELECT * FROM actions WHERE run_id=? AND graph_node=? AND result_hash=? "
            "AND status='SUCCEEDED'", (run_id, node, payload_hash)).fetchone()
        if exact:
            return "ALREADY_APPLIED", exact["action_id"]
        run = conn.execute("SELECT current_graph_node FROM runs WHERE run_id=?",
                           (run_id,)).fetchone()
        prior = conn.execute(
            "SELECT * FROM actions WHERE run_id=? AND graph_node=? AND status='SUCCEEDED' "
            "ORDER BY completed_at DESC LIMIT 1", (run_id, node)).fetchone()
        run_full = conn.execute("SELECT current_graph_node, revision FROM runs WHERE run_id=?",
                                (run_id,)).fetchone()
        if (prior and run_full and run_full["current_graph_node"] == node
                and prior["result_hash"] and prior["result_hash"] != payload_hash
                and prior["revision_at"] == run_full["revision"]):
            # an answer was already applied during THIS visit to the node and
            # the graph has not advanced — two competing answers to one question
            return "CONFLICT", prior["action_id"]
        live = conn.execute(
            "SELECT * FROM actions WHERE run_id=? AND status IN ('PENDING','RUNNING')",
            (run_id,)).fetchone()
        if live and live["graph_node"] == node:
            rev = conn.execute("SELECT revision FROM runs WHERE run_id=?", (run_id,)).fetchone()
            conn.execute("UPDATE actions SET status='SUCCEEDED', result_hash=?, completed_at=?, "
                         "revision_at=? WHERE action_id=?",
                         (payload_hash, now(), rev["revision"] if rev else 0, live["action_id"]))
            _event(conn, run_id, "ACTION_COMPLETED", {"node": node},
                   action_id=live["action_id"], payload_hash=payload_hash)
            return "APPLY", live["action_id"]
        # step-first flow not used: record the submission itself as an action
        key = _h({"run": run_id, "node": node, "payload": payload_hash, "kind": "submission"})
        action_id = "act_" + key
        rev = conn.execute("SELECT revision FROM runs WHERE run_id=?", (run_id,)).fetchone()
        conn.execute("""INSERT OR IGNORE INTO actions
            (action_id,run_id,graph_node,action_type,idempotency_key,status,
             result_hash,attempt_count,revision_at,created_at,completed_at)
            VALUES (?,?,?,?,?,'SUCCEEDED',?,1,?,?,?)""",
            (action_id, run_id, node, "SUBMISSION", key, payload_hash,
             rev["revision"] if rev else 0, now(), now()))
        _event(conn, run_id, "SUBMISSION_APPLIED", {"node": node},
               action_id=action_id, payload_hash=payload_hash)
        return "APPLY", action_id


# ---------------------------------------------------- context envelopes ----
def attach_envelope(action_id: str, run_id: str, node: str, envelope: dict) -> None:
    """Freeze the ContextEnvelope with its PENDING action — write-once. A
    crash-resume must see the SAME context, never a fresh recompile that
    happens to be slightly different (docs/10 reasoning-replay stability)."""
    with connect() as conn:
        conn.execute("""INSERT OR IGNORE INTO context_envelopes
            (action_id,run_id,graph_node,context_hash,manifest_json,envelope_json,created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (action_id, run_id, node,
             (envelope.get("manifest") or {}).get("context_hash", ""),
             json.dumps(envelope.get("manifest") or {}, ensure_ascii=False),
             json.dumps(envelope, ensure_ascii=False), now()))


def get_envelope(action_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT envelope_json FROM context_envelopes WHERE action_id=?",
                           (action_id,)).fetchone()
        return json.loads(row["envelope_json"]) if row else None


def load_work_nodes(run_id: str, node_type: str | None = None) -> list[dict]:
    """Read-side of the Work Graph mirror — context backfill recovers known
    canonical state through THIS api (context.py never touches SQLite)."""
    q = "SELECT node_type, payload_json FROM work_nodes WHERE run_id=?"
    vals: list = [run_id]
    if node_type:
        q += " AND node_type=?"
        vals.append(node_type)
    with connect() as conn:
        return [dict(json.loads(r["payload_json"]), _node_type=r["node_type"])
                for r in conn.execute(q, vals).fetchall()]


def run_audit(run_id: str) -> dict:
    """Read-side qualification audit (docs/15): everything qualify.py needs
    from SQLite, through the one module allowed to know SQLite exists."""
    with connect() as conn:
        run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        actions = conn.execute(
            "SELECT action_id, action_type, status FROM actions WHERE run_id=?",
            (run_id,)).fetchall()
        live = [a for a in actions if a["status"] in ("PENDING", "RUNNING")]
        seqs = [r["sequence"] for r in conn.execute(
            "SELECT sequence FROM events WHERE run_id=? ORDER BY sequence", (run_id,))]
        etypes = {}
        for r in conn.execute("SELECT event_type, COUNT(*) c FROM events WHERE run_id=? "
                              "GROUP BY event_type", (run_id,)):
            etypes[r["event_type"]] = r["c"]
        env_actions = {r["action_id"] for r in conn.execute(
            "SELECT action_id FROM context_envelopes WHERE run_id=?", (run_id,))}
        model_actions = [a for a in actions if a["action_type"] != "SUBMISSION"]
        checks = conn.execute("SELECT COUNT(*) c FROM checks WHERE run_id=?",
                              (run_id,)).fetchone()["c"]
        cps = conn.execute("SELECT COUNT(*) c FROM events WHERE run_id=? AND "
                           "event_type='CHECKPOINT'", (run_id,)).fetchone()["c"]
    return {
        "run": dict(run) if run else None,
        "actions_total": len(actions),
        "live_actions": len(live),
        "model_actions": len(model_actions),
        "model_actions_with_envelope": len([a for a in model_actions
                                            if a["action_id"] in env_actions]),
        "events_monotonic": seqs == sorted(seqs) and len(seqs) == len(set(seqs)),
        "event_types": etypes,
        "checks": checks,
        "checkpoints": cps,
    }


def candidate_recurrence() -> list[dict]:
    """Cross-run RegistryCandidate recurrence (docs/17 triggers). Groups the
    Work Graph's REGISTRY_CANDIDATE rows by (kind, name) and counts DISTINCT
    runs — 20 emissions from one run are one voice."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT payload_json, run_id FROM work_nodes WHERE node_type='REGISTRY_CANDIDATE'"
        ).fetchall()
    seen: dict[tuple, set] = {}
    for r in rows:
        try:
            c = json.loads(r["payload_json"])
        except json.JSONDecodeError:
            continue
        key = (c.get("kind") or "?", c.get("name") or "?")
        seen.setdefault(key, set()).add(r["run_id"])
    return sorted(({"kind": k, "name": n, "runs": len(v)}
                   for (k, n), v in seen.items()),
                  key=lambda x: -x["runs"])


def load_candidates(names: list[str]) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT payload_json FROM work_nodes WHERE node_type='REGISTRY_CANDIDATE'"
        ).fetchall()
    out, want = [], set(names)
    for r in rows:
        try:
            c = json.loads(r["payload_json"])
        except json.JSONDecodeError:
            continue
        if c.get("name") in want and all(c.get("id") != x.get("id") for x in out):
            out.append(c)
    return out


def latest_checkpoint(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM events WHERE run_id=? AND event_type='CHECKPOINT' "
            "ORDER BY sequence DESC LIMIT 1", (run_id,)).fetchone()
        return json.loads(row["payload_json"]) if row and row["payload_json"] else None


# ------------------------------------------------------- events and checks --
def _event(conn, run_id: str, event_type: str, payload: dict | None = None,
           action_id: str | None = None, subject_id: str | None = None,
           payload_hash: str | None = None) -> None:
    seq = conn.execute("SELECT COALESCE(MAX(sequence),0)+1 AS s FROM events WHERE run_id=?",
                       (run_id,)).fetchone()["s"]
    conn.execute("""INSERT INTO events
        (run_id,sequence,event_type,actor,subject_id,action_id,payload_json,payload_hash,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (run_id, seq, event_type, "controller", subject_id, action_id,
         json.dumps(payload, ensure_ascii=False) if payload else None,
         payload_hash, now()))


def record_event(run_id: str, event_type: str, payload: dict | None = None, **kw) -> None:
    with connect() as conn:
        _event(conn, run_id, event_type, payload, **kw)


def write_check(run_id: str, check_type: str, level: str, status: str,
                metrics: dict, reasons: list[str] | None = None,
                subject_id: str | None = None) -> None:
    with connect() as conn:
        conn.execute("""INSERT INTO checks
            (run_id,subject_type,subject_id,check_type,verification_level,status,
             metrics_json,reason_codes_json,input_hash,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (run_id, None, subject_id, check_type, level, status,
             json.dumps(metrics, ensure_ascii=False),
             json.dumps(reasons or [], ensure_ascii=False), _h(metrics), now()))


# ------------------------------------------------------------- work graph --
_NODE_TYPES = {"evaluations": "SEMANTIC_EVALUATION",
               "hypotheses": "BRIDGE_HYPOTHESIS", "gaps": "EVIDENCE_GAP",
               "queries": "RESEARCH_QUERY", "observations": "OBSERVATION",
               "mechanisms": "PRODUCT_MECHANISM", "product_candidates": "PRODUCT_CANDIDATE",
               "supplier_candidates": "SUPPLIER_CANDIDATE", "leads": "LEAD",
               "product_concepts": "PRODUCT_CONCEPT",
               "registry_candidates": "REGISTRY_CANDIDATE",
               # loadout mode
               "lived_situations": "LIVED_SITUATION", "slot_candidates": "PRODUCT_SLOT",
               "frontier_branches": "FRONTIER_BRANCH",
               # commercial-intelligence layer (docs/11) — downstream projections,
               # first-class Work Graph objects, never research evidence
               "market_analysis": "ANALYSIS_CLAIM", "style_intelligence": "STYLE_SIGNAL",
               "market_angles": "MARKET_ANGLE", "product_angles": "PRODUCT_ANGLE",
               "style_angles": "STYLE_ANGLE", "collection_angles": "COLLECTION_ANGLE",
               "ad_angles": "AD_ANGLE", "creative_briefs": "AD_CREATIVE_BRIEF",
               "storefront_strategies": "STOREFRONT_STRATEGY",
               "analysis_chains": "ANALYSIS_CHAIN",
               # discovery modes (docs/12-14)
               "field_signals": "MARKET_SIGNAL", "trend_signals": "TREND_SIGNAL",
               "corpus_signals": "CORPUS_SIGNAL", "supply_signals": "SUPPLY_SIGNAL",
               "commerce_signals": "COMMERCE_SIGNAL",
               "market_scopes": "MARKET_SCOPE", "query_nodes": "QUERY_NODE",
               "whitespace_hypotheses": "WHITESPACE_HYPOTHESIS",
               "signal_divergences": "SIGNAL_DIVERGENCE",
               "promoted_scopes": "MARKET_SCOPE_RECOMMENDATION",
               "product_claims": "PRODUCT_CLAIM",
               "product_meanings": "PRODUCT_MEANING",
               "market_bridges": "MARKET_BRIDGE",
               "market_reframes": "MARKET_REFRAME",
               "demand_gaps": "DEMAND_GAP", "demand_reroutes": "DEMAND_REROUTE",
               "capture_assessments": "CAPTURE_FEASIBILITY"}
_NODE_TYPES["corpus_answers"] = "CORPUS_ANSWER"


def sync_work_nodes(run_id: str, state: dict) -> int:
    """Mirror state.data objects as typed Work Graph rows (upsert by id)."""
    cycle = state["rounds"]["research"]
    n = 0
    with connect() as conn:
        for key, ntype in _NODE_TYPES.items():
            for item in state["data"].get(key) or []:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                payload = json.dumps(item, ensure_ascii=False, sort_keys=True)
                sh = _h(payload)
                row = conn.execute("SELECT semantic_hash FROM work_nodes WHERE run_id=? AND node_id=?",
                                   (run_id, item["id"])).fetchone()
                if row and row["semantic_hash"] == sh:
                    continue
                conn.execute("""INSERT INTO work_nodes
                    (node_id,run_id,node_type,status,authority_class,semantic_hash,
                     payload_json,created_cycle,updated_cycle,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(run_id,node_id) DO UPDATE SET
                      status=excluded.status, authority_class=excluded.authority_class,
                      semantic_hash=excluded.semantic_hash, payload_json=excluded.payload_json,
                      updated_cycle=excluded.updated_cycle, updated_at=excluded.updated_at""",
                    (item["id"], run_id, ntype, item.get("status"),
                     item.get("authority") or item.get("authority_class"), sh, payload,
                     cycle, cycle, now(), now()))
                n += 1
    return n
