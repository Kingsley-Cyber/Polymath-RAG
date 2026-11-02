"""PRODUCT-DECISION-REPORT-V1 (B1, plan §4.2): `fetch_plan.build` makes one round's packets (exact commands) and ONE bash script
that runs them on the user's machine, paced, and uploads each raw output straight to Polymath.
  * deterministic: the same arguments give the same plan and the same script, byte for byte (sha256 included);
  * round 1 per candidate: Reddit 2 Exa, Amazon 1 Exa + 1 Jina search page (with the links summary), Alibaba 1 Exa, eBay 1 Exa
    only without the host's eBay API; round 2: at most 3 Amazon and 3 Alibaba product pages per candidate, from `targets`;
  * the script passes `bash -n`; candidate text (`"; rm -rf ~; echo "`, `$(touch /tmp/x)`) is inert: the script is RUN here in
    a sandbox whose PATH holds stub `mcporter`, `curl`, `rm`, `touch` and `sleep` that only record their argv, with HOME and
    TMPDIR inside the sandbox, and no injected command runs;
  * pacing: keyless at most 3 Exa calls in flight and one Jina read every 3 s; with EXA_API_KEY / JINA_API_KEY 8 in flight and
    5 Jina reads a second; the keys reach only the commands' own arguments at run time, never the plan or the script;
  * every output is POSTed as text/plain to `<upload.url>?packet=<packet_id>`, an EMPTY output too (an empty body the host
    records as EMPTY, so a round can complete); the script exits 0 when sources are blocked or rate limited (the uploads record
    it);
  * a failed read (a non-zero exit, Jina's cached snapshot of a page that had not loaded at any size, under 512 bytes, Jina's
    error JSON) is read once more inside its packet's slot: an Exa search as it was, a Jina read without Jina's cache and with
    time to render (`X-No-Cache: true`, `X-Timeout: 30`, curl -m 120 instead of 90); the stand-in curl records every argv.
Real outputs for round 2 come from tests/fixtures/product_report/ (see tests/contracts/test_report_parsers.py). No network:
nothing here reaches Exa, Jina or Polymath."""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
from collections import Counter

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.acquisition import agent_reach as AR
from polymath_shared.product_search import fetch_plan as FP

FIX = ROOT / "tests" / "fixtures" / "product_report"
REPORT = "rpt_0123456789abcdef01234567"
UPLOAD = {"url": f"http://127.0.0.1:7200/product/report/{REPORT}/upload/tok_Q7xw2", "expires_at": "2026-11-02T21:00:00Z"}
BRUSH = {"candidate_id": "c1", "title": "Self-cleaning slicker brush", "search_terms": ["self-cleaning slicker brush", "self cleaning pet brush"]}
LAMP = {"candidate_id": "c2", "title": "Candle warmer lamp"}
BASH = shutil.which("bash") or "/bin/bash"
REAL = {name: shutil.which(name) for name in ("sleep", "rm", "ls", "wc", "tr", "cp", "cksum", "cut")}
#: a real read is never this short: the stand-ins print more than AR.READER_MIN_BYTES unless a test asks for a failed read
PAD = "x" * 600
#: Jina's own error reply (live 2026-11-02: a 252-byte read of an Amazon search page)
JINA_ERROR = ('{"data":null,"code":422,"name":"AssertionFailureError","status":42206,"message":"Failed to goto https://www.amazon.com/s'
              '?k=x: net::ERR_ABORTED","readableMessage":"AssertionFailureError: Failed to goto"}')
#: Jina's cached snapshot of an Amazon search page that had not loaded (live 2026-11-02, 346 bytes: both warnings, an empty
#: Markdown Content); padded with a longer links summary it is over 512 bytes and still no page
SNAPSHOT = (FIX / "jina_amazon_search_snapshot.out").read_text(encoding="utf-8")
SNAPSHOT_PADDED = SNAPSHOT.replace("This page does not seem to contain any buttons/links.\n",
                                   "".join(f"- [Sign in](https://www.amazon.com/ap/signin?n={n})\n" for n in range(12)))


def _argv(command: str) -> list[str]:
    """A packet's command as the shell splits it when no key is set (the keys' optional arguments expand to nothing)."""
    return shlex.split(command.replace(FP._EXA_KEY_ARG, "").replace(FP._JINA_KEY_ARG, ""))


def _plan(candidates=(BRUSH, LAMP), **kw):
    kw.setdefault("round", 1)
    kw.setdefault("upload", UPLOAD)
    return FP.build(REPORT, list(candidates), **kw)


def test_the_code_under_test_is_this_checkout():
    for mod in (AR, FP):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── the plan
