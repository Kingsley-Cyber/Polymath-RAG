"""PRODUCT-DECISION-REPORT-V1 (B1, plan §4.2): the report's FETCH PLAN. Every Agent Reach read of one round becomes a packet with
its exact command, and ONE bash script runs them all on the USER's machine and uploads each raw output straight to Polymath, so
no fetched page ever passes through the agent's model (the owner, 2026-11-02: any agent, Claude, DeepSeek or Codex, can produce
the report). Polymath parses each upload with `agent_reach.parse_report_source`.

What a round reads (measured 2026-11-02, plan §1):
  round 1, per candidate: Reddit (2 Exa searches: Jina is blocked there), Amazon (1 Exa search + 1 Jina read of the search page
    with `X-With-Links-Summary: true`, the only way the page lists its products' links), Alibaba (1 Exa search), eBay (1 Exa
    search, only when the host has no eBay Browse API: Jina gets eBay's error page and Exa finds mostly non-US listings);
  round 2: product pages chosen from round 1 (`targets`, the parser's `next_targets` with their candidate), at most 3 Amazon and
    3 Alibaba pages per candidate, each read by Jina.

The script (POSIX shell syntax run by bash; bash 3.2 on macOS is enough) needs `mcporter` (Agent Reach's Exa channel) and `curl`:
  * pacing: keyless Exa answered 429 at 4 parallel calls and keyless Jina allows 20 reads a minute per IP, so without keys the
    script keeps at most 3 Exa calls in flight and starts at most one Jina read every 3 seconds; with EXA_API_KEY (10 QPS) it
    keeps 8 Exa calls in flight and with JINA_API_KEY (500 RPM) it starts 5 Jina reads a second at most (300 a minute);
  * one exact command per packet, the same text as the packet's `commands`; the keys enter only through the shell's own
    optional-argument form (`${EXA_API_KEY:+…}`): unset, the command is exactly the keyless one; the keys are never written into
    the script or the plan;
  * every value that comes from a candidate (the title, the search terms) or from a page (a round-2 URL, validated and rebuilt
    to its canonical form first) is single-quoted (`shlex.quote`) into the command: a term like `"; rm -rf ~; echo "` or
    `$(touch /tmp/x)` is a search word, never a command; curl runs with URL globbing off (`-g`) and a time limit;
  * each output is POSTed as `text/plain` to the upload capability with `?packet=<packet_id>`; fetched content is only ever
    written to a file and sent (no eval, no source, no command substitution of it); one summary line per packet; the script
    exits 0 even when a site blocks the reader (the upload records it) and 3 only when it cannot run at all (no curl);
  * an EMPTY output is uploaded too (an empty body, which the host records as EMPTY), so every packet of a round arrives and the
    round can complete (round 2 is minted when round 1 is complete); its summary line says so, and why when it was rate limited.
Pure and deterministic: the same arguments give the same plan, byte for byte (no clock, no randomness, no environment)."""
from __future__ import annotations

import hashlib
import re
import shlex
import unicodedata
from typing import Any
from urllib.parse import quote_plus, urlsplit

from polymath_shared.acquisition import agent_reach as AR

