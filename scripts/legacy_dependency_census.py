#!/usr/bin/env python
"""LEGACY-DEPENDENCY-CENSUS-V1 — slice S1 of RETRIEVAL-MIGRATION-DEPENDENCY-V1.

Answers the question the retirement half of the migration gates on: *where is each
legacy semantic symbol referenced, and is that reference a live runtime reader/writer,
or just a migration / test / doc?* (plan §S1, §12 GAP-01, §22, §S16.) The migration
law is "eliminate readers before stopping writers; stop writers before deleting
state" — so no legacy stage/table/kind may be retired until this census shows its
RUNTIME surface, and every runtime occurrence is classified (no "unknown runtime").

Read-only over repository SOURCE (no DB, no models, no network) — complementary to
`scripts/semantic_lane_census.py`, which measures durable-state LANE liveness
(opportunity-vs-capture) for the concept/procedure compilers. This tool measures
CODE dependency: it is the automated, drift-proof successor to the hand-maintained
classifications in `docs/wiki/reports/2026-09-07T1828/BE-AWARE.md` §10-§11.

    python scripts/legacy_dependency_census.py                 # full report
    python scripts/legacy_dependency_census.py --runtime-only   # just the live surface
    python scripts/legacy_dependency_census.py --symbol document_summaries
    python scripts/legacy_dependency_census.py --json

Classification is deterministic by PATH (migration / test / eval / doc / config /
runtime / script / other) and, for runtime occurrences, a HEURISTIC role
(writer > producer > reader > reference) by line content. A runtime occurrence tagged
`reference` is the review queue: it is a live-tree reference the heuristics could not
prove is a reader/writer/producer, and must be classified by a human before the
owning symbol is retired.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Legacy semantic symbols to inventory, grouped by the migration-plan classification
#: they carry (plan §11 bridge matrix / §10-§11 BE-AWARE). Each group's target state
#: is advisory context; the census only reports occurrences.
SYMBOL_GROUPS: dict[str, dict] = {
    "summaries": {
        "classification": "BRIDGE / DUAL-RUN (still read by retrieval routing; retire after readers migrate)",
        "symbols": [
            "retrieval_summaries", "parent_summaries", "document_summaries",
            "corpus_summaries", "summary_artifacts", "summary_jobs",
        ],
    },
    "summary_representation_kinds": {
        "classification": "BRIDGE (Qdrant routing points; ablate against child/profile)",
        "symbols": [
            "REPRESENTATION_KIND_SECTION_SUMMARY", "REPRESENTATION_KIND_DOCUMENT_SUMMARY",
            "section_summary", "document_summary",
        ],
    },
    "enrichment_latent": {
        "classification": "DUAL-RUN -> RETIRE (legacy latent/Wildcard path; no vNext replacement built)",
        "symbols": ["parent_enrichment", "parent_enrichments", "LATENT-TRANSFER", "latent_transfer"],
    },
    "compile_objects": {
        "classification": "TRACE-BEFORE-CUTOVER / likely KEEP (structured concept/procedure artifacts)",
        "symbols": ["compile_objects", "concept_artifacts", "procedure_artifacts"],
    },
    "compiler_title_context": {
        "classification": "KEEP initially (query-compiler corpus title context; GAP-02 ablation)",
        "symbols": ["POLYMATH_CHAT_COMPILER_TITLES_RANK", "_compiler_titles"],
    },
}

#: Directory names pruned entirely from the walk.
_PRUNE = {".git", "__pycache__", "node_modules", "dist", "var", "graphify-out", ".mypy_cache",
          ".pytest_cache", ".ruff_cache", "site-packages"}
_SCAN_EXT = {".py", ".sql", ".yaml", ".yml", ".toml", ".json", ".md", ".ts", ".tsx", ".js"}
_CONFIG_EXT = {".yaml", ".yml", ".toml", ".json"}

_WRITER_RE = re.compile(
    r"\bINSERT\s+INTO\b|\bUPDATE\s+\w|\bUPSERT\b|ON\s+CONFLICT|\bDELETE\s+FROM\b|"
    r"\bpersist\b|\.write\(|_write\b|save_|_upsert|write_receipt", re.IGNORECASE)
_PRODUCER_RE = re.compile(
    r"\bSTAGE_DAG\b|outbox_events|outbox\b|create_ticket|register.*stage|stage_tickets|"
    r"\barm_|_TICKET\b|emit_event|mint_", re.IGNORECASE)
_READER_RE = re.compile(
    r"\bSELECT\b|\bFROM\b|read_|get_|fetch|load_|\.get\(|\bquery\b|route|_reads?\b", re.IGNORECASE)
_CREATE_RE = re.compile(r"\bCREATE\s+(TABLE|INDEX|VIEW)|ALTER\s+TABLE|DROP\s+", re.IGNORECASE)


def _owner_layer(rel: str) -> str:
    for prefix, layer in (
        ("stores/postgres/migrations/", "migration"),
        ("orchestrator/", "orchestrator"), ("workers/", "worker"), ("control/", "control"),
        ("sidecars/", "sidecar"), ("shared/", "shared"), ("mcp_server/", "mcp"),
        ("tests/", "test"), ("eval/", "eval"), ("docs/", "doc"), ("scripts/", "script"),
        ("contracts/", "contract"), ("config/", "config"), ("resources/", "resource"),
        ("frontend/", "frontend"), ("research/", "research"), ("stores/", "store"),
    ):
        if rel.startswith(prefix):
            return layer
    return "other"


_RUNTIME_LAYERS = {"orchestrator", "worker", "control", "shared", "sidecar", "mcp"}


def _kind(rel: str, layer: str, ext: str) -> str:
    if layer == "migration":
        return "migration"
    if layer in ("test", "eval"):
        return layer
    if layer == "doc" or ext == ".md":
        return "doc"
    if ext in _CONFIG_EXT or layer == "config":
        return "config"
    if layer in _RUNTIME_LAYERS and ext in (".py", ".ts", ".tsx", ".js"):
        return "runtime"
    if layer == "frontend":
        return "frontend"
    if layer == "script":
        return "script"
    return "other"


#: S16(c) BENIGN auto-classification (RETRIEVAL-MIGRATION §S16): a runtime occurrence that matched no
#: writer/producer/reader verb is either a COMMENT or the symbol appearing inside a STRING LITERAL — a
#: name / event-type / dict key / lane-label / constant value, NOT a read of the legacy STATE. A genuine
#: read carries a reader verb (SELECT/FROM/get_/read_/fetch/load_/query/route/.get) caught ABOVE, so these
#: are safe to lift out of the human review queue. `LABEL` is deliberately narrow: the symbol must sit
#: BETWEEN two quotes with no intervening quote, so a bare-identifier reference stays `reference`.
_BENIGN_ROLES = ("comment", "label")


def _role(snippet: str, kind: str, symbol: str | None = None) -> str:
    """Heuristic role for a code occurrence. Precedence writer > producer > reader > (benign) > reference."""
    if kind == "migration":
        return "schema"
    if _CREATE_RE.search(snippet):
        return "schema"
    if _WRITER_RE.search(snippet):
        return "writer"
    if _PRODUCER_RE.search(snippet):
        return "producer"
    if _READER_RE.search(snippet):
        return "reader"
    if snippet.lstrip().startswith("#"):
        return "comment"                                   # a comment line — never a runtime reader
    if symbol and re.search(r"""["'][^"']*\b""" + re.escape(symbol) + r"""\b[^"']*["']""", snippet):
        return "label"                                     # symbol inside a string literal (name/key/label)
    return "reference"