def test_round_one_packets_per_candidate_with_exact_commands():
    plan = _plan()
    assert set(plan) == {"contract", "round", "packets", "script", "script_sha256", "limits", "how", "skipped"}
    assert (plan["contract"], plan["round"], plan["skipped"]) == ("product-report-fetch-plan-v1", 1, [])
    assert [(p["packet_id"], p["candidate_id"], p["source"], p["kind"], p["expect"]["tool_class"]) for p in plan["packets"]] == [
        (f"r1-c{i}-{s}", c, s.split("-")[0], "search", AR.TOOL_JINA if s == "amazon-2" else AR.TOOL_EXA)
        for i, c in ((1, "c1"), (2, "c2")) for s in ("reddit-1", "reddit-2", "amazon-1", "amazon-2", "alibaba-1", "ebay-1")]
    by = {p["packet_id"]: p for p in plan["packets"]}
    assert all(len(p["commands"]) == 1 and p["expect"]["parse"] == {"source": p["source"], "kind": p["kind"]} for p in plan["packets"])
    assert by["r1-c1-reddit-1"]["commands"][0] == (
        'mcporter call ${EXA_API_KEY:+--http-url "https://mcp.exa.ai/mcp?exaApiKey=$EXA_API_KEY"} exa.web_search_exa '
        "'query=site:reddit.com self-cleaning slicker brush worth it' numResults=8 'objective=Reddit threads (reddit.com/r/.../comments/...) "
        "where people say whether self-cleaning slicker brush is worth buying; rank reddit threads first, exclude non-reddit pages; pull "
        "thread title, subreddit, date, score, comment count and opinions'")
    assert _argv(by["r1-c1-reddit-2"]["commands"][0])[3] == "query=site:reddit.com self cleaning pet brush recommendations"
    assert by["r1-c1-amazon-2"]["commands"][0] == (
        "curl -s -g -m 90 ${JINA_API_KEY:+-H \"Authorization: Bearer $JINA_API_KEY\"} -H 'X-With-Links-Summary: true' "
        "'https://r.jina.ai/https://www.amazon.com/s?k=self-cleaning+slicker+brush'")
    assert _argv(by["r1-c2-alibaba-1"]["commands"][0])[:5] == ["mcporter", "call", "exa.web_search_exa",
                                                                "query=site:alibaba.com Candle warmer lamp", "numResults=8"]
    assert _argv(by["r1-c2-ebay-1"]["commands"][0])[5].startswith("objective=eBay item listings (ebay.com/itm/...) for Candle warmer lamp")
    assert len(_argv(by["r1-c2-ebay-1"]["commands"][0])) == 6
    assert plan["limits"] == {"exa_parallel": 3, "jina_per_minute": 20, "with_keys": {"exa_parallel": 8, "jina_per_minute": 300}}
    assert plan["how"]["run"] == f"save `script` as polymath-report-{REPORT}-r1.sh on the user's machine and run: bash polymath-report-{REPORT}-r1.sh"
    assert "built-in web search" in plan["how"]["never"] and plan["how"]["verify"].endswith(plan["script_sha256"])
    for p in plan["packets"]:                                  # every Exa value starts with fixed words: never "@" (mcporter's file read)
        assert not any(w.split("=", 1)[1].startswith("@") for w in _argv(p["commands"][0]) if "=" in w and w[0].isalpha())


def test_the_host_ebay_api_drops_the_ebay_search_and_the_candidate_cap_holds():
    plan = _plan(ebay_api=True)
    assert {p["source"] for p in plan["packets"]} == {"reddit", "amazon", "alibaba"} and len(plan["packets"]) == 10
    many = [{"title": f"product {n}"} for n in range(1, 11)] + [{"candidate_id": "empty", "title": "   "}]
    capped = FP.build(REPORT, many, round=1, upload=UPLOAD)
    assert sorted({p["candidate_id"] for p in capped["packets"]}) == sorted(f"c{n}" for n in range(1, 9))
    assert [(s["candidate_id"], s["code"]) for s in capped["skipped"]] == [("c9", "OVER_LIMIT"), ("c10", "OVER_LIMIT"), ("empty", "OVER_LIMIT")]
    blank = FP.build(REPORT, [{"candidate_id": "blank", "title": " ", "search_terms": ["", "\x00"]}, LAMP], round=1, upload=UPLOAD)
    assert [(s["candidate_id"], s["code"]) for s in blank["skipped"]] == [("blank", "NO_SEARCH_TERMS")]
    assert {p["packet_id"].split("-")[1] for p in blank["packets"]} == {"c1"} and {p["candidate_id"] for p in blank["packets"]} == {"c2"}


