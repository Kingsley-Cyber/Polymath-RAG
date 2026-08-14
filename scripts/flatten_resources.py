#!/usr/bin/env python3
"""flatten_resources.py — raw lexical resources -> immutable lookup tables.

Build-time only. Outputs land under
resources/compiled/<resource_contract_id>/:

  lemma_to_vn_classes.json   lemma -> sorted VerbNet class ids (recursive)
  vn_class_index.json        class id -> {name?, members}
  lemma_to_pb_rolesets.json  lemma -> sorted PropBank rolesets
  pb_roleset_arguments.json  roleset -> {argn: gloss}
  pb_to_vn.json              roleset -> {vn_class: {pb_arg: vn_role}}
  pb_to_fn.json              roleset -> [frames]  (composed via the VN bridge)
  vn_to_fn.json              vn_class -> [frames]
  frame_index.json           frame -> sorted lexical units
  resource_index.json        existence index for compile gates 1-2
  manifest.json              resource_contract_id + source hashes + versions

Determinism (GATE 1): every table is sorted key-ordered JSON; two clean
builds from the same source hashes produce byte-identical files.

Runtime (GATE 10) reads ONLY resources/compiled/ — never vendor/.

Usage:
    python3 scripts/flatten_resources.py [--no-nltk]
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "resources" / "manifests"
VENDOR = ROOT / "resources" / "vendor"
COMPILED_ROOT = ROOT / "resources" / "compiled"

FLATTENER_VERSION = "1.0.0"
NORMALIZATION_SCHEMA_VERSION = "1.0.0"

NS = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_dump(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def flatten_verbnet(archive: Path) -> tuple[dict, dict]:
    """Recurse the 332 class XMLs: lemma -> class ids, class id -> members."""
    lemma_to_classes: dict[str, set[str]] = {}
    class_index: dict[str, dict] = {}

    with zipfile.ZipFile(archive) as zf:
        xml_files = [
            name for name in zf.namelist()
            if name.endswith(".xml") and "/verbnet3.3/" in name
        ]

        def walk_class(el, members_out: dict[str, list[str]]):
            for child in el:
                tag = child.tag.split("}")[-1]
                if tag == "MEMBERS":
                    for member in child.findall("MEMBER"):
                        name = member.get("name")
                        if name:
                            members_out[name] = True
                elif tag == "SUBCLASSES":
                    walk_class(child, members_out)

        for name in xml_files:
            root = ET.fromstring(zf.read(name))
            class_id = root.get("ID")
            if not class_id:
                continue
            members: dict[str, bool] = {}
            walk_class(root, members)
            class_index[class_id] = sorted(members)
            for member in members:
                lemma_to_classes.setdefault(member, set()).add(class_id)

    return (
        {lemma: sorted(classes) for lemma, classes in sorted(lemma_to_classes.items())},
        class_index,
    )


def flatten_propbank(archive: Path) -> tuple[dict, dict, list[str]]:
    """Frameset XMLs: lemma -> rolesets, roleset -> {arg: gloss}.

    Malformed upstream files are SKIPPED and reported (the upstream
    repo contains at least one XML typo, e.g. check.xml) — deterministic
    and auditable, never a silent partial read."""
    lemma_to_rolesets: dict[str, set[str]] = {}
    roleset_args: dict[str, dict] = {}
    skipped: list[str] = []

    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if not (name.endswith(".xml") and "/frames/" in name):
                continue
            try:
                root = ET.fromstring(zf.read(name))
            except ET.ParseError:
                skipped.append(name)
                continue
            for predicate in root.findall(".//predicate"):
                lemma = predicate.get("lemma")
                if not lemma:
                    continue
                for roleset in predicate.findall("roleset"):
                    rs_id = roleset.get("id")
                    if not rs_id:
                        continue
                    lemma_to_rolesets.setdefault(lemma, set()).add(rs_id)
                    args: dict[str, str] = {}
                    for role in roleset.findall(".//role"):
                        n = role.get("n")
                        if n and n.isdigit():
                            args[n] = (role.get("descr") or "").strip()
                    roleset_args[rs_id] = args

    return (
        {lemma: sorted(rs) for lemma, rs in sorted(lemma_to_rolesets.items())},
        roleset_args,
        skipped,
    )


def flatten_semlink(archive: Path, vn_class_index: dict, pb_args: dict, frame_index: dict):
    """SemLink 2 JSON mappings: pb->vn (roles), vn->fn, and pb->fn composed
    through the VN bridge (this release ships no direct pb-fn mapping).

    SemLink's VN ids do not all align with the vendored VN 3.3 class ids
    (documented partial coverage, docx §9) — unresolved keys are RETURNED
    and recorded in the build manifest, never silently dropped or fuzzy-
    joined across versions."""
    pb_to_vn: dict = {}
    vn_to_fn: dict = {}
    unresolved: list[str] = []
    with zipfile.ZipFile(archive) as zf:
        with zf.open(next(n for n in zf.namelist() if n.endswith("pb-vn2.json"))) as fh:
            raw_pb_vn = json.loads(fh.read().decode("utf-8"))
        with zf.open(next(n for n in zf.namelist() if n.endswith("vn-fn2.json"))) as fh:
            raw_vn_fn = json.loads(fh.read().decode("utf-8"))

    id_to_vn_class: dict[str, str] = {}
    for class_id in vn_class_index:
        number = class_id.rsplit("-", 1)[-1]
        id_to_vn_class.setdefault(number, class_id)
        id_to_vn_class.setdefault(class_id, class_id)

    for roleset, classes in sorted(raw_pb_vn.items()):
        mapped: dict[str, dict] = {}
        for key, roles in sorted(classes.items()):
            vn_class = id_to_vn_class.get(key)
            if vn_class is None:
                unresolved.append(f"pb-vn:{roleset}:{key}")
                continue
            mapped[vn_class] = {str(arg): str(role) for arg, role in sorted(roles.items())}
        if mapped:
            pb_to_vn[roleset] = mapped

    for key, frames in sorted(raw_vn_fn.items()):
        vn_class = id_to_vn_class.get(key.rsplit("-", 1)[0] if "-" in key else key)
        if vn_class is None:
            vn_class = id_to_vn_class.get(key)
        if vn_class is None:
            unresolved.append(f"vn-fn:{key}")
            continue
        vn_to_fn[vn_class] = sorted({f for f in frames if isinstance(f, str)})

    # Drop SemLink entries whose endpoints are missing from the FLATTENED
    # resource sets (e.g. rolesets inside upstream-malformed files) —
    # recorded in the manifest as coverage, never silently joined.
    valid_rolesets = set(pb_args)
    valid_frames = set(frame_index)
    pb_to_vn = {
        rs: classes for rs, classes in pb_to_vn.items()
        if rs in valid_rolesets and all(c in vn_class_index for c in classes)
    }
    vn_to_fn = {
        cls: sorted(set(frames) & valid_frames)
        for cls, frames in vn_to_fn.items()
        if set(frames) & valid_frames
    }

    pb_to_fn: dict[str, list[str]] = {}
    for roleset, classes in pb_to_vn.items():
        frames: set[str] = set()
        for vn_class in classes:
            frames.update(vn_to_fn.get(vn_class, []))
        if frames:
            pb_to_fn[roleset] = sorted(frames)

    # Directly attested vs derived: this SemLink 2 release ships NO direct
    # pb->fn mapping file; every pb->fn entry is COMPOSED through the VN
    # bridge. Recorded explicitly so consumers never confuse a chain
    # derivation with an attested mapping (docx §9).
    return pb_to_vn, vn_to_fn, pb_to_fn, {"direct": {}, "composed": pb_to_fn}, unresolved


def flatten_framenet(nltk_zip: Path) -> dict:
    """FrameNet 1.7 via the NLTK corpus: frame -> sorted lexical units."""
    import nltk

    # Point NLTK at the vendored corpus FIRST: the build must read the
    # pinned zip, never whatever happens to be in ~/nltk_data.
    corpora_root = VENDOR / "nltk" / "corpora"
    if str(corpora_root) not in nltk.data.path:
        nltk.data.path.insert(0, str(corpora_root))
    if str(VENDOR / "nltk") not in nltk.data.path:
        nltk.data.path.insert(0, str(VENDOR / "nltk"))

    from nltk.corpus import framenet

    frame_index: dict[str, list[str]] = {}
    frames = sorted(framenet.frames(), key=lambda f: f.name)
    for frame in frames:
        lus = sorted({lu.name for lu in frame.lexUnit.values()})
        frame_index[frame.name] = lus
    return frame_index


def _build_statistics(
    *,
    vn_index: dict,
    lemma_to_vn: dict,
    lemma_to_pb: dict,
    pb_args: dict,
    frame_index: dict,
    pb_to_vn: dict,
    vn_to_fn: dict,
    pb_to_fn: dict,
) -> dict:
    """Deterministic build statistics (spec §24). Diagnostic metadata —
    never part of the resource contract identity."""
    unified_lemmas = set(lemma_to_vn) | set(lemma_to_pb)
    return {
        "verbnet_classes": len(vn_index),
        "verbnet_member_lemmas": len(lemma_to_vn),
        "propbank_lemmas": len(lemma_to_pb),
        "propbank_rolesets": len(pb_args),
        "propbank_argument_definitions": sum(len(a) for a in pb_args.values()),
        "framenet_frames": len(frame_index),
        "framenet_lexical_units": sum(len(lus) for lus in frame_index.values()),
        "semlink_pb_to_vn_mappings": len(pb_to_vn),
        "semlink_vn_to_fn_mappings": len(vn_to_fn),
        "semlink_pb_to_fn_composed": len(pb_to_fn),
        "semlink_pb_to_fn_direct": 0,
        "unified_lemmas": len(unified_lemmas),
    }


def main() -> int:
    no_nltk = "--no-nltk" in sys.argv

    manifests = {}
    for manifest_path in sorted(MANIFESTS.glob("*.yaml")):
        m = yaml.safe_load(manifest_path.read_text())
        manifests[m["id"]] = m

    # -- verify checksums first (GATE 2) -------------------------------
    hashes: dict[str, str] = {}
    for mid, m in manifests.items():
        if m["kind"] == "archive":
            archive = VENDOR / m["archive_name"]
        else:
            archive = VENDOR / "nltk" / "corpora" / f"{m['corpus']}.zip"
        if not archive.exists():
            print(f"missing archive for {mid}; run fetch_resources.py first")
            return 1
        actual = _sha256_bytes(archive.read_bytes())
        if actual != m["sha256"]:
            print(f"CHECKSUM MISMATCH: {mid}\n  expected {m['sha256']}\n  actual   {actual}")
            return 1
        hashes[mid] = actual

    print("[verbnet] flattening classes...")
    lemma_to_vn, vn_index = flatten_verbnet(VENDOR / manifests["verbnet"]["archive_name"])
    print(f"  {len(vn_index)} classes, {len(lemma_to_vn)} member lemmas")

    print("[propbank] flattening rolesets...")
    lemma_to_pb, pb_args, pb_skipped = flatten_propbank(
        VENDOR / manifests["propbank"]["archive_name"]
    )
    print(f"  {len(lemma_to_pb)} lemmas, {len(pb_args)} rolesets, {len(pb_skipped)} malformed skipped")

    frame_index: dict = {}
    if not no_nltk:
        print("[framenet] flattening frame index (nltk)...")
        frame_index = flatten_framenet(VENDOR / "nltk" / "corpora" / "framenet_v17.zip")
        print(f"  {len(frame_index)} frames")

    print("[semlink] flattening mappings...")
    pb_to_vn, vn_to_fn, pb_to_fn, semlink_derivation, semlink_unresolved = flatten_semlink(
        VENDOR / manifests["semlink"]["archive_name"], vn_index, pb_args, frame_index
    )
    print(
        f"  {len(pb_to_vn)} pb->vn, {len(vn_to_fn)} vn->fn, "
        f"{len(pb_to_fn)} pb->fn (composed), {len(semlink_unresolved)} unresolved keys"
    )

    # -- resource contract id -------------------------------------------
    contract_parts = [
        f"verbnet:{hashes['verbnet']}",
        f"propbank:{hashes['propbank']}",
        f"framenet:{hashes['framenet']}",
        f"semlink:{hashes['semlink']}",
        f"flattener:{FLATTENER_VERSION}",
        f"schema:{NORMALIZATION_SCHEMA_VERSION}",
    ]
    resource_contract_id = hashlib.sha256("+".join(contract_parts).encode()).hexdigest()

    out_dir = COMPILED_ROOT / resource_contract_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tables = {
        "semlink_derivation.json": semlink_derivation,
        "lemma_to_vn_classes.json": lemma_to_vn,
        "vn_class_index.json": vn_index,
        "lemma_to_pb_rolesets.json": lemma_to_pb,
        "pb_roleset_arguments.json": pb_args,
        "pb_to_vn.json": pb_to_vn,
        "pb_to_fn.json": pb_to_fn,
        "vn_to_fn.json": vn_to_fn,
        "frame_index.json": frame_index,
        "resource_index.json": {
            "verbnet_classes": sorted(vn_index),
            "propbank_rolesets": sorted(pb_args),
            "framenet_frames": sorted(frame_index),
            "framenet_lus": sorted({lu for lus in frame_index.values() for lu in lus}),
        },
    }
    for name, table in tables.items():
        (out_dir / name).write_text(_json_dump(table))

    # Byte-identity digest over the generated tables (GATE 1): two clean
    # builds from the same source hashes must produce this same digest.
    tables_digest = _sha256_bytes(
        b"".join(
            sorted((out_dir / name).read_bytes() for name in sorted(tables))
        )
    )

    stats = _build_statistics(
        vn_index=vn_index,
        lemma_to_vn=lemma_to_vn,
        lemma_to_pb=lemma_to_pb,
        pb_args=pb_args,
        frame_index=frame_index,
        pb_to_vn=pb_to_vn,
        vn_to_fn=vn_to_fn,
        pb_to_fn=pb_to_fn,
    )
    (out_dir / "build_statistics.json").write_text(_json_dump(stats))

    (out_dir / "manifest.json").write_text(_json_dump({
        "resource_contract_id": resource_contract_id,
        "flattener_version": FLATTENER_VERSION,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
        "source_hashes": hashes,
        "source_versions": {mid: m["version"] for mid, m in manifests.items()},
        "tables": sorted(tables),
        "build_statistics": stats,
        "tables_sha256": tables_digest,
        "skipped_files": sorted(pb_skipped),
        "semlink_unresolved_keys": sorted(semlink_unresolved),
    }))

    print(f"\ncompiled into resources/compiled/{resource_contract_id}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