@dataclass(frozen=True)
class Occurrence:
    group: str
    symbol: str
    file: str
    line: int
    layer: str
    kind: str
    role: str
    snippet: str


def _iter_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in _SCAN_EXT:
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(part in _PRUNE or part.startswith(".venv") for part in rel_parts):
            continue
        yield path


def collect(symbols_filter: set[str] | None = None) -> list[Occurrence]:
    wanted = {(g, s) for g, spec in SYMBOL_GROUPS.items() for s in spec["symbols"]
              if not symbols_filter or s in symbols_filter}
    by_symbol: dict[str, list[str]] = {}
    for g, s in wanted:
        by_symbol.setdefault(s, []).append(g)
    # word-boundary match so `document_summary` does not count inside `document_summaries`
    # and `section_summary` does not count inside `routing_section_summary`.
    pattern = {s: re.compile(r"\b" + re.escape(s) + r"\b") for s in by_symbol}
    out: list[Occurrence] = []
    for path in _iter_files():
        rel = str(path.relative_to(ROOT))
        # the census tool itself only DEFINES the symbol list — skip it so it is not
        # reported as a runtime dependency on every symbol it names.
        if rel == "scripts/legacy_dependency_census.py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        layer = _owner_layer(rel)
        ext = path.suffix
        kind = _kind(rel, layer, ext)
        for lineno, line in enumerate(text.splitlines(), 1):
            for symbol, groups in by_symbol.items():
                if pattern[symbol].search(line):
                    snippet = line.strip()[:120]
                    out.append(Occurrence(groups[0], symbol, rel, lineno, layer, kind,
                                           _role(snippet, kind, symbol), snippet))
    out.sort(key=lambda o: (o.group, o.symbol, o.file, o.line))
    return out


