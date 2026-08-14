# Lexical resource layer

The predicate compiler's lexical-semantic evidence comes from four
pinned linguistic resources, flattened at BUILD time into immutable
runtime tables. Runtime never reads `resources/vendor/` — it reads
`resources/compiled/<resource_contract_id>/` only (proven by GATE 10).

## Pinned sources (compatibility family: SemLink 2 generation)

| Resource | Declared version | Immutable source |
|---|---|---|
| VerbNet | 3.3 | github.com/cu-clear/verbnet tag `vn-3.3` @ commit `9c6f7b949560189d5c72b863ee3cb47da4409a41` |
| PropBank | Unified frames (SemLink-2 generation) | github.com/propbank/propbank-frames `main` @ `c66e0ccf28b53f00051b187db83e937b5bee2e32` |
| FrameNet | 1.7 | NLTK corpus `framenet_v17` |
| SemLink | 2.0 | github.com/cu-clear/semlink `master` @ `2636bf5a4ae9c93b669a1184a8aaae9ca21552d3` |

Archives are pinned by sha256 in `resources/manifests/*.yaml`. Builds
NEVER follow `main`/`master`/`latest` — the URLs resolve the exact
commit, and the checksum is the final word (a moved ref cannot change
bytes silently; a changed byte fails verification).

Do NOT upgrade to newer resources casually: SemLink 2 was constructed
against VN 3.3 + Unified PropBank + FN 1.7. Newer is not better — the
family must stay aligned (docx §9).

## Licenses

Recorded per manifest: VerbNet 3.3 (VerbNet license), PropBank frames
(PropBank license), FrameNet 1.7 via NLTK distribution (FrameNet 1.7
license), SemLink (SemLink license). Raw archives are NOT committed —
`resources/vendor/` is gitignored; the manifest + deterministic fetch +
checksum reproduce them. The compiled tables under
`resources/compiled/` are committed (runtime artifact, derived data).

## Build pipeline

```bash
python scripts/fetch_resources.py        # atomic fetch, verifies inline
python scripts/verify_resources.py       # checksum gate (hard-fail)
python scripts/flatten_resources.py      # deterministic tables + contract
python scripts/compile_predicate_rules.py  # rule validation + coverage
```

A clean rebuild is byte-identical (GATE 1: `tables_sha256` in the
compiled manifest). Two clean builds → identical contract id.

## Resource contract identity

```text
resource_contract_id = sha256(
    verbnet source hash + propbank source hash + framenet source hash
    + semlink source hash + flattener version + normalization schema)
```

Facts carry the contract id + `compiled_lexical_sha256` in provenance,
so every compiled edge names the exact lexical world that produced it.

## Upgrade procedure (contract migration)

A lexical-resource upgrade is a deliberate migration, never an in-place
mutation:

1. pin the new immutable source + sha256 in the manifest;
2. `fetch_resources.py --force` → `verify_resources.py`;
3. `flatten_resources.py` → NEW `resource_contract_id` directory;
4. `compile_predicate_rules.py` → collision checks must pass;
5. run the lexical coverage report (compiled_lexical.json
   `rule_coverage`) — review MANUAL_ONLY → PARTIAL/COMPLETE moves and
   any CONFLICT;
6. run the extraction regression corpus (experiment 0002 gold);
7. compare graph facts under both contracts;
8. replace the OLD compiled directory in the repository (the old
   contract remains reconstructable by re-running the pinned old
   manifest/flattener — recorded in git history);
9. update the TREE entries for the new compiled paths and bump the
   work log + changelog.

The active compiled directory is always exactly ONE; the compiler
refuses to run with zero or multiple contract directories.