CONTRACT = "product-report-fetch-plan-v1"
ROUNDS = (1, 2)
MAX_CANDIDATES = 8                                     # the report's own cap (plan §3: max_products default 5, cap 8)
EXA_RESULTS = 8                                        # numResults of every Exa search (the probes of 2026-11-02 used 8)
ROUND2_PAGES = {"amazon": 3, "alibaba": 3}             # product pages per candidate in round 2 (plan §4.2)
#: keyless pacing (Exa answered 429 at 4 parallel calls; Jina allows 20 reads a minute per IP) and the pacing with the user's keys
LIMITS = {"exa_parallel": 3, "jina_per_minute": 20}
LIMITS_WITH_KEYS = {"exa_parallel": 8, "jina_per_minute": 300}
JINA_PARALLEL = {"keyless": 1, "with_keys": 5}         # Jina reads started together; the gap between starts keeps jina_per_minute
EXA_GAP_S = 1                                          # pause between Exa batches
JINA_TIMEOUT_S, UPLOAD_TIMEOUT_S, RETRY_AFTER_S = 90, 120, 5
EXA_KEYED_URL = "https://mcp.exa.ai/mcp?exaApiKey="    # Exa's own keyed endpoint (its 429 message names it)
#: the keys enter a command only through the shell's optional-argument form: expanded to nothing when unset
_EXA_KEY_ARG = '${EXA_API_KEY:+--http-url "' + EXA_KEYED_URL + '$EXA_API_KEY"}'
_JINA_KEY_ARG = '${JINA_API_KEY:+-H "Authorization: Bearer $JINA_API_KEY"}'
_LINKS_HEADER = "X-With-Links-Summary: true"

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_CANDIDATE_ID = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})?)?")
#: the upload capability as the host makes it (http://127.0.0.1:7200/product/report/<id>/upload/<token>): no quote, no `$`, no space
_SAFE_URL = re.compile(r"https?://[A-Za-z0-9.-]+(?::\d{1,5})?(?:/[A-Za-z0-9._~%+=:@/-]*)?(?:\?[A-Za-z0-9._~%+=:@/&-]*)?")
_ALIBABA_DETAIL = re.compile(r"https://(?:[a-z0-9-]+\.)*alibaba\.com/product-detail/[A-Za-z0-9._~%-]{1,300}_\d{8,}\.html")
_SITE_WORD = re.compile(r"\bsite:\S*", re.IGNORECASE)
_TERM_CHARS = 120

#: what each Exa search asks (the objectives the probes of 2026-11-02 measured; Exa's schema requires one)
_OBJECTIVE = {
    "reddit": ("Reddit threads (reddit.com/r/.../comments/...) where people say whether {terms} is worth buying; rank reddit threads "
               "first, exclude non-reddit pages; pull thread title, subreddit, date, score, comment count and opinions"),
    "reddit_2": ("Reddit threads (reddit.com/r/.../comments/...) where people recommend, compare or warn against {terms}; rank reddit "
                 "threads first, exclude non-reddit pages; pull thread title, subreddit, date, score, comment count and opinions"),
    "amazon": ("Amazon.com product detail pages (amazon.com/.../dp/ASIN) for {terms}; rank product pages first; pull price, star "
               "rating, review count, best sellers rank, delivery estimate"),
    "alibaba": ("Alibaba.com product detail pages (alibaba.com/product-detail/...) for {terms}; rank product detail pages first; pull "
                "price tiers, minimum order quantity, lead time, estimated delivery, supplier name, ships from"),
    "ebay": ("eBay item listings (ebay.com/itm/...) for {terms}; rank listing pages first; pull price, shipping cost, number sold, "
             "item location, delivery estimate, condition"),
}
_SITE = {"reddit": "reddit.com", "amazon": "amazon.com", "alibaba": "alibaba.com", "ebay": "ebay.com"}


# ------------------------------------------------------------------------------------------------------------ commands --
def _words(value: Any) -> str:
    """A candidate's text as one line of search words: NFKC, no control or bidi characters, no `site:` operator of its own,
    single spaces, at most 120 characters. Quoting, not this, is what keeps it inert in the shell."""
    text = AR._CONTROL.sub(" ", unicodedata.normalize("NFKC", str(value or "")))
    return " ".join(_SITE_WORD.sub(" ", text).split())[:_TERM_CHARS].strip()


def exa_command(source: str, words: str, *, objective: str | None = None, suffix: str = "") -> str:
    """The exact Exa search for `source` through mcporter: `mcporter call exa.web_search_exa query=… numResults=8 objective=…`
    (with EXA_API_KEY set, the keyed endpoint is added in front of the tool). The query starts with `site:` and the objective with
    fixed words, so no value starts with "@" (mcporter reads a FILE for `key=@path`)."""
    query = " ".join(f"site:{_SITE[source]} {words} {suffix}".split())
    goal = " ".join((objective or _OBJECTIVE[source]).format(terms=words).split())
    return " ".join(["mcporter", "call", _EXA_KEY_ARG, "exa.web_search_exa", shlex.quote(f"query={query}"),
                     f"numResults={EXA_RESULTS}", shlex.quote(f"objective={goal}")])


