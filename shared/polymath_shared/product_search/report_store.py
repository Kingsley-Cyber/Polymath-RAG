"""PRODUCT-DECISION-REPORT-V1 (B4b, plan §4.6): the decision reports' store — migration 0068 (`product_reports`,
`product_report_uploads`).

Every function takes an open psycopg connection from `polymath_shared.db.tx`; the caller owns the transaction (the shape of the
adapter store). What is decided here:
  * a report is minted with `report_id` = 'rpt_' + 24 hex and its first upload token: `create` returns the raw token once. A
    later token is minted by `mint_token` (the status route mints one for a caller without a token, at most once per report per
    MINT_EVERY_S: contract C1). An upload token is NOT one-time: any token the report holds uploads (or replaces) any packet of
    the current round until the report's capability expires. ONLY sha256 hashes are stored (`upload_tokens`: [{sha256,
    minted_at, used_at}], a database read never yields a capability), at most MAX_TOKENS: past the cap the least recently
    ACTIVE token (minted or last used) is dropped, so a script that is still uploading keeps its token. The token list departs
    from plan §4.6's single `upload_token_sha256` (unapproved; reported to the owner). Every token of a report expires with the
    report's capability, UPLOAD_TTL (6 h) after the report is made;
  * PRIVACY (the rule of adapter runs, migration 0066): `principal_id` None = the owner / a trusted-local caller, who reaches every
    report; a principal reaches only the reports it owns. A missing report and another principal's report are ONE answer
    (`UnknownReport`), so a report's existence is never disclosed;
  * the upload capability (`by_capability`): sha256(token) must be one of the report's held hashes (each compared in constant
    time), and the capability must not have expired. A wrong token, a dropped token, a token of another report and an unknown
    report are one answer (403);
  * an upload is idempotent per (report_id, packet_id): a re-upload REPLACES the packet's row — except that an OK row is never
    replaced by a worse one (EMPTY, BLOCKED, OUTPUT_TOO_LARGE, ...: a keyless re-run of a round's script often hits the readers'
    rate limits); the answer says when the earlier OK packet was kept. At most MAX_UPLOAD_BYTES (2 MiB) per upload and
    MAX_UPLOADS (300) distinct packets per report (a re-upload of a packet already held does not count again). The caller holds
    the report row's lock (`get(..., for_update=True)`) while it adds, so the count cannot race;
  * status moves only along TRANSITIONS, as a compare-and-set on the current status (a concurrent change is refused, never
    overwritten); the move to `compiling` stamps `compile_started_at` (a compile older than the service's stale limit by it was
    lost and may run again);
  * U+0000 never reaches Postgres (jsonb and text refuse it): every JSON value and the HTML are stripped of it before a write.
The JSON shapes kept in the columns are the service's (orchestrator/api/product_report.py): `candidates` {status, source, items,
error, ...}, `host` {status, started_at, finished_at, error, data}, `model` {compiled_at, decision, ...}, `verdicts` {by, items}.
No network, no model; nothing here decides a number."""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Iterable, Mapping
from typing import Any

CONTRACT = "product-report-v1"
STATUSES = ("collecting", "compiling", "compiled", "failed")
#: a report's status moves only along these edges (compile may be re-run: compiled -> compiling, failed -> compiling)
TRANSITIONS: dict[str, frozenset[str]] = {
    "collecting": frozenset({"compiling", "failed"}),
    "compiling": frozenset({"compiled", "failed"}),
    "compiled": frozenset({"compiling"}),
    "failed": frozenset({"compiling"}),
}
UPLOAD_TTL = _dt.timedelta(hours=6)
#: the upload tokens a report holds at once (their hashes): past it the least recently minted-or-used is dropped
MAX_TOKENS = 30
#: contract C1: a caller without a token gets a fresh one at most once per report per this many seconds
MINT_EVERY_S = 60
#: the same number as agent_reach.MAX_REPORT_BYTES (the parser's cap; a test pins the two together)
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_UPLOADS = 300
MAX_ROUND = 2
#: the per-candidate parsed lists of the decision bundle (plan §4.4)
SOURCES = ("reddit", "amazon", "ebay", "alibaba")
REPORT_ID_RE = re.compile(r"^rpt_[0-9a-f]{24}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")          # secrets.token_urlsafe(32)
PACKET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")

_COLS = ("report_id", "owner_principal_id", "status", "request", "candidates", "host", "model", "verdicts", "upload_tokens",
         "upload_expires_at", "round", "compile_started_at", "created_at", "updated_at")
