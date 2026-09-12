---
title: "WORK LOG — re-reading the authority found three mandatory clauses the verifier never measured, and one gate greener than reality"
change_id: AUTHORITY-GATE-RECOVERAGE-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.245
architecture_impact: "verifier gains four gates (real-URL functional verification, V2 views/backends, reader classification, re-fire) and migration 0060 adds verification_runs so a re-fire can be PROVEN rather than claimed. The public-URL gate no longer reports PASS while the page is 401. No product behaviour changed."
---

> I reported "25 PASS · 1 BLOCKED_OWNER" without re-reading the authority in this
> session. Re-reading it found three mandatory clauses with no gate at all, and a fourth
> gate that was passing on a redirect while the actual page was unreachable.

## Contract

§23 `<completion_gate>` and `<frontend_v2_real_url_cutover_gate>`, §22 `<global_target>`,
§20A `<mandatory_completion_gate>`, §17 re-fire.

## Changes

**The mapping.** 25 `<section>` blocks and 29 other top-level blocks. Mapping every
mandatory clause against the verifier's gate list found four problems.

**1 — the frontend gate was greener than reality.** `frontend_public_url_serves_v2`
probed `https://rag.kingsleylab.xyz/` and passed on `302 -> /v2/`. Probing `/v2/` itself,
which no gate did, returns:

```
HTTP/2 401
www-authenticate: Basic realm="restricted"
```

The real user-facing page is behind HTTP Basic auth whose credential is owner-held.
A browser confirms it: the page renders blank, console shows one 401. So the redirect was
being reported as though it proved the page serves V2, when the page cannot be reached at
all without a credential I must not guess. Now split:

| gate | verdict |
|---|---|
| `frontend_public_url_serves_v2` | PASS — routing is genuinely correct |
| `frontend_real_url_functionally_verified` | **BLOCKED_OWNER** — 401, credential owner-held |
| `frontend_v2_views_and_backends` | PASS — the functional half, at the origin the proxy fronts |

**2 — §23's frontend gate names eight checks; roughly one was measured.** The rest are
now covered, partly by a new automated gate and partly by browser verification recorded
here. Driven by hand at the origin (`127.0.0.1:7200/v2/`, the bundle the proxy fronts):

- **all six named views render** — Chat, Compare, Files, Graph, Control Plane, Settings
  (plus Overview);
- **Control Plane reflects backend authority** — `IDLE · 23 live workers · 0 queued`,
  matching the fleet count measured independently in Postgres, with per-function lane
  breakdowns (GRAPH_EXTRACTION 18 lanes active, DOCUMENT_PROFILE 2);
- **Files uses canonical readiness/status** — the three verdicts (CONTROL / SEMANTIC /
  VNEXT) plus per-document `GRAPH ENT.` / `GRAPH REL.` columns, i.e. the narrow
  operational projection this session's hot-path migration built;
- **Graph loads real data** — attested entities with surfaces, types, mention and doc
  counts from the canary corpus;
- **chat reaches the canonical backend** — a question typed into the UI posted to
  `POST /chat/stream -> 200`, and the durable receipt says
  `mode=HYBRID · status=ok · verdict=generated · plan=chat-retrieval-v2 ·
  synth=litellm:anthropic/deepseek-v4-flash-0731`. The final core, proven from the UI
  rather than from a test harness;
- **deep-link and refresh** — `/v2/files` and `/v2/graph/deep/link` both serve the SPA
  entry, while `/v2/assets/does-not-exist.js` correctly **404s instead of falling back to
  index.html** (a fallback there would hide broken builds);
- **console** — no errors from the origin app.

The re-firable half is now `frontend_v2_views_and_backends`: assets fetched from the
served index, all six view names present in the built bundle, `/corpora` +
`/control_plane` + `/semantic_readiness` all 200, deep-link falls back, missing asset
404s.

**3 — "`/ask`, MCP, and evaluation readers are explicitly classified" had no gate.** Now
measured live, and the answers were not what the docstrings implied:

- **`/ask` is not a retrieval-core reader at all.** Fired live, it returns
  `grounding: stored-objects-only-v1`, `query_router: query-router-v1`, and 4 stored
  objects — no engine, no mode. Engine convergence does not apply to it. That is a
  classification, not an exemption, and the gate re-derives it every run.
- **MCP is an HTTP reader** — no engine import; it goes through `/chat`, `/retrieve`,
  `/retrieve/plan` and friends, inheriting whatever those are gated to.
- **Two evaluation harnesses import the LEGACY engine directly** —
  `eval/r1f/measure.py` and `eval/r2a/harness.py` both
  `from orchestrator.api.hybrid import hybrid_fast_retrieve`. Verified: last touched
  2026-08-15, referenced only by docs, invoked by nothing, not imported by the suite.
  Classified per §23 as **intentionally retained with a reason** — they are the
  reproducible record of the experiment they ran, and porting them to the current core
  would destroy the very comparison they document. They are named in the gate, so if one
  ever goes live again that is where it shows.

  *The first version of this census flagged a `REPORT.md` and a JSON manifest for merely
  naming the symbol — the match-the-mention bug fixed twice already this session. It now
  matches an import line.*

**4 — re-fire was performed but never proven.** §23 requires production verification to
execute twice with the same commands and no source edits. Running it twice satisfies the
clause; the evidence lived in a terminal scrollback. Migration **0060** adds
`verification_runs` (commit, per-gate verdicts, counts), the verifier appends a row at the
end of every run, and `verification_refires_identically` compares this run against the
last clean run at the same commit — exposing what one run cannot: a verification that is
not reproducible, and a re-fire that never happened. It reports NOT_TESTED on a first
fire, never PASS.

## Proof

- `frontend_real_url_functionally_verified` → BLOCKED_OWNER with the literal 401 and
  `www-authenticate` header.
- `frontend_v2_views_and_backends` → PASS: `2 asset(s) fetched, 287697 bytes; all 6 §23
  views present in the bundle; corpora/control_plane/semantic_readiness all 200;
  deep-link falls back to the SPA; a missing asset 404s`.
- `readers_ask_mcp_eval_classified` → PASS with all three classes and their evidence.
- `verification_refires_identically` → NOT_TESTED on the first fire at this commit, by
  design; PASS only after a genuine second run.
- Browser evidence for the checks only a browser can show, listed above.

## Rejected claims

- **"25 PASS means the authority's gates pass."** Withdrawn. The verifier's gate list was
  derived from the authority earlier, but I had not re-checked the mapping in this
  session and asserted coverage I had not verified. Three clauses had no gate.
- **"The public URL serves V2 — the redirect proves it."** Rejected: the redirect proves
  routing. The page behind it is 401.
- **"Guess or reset the basic-auth credential to finish the frontend gate."** Refused.
  It is owner-held; the gate is BLOCKED_OWNER, which is the honest verdict.
- **"The two eval harnesses are dead code — delete them."** Rejected: §11 requires
  reader/writer disposition with proof, and their value IS being the frozen record of a
  past experiment. Classified, not removed.

## Open contract gaps

- The real URL's functional verification stays BLOCKED_OWNER until the owner supplies the
  basic-auth credential or opens the path. Everything else about that cutover is proven.
- Browser-only checks (rendered data, clean console) are verified by hand and recorded
  here; they are not re-firable without a browser driver.