def test_round_two_reads_at_most_three_pages_per_source_per_candidate_from_the_parsed_targets():
    amazon = AR.parse_report_source("amazon", (FIX / "jina_amazon_search_links.out").read_text(), kind="search",
                                    candidate_terms=BRUSH["search_terms"])
    brush = AR.parse_report_source("alibaba", (FIX / "exa_alibaba_brush.out").read_text(), kind="search")
    lamp = AR.parse_report_source("alibaba", (FIX / "exa_alibaba_candle.out").read_text(), kind="search")
    targets = ([{**t, "candidate_id": "c1"} for t in amazon["next_targets"] + brush["next_targets"]]
               + [{**t, "candidate_id": "c2"} for t in lamp["next_targets"]]
               + [{"url": "https://www.reddit.com/r/x/comments/abc123/x/", "source": "reddit", "candidate_id": "c1"},
                  {"url": "https://www.amazon.com/dp/B0CLLPVZRV", "source": "amazon", "candidate_id": "c9"},
                  {"url": "https://www.alibaba.com/showroom/candle.html", "source": "alibaba", "candidate_id": "c2"},
                  {"url": "https://www.alibaba.com/product-detail/$(touch x)_1600000000001.html", "source": "alibaba", "candidate_id": "c2"},
                  {"url": amazon["next_targets"][0]["url"] + "?ref=dup", "source": "amazon", "candidate_id": "c1"}])
    plan = _plan(round=2, targets=targets)
    assert [(p["packet_id"], p["candidate_id"], p["source"], p["kind"]) for p in plan["packets"]] == [
        ("r2-c1-amazon-1", "c1", "amazon", "page"), ("r2-c1-amazon-2", "c1", "amazon", "page"), ("r2-c1-amazon-3", "c1", "amazon", "page"),
        ("r2-c1-alibaba-1", "c1", "alibaba", "page"), ("r2-c1-alibaba-2", "c1", "alibaba", "page"), ("r2-c1-alibaba-3", "c1", "alibaba", "page"),
        ("r2-c2-alibaba-1", "c2", "alibaba", "page"), ("r2-c2-alibaba-2", "c2", "alibaba", "page")]
    assert plan["packets"][0]["commands"][0] == ("curl -s -g -m 90 ${JINA_API_KEY:+-H \"Authorization: Bearer $JINA_API_KEY\"} "
                                                 "https://r.jina.ai/https://www.amazon.com/dp/B0CLLPVZRV")   # nothing to quote in it
    assert _argv(plan["packets"][3]["commands"][0])[-1].startswith("https://r.jina.ai/https://www.alibaba.com/product-detail/")
    for n, p in enumerate(plan["packets"], 1):                 # each page's one retry: fresh, with time to render, no links summary
        assert (f"\np{n:03d}r() {{ curl -s -g -m 120 ${{JINA_API_KEY:+-H \"Authorization: Bearer $JINA_API_KEY\"}} -H 'X-No-Cache: true' "
                f"-H 'X-Timeout: 30' {shlex.quote('https://r.jina.ai/' + p['reads'])}; }}\n") in plan["script"]
    assert all(p["expect"] == {"tool_class": AR.TOOL_JINA, "parse": {"source": p["source"], "kind": "page"}, "max_bytes": AR.MAX_REPORT_BYTES}
               for p in plan["packets"])
    assert Counter(s["code"] for s in plan["skipped"]) == Counter({"OVER_LIMIT": 7 + 5, "SOURCE_NOT_READ": 1, "UNKNOWN_CANDIDATE": 1,
                                                                   "NOT_A_PRODUCT_PAGE": 2})
    assert _plan(round=2)["packets"] == [] and "round-2" not in _plan(round=2)["how"]["then"]


def test_round_two_reads_the_plain_text_search_pages_products_too():
    """Live 2026-11-02: the plain-text layout of an Amazon search page names its products for round 2 like the markdown one."""
    plain = AR.parse_report_source("amazon", (FIX / "jina_amazon_search_plain.out").read_text(), kind="search",
                                   candidate_terms=["pet water fountain"])
    plan = _plan(candidates=({"candidate_id": "c2", "title": "Pet water fountain"},), round=2,
                 targets=[{**t, "candidate_id": "c2"} for t in plain["next_targets"]])
    assert [(p["packet_id"], p["kind"], _argv(p["commands"][0])[-1]) for p in plan["packets"]] == [
        (f"r2-c1-amazon-{n}", "page", f"https://r.jina.ai/{t['url']}") for n, t in enumerate(plain["next_targets"][:3], 1)]
    assert [s["code"] for s in plan["skipped"]] == ["OVER_LIMIT"] * (len(plain["next_targets"]) - 3)


@pytest.mark.parametrize("args,needle", [
    (("rpt x", [BRUSH]), "report_id"), (("rpt_1", [BRUSH], {"round": 3}), "round"),
    (("rpt_1", [BRUSH], {"upload": {"url": "http://127.0.0.1:7200/u/t'; touch x; '", "expires_at": "2026-11-02T21:00:00Z"}}), "upload.url"),
    (("rpt_1", [BRUSH], {"upload": {"url": "javascript:alert(1)", "expires_at": "2026-11-02T21:00:00Z"}}), "upload.url"),
    (("rpt_1", [BRUSH], {"upload": {"url": UPLOAD["url"], "expires_at": "soon\nrm -rf ~"}}), "expires_at"),
    (("rpt_1", [{"candidate_id": "c 1", "title": "x"}]), "candidate_id"),
    (("rpt_1", [{"candidate_id": "c1", "title": "x"}, {"candidate_id": "c1", "title": "y"}]), "twice"),
    (("rpt_1", [{"candidate_id": "c1", "title": " "}, {"candidate_id": "c1", "title": "y"}]), "twice"),     # a skipped one counts too
])
def test_what_the_host_hands_in_is_validated(args, needle):
    kw = {"round": 1, "upload": UPLOAD, **(args[2] if len(args) > 2 else {})}
    with pytest.raises(ValueError, match=needle):
        FP.build(args[0], args[1], **kw)


def test_the_plan_is_deterministic_byte_for_byte():
    one, two = _plan(), _plan()
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)
    assert one["script_sha256"] == hashlib.sha256(one["script"].encode("utf-8")).hexdigest()
    other = _plan(upload={**UPLOAD, "url": UPLOAD["url"] + "x"})
    assert other["script_sha256"] != one["script_sha256"] and other["packets"] == one["packets"]
    assert "?" not in UPLOAD["url"] and "UPLOAD_SEP='?'" in one["script"]
    assert "UPLOAD_SEP='&'" in _plan(upload={**UPLOAD, "url": UPLOAD["url"] + "?v=1"})["script"]


