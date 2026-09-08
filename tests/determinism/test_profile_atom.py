"""PROFILE-ATOM-V1 — pure extraction/identity tests (no DB)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from polymath_shared.document_profile.profile_atom import (  # noqa: E402
    ATOM_KINDS,
    MECHANISM_KINDS,
    RELATIONAL_KINDS,
    atom_id,
    extract_atoms,
)

CONTRACT = "doc-profile-schema-vX"


def test_extract_maps_every_kind_and_preserves_ordinal():
    compiled = {
        "theories": ["impact is anticipation-gated", "weight communicates force"],
        "concepts": ["kinetic chain"],
        "latent_pattern": ["compression before release"],
        "boundary": ["fast motion can reduce readability"],
        "seealso": ["Laban effort"],
        "bridge": ["control theory feedback"],
        "anchor": ["hydraulics"],
        "tension": ["speed vs readability"],
        "inversion": ["no anticipation → weak"],
        "recallq": ["what made the punch land?"],
        "topics": ["should be ignored"],   # not an atom kind
        "terms": ["FACS"],                 # not an atom kind
    }
    atoms = extract_atoms(compiled, doc_id="d1", corpus_id="cinema", profile_contract=CONTRACT)
    kinds = {a.kind for a in atoms}
    assert kinds == set(ATOM_KINDS)                         # all 10 kinds, nothing else
    assert not (kinds & {"TOPIC", "TERM"})
    theory = [a for a in atoms if a.kind == "THEORY"]
    assert [a.text for a in theory] == ["impact is anticipation-gated", "weight communicates force"]
    assert [a.ordinal for a in theory] == [0, 1]
    assert set(MECHANISM_KINDS) | set(RELATIONAL_KINDS) | {"RECALLQ"} == set(ATOM_KINDS)


def test_extract_dedupes_and_skips_blanks():
    compiled = {"concepts": ["kinetic chain", "  kinetic   chain ", "", "  ", "force"]}
    atoms = extract_atoms(compiled, doc_id="d1", corpus_id="c", profile_contract=CONTRACT)
    assert [a.text for a in atoms] == ["kinetic chain", "force"]   # normalized dup + blanks dropped


def test_atom_id_is_deterministic_and_content_addressed():
    a = atom_id("d1", CONTRACT, "THEORY", "impact is anticipation-gated")
    b = atom_id("d1", CONTRACT, "THEORY", "  impact   is anticipation-gated ")   # normalized-equal
    c = atom_id("d1", CONTRACT, "CONCEPT", "impact is anticipation-gated")       # different kind
    d = atom_id("d2", CONTRACT, "THEORY", "impact is anticipation-gated")        # different doc
    assert a == b and a.startswith("atom_")
    assert a != c and a != d


def test_empty_profile_yields_no_atoms():
    assert extract_atoms({}, doc_id="d1", corpus_id="c", profile_contract=CONTRACT) == []


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
