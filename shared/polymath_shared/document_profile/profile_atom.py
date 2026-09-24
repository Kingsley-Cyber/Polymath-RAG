"""PROFILE-ATOM-V1 — the Profile Atom primitive (R4): extract + persist atoms as first-class
records, independent of the global Document Profile.

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §6/§9/§34/§64: a Profile Atom is a single routing-
inferred unit (one THEORY / CONCEPT / LATENT-PATTERN / BOUNDARY / SEEALSO / BRIDGE / ANCHOR /
TENSION / INVERSION / RECALLQ) — "one atom = one dense vector" — used for **semantic routing /
expansion**, never as factual evidence. The document-profile compiler already produces these
fields; this module lifts them out of the compiled profile into their own durable rows
(Postgres = authority, §51) so the atom lane can search them independently. It does NOT
collapse atoms into the global profile.

Pure + store-thin: `extract_atoms` is deterministic over a compiled-profile dict; the persist /
read helpers take a live connection. Supersession is per (doc, profile_contract): a fresh
profile deactivates the doc's old atoms and (re)activates the new set — same atom text yields
the same `atom_id`, so re-persisting is idempotent.

ATOM-REPAIR-V1 (owner 2026-09-24, decision D4 "alongside"): a document can carry atoms from TWO
profile families — the base profile (v3.x: ~10 theories / concepts / seealso) and the vNext
research-index profile (one item per kind, incl. the latent kinds). A `source` tag
(`family:compiled_hash`, kept in `source_profile_hash`) scopes supersession to ONE family, so a
fresh vNext profile never deactivates the base atoms (the 2026-09-08 regression) and a fresh base
profile never deactivates the vNext atoms. Untagged (legacy) rows are superseded as before.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from polymath_shared.surface_registry import (  # single source of the atom taxonomy (P4a)
    ATOM_KINDS, ATTR_TO_KIND as _ATTR_TO_KIND, MECHANISM_KINDS, REDISCOVERY_KINDS, RELATIONAL_KINDS,
)

PROFILE_ATOM_VERSION = "profile-atom-v1"


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def atom_id(doc_id: str, profile_contract: str, kind: str, text: str) -> str:
    """Content identity — same (doc, contract, kind, normalized text) ⇒ same id (idempotent)."""
    key = f"{doc_id}|{profile_contract}|{kind}|{_norm(text).lower()}"
    return "atom_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class ProfileAtom:
    atom_id: str
    doc_id: str
    corpus_id: str | None
    profile_contract: str
    kind: str
    text: str
    ordinal: int


def extract_atoms(compiled: dict, *, doc_id: str, corpus_id: str | None,
                  profile_contract: str) -> list[ProfileAtom]:
    """One ProfileAtom per non-empty atom item across the 10 kinds, deduped by (kind, text).
    `compiled` is the artifact's `doc_profile.compiled` dict (or a compiler Record's dict)."""
    out: list[ProfileAtom] = []
    seen: set[str] = set()
    for attr, kind in _ATTR_TO_KIND.items():
        for i, raw in enumerate(compiled.get(attr) or []):
            t = _norm(raw)
            if not t:
                continue
            aid = atom_id(doc_id, profile_contract, kind, t)
            if aid in seen:
                continue
            seen.add(aid)
            out.append(ProfileAtom(aid, doc_id, corpus_id, profile_contract, kind, t, i))
    return out


#: ATOM-REPAIR-V1: the profile families whose atoms live side by side (D4 "alongside").
PROFILE_FAMILIES = ("base", "vnext")


def source_tag(family: str, compiled_hash: str) -> str:
    """The provenance an atom row keeps in `source_profile_hash`: `family:compiled_hash`."""
    if family not in PROFILE_FAMILIES:
        raise ValueError(f"unknown profile family {family!r}")
    return f"{family}:{compiled_hash or ''}"


def family_of(source: str | None) -> str | None:
    """The family of a `source_profile_hash`; None for an untagged (legacy) row."""
    fam = str(source or "").split(":", 1)[0] if ":" in str(source or "") else ""
    return fam if fam in PROFILE_FAMILIES else None


def persist_atoms(conn, *, doc_id: str, profile_contract: str, atoms: Sequence[ProfileAtom],
                  source: str | None = None) -> dict:
    """Supersede the doc's prior active atoms for this contract, then (re)activate the new set.
    Returns {'active': n, 'deactivated': m}. Idempotent.

    With a `source` (ATOM-REPAIR-V1) only the doc's active atoms of the SAME family — or untagged
    legacy rows — are superseded; the other family's atoms stay active, and every new row records
    the source. Without one, the original whole-document supersession runs unchanged."""
    if source is not None:
        fam = family_of(source)
        if fam is None:
            raise ValueError(f"source must be family:compiled_hash, got {source!r}")
        rows = conn.execute(
            "SELECT atom_id, source_profile_hash FROM document_profile_atoms "
            "WHERE doc_id=%s AND profile_contract=%s AND active",
            (doc_id, profile_contract),
        ).fetchall()
        doomed = [r[0] for r in rows if family_of(r[1]) in (fam, None)]
        if doomed:
            conn.execute(
                "UPDATE document_profile_atoms SET active=FALSE, updated_at=now() WHERE atom_id = ANY(%s)",
                (doomed,),
            )
        for a in atoms:
            conn.execute(
                "INSERT INTO document_profile_atoms "
                "(atom_id, doc_id, corpus_id, profile_contract, atom_kind, atom_text, ordinal, source_profile_hash, active) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE) "
                "ON CONFLICT (atom_id) DO UPDATE SET active=TRUE, ordinal=EXCLUDED.ordinal, "
                "corpus_id=EXCLUDED.corpus_id, source_profile_hash=EXCLUDED.source_profile_hash, updated_at=now()",
                (a.atom_id, a.doc_id, a.corpus_id, a.profile_contract, a.kind, a.text, a.ordinal, source),
            )
        return {"active": len(atoms), "deactivated": len(doomed), "family": fam}
    cur = conn.execute(
        "UPDATE document_profile_atoms SET active=FALSE, updated_at=now() "
        "WHERE doc_id=%s AND profile_contract=%s AND active",
        (doc_id, profile_contract),
    )
    deactivated = getattr(cur, "rowcount", 0) or 0
    for a in atoms:
        conn.execute(
            "INSERT INTO document_profile_atoms "
            "(atom_id, doc_id, corpus_id, profile_contract, atom_kind, atom_text, ordinal, active) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE) "
            "ON CONFLICT (atom_id) DO UPDATE SET active=TRUE, ordinal=EXCLUDED.ordinal, "
            "corpus_id=EXCLUDED.corpus_id, updated_at=now()",
            (a.atom_id, a.doc_id, a.corpus_id, a.profile_contract, a.kind, a.text, a.ordinal),
        )
    return {"active": len(atoms), "deactivated": deactivated}


def active_atoms(conn, *, corpus_id: str | None = None, doc_id: str | None = None,
                 kinds: Iterable[str] | None = None) -> list[ProfileAtom]:
    """Read active atoms, optionally scoped by corpus / doc / kinds."""
    where = ["active"]
    params: list = []
    if corpus_id is not None:
        where.append("corpus_id=%s")
        params.append(corpus_id)
    if doc_id is not None:
        where.append("doc_id=%s")
        params.append(doc_id)
    ks = tuple(kinds or ())
    if ks:
        where.append("atom_kind = ANY(%s)")
        params.append(list(ks))
    rows = conn.execute(
        "SELECT atom_id, doc_id, corpus_id, profile_contract, atom_kind, atom_text, ordinal "
        "FROM document_profile_atoms WHERE " + " AND ".join(where) +
        " ORDER BY doc_id, atom_kind, ordinal",
        tuple(params),
    ).fetchall()
    return [ProfileAtom(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows]


def active_atom_count(conn, *, corpus_id: str) -> int:
    return conn.execute(
        "SELECT count(*) FROM document_profile_atoms WHERE active AND corpus_id=%s", (corpus_id,)
    ).fetchone()[0]
