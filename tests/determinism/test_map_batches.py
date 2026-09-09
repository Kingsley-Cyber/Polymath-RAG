"""DOCUMENT-SEMANTIC-INDEX-V1 slice S3 — token packer / capacity model.

Acceptance shape from the plan §36.3: the 40-parent measured fixture fits the
known baseline; the 60-parent estimated pack respects the token target; the
packer never exceeds the completion / TPM guard; the same measured density +
inputs give deterministic batch boundaries. Pure pins — composed with real S1
skeleton manifests, no API.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import map_batches as MB  # noqa: E402
from polymath_shared.document_profile import parent_skeleton as PS  # noqa: E402


def _manifest(n):
    parents = [
        {
            "chunk_id": f"par-{i}",
            "char_start": i * 100,
            "heading_path": [f"Section {i}"],
            "region_role": "body",
            "text": f"section {i} graph traversal reinforcement token{i} identifier ID{i:04d}",
        }
        for i in range(n)
    ]
    return PS.build_parent_skeletons(parents)


def _manifest_variant(n, tag):
    # A DIFFERENT document with the SAME alias set (P0001..) but different content.
    parents = [
        {
            "chunk_id": f"{tag}-par-{i}",
            "char_start": i * 100,
            "heading_path": [f"{tag} Section {i}"],
            "region_role": "body",
            "text": f"{tag} chapter {i} distinct content vocabulary token{i} MK{i:04d}",
        }
        for i in range(n)
    ]
    return PS.build_parent_skeletons(parents)


def test_mapping_only_capacity_is_reliability_capped():
    # The token envelope supports 60 (MAPPING_ONLY_TARGET), but compound-mini reliably maps
    # only small batches, so MAP_RELIABILITY_CAP (15) dominates — see the map_batches constant
    # (measured 2026-09-08: >=25-alias batches flakily return EMPTY, losing large-doc maps).
    assert MB.mapping_only_capacity(MB.DEFAULT_DENSITY) == MB.MAP_RELIABILITY_CAP == 15
    assert MB.MAP_RELIABILITY_CAP < MB.MAPPING_ONLY_TARGET == 60


def test_40_parent_token_baseline_holds_but_batches_are_reliability_capped():
    # Token baseline (§14.5) is unchanged — 40 parents ~= 8908 total tokens, 4 RPM feasible.
    assert round(MB.request_total_tokens(MB.DEFAULT_DENSITY, 40)) == 8908
    assert MB.token_feasible_rpm(MB.request_total_tokens(MB.DEFAULT_DENSITY, 40)) == 4
    # But batching is now reliability-capped at 15 → 3 batches [15, 15, 10] (not one 40-batch,
    # which compound-mini returned empty for). Each stays well under the completion envelope.
    plan = MB.plan_batches(_manifest(40))
    assert [b.parent_count for b in plan.batches] == [15, 15, 10]
    assert all(b.est_billed_tokens <= MB.COMPLETION_ENVELOPE_TOKENS for b in plan.batches)


def test_60_parent_pack_is_reliability_batched():
    # §14.5 token math at 60 parents is unchanged; batching is now 4 x 15 (was one 60-batch).
    assert round(MB.request_total_tokens(MB.DEFAULT_DENSITY, 60)) == 13362
    plan = MB.plan_batches(_manifest(60))
    assert [b.parent_count for b in plan.batches] == [15, 15, 15, 15]
    assert all(b.est_billed_tokens <= MB.COMPLETION_ENVELOPE_TOKENS for b in plan.batches)
    assert MB.token_feasible_rpm(MB.request_total_tokens(MB.DEFAULT_DENSITY, 60)) == 4


def test_overflow_splits_into_deterministic_bounded_batches():
    plan = MB.plan_batches(_manifest(150))
    assert [b.parent_count for b in plan.batches] == [15] * 10
    # Every batch stays under the completion envelope.
    assert all(b.est_billed_tokens <= MB.COMPLETION_ENVELOPE_TOKENS for b in plan.batches)
    # Aliases partition exactly once, in order, no gaps or repeats.
    seen = [a for b in plan.batches for a in b.aliases]
    assert seen == [s.alias for s in _manifest(150).skeletons]
    assert len(set(seen)) == 150
    # Deterministic.
    assert MB.plan_batches(_manifest(150)).plan_hash == plan.plan_hash


def test_packer_never_exceeds_completion_envelope_across_sizes():
    for n in (1, 5, 40, 61, 120, 181):
        plan = MB.plan_batches(_manifest(n))
        assert plan.total_parents == n
        for b in plan.batches:
            assert b.est_billed_tokens <= MB.COMPLETION_ENVELOPE_TOKENS


def test_token_feasible_rpm_guard():
    # Under the per-request cap => the 4 RPM ceiling stands.
    assert MB.token_feasible_rpm(13362) == 4
    # Above the cap => drop below 4.
    assert MB.token_feasible_rpm(20000) == 3   # 70000 // 20000
    assert MB.token_feasible_rpm(60000) == 1
    assert MB.token_feasible_rpm(0) == MB.TARGET_RPM


def test_token_feasible_rpm_boundary_at_15k():
    # The bug this pins: 15,001-17,500-token requests floor to 4 under TPM math,
    # so the per-request cap itself must drop the ceiling to 3 there.
    assert MB.token_feasible_rpm(15000) == 4   # exactly at the cap: still feasible
    assert MB.token_feasible_rpm(15001) == 3   # one over: reduced (was silently 4)
    assert MB.token_feasible_rpm(17500) == 3   # still reduced across the window
    assert MB.token_feasible_rpm(17501) == 3


def test_combined_capacity_leaves_room_for_the_global_profile():
    d = MB.DEFAULT_DENSITY
    assert MB.combined_capacity(d, global_profile_billed_tokens=1200) == (6500 - 1200 - 512) // 87
    # A large global profile leaves little room; an oversized one leaves none.
    assert MB.combined_capacity(d, global_profile_billed_tokens=5000) == (6500 - 5000 - 512) // 87
    assert MB.combined_capacity(d, global_profile_billed_tokens=7000) == 0


def test_combined_first_batch_then_mapping_only_overflow():
    plan = MB.plan_batches(_manifest(90), combined_global_profile_billed_tokens=1200)
    assert plan.batches[0].is_combined
    comb = MB.combined_capacity(MB.DEFAULT_DENSITY, global_profile_billed_tokens=1200)
    assert plan.batches[0].parent_count == comb
    assert all(not b.is_combined for b in plan.batches[1:])
    assert plan.total_parents == 90


def test_density_ema_update_moves_toward_new_measurement():
    d = MB.DEFAULT_DENSITY
    # A request that billed 100 tokens/parent over 40 parents.
    d2 = d.update(input_tokens=5428, billed_tokens=4000, visible_tokens=1165, parents=40)
    # EMA alpha 0.3: 87*0.7 + 100*0.3 = 90.9.
    assert 87.0 < d2.billed_tokens_per_parent <= 91.0
    # And re-planning with the new density is still deterministic + valid.
    plan = MB.plan_batches(_manifest(80), d2)
    assert plan.total_parents == 80
    assert all(b.est_billed_tokens <= MB.COMPLETION_ENVELOPE_TOKENS for b in plan.batches)


def test_deterministic_same_inputs_same_plan():
    a = MB.plan_batches(_manifest(75))
    b = MB.plan_batches(_manifest(75))
    assert a.plan_hash == b.plan_hash
    assert [x.aliases for x in a.batches] == [x.aliases for x in b.batches]


def test_batch_hash_binds_source_identity_no_cross_document_collision():
    # Two DIFFERENT documents that both alias P0001..P0060 identically...
    doc_a = _manifest(60)
    doc_b = _manifest_variant(60, "docB")
    assert [s.alias for s in doc_a.skeletons] == [s.alias for s in doc_b.skeletons]
    assert doc_a.manifest_hash != doc_b.manifest_hash
    a = MB.plan_batches(doc_a)
    b = MB.plan_batches(doc_b)
    # ...must never share durable batch identity (manifest_hash + skeleton_hashes bind it).
    assert a.batches[0].batch_hash != b.batches[0].batch_hash
    assert a.plan_hash != b.plan_hash


def test_skeleton_prompt_tokens_positive_and_bounded():
    man = _manifest(3)
    for s in man.skeletons:
        t = MB.skeleton_prompt_tokens(s)
        assert 0 < t < 200  # a skeleton is compact by construction


def test_module_is_pure():
    source = (ROOT / "shared" / "polymath_shared" / "document_profile" / "map_batches.py").read_text()
    roots = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    allowed = {"__future__", "hashlib", "math", "dataclasses", "typing", "polymath_shared"}
    assert roots <= allowed, f"unexpected imports in a pure stage: {roots - allowed}"