def jina_command(url: str, *, links: bool = False) -> str:
    """The exact Jina Reader read of `url`: `curl -s "https://r.jina.ai/<url>"` (with JINA_API_KEY set, its Authorization header;
    for an Amazon search page, `X-With-Links-Summary: true`), URL globbing off and a time limit."""
    parts = ["curl", "-s", "-g", "-m", str(JINA_TIMEOUT_S), _JINA_KEY_ARG]
    if links:
        parts += ["-H", shlex.quote(_LINKS_HEADER)]
    return " ".join([*parts, shlex.quote(f"https://r.jina.ai/{url}")])


def amazon_search_url(words: str) -> str:
    return f"https://www.amazon.com/s?k={quote_plus(words)}"


# ------------------------------------------------------------------------------------------------------------ packets --
def _phrases(candidate: dict[str, Any]) -> tuple[str, str]:
    """(the first search phrase, a second one for the second Reddit search): the candidate's search terms, else its title."""
    terms = [w for w in (_words(t) for t in (candidate.get("search_terms") or [])[:10]) if w]
    title = _words(candidate.get("title"))
    first = terms[0] if terms else title
    second = next((t for t in [*terms[1:], title] if t and t.lower() != first.lower()), first)
    return first, second


def _packet(packet_id: str, candidate_id: str, source: str, kind: str, command: str, tool: str, reads: str) -> dict[str, Any]:
    return {"packet_id": packet_id, "candidate_id": candidate_id, "source": source, "kind": kind, "commands": [command],
            "reads": reads, "expect": {"tool_class": tool, "parse": {"source": source, "kind": kind}, "max_bytes": AR.MAX_REPORT_BYTES}}


def _round1(index: int, cid: str, candidate: dict[str, Any], ebay_api: bool) -> list[dict[str, Any]]:
    first, second = _phrases(candidate)
    p = f"r1-c{index}"
    out = [
        _packet(f"{p}-reddit-1", cid, "reddit", "search", exa_command("reddit", first, suffix="worth it"), AR.TOOL_EXA,
                f"site:reddit.com {first} worth it"),
        _packet(f"{p}-reddit-2", cid, "reddit", "search",
                exa_command("reddit", second, objective=_OBJECTIVE["reddit_2"], suffix="recommendations"), AR.TOOL_EXA,
                f"site:reddit.com {second} recommendations"),
        _packet(f"{p}-amazon-1", cid, "amazon", "search", exa_command("amazon", first), AR.TOOL_EXA, f"site:amazon.com {first}"),
        _packet(f"{p}-amazon-2", cid, "amazon", "search", jina_command(amazon_search_url(first), links=True), AR.TOOL_JINA,
                amazon_search_url(first)),
        _packet(f"{p}-alibaba-1", cid, "alibaba", "search", exa_command("alibaba", first), AR.TOOL_EXA, f"site:alibaba.com {first}"),
    ]
    if not ebay_api:
        out.append(_packet(f"{p}-ebay-1", cid, "ebay", "search", exa_command("ebay", first), AR.TOOL_EXA, f"site:ebay.com {first}"))
    return out


def _target_url(source: str, url: Any) -> str | None:
    """A round-2 target's canonical page URL (an amazon.com /dp/<ASIN> page, an alibaba.com product-detail page), else None."""
    if source == "amazon":
        found = AR.amazon_product_url(url)
        return found[0] if found else None
    if source == "alibaba":
        found = AR.alibaba_page_url(url)
        return found[0] if found and found[2] == "detail" and _ALIBABA_DETAIL.fullmatch(found[0]) else None
    return None


