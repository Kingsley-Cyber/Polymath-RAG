"""Document frontmatter (RETRIEVE-EVIDENCE-ROWS-V1, 2026-09-03).

Transcript exporters and book materializers write a `--- key: value ---` head.
Intake stamps it into `documents.frontmatter` (migration 0051); the evidence
view reads it so a row's source is auditable ("title · channel · date ·
9:25–9:41"), never a filesystem path. Pure, deterministic, no YAML dependency
(the head is flat key: value lines).
"""
from __future__ import annotations

import re

_FM_LINE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):\s*"?(.*?)"?\s*$', re.M)
FRONTMATTER_KEYS = ("title", "channel", "upload_date", "video_id", "url", "author",
                    "source_file", "source_type", "date", "duration")


def parse_frontmatter(text: str) -> dict:
    """Flat `key: value` frontmatter between the first two `---` lines, or a
    bare `title: "..."` head (document profiles). {} when absent."""
    if not text:
        return {}
    head = text.lstrip()
    if not head.startswith("---"):
        m = re.match(r'title:\s*"([^"]+)"', head)
        return {"title": m.group(1).strip()} if m else {}
    end = head.find("\n---", 3)
    block = head[3:end] if end != -1 else head[3:800]
    out: dict[str, str] = {}
    for k, v in _FM_LINE.findall(block):
        if k in FRONTMATTER_KEYS and v and k not in out:
            out[k] = v.strip().strip('"')
    return out