# ─────────────────────────────────────────────────────────── the script, statically
def _unquoted_dollars(script: str) -> list[str]:
    """Every `$` outside single and double quotes (comments skipped), with what follows it."""
    found, state, i = [], None, 0
    while i < len(script):
        ch = script[i]
        if state is None:
            if ch == "#" and (i == 0 or script[i - 1] in " \t\n;"):
                i = script.find("\n", i) if "\n" in script[i:] else len(script)
                continue
            if ch == "\\":
                i += 2
                continue
            if ch in "'\"":
                state = ch
            elif ch == "$":
                found.append(script[max(0, i - 1): i + 18])
        elif ch == state:
            state = None
        elif state == '"' and ch == "\\":
            i += 1
        i += 1
    assert state is None, "unbalanced quotes"
    return found


@pytest.mark.parametrize("kw", [{}, {"round": 2, "targets": []}, {"ebay_api": True}])
def test_the_script_passes_bash_n_quotes_every_variable_and_never_evaluates_content(kw, tmp_path):
    plan = _plan(**kw)
    path = tmp_path / "plan.sh"
    path.write_text(plan["script"])
    assert subprocess.run([BASH, "-n", str(path)], capture_output=True, text=True, check=False).returncode == 0
    if shutil.which("dash"):                                    # POSIX shell syntax too
        assert subprocess.run([shutil.which("dash"), "-n", str(path)], capture_output=True, text=True, check=False).returncode == 0
    script = plan["script"]
    assert script.startswith("#!/usr/bin/env bash\n") and "\nset -u\n" in script and script.rstrip().endswith("exit 0")
    command_word = re.compile(r"(?:^|[;&|{(]|\bthen|\bdo|\belse)\s*(eval|source|\.|exec)\s", re.MULTILINE)
    assert not command_word.search(script) and "`" not in script and "bash -c" not in script and "sh -c" not in script
    for unquoted in _unquoted_dollars(script):                  # only assignments, arithmetic and the keys' optional arguments
        assert (unquoted[0] == "=" or unquoted[1:].startswith(("${EXA_API_KEY:+", "${JINA_API_KEY:+"))), unquoted
    for n, p in enumerate(plan["packets"], 1):                  # the script runs exactly the packet's command
        assert script.count(p["commands"][0]) == 1
        retry = [line for line in script.splitlines() if line.startswith(f"p{n:03d}r() {{ ")]
        if p["expect"]["tool_class"] == AR.TOOL_EXA:            # an Exa search is retried as it was: no retry command of its own
            assert retry == [] and f"  exa {p['packet_id']} {p['source']} {p['kind']} p{n:03d}\n" in script
            continue
        first = _argv(p["commands"][0])                         # a Jina read's one retry: the same read, fresh, with time to render
        assert first[3:5] == ["-m", "90"] and len(retry) == 1 and retry[0].endswith("; }")
        assert _argv(retry[0][len(f"p{n:03d}r() {{ "):-3]) == [*first[:3], "-m", "120", *first[5:-1], "-H", "X-No-Cache: true",
                                                                 "-H", "X-Timeout: 30", first[-1]]
        assert f"  jina {p['packet_id']} {p['source']} {p['kind']} p{n:03d} p{n:03d}r\n" in script


# ─────────────────────────────────────────────────────────── the script, run in a sandbox with recording stubs
STUBS = {
    "mcporter": r"""#!/bin/sh
L="$STUB_LOG"
printf '%s\0' "$@" > "$L/mcporter.$$.argv"
: > "$L/running_exa/$$"
{ls} "$L/running_exa" | {wc} -l | {tr} -d ' ' >> "$L/exa_concurrency"
{sleep} 0.4
{rm} -f "$L/running_exa/$$"
key=$(printf '%s' "$*" | {cksum} | {cut} -d ' ' -f 1)
if [ "${STUB_MCPORTER:-}" = fail429 ]; then echo "[mcporter] exa.web_search_exa responded with HTTP 429" >&2; exit 1; fi
if [ "${STUB_MCPORTER:-}" = empty ]; then exit 0; fi
if [ "${STUB_MCPORTER:-}" = fail_once ] && [ ! -e "$L/once.$key" ]; then
  : > "$L/once.$key"; echo "[mcporter] exa.web_search_exa responded with HTTP 429" >&2; exit 1
fi
printf 'Title: Thread : r/test\nURL: https://www.reddit.com/r/test/comments/abc123/thread/\nPublished: N/A\nAuthor: N/A\nHighlights:\nhello %s\n' "$STUB_PAD"
""",
    "curl": r"""#!/bin/sh
L="$STUB_LOG"
printf '%s\0' "$@" > "$L/curl.$$.argv"
up=0
for a in "$@"; do if [ "$a" = --data-binary ]; then up=1; fi; done
if [ "$up" = 1 ]; then
  for a in "$@"; do case "$a" in @*) {cp} "${a#@}" "$L/upload.$$.body" ;; esac; done
  printf '%s' "${STUB_UPLOAD_CODE:-200}"
  exit 0
fi
: > "$L/running_jina/$$"
{ls} "$L/running_jina" | {wc} -l | {tr} -d ' ' >> "$L/jina_concurrency"
{sleep} 0.4
{rm} -f "$L/running_jina/$$"
for a in "$@"; do url=$a; done
key=$(printf '%s' "$url" | {cksum} | {cut} -d ' ' -f 1)
if [ "${STUB_CURL:-}" = blocked ]; then
  printf 'Title: Blocked\n\nURL Source: https://www.amazon.com/s?k=x\n\nWarning: Target URL returned error 403: Forbidden\n\nMarkdown Content:\n## whoa there, pardner!\n'
elif [ "${STUB_CURL:-}" = error_json ]; then
  printf '%s' "$STUB_JINA_ERROR"
elif [ "${STUB_CURL:-}" = error_once ] && [ ! -e "$L/once.$key" ]; then
  : > "$L/once.$key"; printf '%s' "$STUB_JINA_ERROR"
elif [ "${STUB_CURL:-}" = snapshot ]; then
  printf '%s' "$STUB_SNAPSHOT"
elif [ "${STUB_CURL:-}" = snapshot_once ] && [ ! -e "$L/once.$key" ]; then
  : > "$L/once.$key"; printf '%s' "$STUB_SNAPSHOT"
else
  printf 'Title: Amazon.com : x\n\nURL Source: https://www.amazon.com/s?k=x\n\nMarkdown Content:\nhello %s\n' "$STUB_PAD"
fi
""",
    "rm": "#!/bin/sh\nprintf '%s\\0' \"$@\" > \"$STUB_LOG/rm.$$.argv\"\n",
    "touch": "#!/bin/sh\nprintf '%s\\0' \"$@\" > \"$STUB_LOG/touch.$$.argv\"\n",
    "sleep": "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$STUB_LOG/sleep.log\"\n",
}