def _round2(targets: list[dict[str, Any]], index_of: dict[str, int], skipped: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    taken: dict[tuple[str, str], int] = {}
    seen: set[tuple[str, str]] = set()
    for t in targets:
        t = t if isinstance(t, dict) else {}
        cid, source = str(t.get("candidate_id") or ""), str(t.get("source") or "").strip().lower()
        if cid not in index_of:
            skipped.append({"target": AR._clip(t.get("url"), 300), "code": "UNKNOWN_CANDIDATE", "why": "the target names no candidate of this report"})
            continue
        if source not in ROUND2_PAGES:
            skipped.append({"target": AR._clip(t.get("url"), 300), "code": "SOURCE_NOT_READ",
                            "why": "round 2 reads Amazon and Alibaba product pages only (Reddit and eBay block page readers, measured 2026-11-02)"})
            continue
        url = _target_url(source, t.get("url"))
        if url is None:
            skipped.append({"target": AR._clip(t.get("url"), 300), "code": "NOT_A_PRODUCT_PAGE",
                            "why": f"not a {source} product page this plan reads"})
            continue
        if (cid, url) in seen:
            continue
        if taken.get((cid, source), 0) >= ROUND2_PAGES[source]:
            skipped.append({"target": url, "code": "OVER_LIMIT", "why": f"at most {ROUND2_PAGES[source]} {source} pages per candidate"})
            continue
        seen.add((cid, url))
        taken[(cid, source)] = n = taken.get((cid, source), 0) + 1
        packets.append(_packet(f"r2-c{index_of[cid]}-{source}-{n}", cid, source, "page", jina_command(url), AR.TOOL_JINA, url))
    return packets


# ------------------------------------------------------------------------------------------------------------- script --
_HEAD = """#!/usr/bin/env bash
# Polymath product decision report {report_id}: fetch plan, round {round} ({contract}).
# Generated by Polymath; do not edit. Runs every Agent Reach read of this round on THIS machine and uploads each raw output
# straight to Polymath, which parses it. Fetched content is only written to a file and uploaded: it is never run or evaluated.
# Needs mcporter (Agent Reach's Exa channel) and curl. Optional: EXA_API_KEY / JINA_API_KEY raise the pacing.
# The upload capability in UPLOAD_URL expires {expires_at}.
set -u
REPORT={report_q}
ROUND={round}
UPLOAD_URL={upload_q}
UPLOAD_SEP={sep_q}
PACKETS={count}
if [ -n "${{EXA_API_KEY:-}}" ]; then EXA_PARALLEL={exa_keyed}; EXA_MODE='EXA_API_KEY'; else EXA_PARALLEL={exa_keyless}; EXA_MODE='keyless'; fi
if [ -n "${{JINA_API_KEY:-}}" ]; then JINA_PARALLEL={jina_par_keyed}; JINA_GAP={jina_gap_keyed}; JINA_MODE='JINA_API_KEY'; else JINA_PARALLEL={jina_par_keyless}; JINA_GAP={jina_gap_keyless}; JINA_MODE='keyless'; fi
EXA_GAP={exa_gap}
if ! command -v curl >/dev/null 2>&1; then echo "polymath-fetch: curl is required: nothing was read or uploaded"; exit 3; fi
if ! command -v mcporter >/dev/null 2>&1; then echo "polymath-fetch: mcporter not found (Agent Reach: {repo}): the Exa packets will fail"; fi
WORK=$(mktemp -d "${{TMPDIR:-/tmp}}/polymath-report.XXXXXX") || {{ echo "polymath-fetch: cannot make a temporary directory"; exit 3; }}
trap 'rm -rf "$WORK"' EXIT
echo "polymath-fetch: report $REPORT round $ROUND: $PACKETS packets; Exa $EXA_PARALLEL in flight ($EXA_MODE); Jina $JINA_PARALLEL every $JINA_GAP s ($JINA_MODE)"

run_packet() {{
  # $1 packet id, $2 source, $3 kind, $4 the packet's command (a function below). The output goes to a file and is uploaded.
  out="$WORK/$1.out"
  err="$WORK/$1.err"
  "$4" >"$out" 2>"$err"
  rc=$?
  if [ "$rc" -ne 0 ] && [ ! -s "$out" ] && grep -q '429' "$err" 2>/dev/null; then
    sleep {retry}
    "$4" >"$out" 2>"$err"
    rc=$?
  fi
  bytes=$(wc -c <"$out" | tr -d ' ')
  note=''
  if grep -q '^Warning: Target URL returned error' "$out" 2>/dev/null; then note=' (the site refused the reader: the upload records it)'; fi
  if [ "$bytes" -eq 0 ]; then
    # an empty output is uploaded too (an empty body: the host records the packet as EMPTY), so the round can complete
    note=' (no output: recorded as EMPTY)'
    if grep -q '429' "$err" 2>/dev/null; then note=' (no output: recorded as EMPTY; rate limited (HTTP 429): set EXA_API_KEY to read faster)'; fi
  fi
  code=$(curl -s -o /dev/null -w '%{{http_code}}' -m {upload_timeout} --data-binary "@$out" -H 'content-type: text/plain' "${{UPLOAD_URL}}${{UPLOAD_SEP}}packet=$1")
  case "$code" in 2??) echo "$1" >>"$WORK/uploaded" ;; esac
  echo "polymath-fetch: $1 $2/$3: exit $rc, $bytes bytes, upload http $code$note"
}}

EXA_N=0
exa() {{
  run_packet "$1" "$2" "$3" "$4" &
  EXA_N=$((EXA_N + 1))
  if [ "$EXA_N" -ge "$EXA_PARALLEL" ]; then wait; EXA_N=0; sleep "$EXA_GAP"; fi
}}

JINA_N=0
jina() {{
  run_packet "$1" "$2" "$3" "$4" &
  JINA_N=$((JINA_N + 1))
  if [ "$JINA_N" -ge "$JINA_PARALLEL" ]; then wait; JINA_N=0; sleep "$JINA_GAP"; fi
}}
"""

_TAIL = """
exa_queue() {{
{exa_calls}
  wait
}}

jina_queue() {{
{jina_calls}
  wait
}}

exa_queue &
jina_queue &
wait
uploaded=$(grep -c . "$WORK/uploaded" 2>/dev/null || true)
echo "polymath-fetch: done: ${{uploaded:-0}} of $PACKETS packets uploaded for report $REPORT round $ROUND; next: product_report_status"
exit 0
"""


def _jina_gap(limits: dict[str, int], parallel: int) -> int:
    """Whole seconds between Jina batch starts so `parallel` reads per batch stay within `jina_per_minute` (rounded up)."""
    return max(1, -(-60 * parallel // limits["jina_per_minute"]))


def _script(report_id: str, round_: int, upload_url: str, expires_at: str, packets: list[dict[str, Any]]) -> str:
    sep = "&" if "?" in upload_url else "?"
    head = _HEAD.format(report_id=report_id, round=round_, contract=CONTRACT, expires_at=expires_at, report_q=shlex.quote(report_id),
                        upload_q=shlex.quote(upload_url), sep_q=shlex.quote(sep), count=len(packets),
                        exa_keyed=LIMITS_WITH_KEYS["exa_parallel"], exa_keyless=LIMITS["exa_parallel"],
                        jina_par_keyed=JINA_PARALLEL["with_keys"], jina_par_keyless=JINA_PARALLEL["keyless"],
                        jina_gap_keyed=_jina_gap(LIMITS_WITH_KEYS, JINA_PARALLEL["with_keys"]),
                        jina_gap_keyless=_jina_gap(LIMITS, JINA_PARALLEL["keyless"]), exa_gap=EXA_GAP_S, repo=AR.REPO,
                        retry=RETRY_AFTER_S, upload_timeout=UPLOAD_TIMEOUT_S)
    functions, exa_calls, jina_calls = [], [], []
    for n, p in enumerate(packets, 1):
        name = f"p{n:03d}"
        functions.append(f"{name}() {{ {p['commands'][0]}; }}")
        call = f"  {'exa' if p['expect']['tool_class'] == AR.TOOL_EXA else 'jina'} {shlex.quote(p['packet_id'])} {p['source']} {p['kind']} {name}"
        (exa_calls if p["expect"]["tool_class"] == AR.TOOL_EXA else jina_calls).append(call)
    body = "\n# the packets: one exact command each (the same text as the plan's commands)\n" + "\n".join(functions) + "\n"
    return head + body + _TAIL.format(exa_calls="\n".join(exa_calls) or "  :", jina_calls="\n".join(jina_calls) or "  :")


# -------------------------------------------------------------------------------------------------------------- build --
def build(report_id: str, candidates: list[dict], *, round: int, upload: dict, targets: list[dict] | None = None,
          ebay_api: bool = False) -> dict[str, Any]:
    """The fetch plan of one round -> {round, packets: [{packet_id, candidate_id, source, kind, commands: [str], expect, reads}],
    script, script_sha256, limits: {exa_parallel, jina_per_minute, with_keys: {...}}, how, skipped}.

    `candidates`: [{candidate_id?, title, search_terms?: [str]}] (at most MAX_CANDIDATES are planned; a missing id becomes
    "c<n>"); `upload`: {"url": the upload capability, "expires_at": ISO 8601}; `targets` (round 2): [{url, source, candidate_id,
    ...}] (the parser's next_targets, each with its candidate); `ebay_api`: the host reads eBay through its Browse API, so no eBay
    Exa search is planned. Raises ValueError on a malformed report id, round, upload or candidate id."""
    if not isinstance(report_id, str) or not _ID.fullmatch(report_id):
        raise ValueError("report_id is 1-64 letters, digits, '_' or '-'")
    if round not in ROUNDS:
        raise ValueError(f"round is one of {ROUNDS}")
    upload = upload if isinstance(upload, dict) else {}
    url, expires_at = str(upload.get("url") or ""), str(upload.get("expires_at") or "")
    parts = urlsplit(url) if _SAFE_URL.fullmatch(url) else None
    if parts is None or parts.scheme not in ("http", "https") or not parts.hostname or "#" in url or len(url) > 2000:
        raise ValueError("upload.url is the http(s) upload capability, without spaces, quotes or a fragment")
    if not _ISO.fullmatch(expires_at):
        raise ValueError("upload.expires_at is an ISO 8601 time")
    skipped: list[dict[str, Any]] = []
    index_of: dict[str, int] = {}
    planned: list[tuple[int, str, dict[str, Any]]] = []
    ids: set[str] = set()
    for n, candidate in enumerate(candidates or [], 1):
        candidate = candidate if isinstance(candidate, dict) else {}
        cid = str(candidate.get("candidate_id") or f"c{n}")
        if not _CANDIDATE_ID.fullmatch(cid):
            raise ValueError(f"candidate_id {cid[:40]!r} is 1-64 letters, digits, '_', '.', ':' or '-'")
        if cid in ids:
            raise ValueError(f"candidate_id {cid!r} appears twice")
        ids.add(cid)
        if len(planned) >= MAX_CANDIDATES:
            skipped.append({"candidate_id": cid, "code": "OVER_LIMIT", "why": f"at most {MAX_CANDIDATES} candidates per report"})
            continue
        if not _phrases(candidate)[0]:
            skipped.append({"candidate_id": cid, "code": "NO_SEARCH_TERMS", "why": "the candidate has no title or search terms to search for"})
            continue
        index_of[cid] = len(planned) + 1
        planned.append((index_of[cid], cid, candidate))
    if round == 1:
        packets = [p for i, cid, c in planned for p in _round1(i, cid, c, bool(ebay_api))]
    else:
        packets = _round2(list(targets or []), index_of, skipped)
    script = _script(report_id, round, url, expires_at, packets)
    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()
    name = f"polymath-report-{report_id}-r{round}.sh"
    how = {
        "run": f"save `script` as {name} on the user's machine and run: bash {name}",
        "needs": f"Agent Reach on the user's machine (mcporter for Exa, curl for Jina Reader): {AR.REPO}; check it with: {AR.VERIFY}",
        "keys": (f"optional: with EXA_API_KEY and/or JINA_API_KEY in the environment the script runs faster (Exa "
                 f"{LIMITS_WITH_KEYS['exa_parallel']} in flight, Jina {LIMITS_WITH_KEYS['jina_per_minute']} a minute); without them it "
                 f"paces itself to the keyless limits (Exa {LIMITS['exa_parallel']} in flight, Jina {LIMITS['jina_per_minute']} a minute)"),
        "never": ("do not open, read, paste or summarise the fetched pages, and do not use your agent's built-in web search or web "
                  "fetch: the script uploads every raw output straight to Polymath, which parses it"),
        "output": ("one line per packet (exit code, bytes, upload status) and a final done line; every packet is uploaded, an empty "
                   "output too (recorded as EMPTY, so the round can complete); it exits 0 even when a site blocks the reader (the "
                   "upload records it), 3 only when it cannot run (no curl)"),
        "then": "call product_report_status for this report: it shows what was parsed" + (" and the round-2 plan" if round == 1 else ""),
        "expires": f"the upload capability expires at {expires_at}: run the script before then",
        "verify": f"sha256 of the script: {digest}",
    }
    return {"contract": CONTRACT, "round": round, "packets": packets, "script": script, "script_sha256": digest,
            "limits": {**LIMITS, "with_keys": dict(LIMITS_WITH_KEYS)}, "how": how, "skipped": skipped}
