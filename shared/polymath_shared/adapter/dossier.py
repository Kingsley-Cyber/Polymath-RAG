"""TRAIL-INTERFACE-V1 T5 — a run's research dossier, rendered on the server.

The dossier renderer is the ecommerce engine's own (`adapters/ecommerce/python/report.py`, reached through `governed_run.py report`). Its
one input is the governed run JOURNAL a host keeps beside a run. The server never had that file, but it stores the same facts: the run row,
every issued step with its accepted submission, and the terminal result. `journal_from_store` rebuilds the journal from them in the exact
shape `governed_run.py` writes, so the renderer runs unchanged. `render_dossier` runs it OUT OF PROCESS (the engine's top-level module
names `models`, `graph`, `report` never enter this process), keeps only the renderer's own tags and attributes from what comes back, and
wraps it in a document the route sends under a CSP that allows no script. Nothing here writes, scores or decides."""
from __future__ import annotations

import hashlib
import html
import json
import os
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from . import evidence_boundary as EB
from .contracts import _REPO

ENGINE = _REPO / "adapters" / "ecommerce"
RENDERER = ENGINE / "python" / "governed_run.py"
#: the adapters whose results the engine's governed renderer draws (report.build_model_from_governed): the legacy
#: `trail.product_discovery` it was written for, and `ecommerce.product_research`, which replaced it. No other adapter has a dossier.
DOSSIER_ADAPTERS = frozenset({"ecommerce.product_research", "trail.product_discovery"})
LAYOUTS = ("FULL_RESEARCH", "SOURCING", "EXECUTIVE", "COMMERCIAL")         # governed_run.py report --layout
JOURNAL_VERSION = "governed-run-journal-v1"                                # governed_run.JOURNAL_VERSION
MAX_EVIDENCE_ROWS = 60                                                     # governed_run.MAX_EVIDENCE_ROWS
RENDER_TIMEOUT_S = 30.0
MAX_HTML_BYTES = 5_000_000
#: an agent-answered step: the run status adapter_next showed beside it, and the submission kind that answers it
_AWAITING = {"AGENT_REASON": ("awaiting_agent", "reasoning"), "HARNESS_ACTION": ("awaiting_harness", "receipt")}


class NoDossier(LookupError):
    """The run's adapter has no dossier renderer."""


class DossierError(RuntimeError):
    """The renderer failed, timed out or answered too much. `code` is typed; the message may carry the renderer's stderr (log it,
    never send it to a caller)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ─────────────────────────────────────────────────────────── the journal
def _skill_version() -> str:
    """governed_run._skill_version: the engine manifest's `version:` line."""
    try:
        with open(ENGINE / "manifest.yaml", encoding="utf-8") as f:
            return next((line.split(":", 1)[1].strip() for line in f if line.startswith("version:")), "unknown")
    except OSError:
        return "unknown"