def _argvs(log: pathlib.Path, tool: str) -> list[list[str]]:
    return [p.read_bytes().decode().split("\0")[:-1] for p in sorted(log.glob(f"{tool}.*.argv"))]


def _run(tmp_path: pathlib.Path, plan: dict, **env_extra: str) -> tuple[subprocess.CompletedProcess, pathlib.Path, dict]:
    assert all(REAL.values()), REAL
    box = tmp_path / "box"
    stubs, log, home, tmp = box / "bin", box / "log", box / "home", box / "tmp"
    for d in (stubs, log, log / "running_exa", log / "running_jina", home, tmp):
        d.mkdir(parents=True)
    (home / "canary").write_text("still here")
    for name, body in STUBS.items():
        stub = stubs / name
        stub.write_text(body.replace("{ls}", REAL["ls"]).replace("{wc}", REAL["wc"]).replace("{tr}", REAL["tr"])
                        .replace("{sleep}", REAL["sleep"]).replace("{rm}", REAL["rm"]).replace("{cp}", REAL["cp"])
                        .replace("{cksum}", REAL["cksum"]).replace("{cut}", REAL["cut"]))
        stub.chmod(0o755)
    script = box / "plan.sh"
    script.write_text(plan["script"])
    env = {"PATH": f"{stubs}:/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(tmp), "STUB_LOG": str(log), "LC_ALL": "C",
           "STUB_PAD": PAD, "STUB_JINA_ERROR": JINA_ERROR, "STUB_SNAPSHOT": SNAPSHOT_PADDED, **env_extra}
    done = subprocess.run([BASH, str(script)], cwd=box, env=env, capture_output=True, text=True, timeout=120, check=False)
    return done, log, {"home": home, "tmp": tmp, "box": box}


def _ints(path: pathlib.Path) -> list[int]:
    return [int(x) for x in path.read_text().split()] if path.exists() else []


def test_hostile_candidate_text_stays_a_search_word_when_the_script_runs(tmp_path):
    pwned = tmp_path / "box" / "pwned_abs"                    # the script runs in box/: an absolute /usr/bin/touch would make it
    hostile = [{"candidate_id": "evil1", "title": '"; rm -rf ~; echo " candle'},
               {"candidate_id": "evil2", "title": "lamp", "search_terms": ["$(touch /tmp/x) lamp", "`touch /tmp/y` $(/usr/bin/touch pwned_abs) brush"]}]
    plan = FP.build(REPORT, hostile, round=1, upload=UPLOAD)
    queries = {p["packet_id"]: _argv(p["commands"][0])[3] for p in plan["packets"] if p["expect"]["tool_class"] == AR.TOOL_EXA}
    assert queries["r1-c1-reddit-1"] == 'query=site:reddit.com "; rm -rf ~; echo " candle worth it'
    assert queries["r1-c2-reddit-1"] == "query=site:reddit.com $(touch /tmp/x) lamp worth it"
    assert queries["r1-c2-reddit-2"] == "query=site:reddit.com `touch /tmp/y` $(/usr/bin/touch pwned_abs) brush recommendations"
    for p in plan["packets"]:
        assert "'" in p["commands"][0]                           # the candidate's words sit inside single quotes
    done, log, box = _run(tmp_path, plan)
    assert done.returncode == 0, done.stderr
    assert not list(log.glob("touch.*.argv")) and not pwned.exists()                 # no injected command ran
    assert (box["home"] / "canary").read_text() == "still here"
    rms = _argvs(log, "rm")
    assert len(rms) == 1 and rms[0][0] == "-rf" and pathlib.Path(rms[0][1]).parent == box["tmp"]   # only the trap's own clean-up
    seen = {a for argv in _argvs(log, "mcporter") for a in argv if a.startswith("query=")}
    assert set(queries.values()) == seen                                             # each arrived as ONE literal argument
    fetched = {argv[-1] for argv in _argvs(log, "curl") if "--data-binary" not in argv}
    assert fetched == {"https://r.jina.ai/https://www.amazon.com/s?k=%22%3B+rm+-rf+~%3B+echo+%22+candle",
                       "https://r.jina.ai/https://www.amazon.com/s?k=%24%28touch+%2Ftmp%2Fx%29+lamp"}
    assert done.stdout.strip().splitlines()[-1] == f"polymath-fetch: done: 12 of 12 packets uploaded for report {REPORT} round 1; next: product_report_status"