_UPLOAD_COLS = ("report_id", "packet_id", "round", "source", "kind", "received_at", "bytes", "sha256", "status", "parsed", "refused")
_JSON_COLS = ("request", "candidates", "host", "model", "verdicts", "upload_tokens", "parsed", "refused")


class UnknownReport(LookupError):
    """No such report FOR THIS CALLER: a missing report and another principal's report are deliberately one answer."""


class UploadRefused(Exception):
    """A typed refusal of an upload (or of a capability check): `code`, HTTP `status`, a plain `message`."""

    def __init__(self, code: str, status: int, message: str) -> None:
        super().__init__(message)
        self.code, self.status, self.message = code, status, message

    def detail(self) -> dict[str, str]:
        return {"error_code": self.code, "message": self.message}


class MintTooSoon(Exception):
    """Contract C1: this report minted a token less than MINT_EVERY_S ago; `mint_after` is when a mint is allowed again."""

    def __init__(self, mint_after: _dt.datetime) -> None:
        super().__init__(f"a token was minted for this report less than {MINT_EVERY_S} s ago")
        self.mint_after = mint_after


class BadTransition(RuntimeError):
    """The status cannot move from `current` to `wanted` (an illegal edge, or the status changed under the caller)."""

    def __init__(self, current: str | None, wanted: str) -> None:
        super().__init__(f"product report status cannot move {current!r} -> {wanted!r}")
        self.current, self.wanted = current, wanted


