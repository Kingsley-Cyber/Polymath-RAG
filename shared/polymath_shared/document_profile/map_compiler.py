"""Parent-map compiler — tolerant format, strict identity.

Plan of record: docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md §9-§11, §18-§19,
§30-§33, §36.2, slice S2.

Deterministic policy (shared/): no I/O, no model. It parses the parent-map DSL the
LLM is asked to emit — one line per parent —

    MAP|<alias>|<routing signature>|<hook1>;<hook2>;<hook3>

into durable ``CompiledMap`` records, keyed to the real parent by the S1
``SkeletonManifest``. Governing rules:

* **Tolerant format, strict identity** (§18): accept harmless drift (``MAP|P17|``,
  ``MAP | P0017 |``, stray whitespace, Unicode punctuation) and resolve the alias
  to a KNOWN skeleton alias; reject an unknown / ambiguous / invented alias and an
  empty signature rather than attach a map to the wrong parent.
* **Partial output is useful work** (§18.4): 73 of 90 valid lines persist 73;
  ``missing_aliases`` is the exact remaining 17 to repair — successful lines are
  never re-run.
* **Exact identifiers are deterministic, not model hooks** (§9): every compiled
  map carries the skeleton's Python-extracted ``exact_identifiers`` verbatim,
  independent of whether the model listed an identifier as a semantic hook.
* **Reuse the repository normalization contract** (§10): compiled search text is
  NFC-normalized (as ``canonicalizer`` / ``identity`` do) with the measured
  Compound-Mini artifacts folded (non-breaking hyphen/space); the raw model text
  is hashed FIRST so ``raw_response_hash != map_completeness_hash`` by design.
* **Source text is untrusted data** (§30): an injected instruction inside a MAP
  line is compiled as the signature string; this compiler executes nothing.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Sequence

from polymath_shared.document_profile.parent_skeleton import SkeletonManifest

#: Versioned independently of the skeleton builder and the map prompt (§32).
MAP_COMPILER_VERSION = "map-compiler-v1"

MAX_HOOKS = 3

#: Generic hooks / signatures carry no routing signal (§19.2). Flagged, not fatal.
_GENERIC = frozenset(
    """
    system information important concept concepts section this that overview
    introduction summary details detail general various topic topics content
    """.split()
)
_GENERIC_SIGNATURE_RE = re.compile(
    r"^(this|the)\s+(section|chapter|part|document)\s+(discusses|covers|describes|is about|contains)",
    re.IGNORECASE,
)

#: Measured Compound-Mini artifacts (plan §10): non-breaking hyphen U+2011 in
#: "top‑k" / "micro‑damage" and non-breaking space U+00A0. Folded to ASCII in
#: SEARCH text only; identifiers are never routed through this.
_UNICODE_FOLD = {"‑": "-", " ": " ", "‐": "-"}
_WS_RE = re.compile(r"\s+")
_MAP_LINE_RE = re.compile(r"^\s*MAP\s*\|", re.IGNORECASE)
_ALIAS_RE = re.compile(r"^P?0*([0-9]+)$")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_search_text(text: str) -> str:
    """The repository's NFC Unicode contract (as canonicalizer/identity apply)
    plus the measured non-breaking-hyphen/space fold, quote/emphasis stripping and
    whitespace collapse — case preserved (this is display + embed text, not an
    identity key). Never applied to exact identifiers."""
    text = unicodedata.normalize("NFC", str(text or ""))
    text = "".join(_UNICODE_FOLD.get(ch, ch) for ch in text)
    text = text.strip().strip("\"'`*_ ").strip()
    return _WS_RE.sub(" ", text).strip()


def _alias_key(raw: str) -> str:
    """Mirror the profile compiler's tag normalization: strip, drop inner
    whitespace, upper-case. ``' p 17 '`` -> ``'P17'``."""
    return re.sub(r"\s+", "", str(raw or "").strip()).upper()


def _is_generic_signature(signature: str) -> bool:
    if _GENERIC_SIGNATURE_RE.search(signature):
        return True
    words = [w for w in re.findall(r"[A-Za-z']+", signature.lower())]
    return bool(words) and all(w in _GENERIC for w in words)


@dataclass(frozen=True)
class CompiledMap:
    alias: str
    parent_id: str
    routing_signature: str
    semantic_hooks: tuple[str, ...]
    exact_identifiers: tuple[str, ...]
    map_hash: str
    quality_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "parent_id": self.parent_id,
            "routing_signature": self.routing_signature,
            "semantic_hooks": list(self.semantic_hooks),
            "exact_identifiers": list(self.exact_identifiers),
            "map_hash": self.map_hash,
            "quality_flags": list(self.quality_flags),
        }


@dataclass(frozen=True)
class RejectedLine:
    raw: str
    reason: str
    alias: str | None = None


@dataclass(frozen=True)
class MapCompileResult:
    contract: str
    maps: tuple[CompiledMap, ...]
    missing_aliases: tuple[str, ...]
    unknown_aliases: tuple[str, ...]
    duplicate_aliases: tuple[str, ...]
    rejected: tuple[RejectedLine, ...]
    raw_response_hash: str
    #: The parent-map completeness hash (§33): binds the source manifest, the
    #: EXPECTED alias set, the valid (alias, map_hash) pairs AND the missing set —
    #: so a 73/90 partial and a different 73/90 partial never collide, and neither
    #: matches a complete 90/90 run of the same document.
    map_completeness_hash: str

    @property
    def expected_count(self) -> int:
        return len(self.maps) + len(self.missing_aliases)

    @property
    def complete(self) -> bool:
        return not self.missing_aliases

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "maps": [m.to_dict() for m in self.maps],
            "missing_aliases": list(self.missing_aliases),
            "unknown_aliases": list(self.unknown_aliases),
            "duplicate_aliases": list(self.duplicate_aliases),
            "rejected": [
                {"raw": r.raw, "reason": r.reason, "alias": r.alias} for r in self.rejected
            ],
            "raw_response_hash": self.raw_response_hash,
            "map_completeness_hash": self.map_completeness_hash,
        }


def _resolve_alias(raw_alias: str, expected_by_number: dict[int, list[str]]) -> tuple[str | None, str]:
    """Resolve a possibly-drifted alias (``P17`` / ``p0017``) to a known skeleton
    alias by its numeric value (zero-padding is cosmetic). Returns (alias, status)
    where status is 'ok' | 'unknown' | 'ambiguous'."""
    key = _alias_key(raw_alias)
    match = _ALIAS_RE.match(key)
    if not match:
        return None, "unknown"
    number = int(match.group(1))
    candidates = expected_by_number.get(number)
    if not candidates:
        return None, "unknown"
    if len(candidates) > 1:
        return None, "ambiguous"
    return candidates[0], "ok"


def _hooks(raw_hooks: str) -> tuple[tuple[str, ...], list[str]]:
    """Split ';'-separated hooks, normalize, drop empties/generics, dedup
    preserving order, cap at MAX_HOOKS. Returns (hooks, flags)."""
    flags: list[str] = []
    seen: dict[str, None] = {}
    dropped_generic = 0
    for part in raw_hooks.split(";"):
        hook = normalize_search_text(part)
        if not hook:
            continue
        if hook.lower() in _GENERIC:
            dropped_generic += 1
            continue
        seen.setdefault(hook, None)
    hooks = tuple(list(seen)[:MAX_HOOKS])
    if dropped_generic:
        flags.append(f"generic_hooks_dropped:{dropped_generic}")
    if len(hooks) != MAX_HOOKS:
        flags.append(f"hooks_count:{len(hooks)}")
    return hooks, flags


def compile_maps(
    raw_response: str,
    manifest: SkeletonManifest,
    *,
    contract: str = MAP_COMPILER_VERSION,
) -> MapCompileResult:
    """Compile a raw parent-map model response against the S1 skeleton manifest.

    Deterministic: same (raw_response, manifest) => same result. Only lines that
    resolve to a known alias with a non-empty signature become maps; the first
    valid record wins per alias (duplicates receipted); every remaining expected
    alias is reported for exact repair.
    """
    identifiers_by_alias = {
        s.alias: s.identifiers for s in manifest.skeletons
    }
    parent_by_alias = dict(manifest.alias_to_parent)
    expected_aliases = set(parent_by_alias)
    expected_by_number: dict[int, list[str]] = {}
    for alias in expected_aliases:
        m = _ALIAS_RE.match(alias)
        if m:
            expected_by_number.setdefault(int(m.group(1)), []).append(alias)

    maps: dict[str, CompiledMap] = {}
    duplicate_aliases: list[str] = []
    unknown_aliases: list[str] = []
    rejected: list[RejectedLine] = []

    for line in (raw_response or "").splitlines():
        if not line.strip():
            continue
        if not _MAP_LINE_RE.match(line):
            rejected.append(RejectedLine(raw=line.strip()[:200], reason="not_a_map_line"))
            continue
        parts = line.split("|")
        if len(parts) < 3:
            rejected.append(RejectedLine(raw=line.strip()[:200], reason="malformed_too_few_fields"))
            continue
        raw_alias = parts[1]
        signature = normalize_search_text(parts[2])
        raw_hooks = "|".join(parts[3:]) if len(parts) > 3 else ""

        alias, status = _resolve_alias(raw_alias, expected_by_number)
        if status != "ok":
            unknown_aliases.append(_alias_key(raw_alias))
            rejected.append(RejectedLine(raw=line.strip()[:200], reason=f"alias_{status}", alias=_alias_key(raw_alias)))
            continue
        assert alias is not None
        if not signature:
            rejected.append(RejectedLine(raw=line.strip()[:200], reason="empty_signature", alias=alias))
            continue
        if alias in maps:
            duplicate_aliases.append(alias)
            rejected.append(RejectedLine(raw=line.strip()[:200], reason="duplicate_alias", alias=alias))
            continue  # first valid record wins (pinned rule §18.3)

        hooks, flags = _hooks(raw_hooks)
        if _is_generic_signature(signature):
            flags.append("generic_signature")
        identifiers = tuple(identifiers_by_alias.get(alias, ()))
        map_hash = _sha256(
            "\x1f".join(
                [
                    contract,
                    alias,
                    parent_by_alias[alias],
                    signature,
                    "\x1e".join(hooks),
                    "\x1e".join(identifiers),
                ]
            )
        )
        maps[alias] = CompiledMap(
            alias=alias,
            parent_id=parent_by_alias[alias],
            routing_signature=signature,
            semantic_hooks=hooks,
            exact_identifiers=identifiers,
            map_hash=map_hash,
            quality_flags=tuple(flags),
        )

    ordered = tuple(maps[a] for a in sorted(maps))
    missing = tuple(sorted(expected_aliases - set(maps)))
    map_completeness_hash = _sha256(
        "\x1d".join(
            [
                "manifest:" + manifest.manifest_hash,
                "expected:" + ",".join(sorted(expected_aliases)),
                "valid:" + "|".join(f"{m.alias}\x1c{m.map_hash}" for m in ordered),
                "missing:" + ",".join(missing),
            ]
        )
    )
    return MapCompileResult(
        contract=contract,
        maps=ordered,
        missing_aliases=missing,
        unknown_aliases=tuple(sorted(set(unknown_aliases))),
        duplicate_aliases=tuple(sorted(set(duplicate_aliases))),
        rejected=tuple(rejected),
        raw_response_hash=_sha256(raw_response or ""),
        map_completeness_hash=map_completeness_hash,
    )