def _payload_hash(obj: Any) -> str:
    """governed_run._hash."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def _append(journal: dict[str, Any], kind: str, data: dict[str, Any], at: str | None) -> None:
    journal["events"].append({"seq": len(journal["events"]) + 1, "at": at or journal["created_at"], "kind": kind, "data": data})


def _evidence(sequence: int, step: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """What adapter_next showed beside the step (service._readable_evidence), rebuilt from the steps stored BEFORE it: hydration reads
    stored outputs only, so these are the rows the agent read. Trimmed as governed_run.record_next trims them."""
    try:
        ev = EB.hydrate((step.get("context") or {}).get("evidence_refs") or [],
                        [{"step_id": r["step_id"], "sequence": r["sequence"], "output": r.get("output")} for r in rows if int(r["sequence"]) < sequence])
    except Exception as exc:  # noqa: BLE001 — as in adapter_next: a failed hydration is said, never raised
        ev = {"rows": [], "receipts": [], "error": f"{type(exc).__name__}: {exc}"[:500]}
    return {"rows": list(ev.get("rows") or [])[:MAX_EVIDENCE_ROWS], "receipts": list(ev.get("receipts") or []), "coverage": ev.get("coverage"),
            **({"allocation": ev["allocation"]} if ev.get("allocation") else {}), **({"error": ev["error"]} if ev.get("error") else {})}


def journal_from_store(run: dict[str, Any], steps: list[dict[str, Any]], result: dict[str, Any] | None) -> dict[str, Any]:
    """The governed journal (governed_run.new_journal → record_next → record_submission → record_result) of a stored run.

    `run`: run_id, adapter_id, adapter_version, workflow_version, created_at, updated_at, agent_identity, input. `steps`: the run's
    store.list_steps rows. `result`: the terminal AdapterResultV1, or None while the run is live (the dossier then reads as in progress).
    One step event per agent-answered step, with the evidence it carried; one submission event per ACCEPTED submission (the store keeps
    no rejected one), kind `reasoning` for AGENT_REASON and `receipt` for HARNESS_ACTION. Status polls and the `materials` shown beside a
    step are not stored, so they are absent. Deterministic: sequence order, every time read from the store, `built_at` = the result's
    terminal time (else the run's last update), never now."""
    rows = sorted(steps, key=lambda s: int(s["sequence"]))
    answered = [r for r in rows if r["step_type"] in _AWAITING]
    accepted = {int(r["sequence"]): r["submission"] for r in answered if r["status"] == "accepted" and isinstance(r.get("submission"), dict)}
    # who reasoned and who researched: the run's own agent identity, else the identities its accepted submissions name
    reasoned_by = [(accepted[int(r["sequence"])].get("submitted_by") or {}).get("agent_identity")
                   for r in answered if r["step_type"] == "AGENT_REASON" and int(r["sequence"]) in accepted]
    agent = run.get("agent_identity") or next((str(who) for who in reasoned_by if who), None)
    harness = next((str(p["harness_id"]) for p in (sub.get("payload") for sub in accepted.values()) if isinstance(p, dict) and p.get("harness_id")), None)
    inp = dict(run.get("input") or {})
    ref = {k: run.get(k) for k in ("run_id", "adapter_id", "adapter_version", "workflow_version", "created_at")}
    journal: dict[str, Any] = {
        "journal_version": JOURNAL_VERSION, "skill_version": _skill_version(), "run_id": run["run_id"], "adapter_id": run["adapter_id"],
        "adapter_version": run.get("adapter_version"), "workflow_version": run.get("workflow_version"), "created_at": run.get("created_at"),
        "agent_identity": agent, "harness_id": harness or agent, "input": inp, "corpus_ids": list(inp.get("corpus_ids") or []), "events": []}
    _append(journal, "start", {"run_ref": {**ref, "status": "running"}}, run.get("created_at"))
    done = 0                                              # steps accepted so far: what adapter_submit's status answer counted
    for r in rows:
        if r["status"] in ("accepted", "executed"):
            done += 1
        awaiting = _AWAITING.get(r["step_type"])
        if not awaiting:
            continue
        step = r["step"] or {}
        _append(journal, "step", {"step": step, "status": awaiting[0], "evidence": _evidence(int(r["sequence"]), step, rows)}, step.get("issued_at"))
        sub = accepted.get(int(r["sequence"]))
        if sub is not None:
            payload = sub.get("payload")
            _append(journal, "submission", {"step_id": r["step_id"], "kind": awaiting[1], "payload": payload, "payload_hash": _payload_hash(payload),
                                            "accepted": True, "response": {"status": "running", "current_step_id": r["step_id"], "steps_accepted": done,
                                                                           "gap": None, "failure": None}}, sub.get("submitted_at"))
    if result is not None:
        _append(journal, "result", {"result": result}, result.get("terminal_at"))
    journal["built_at"] = (result or {}).get("terminal_at") or run.get("updated_at") or run.get("created_at")
    return journal


# ─────────────────────────────────────────────────────────── the page
#: report.render's own markup — every other tag is dropped (its text kept, escaped), every other attribute too
ALLOWED_TAGS = frozenset({"style", "header", "footer", "div", "p", "span", "strong", "em", "b", "br", "h1", "h2", "h3", "ul", "ol", "li",
                          "table", "tr", "th", "td", "blockquote"})
ALLOWED_ATTRIBUTES = frozenset({"class", "style", "title", "colspan"})
#: never in the renderer's output; if one ever appears, its content goes with it
_DROPPED_WITH_CONTENT = frozenset({"script", "noscript", "template", "iframe", "object", "embed", "svg", "math"})


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.dropping = 0
        self.in_style = 0

    def _open(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        kept = "".join(f' {k}="{html.escape(v or "", quote=True)}"' for k, v in attrs if k in ALLOWED_ATTRIBUTES)
        self.out.append(f"<{tag}{kept}>")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _DROPPED_WITH_CONTENT:
            self.dropping += 1
        elif not self.dropping and tag in ALLOWED_TAGS:
            self.in_style += tag == "style"
            self._open(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self.dropping and tag in ALLOWED_TAGS and tag != "style":
            self._open(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROPPED_WITH_CONTENT:
            self.dropping = max(0, self.dropping - 1)
        elif not self.dropping and tag in ALLOWED_TAGS and tag != "br":
            self.in_style = max(0, self.in_style - (tag == "style"))
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.dropping:
            # a stylesheet is raw text (entities are not decoded there); without `<` it cannot end its element early
            self.out.append(data.replace("<", "") if self.in_style else html.escape(data, quote=False))


def sanitize(fragment: str) -> str:
    """Re-serialize the renderer's HTML through a fixed allowlist of tags and attributes: text is escaped again, comments, doctypes,
    links, images, event handlers and scripts are gone. Defence in depth behind report.py's own escaping and the route's CSP."""
    p = _Sanitizer()
    p.feed(fragment)
    p.close()
    return "".join(p.out)


def document(body: str, title: str) -> str:
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(title)}</title></head><body>{body}</body></html>\n")


def render_dossier(journal: dict[str, Any], layout: str = "FULL_RESEARCH", *, title: str | None = None,
                   timeout_s: float = RENDER_TIMEOUT_S) -> str:
    """The dossier page for a journal: `governed_run.py report` in a subprocess (this interpreter, a private temporary directory, a
    minimal environment, a timeout), sanitized, wrapped in a document. Raises DossierError."""
    if layout not in LAYOUTS:
        raise DossierError("DOSSIER_LAYOUT_UNKNOWN", f"unknown layout {layout!r}")
    with tempfile.TemporaryDirectory(prefix="polymath-dossier-") as tmp:
        jpath, out = Path(tmp) / "journal.json", Path(tmp) / "dossier.html"
        jpath.write_text(json.dumps(journal, ensure_ascii=False, default=str), encoding="utf-8")
        # no DSN, no token; the engine's loop database (never used by the report) points into the temporary directory
        env = {"PATH": os.environ.get("PATH", ""), "LANG": os.environ.get("LANG", "en_US.UTF-8"), "PYTHONDONTWRITEBYTECODE": "1",
               "OPPORTUNITY_RESEARCH_DB": str(Path(tmp) / "loop.sqlite3")}
        try:
            proc = subprocess.run([sys.executable, str(RENDERER), "report", "--journal", str(jpath), "--out", str(out), "--layout", layout],
                                  capture_output=True, text=True, timeout=timeout_s, cwd=tmp, env=env, check=False)
        except subprocess.TimeoutExpired as exc:
            raise DossierError("DOSSIER_TIMEOUT", f"the dossier renderer took longer than {timeout_s:g}s") from exc
        if proc.returncode != 0 or not out.is_file():
            raise DossierError("DOSSIER_RENDER_FAILED", f"the dossier renderer exited {proc.returncode}: {proc.stderr.strip()[-600:]}")
        if out.stat().st_size > MAX_HTML_BYTES:
            raise DossierError("DOSSIER_TOO_LARGE", f"the dossier is larger than {MAX_HTML_BYTES} bytes")
        raw = out.read_text(encoding="utf-8")
    return document(sanitize(raw), title or f"Dossier · {journal.get('run_id')}")