# ─────────────────────────────────────────────────────────── pure helpers
def now() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def iso(value: Any) -> str | None:
    """A timestamp as UTC ISO-8601 with a Z (seconds); a string is passed through; None stays None."""
    if value is None or isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=_dt.UTC)
    return value.astimezone(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_report_id() -> str:
    return "rpt_" + secrets.token_hex(12)


def new_upload_token() -> str:
    return secrets.token_urlsafe(32)


def stamp(value: _dt.datetime | None = None) -> str:
    """A token's time, to the microsecond (fixed width: stamps order as strings)."""
    t = (value or now()).astimezone(_dt.UTC)
    return t.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def tokens_of(row: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    return [dict(e) for e in (row or {}).get("upload_tokens") or [] if isinstance(e, Mapping)]


def held(row: Mapping[str, Any] | None, token: Any) -> dict[str, Any] | None:
    """The held entry whose sha256 is the token's, or None (every entry compared in constant time; a malformed token is none)."""
    if not isinstance(token, str) or not TOKEN_RE.match(token):
        return None
    digest, found = token_sha256(token), None
    for entry in tokens_of(row):
        if hmac.compare_digest(digest, str(entry.get("sha256") or "")):
            found = entry
    return found


def last_minted(row: Mapping[str, Any] | None) -> _dt.datetime | None:
    """When the report's newest token was minted (None when it holds none)."""
    stamps = [str(e.get("minted_at")) for e in tokens_of(row) if e.get("minted_at")]
    return _dt.datetime.fromisoformat(max(stamps)) if stamps else None


def _activity(entry: Mapping[str, Any]) -> str:
    return max(str(entry.get("minted_at") or ""), str(entry.get("used_at") or ""))


def with_token(entries: Iterable[Mapping[str, Any]], digest: str, at: _dt.datetime | None = None,
               cap: int = MAX_TOKENS) -> list[dict[str, Any]]:
    """`entries` plus a new token's entry; past `cap`, the least recently active (minted or last used) are dropped, the oldest
    first on a tie. Mint order is kept."""
    out = [dict(e) for e in entries] + [{"sha256": digest, "minted_at": stamp(at), "used_at": None}]
    while len(out) > cap:
        out.pop(min(range(len(out)), key=lambda i: (_activity(out[i]), i)))
    return out


def touched(entries: Iterable[Mapping[str, Any]], digest: str, at: _dt.datetime | None = None) -> list[dict[str, Any]]:
    """`entries` with the token `digest` marked used now (its upload keeps it among the active ones)."""
    return [{**dict(e), "used_at": stamp(at)} if e.get("sha256") == digest else dict(e) for e in entries]


def token_sha256(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def content_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def strip_nul(value: Any) -> Any:
    """`value` with every U+0000 removed from its strings (keys included): Postgres's jsonb and text refuse that character."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, Mapping):
        return {strip_nul(k) if isinstance(k, str) else k: strip_nul(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [strip_nul(v) for v in value]
    return value


def _j(value: Any) -> str:
    return json.dumps(strip_nul(value), sort_keys=True, ensure_ascii=False, default=str)


def uploads_digest(rows: Iterable[Mapping[str, Any]]) -> str:
    """The identity of a set of stored uploads: sha256 over their sorted (packet_id, sha256) pairs. A compiled report is stale
    when the uploads' digest no longer equals the one its compile read (timestamps cut to the second cannot say that)."""
    pairs = sorted(f"{r.get('packet_id')}:{r.get('sha256')}" for r in rows)
    return hashlib.sha256("\n".join(pairs).encode("utf-8")).hexdigest()


def _load(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _row(cols: Iterable[str], values: Iterable[Any]) -> dict[str, Any]:
    d = dict(zip(cols, values))
    for k in _JSON_COLS:
        if k in d:
            d[k] = _load(d[k])
    return d


def expired(row: Mapping[str, Any], at: _dt.datetime | None = None) -> bool:
    exp = row.get("upload_expires_at")
    if isinstance(exp, str):
        exp = _dt.datetime.fromisoformat(exp)
    return exp is None or (at or now()) >= exp


def capability_state(row: Mapping[str, Any], token: str | None, at: _dt.datetime | None = None) -> str:
    """A token a status caller sent back (X-Upload-Token): 'absent' | 'invalid' | 'expired' | 'valid'."""
    if not token:
        return "absent"
    if held(row, token) is None:
        return "invalid"
    return "expired" if expired(row, at) else "valid"


def check_transition(current: str | None, wanted: str) -> None:
    if wanted not in STATUSES or current not in TRANSITIONS or wanted not in TRANSITIONS[current]:
        raise BadTransition(current, wanted)


def upload_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """{total, by_round: {"1": n, ...}, by_source: {source: {status: n}}} over the stored upload rows (counts only)."""
    total, by_round, by_source = 0, {}, {}
    for r in rows:
        total += 1
        key = str(r.get("round"))
        by_round[key] = by_round.get(key, 0) + 1
        src = by_source.setdefault(str(r.get("source")), {})
        st = str(r.get("status") or "NONE")
        src[st] = src.get(st, 0) + 1
    return {"total": total, "by_round": dict(sorted(by_round.items())),
            "by_source": {k: dict(sorted(v.items())) for k, v in sorted(by_source.items())}}


def round_targets(rows: Iterable[Mapping[str, Any]], round_: int = 1) -> list[dict[str, Any]]:
    """The next round's page targets: every `next_targets` entry the parser found in this round's uploads, each tagged with the
    candidate its packet belongs to; packet order, then the parser's order; one entry per (candidate, url)."""
    out, seen = [], set()
    for r in sorted((r for r in rows if int(r.get("round") or 0) == round_), key=lambda r: str(r.get("packet_id"))):
        parsed = r.get("parsed") if isinstance(r.get("parsed"), Mapping) else {}
        cid = parsed.get("candidate_id")
        for t in parsed.get("next_targets") or []:
            if not isinstance(t, Mapping) or not isinstance(t.get("url"), str) or not t.get("url"):
                continue
            key = (cid, t["url"])
            if key in seen:
                continue
            seen.add(key)
            out.append({**dict(t), "candidate_id": cid})
    return out


def parsed_by_candidate(rows: Iterable[Mapping[str, Any]], candidate_ids: Iterable[str]) -> dict[str, dict[str, list[Any]]]:
    """The bundle's `parsed` (plan §4.4): {candidate_id: {reddit: [...], amazon: [...], ebay: [...], alibaba: [...]}} — every
    record the parser admitted, round 1 then round 2, packet order. A packet whose candidate is not in the report is left out."""
    out: dict[str, dict[str, list[Any]]] = {cid: {s: [] for s in SOURCES} for cid in candidate_ids}
    for r in sorted(rows, key=lambda r: (int(r.get("round") or 0), str(r.get("packet_id")))):
        parsed = r.get("parsed") if isinstance(r.get("parsed"), Mapping) else {}
        cid = parsed.get("candidate_id")
        if cid not in out:
            continue
        out[cid].setdefault(str(r.get("source")), []).extend(x for x in parsed.get("records") or [] if isinstance(x, Mapping))
    return out


# ─────────────────────────────────────────────────────────── reports
def create(conn, *, owner_principal_id: str | None, request: Mapping[str, Any], candidates: Mapping[str, Any],
           host: Mapping[str, Any] | None = None, at: _dt.datetime | None = None) -> tuple[dict[str, Any], str]:
    """Mint a report in status `collecting`, round 1. Returns (the row, the RAW upload token): the token is returned here once and
    only its sha256 is stored; it expires UPLOAD_TTL after `at`."""
    t = at or now()
    report_id, token = new_report_id(), new_upload_token()
    conn.execute(
        """INSERT INTO product_reports (report_id, owner_principal_id, status, request, candidates, host, upload_tokens,
                                        upload_expires_at, round, created_at, updated_at)
           VALUES (%s, %s, 'collecting', %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, 1, %s, %s)""",
        (report_id, owner_principal_id, _j(dict(request)), _j(dict(candidates)), _j(dict(host)) if host is not None else None,
         _j(with_token([], token_sha256(token), t)), t + UPLOAD_TTL, t, t))
    return get(conn, report_id, principal_id=None), token


def mint_token(conn, report_id: str, *, at: _dt.datetime | None = None, every_s: float | None = None) -> str:
    """A fresh upload token for a report: its hash joins the held ones (the row is locked, so concurrent mints never lose one;
    past MAX_TOKENS the least recently active is dropped). With `every_s`, `MintTooSoon` when the report's newest token is younger
    than that (contract C1: at most one mint per report per minute for callers without a token). Returns the RAW token: shown
    once, never stored. The caller has already checked who may see the report; `UnknownReport` when it does not exist."""
    row = conn.execute("SELECT upload_tokens FROM product_reports WHERE report_id = %s FOR UPDATE", (report_id,)).fetchone()
    if row is None:
        raise UnknownReport(report_id)
    held_now = tokens_of({"upload_tokens": _load(row[0])})
    t = at or now()
    newest = last_minted({"upload_tokens": held_now})
    if every_s is not None and newest is not None and t < newest + _dt.timedelta(seconds=every_s):
        raise MintTooSoon(newest + _dt.timedelta(seconds=every_s))
    token = new_upload_token()
    conn.execute("UPDATE product_reports SET upload_tokens = %s::jsonb WHERE report_id = %s",
                 (_j(with_token(held_now, token_sha256(token), t)), report_id))
    return token


def mark_used(conn, report_id: str, token: str, *, at: _dt.datetime | None = None) -> None:
    """The token's last use is now. The row is locked (FOR UPDATE: a concurrent mint is never overwritten); an upload already
    holds that lock (`by_capability(..., for_update=True)`), which this re-takes at no cost."""
    row = conn.execute("SELECT upload_tokens FROM product_reports WHERE report_id = %s FOR UPDATE", (report_id,)).fetchone()
    if row is not None:
        conn.execute("UPDATE product_reports SET upload_tokens = %s::jsonb WHERE report_id = %s",
                     (_j(touched(tokens_of({"upload_tokens": _load(row[0])}), token_sha256(token), at)), report_id))


def get(conn, report_id: str, *, principal_id: str | None, for_update: bool = False, with_html: bool = False) -> dict[str, Any]:
    """One report for this caller (no principal = the owner: any report; a principal: only its own). `UnknownReport` otherwise."""
    if not isinstance(report_id, str) or not REPORT_ID_RE.match(report_id):
        raise UnknownReport(report_id)
    cols = _COLS + (("html",) if with_html else ())
    row = conn.execute(
        f"""SELECT {", ".join(cols)} FROM product_reports
             WHERE report_id = %s AND (%s::text IS NULL OR owner_principal_id = %s)
             {"FOR UPDATE" if for_update else ""}""", (report_id, principal_id, principal_id)).fetchone()
    if row is None:
        raise UnknownReport(report_id)
    return _row(cols, row)


def well_formed_capability(report_id: Any, token: Any) -> bool:
    return isinstance(report_id, str) and bool(REPORT_ID_RE.match(report_id)) and isinstance(token, str) and bool(TOKEN_RE.match(token))


def check_capability(row: Mapping[str, Any] | None, token: str, at: _dt.datetime | None = None) -> None:
    """403 UPLOAD_TOKEN_INVALID for no report, a malformed token or a token whose sha256 the report does not hold (another
    report's token and a dropped one included: one answer for all); 410 UPLOAD_EXPIRED once the report's capability has expired
    (said only to a holder of a held token). Every compare is constant-time."""
    if row is None or held(row, token) is None:
        raise UploadRefused("UPLOAD_TOKEN_INVALID", 403, "this upload link is not valid for this report")
    if expired(row, at):
        raise UploadRefused("UPLOAD_EXPIRED", 410, "this report's upload link has expired (links last 6 hours): compile the report "
                                                   "with what was uploaded, or start a new report")


def check_upload(size: int, packet_id: str, *, replaced: bool, held: int) -> None:
    """413 UPLOAD_TOO_LARGE over MAX_UPLOAD_BYTES; 409 UPLOAD_LIMIT_REACHED for a NEW packet once MAX_UPLOADS packets are held (a
    re-upload replaces and never counts again); 404 UNKNOWN_PACKET for a malformed packet id."""
    if size > MAX_UPLOAD_BYTES:
        raise UploadRefused("UPLOAD_TOO_LARGE", 413, f"an upload holds at most {MAX_UPLOAD_BYTES} bytes")
    if not isinstance(packet_id, str) or not PACKET_ID_RE.match(packet_id):
        raise UploadRefused("UNKNOWN_PACKET", 404, "no such packet in this report's fetch plan")
    if not replaced and held >= MAX_UPLOADS:
        raise UploadRefused("UPLOAD_LIMIT_REACHED", 409, f"a report holds at most {MAX_UPLOADS} uploaded packets")


def by_capability(conn, report_id: str, token: str, *, at: _dt.datetime | None = None, for_update: bool = False) -> dict[str, Any]:
    """The report an upload capability opens (`check_capability`: one 403 for a wrong token, another report's token and an unknown
    report; 410 once expired)."""
    if not well_formed_capability(report_id, token):
        check_capability(None, token, at)
    row = conn.execute(f"SELECT {', '.join(_COLS)} FROM product_reports WHERE report_id = %s {'FOR UPDATE' if for_update else ''}",
                       (report_id,)).fetchone()
    d = _row(_COLS, row) if row is not None else None
    check_capability(d, token, at)
    return d


def list_for(conn, principal_id: str | None, *, limit: int = 50, before: str | None = None) -> list[dict[str, Any]]:
    """Newest first. A principal sees only its own reports; no principal (the owner / a trusted-local caller) sees every report.
    `before` is a report_id cursor. No HTML and no capability hash leave the store here."""
    where, args = ["TRUE"], []
    if principal_id is not None:
        where.append("r.owner_principal_id = %s")
        args.append(principal_id)
    if before:
        where.append("(r.created_at, r.report_id) < (SELECT created_at, report_id FROM product_reports WHERE report_id = %s)")
        args.append(before)
    cols = ("report_id", "owner_principal_id", "status", "request", "candidates", "round", "created_at", "updated_at",
            "upload_expires_at", "compiled", "compiled_at", "uploads")
    rows = conn.execute(
        f"""SELECT r.report_id, r.owner_principal_id, r.status, r.request, r.candidates, r.round, r.created_at, r.updated_at,
                   r.upload_expires_at, r.html IS NOT NULL, r.model->>'compiled_at',
                   (SELECT count(*) FROM product_report_uploads u WHERE u.report_id = r.report_id)
              FROM product_reports r
             WHERE {" AND ".join(where)}
             ORDER BY r.created_at DESC, r.report_id DESC LIMIT %s""", (*args, max(1, min(int(limit), 200)))).fetchall()
    return [_row(cols, r) for r in rows]


def html_of(conn, report_id: str, *, principal_id: str | None) -> str | None:
    """The stored HTML for this caller (None = not compiled yet); `UnknownReport` as `get`."""
    return get(conn, report_id, principal_id=principal_id, with_html=True).get("html")


def _touch(conn, report_id: str, sets: str, args: tuple[Any, ...]) -> int:
    cur = conn.execute(f"UPDATE product_reports SET {sets}, updated_at = now() WHERE report_id = %s", (*args, report_id))
    return int(getattr(cur, "rowcount", 1) or 0)


def save_candidates(conn, report_id: str, candidates: Mapping[str, Any]) -> None:
    _touch(conn, report_id, "candidates = %s::jsonb", (_j(dict(candidates)),))


def save_host(conn, report_id: str, host: Mapping[str, Any]) -> None:
    _touch(conn, report_id, "host = %s::jsonb", (_j(dict(host)),))


def save_model(conn, report_id: str, model: Mapping[str, Any]) -> None:
    _touch(conn, report_id, "model = %s::jsonb", (_j(dict(model)),))


def save_verdicts(conn, report_id: str, verdicts: Mapping[str, Any] | None) -> None:
    _touch(conn, report_id, "verdicts = %s::jsonb", (_j(dict(verdicts)) if verdicts is not None else None,))


def save_html(conn, report_id: str, html: str) -> None:
    _touch(conn, report_id, "html = %s", (str(html).replace("\x00", ""),))


def transition(conn, report_id: str, wanted: str, *, current: str, at: _dt.datetime | None = None) -> None:
    """Compare-and-set: move `current` -> `wanted` along TRANSITIONS, only if the row still holds `current`. The move to
    `compiling` stamps `compile_started_at` (`at`, default now)."""
    check_transition(current, wanted)
    if wanted == "compiling":
        cur = conn.execute("UPDATE product_reports SET status = %s, compile_started_at = %s, updated_at = now() "
                           "WHERE report_id = %s AND status = %s", (wanted, at or now(), report_id, current))
    else:
        cur = conn.execute("UPDATE product_reports SET status = %s, updated_at = now() WHERE report_id = %s AND status = %s",
                           (wanted, report_id, current))
    if int(getattr(cur, "rowcount", 0) or 0) != 1:
        raise BadTransition(current, wanted)


def advance_round(conn, report_id: str, *, current: int) -> bool:
    """Round `current` -> `current + 1` (at most MAX_ROUND), only if the row still holds `current`. True when it moved."""
    if current >= MAX_ROUND:
        return False
    cur = conn.execute("UPDATE product_reports SET round = %s, updated_at = now() WHERE report_id = %s AND round = %s",
                       (current + 1, report_id, current))
    return int(getattr(cur, "rowcount", 0) or 0) == 1


# ─────────────────────────────────────────────────────────── uploads
def uploads(conn, report_id: str, *, round_: int | None = None) -> list[dict[str, Any]]:
    sql = f"SELECT {', '.join(_UPLOAD_COLS)} FROM product_report_uploads WHERE report_id = %s"
    args: tuple[Any, ...] = (report_id,)
    if round_ is not None:
        sql += " AND round = %s"
        args += (round_,)
    return [_row(_UPLOAD_COLS, r) for r in conn.execute(sql + " ORDER BY round, packet_id", args).fetchall()]


def add_upload(conn, report_id: str, *, packet_id: str, round_: int, source: str, kind: str, raw: bytes, status: str,
               parsed: Mapping[str, Any] | None, refused: list[Any] | None, at: _dt.datetime | None = None) -> dict[str, Any]:
    """Store one packet's upload (a re-upload replaces the packet's row, unless the stored row is OK and this one is not: the
    OK packet is kept, `kept_earlier`). The caller holds the report row's lock. Refused: 413 UPLOAD_TOO_LARGE over
    MAX_UPLOAD_BYTES; 409 UPLOAD_LIMIT_REACHED for a NEW packet once MAX_UPLOADS packets are held. Returns {replaced,
    kept_earlier, bytes, sha256, uploads (packets held after this one)}."""
    check_upload(len(raw), packet_id, replaced=False, held=0)          # size and packet id first: nothing is read for a refusal
    replaced = conn.execute("SELECT 1 FROM product_report_uploads WHERE report_id = %s AND packet_id = %s",
                            (report_id, packet_id)).fetchone() is not None
    held = int(conn.execute("SELECT count(*) FROM product_report_uploads WHERE report_id = %s", (report_id,)).fetchone()[0])
    check_upload(len(raw), packet_id, replaced=replaced, held=held)
    digest = content_sha256(raw)
    written = conn.execute(
        """INSERT INTO product_report_uploads (report_id, packet_id, round, source, kind, received_at, bytes, sha256, status, parsed,
                                               refused)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
           ON CONFLICT (report_id, packet_id) DO UPDATE SET
               round = EXCLUDED.round, source = EXCLUDED.source, kind = EXCLUDED.kind, received_at = EXCLUDED.received_at,
               bytes = EXCLUDED.bytes, sha256 = EXCLUDED.sha256, status = EXCLUDED.status, parsed = EXCLUDED.parsed,
               refused = EXCLUDED.refused
           WHERE product_report_uploads.status <> 'OK' OR EXCLUDED.status = 'OK'
           RETURNING packet_id""",
        (report_id, packet_id, int(round_), source, kind, at or now(), len(raw), digest, status,
         _j(dict(parsed)) if parsed is not None else None, _j(list(refused)) if refused is not None else None)).fetchone()
    kept = written is None                                       # the stored row is OK and this upload is not: it stays
    conn.execute("UPDATE product_reports SET updated_at = now() WHERE report_id = %s", (report_id,))
    return {"replaced": replaced and not kept, "kept_earlier": kept, "bytes": len(raw), "sha256": digest,
            "uploads": held + (0 if replaced else 1)}