def _print_report(occ: list[Occurrence], runtime_only: bool) -> None:
    runtime = [o for o in occ if o.kind == "runtime"]
    unclassified = [o for o in runtime if o.role == "reference"]
    benign = [o for o in runtime if o.role in _BENIGN_ROLES]
    print("LEGACY-DEPENDENCY-CENSUS-V1 (repository source scan; read-only)\n")
    if not runtime_only:
        print("== occurrences by symbol (kind counts) ==")
        symbols = sorted({o.symbol for o in occ})
        kinds = ("runtime", "migration", "config", "test", "eval", "doc", "script", "frontend", "other")
        print(f"  {'symbol':38} {'total':>5}  " + "  ".join(f"{k[:4]:>4}" for k in kinds))
        for sym in symbols:
            so = [o for o in occ if o.symbol == sym]
            counts = {k: sum(1 for o in so if o.kind == k) for k in kinds}
            print(f"  {sym:38} {len(so):>5}  " + "  ".join(f"{counts[k]:>4}" for k in kinds))
        print()
    print(f"== RUNTIME surface ({len(runtime)} occurrences; the live dependency the migration must migrate) ==")
    for o in runtime:
        print(f"  [{o.role:9}] {o.layer:12} {o.file}:{o.line}  {o.snippet}")
    from collections import Counter as _C
    _brk = _C(o.role for o in benign)
    print(f"\n== BENIGN runtime ({len(benign)}; auto-classified out of the review queue, §S16c: "
          + ", ".join(f"{r}={_brk[r]}" for r in _BENIGN_ROLES) + ") ==")
    print("  (symbol as comment / string-literal name / event-type / dict key / lane label — no state read)")
    print(f"\n== UNCLASSIFIED RUNTIME ({len(unclassified)}; classify before retiring the owning symbol) ==")
    for o in unclassified:
        print(f"  {o.symbol:24} {o.file}:{o.line}  {o.snippet}")
    print(f"\nTOTAL occurrences={len(occ)}  runtime={len(runtime)}  "
          f"benign={len(benign)}  unclassified_runtime={len(unclassified)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Legacy semantic-dependency census (repo source scan).")
    ap.add_argument("--symbol", action="append", help="restrict to these symbols (repeatable)")
    ap.add_argument("--json", action="store_true", help="emit occurrences as JSON")
    ap.add_argument("--runtime-only", action="store_true", help="print only the runtime surface")
    args = ap.parse_args(argv)
    occ = collect(set(args.symbol) if args.symbol else None)
    if args.json:
        print(json.dumps([asdict(o) for o in occ], indent=2))
    else:
        _print_report(occ, args.runtime_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