def test_each_output_is_posted_raw_as_text_plain_to_the_upload_capability(tmp_path):
    plan = _plan(candidates=(LAMP,), ebay_api=True)
    done, log, box = _run(tmp_path, plan)
    assert done.returncode == 0, done.stderr
    uploads = [a for a in _argvs(log, "curl") if "--data-binary" in a]
    assert len(uploads) == len(plan["packets"]) == 5
    ids = []
    for argv in uploads:
        assert argv[:6] == ["-s", "-o", "/dev/null", "-w", "%{http_code}", "-m"] and argv[7] == "--data-binary"
        assert argv[8].startswith("@") and pathlib.Path(argv[8][1:]).parent.parent == box["tmp"]
        assert argv[9:11] == ["-H", "content-type: text/plain"] and argv[11].startswith(UPLOAD["url"] + "?packet=")
        ids.append(argv[11].split("?packet=", 1)[1])
    assert sorted(ids) == sorted(p["packet_id"] for p in plan["packets"])
    bodies = sorted(p.read_text() for p in log.glob("upload.*.body"))
    assert bodies.count(bodies[-1]) >= 1 and any(b.startswith("Title: Thread : r/test\nURL: https://www.reddit.com/") for b in bodies)
    lines = done.stdout.strip().splitlines()
    assert len(lines) == 2 + len(plan["packets"])                                    # a header, one line per packet, a done line
    assert all(" upload http 200" in line for line in lines[1:-1])


def test_pacing_without_keys_three_exa_in_flight_and_one_jina_read_every_three_seconds(tmp_path):
    plan = _plan()                                                                   # 10 Exa packets, 2 Jina packets
    done, log, _ = _run(tmp_path, plan)
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines()[0] == f"polymath-fetch: report {REPORT} round 1: 12 packets; Exa 3 in flight (keyless); Jina 1 every 3 s (keyless)"
    assert max(_ints(log / "exa_concurrency")) == FP.LIMITS["exa_parallel"] == 3
    assert max(_ints(log / "jina_concurrency")) == 1
    assert Counter((log / "sleep.log").read_text().split()) == Counter({"1": 3, "3": 2})   # 3 full Exa batches; after each Jina read
    assert 60 / 3 == FP.LIMITS["jina_per_minute"]
    exa = _argvs(log, "mcporter")
    assert len(exa) == 10 and all(argv[:2] == ["call", "exa.web_search_exa"] and argv[3] == "numResults=8" for argv in exa)
    jina = [a for a in _argvs(log, "curl") if "--data-binary" not in a]
    assert all("Authorization: Bearer" not in " ".join(a) for a in jina)
    assert all(a[:5] == ["-s", "-g", "-m", "90", "-H"] and a[5] == "X-With-Links-Summary: true" for a in jina)


def test_pacing_with_keys_eight_exa_in_flight_and_five_jina_reads_a_second(tmp_path):
    plan = _plan()
    done, log, _ = _run(tmp_path, plan, EXA_API_KEY="test-exa-key-1", JINA_API_KEY="test-jina-key-2")
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines()[0].endswith("Exa 8 in flight (EXA_API_KEY); Jina 5 every 1 s (JINA_API_KEY)")
    assert max(_ints(log / "exa_concurrency")) == FP.LIMITS_WITH_KEYS["exa_parallel"] == 8
    assert max(_ints(log / "jina_concurrency")) == 2                                 # both Jina reads at once (5 allowed)
    assert Counter((log / "sleep.log").read_text().split()) == Counter({"1": 1})     # one full Exa batch of 8
    assert 60 * 5 / 1 == FP.LIMITS_WITH_KEYS["jina_per_minute"]
    for argv in _argvs(log, "mcporter"):
        assert argv[:4] == ["call", "--http-url", "https://mcp.exa.ai/mcp?exaApiKey=test-exa-key-1", "exa.web_search_exa"]
    for argv in (a for a in _argvs(log, "curl") if "--data-binary" not in a):
        assert argv[4:8] == ["-H", "Authorization: Bearer test-jina-key-2", "-H", "X-With-Links-Summary: true"]
    text = json.dumps(plan)
    assert "test-exa-key" not in text and "test-jina-key" not in text                # keys exist only in the user's environment


