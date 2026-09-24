"""C0: is PyYAML (already installed) enough for the YAML card's spans? (CODE-KNOWLEDGE-V1 C0, spec §8 item 3)

The card needs, per file: parents = top-level sections with exact line spans; children = key blocks as exact source
ranges; `ALIASES` edges (alias -> anchor) with positions; comments kept in the evidence text. PyYAML's `compose()`
gives node start / end marks but drops comments from the node tree. The evidence is the EXACT SOURCE sliced by those
marks, so a comment is lost only if it falls outside every section slice. This script measures that on the repository
and checks anchors / aliases / merge keys / multi-document files on a fixture (the repository has none).

Rule tested: lines between sections (blank, comment, `---`) attach to the FOLLOWING section; trailing lines attach
to the last one. A gap line that is neither blank, a comment nor a document marker would be content outside every
section: it is counted as `uncovered_content_lines` (must be 0).

Deterministic, no network, no database. Run from the repository root:
    .venv/bin/python docs/wiki/experiments/code-knowledge-c0-2026-09-24/yaml_spans.py . > yaml_spans.json
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent

FIXTURE = """# game balance (fixture)
defaults: &base          # anchor on a mapping
  cooldown_s: 1.5
  damage: 10
sword:
  <<: *base              # merge key through an alias
  damage: 25
bow:
  <<: *base
  range: 40
aliases_list: [*base]
---
# second document
services:
  api:
    image: app:latest
    depends_on: [db]
  db:
    image: postgres:16
"""


def section_spans(text: str) -> tuple[list[dict], list[str]]:
    """(sections, lines): top-level key spans (0-based, inclusive) for every document of the file."""
    lines = text.splitlines()
    sections = []
    for doc_i, root in enumerate(yaml.compose_all(text, Loader=yaml.SafeLoader)):
        if not isinstance(root, yaml.MappingNode):
            if root is not None:
                end = root.end_mark.line - (1 if root.end_mark.column == 0 else 0)
                sections.append({"doc": doc_i, "key": "<non-mapping root>", "start": root.start_mark.line,
                                 "end": end})
            continue
        for k, v in root.value:
            end = v.end_mark.line - (1 if v.end_mark.column == 0 else 0)
            sections.append({"doc": doc_i, "key": str(k.value), "start": k.start_mark.line, "end": max(end, k.start_mark.line),
                             "start_index": k.start_mark.index, "end_index": v.end_mark.index})
    return sections, lines


def gap_report(sections: list[dict], lines: list[str]) -> dict:
    covered = set()
    overlaps = 0
    last_end = -1
    char_overlaps = 0
    last_char_end = -1
    for s in sections:
        if s["start"] <= last_end:
            overlaps += 1
        if s.get("start_index", 0) < last_char_end:
            char_overlaps += 1
        covered.update(range(s["start"], s["end"] + 1))
        last_end = max(last_end, s["end"])
        last_char_end = max(last_char_end, s.get("end_index", -1))
    comment_in = comment_gap = uncovered = blank_gap = marker_gap = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i in covered:
            if stripped.startswith("#"):
                comment_in += 1
            continue
        if not stripped:
            blank_gap += 1
        elif stripped.startswith("#"):
            comment_gap += 1
        elif stripped in ("---", "...") or stripped.startswith("--- "):
            marker_gap += 1
        else:
            uncovered += 1
    return {"sections": len(sections), "overlaps": overlaps, "char_offset_overlaps": char_overlaps, "comment_lines_inside_sections": comment_in,
            "comment_lines_between_sections": comment_gap, "blank_gap_lines": blank_gap,
            "document_marker_lines": marker_gap, "uncovered_content_lines": uncovered}


def anchors_and_aliases(text: str) -> dict:
    anchors, aliases = [], []
    for ev in yaml.parse(text, Loader=yaml.SafeLoader):
        if isinstance(ev, yaml.AliasEvent):
            aliases.append({"name": ev.anchor, "line": ev.start_mark.line + 1})
        elif getattr(ev, "anchor", None):
            anchors.append({"name": ev.anchor, "line": ev.start_mark.line + 1})
    return {"anchors": anchors, "aliases": aliases}


def main(root: Path) -> dict:
    spec = importlib.util.spec_from_file_location("census", HERE / "census.py")
    census = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(census)
    totals = {"files": 0, "sections": 0, "overlaps": 0, "char_offset_overlaps": 0, "comment_lines_inside_sections": 0,
              "comment_lines_between_sections": 0, "uncovered_content_lines": 0, "document_marker_lines": 0}
    problems = []
    for p in census.tracked_files(root):
        if not p.endswith((".yaml", ".yml")):
            continue
        text = (root / p).read_text(encoding="utf-8", errors="replace")
        sections, lines = section_spans(text)
        rep = gap_report(sections, lines)
        totals["files"] += 1
        for k in totals:
            if k != "files":
                totals[k] += rep[k]
        if rep["overlaps"] or rep["char_offset_overlaps"] or rep["uncovered_content_lines"]:
            problems.append({"path": p, **rep})
    fx_sections, fx_lines = section_spans(FIXTURE)
    fixture = {"sections": [(s["doc"], s["key"], s["start"] + 1, s["end"] + 1) for s in fx_sections],
               "gaps": gap_report(fx_sections, fx_lines), **anchors_and_aliases(FIXTURE),
               "merge_key_resolved_value": yaml.safe_load_all(FIXTURE).__next__()["sword"]}
    return {"measure": "CODE-KNOWLEDGE-V1 C0 YAML spans with PyYAML " + yaml.__version__,
            "repository": totals, "files_with_problems": problems, "fixture": fixture,
            "reading": ["comments between sections survive when gap lines attach to the following section",
                        ("LINE spans overlap on flow-style (single-line JSON-like) YAML; CHARACTER offsets (mark.index) "
                         "never do, so children are cut by offsets (chunks.char_start / char_end)"),
                        "the event stream gives every anchor and alias with its line: ALIASES edges need no other parser",
                        "PyYAML resolves `<<: *base` merge keys in load(); compose() keeps the alias node for the edge"]}


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()), indent=1, default=str))