def test_blocked_and_rate_limited_sources_still_exit_zero_and_the_upload_records_the_block(tmp_path):
    plan = _plan()
    done, log, _ = _run(tmp_path, plan, STUB_MCPORTER="fail429", STUB_CURL="blocked")
    assert done.returncode == 0, done.stderr
    lines = done.stdout.strip().splitlines()
    exa_lines = [line for line in lines if "/search: exit 1" in line]
    assert len(exa_lines) == 10 and all(line.endswith(", 0 bytes, upload http 200 (retried once: exit 1) (no output: recorded as EMPTY; "
                                                      "rate limited (HTTP 429): set EXA_API_KEY to read faster)") for line in exa_lines)
    assert len(_argvs(log, "mcporter")) == 20                                        # each rate-limited search is tried once more
    blocked = [line for line in lines if "amazon/search: exit 0" in line]              # a short block page is read once more too
    assert len(blocked) == 2 and all(re.search(r"upload http 200 \(retried once: only \d+ bytes\) \(the site refused the reader: the "
                                               r"upload records it\)$", line) for line in blocked)
    # every packet arrives, the empty ones too: the round can complete
    assert lines[-1] == f"polymath-fetch: done: 12 of 12 packets uploaded for report {REPORT} round 1; next: product_report_status"
    bodies = [p.read_text() for p in log.glob("upload.*.body")]
    assert len(bodies) == 12 and bodies.count("") == 10
    (body,) = {b for b in bodies if b}
    parsed = AR.parse_report_source("amazon", body, kind="search")
    assert (parsed["status"], parsed["refused"][0]["code"]) == ("BLOCKED", "BLOCKED")
    assert AR.parse_report_source("reddit", "", kind="search")["status"] == "EMPTY"     # what the host records for an empty body


def test_an_empty_output_is_uploaded_as_an_empty_body_so_the_round_can_complete(tmp_path):
    plan = _plan(candidates=(LAMP,), ebay_api=True)                                  # 4 Exa packets, 1 Jina packet
    done, log, _ = _run(tmp_path, plan, STUB_MCPORTER="empty")
    assert done.returncode == 0, done.stderr
    uploads = [a for a in _argvs(log, "curl") if "--data-binary" in a]
    assert sorted(a[11].split("?packet=", 1)[1] for a in uploads) == sorted(p["packet_id"] for p in plan["packets"])
    lines = done.stdout.strip().splitlines()
    empty = [line for line in lines if line.endswith("upload http 200 (retried once: only 0 bytes) (no output: recorded as EMPTY)")]
    assert len(empty) == 4 and all(": exit 0, 0 bytes, " in line for line in empty)   # the reader ran twice and found nothing
    assert len(_argvs(log, "mcporter")) == 8
    assert sorted(p.read_text() for p in log.glob("upload.*.body")).count("") == 4
    assert lines[-1] == f"polymath-fetch: done: 5 of 5 packets uploaded for report {REPORT} round 1; next: product_report_status"


def test_a_failed_read_is_read_once_more_before_its_one_upload(tmp_path):
    """Live 2026-11-02 (rpt_64ad6f4a34dccc5d915547ab, r1-c3-amazon-2): a 252-byte Jina read was uploaded, stored as "no product
    links", and the round counted complete. A read that exits non-zero, prints under 512 bytes, or prints Jina's own error JSON is
    read ONCE more (Exa after 5 s, Jina after 4 s, inside the pacing) and uploaded exactly once; the line says so."""
    plan = _plan(candidates=(LAMP,), ebay_api=True)                                   # 4 Exa packets, 1 Jina packet
    done, log, _ = _run(tmp_path / "once", plan, STUB_MCPORTER="fail_once", STUB_CURL="error_once")
    assert done.returncode == 0, done.stderr
    lines = done.stdout.strip().splitlines()
    exa_lines = [line for line in lines if "/search: " in line and "amazon-2" not in line]
    assert len(exa_lines) == 4 and all(": exit 0, " in line and line.endswith(" upload http 200 (retried once: exit 1)") for line in exa_lines)
    (jina_line,) = [line for line in lines if "r1-c1-amazon-2 " in line]
    assert jina_line.endswith(f"upload http 200 (retried once: only {len(JINA_ERROR)} bytes)") and ": exit 0, " in jina_line
    assert len(_argvs(log, "mcporter")) == 8 and len([a for a in _argvs(log, "curl") if "--data-binary" not in a]) == 2
    uploads = [a[11].split("?packet=", 1)[1] for a in _argvs(log, "curl") if "--data-binary" in a]
    assert sorted(uploads) == sorted(p["packet_id"] for p in plan["packets"])         # every packet uploaded exactly once
    bodies = [p.read_text() for p in log.glob("upload.*.body")]
    assert JINA_ERROR not in bodies and all(len(b) > AR.READER_MIN_BYTES for b in bodies)   # the second, real read went up
    assert Counter((log / "sleep.log").read_text().split()) == Counter({"5": 4, "4": 1, "1": 1, "3": 1})   # retries inside the pacing
    assert lines[-1] == f"polymath-fetch: done: 5 of 5 packets uploaded for report {REPORT} round 1; next: product_report_status"
    # Jina's error JSON every time, over 512 bytes: still a failed read (by its shape), read once more, uploaded once, never eval'd
    long_error = JINA_ERROR.replace("net::ERR_ABORTED", "net::ERR_ABORTED " + "z" * 600)
    done, log, _ = _run(tmp_path / "json", plan, STUB_CURL="error_json", STUB_JINA_ERROR=long_error)
    (jina_line,) = [line for line in done.stdout.splitlines() if "r1-c1-amazon-2 " in line]
    assert jina_line.endswith("upload http 200 (retried once: the reader's own error reply)") and done.returncode == 0
    assert len([a for a in _argvs(log, "curl") if "--data-binary" not in a]) == 2
    (body,) = {b for b in (p.read_text() for p in log.glob("upload.*.body")) if b.startswith("{")}
    parsed = AR.parse_report_source("amazon", body, kind="search")
    assert (parsed["status"], [r["code"] for r in parsed["refused"]]) == ("EMPTY", ["READER_FAILED"])


def test_a_jina_retry_reads_fresh_with_time_to_render_and_counts_once_in_the_pacing(tmp_path):
    """Live 2026-11-02 (amz_feeder.txt, now jina_amazon_search_snapshot.out): Jina answered an Amazon search read with its cached
    snapshot of a page that had not loaded, its two warnings over an empty Markdown Content. That is a failed read at any size
    (here padded over 512 bytes). The one retry of a Jina packet sends `X-No-Cache: true` and `X-Timeout: 30` with curl's limit
    raised from 90 to 120 s, the first read stays cached; an Exa retry runs its command as it was; the retry stays inside its
    packet's slot: one pause, no extra start, never two Jina reads at once keyless."""
    assert len(SNAPSHOT.encode()) == 346 and len(SNAPSHOT_PADDED.encode()) > AR.READER_MIN_BYTES
    plan = _plan(candidates=(LAMP,), ebay_api=True)                                   # 4 Exa packets, 1 Jina packet
    url = "https://r.jina.ai/https://www.amazon.com/s?k=Candle+warmer+lamp"
    for keyed in (False, True):
        env = {"JINA_API_KEY": "test-jina-key-2"} if keyed else {}
        auth = ["-H", "Authorization: Bearer test-jina-key-2"] if keyed else []
        done, log, _ = _run(tmp_path / f"keyed{int(keyed)}", plan, STUB_CURL="snapshot_once", STUB_MCPORTER="fail_once", **env)
        assert done.returncode == 0, done.stderr
        lines = done.stdout.strip().splitlines()
        (jina_line,) = [line for line in lines if "r1-c1-amazon-2 " in line]
        assert jina_line.endswith("upload http 200 (retried once: a cached snapshot of a page that had not loaded)")
        fetches = sorted((a for a in _argvs(log, "curl") if "--data-binary" not in a), key=lambda a: a[3] != "90")
        assert fetches == [                                                           # the stand-in curl's own record of each read
            ["-s", "-g", "-m", "90", *auth, "-H", "X-With-Links-Summary: true", url],
            ["-s", "-g", "-m", "120", *auth, "-H", "X-With-Links-Summary: true", "-H", "X-No-Cache: true", "-H", "X-Timeout: 30", url]]
        exa = Counter(tuple(a) for a in _argvs(log, "mcporter"))                      # each Exa search twice, as it was
        assert len(exa) == 4 and set(exa.values()) == {2} and not any("X-No-Cache: true" in a for a in exa)
        uploads = [a[11].split("?packet=", 1)[1] for a in _argvs(log, "curl") if "--data-binary" in a]
        assert sorted(uploads) == sorted(p["packet_id"] for p in plan["packets"])     # one upload per packet
        bodies = [p.read_text() for p in log.glob("upload.*.body")]
        assert SNAPSHOT_PADDED not in bodies and all(len(b) > AR.READER_MIN_BYTES for b in bodies)   # the fresh read went up
        # one retry pause each and no extra start: keyless the Jina queue still sleeps its 3 s gap once (keyed: no full batch)
        jina_gap = {"3": 1} if not keyed else {}
        assert Counter((log / "sleep.log").read_text().split()) == Counter({"5": 4, "4": 1, "1": 1, **jina_gap})
        assert max(_ints(log / "jina_concurrency")) == 1
    # the snapshot every time: read once more, uploaded once, and the host's parser names it a failed read
    done, log, _ = _run(tmp_path / "always", plan, STUB_CURL="snapshot")
    (jina_line,) = [line for line in done.stdout.splitlines() if "r1-c1-amazon-2 " in line]
    assert jina_line.endswith("upload http 200 (retried once: a cached snapshot of a page that had not loaded)") and done.returncode == 0
    assert len([a for a in _argvs(log, "curl") if "--data-binary" not in a]) == 2
    (body,) = [b for b in (p.read_text() for p in log.glob("upload.*.body")) if "cached snapshot" in b]
    parsed = AR.parse_report_source("amazon", body, kind="search")
    assert body == SNAPSHOT_PADDED and (parsed["status"], [r["code"] for r in parsed["refused"]]) == ("EMPTY", ["READER_FAILED"])


def test_an_upload_the_host_refuses_is_reported_and_no_curl_means_exit_three(tmp_path):
    plan = _plan(candidates=(LAMP,), ebay_api=True)
    done, _, _ = _run(tmp_path, plan, STUB_UPLOAD_CODE="410")
    assert done.returncode == 0 and all(" upload http 410" in line for line in done.stdout.strip().splitlines()[1:-1])
    assert done.stdout.strip().splitlines()[-1].startswith("polymath-fetch: done: 0 of 5 packets uploaded")
    empty = tmp_path / "nocurl"
    empty.mkdir()
    script = empty / "plan.sh"
    script.write_text(plan["script"])
    gone = subprocess.run([BASH, str(script)], cwd=empty, env={"PATH": str(empty), "HOME": str(empty), "TMPDIR": str(empty)},
                          capture_output=True, text=True, timeout=30, check=False)
    assert gone.returncode == 3 and gone.stdout.strip() == "polymath-fetch: curl is required: nothing was read or uploaded"
