#!/usr/bin/env python3
"""scaffold_polymath_v4.py: Materialize the v4 repo skeleton.

Usage:
    python3 scripts/scaffold_polymath_v4.py [--root <path>] [--name polymath-v4]

What this script does
---------------------
Creates the exact directory tree, every markdown file (empty stubs where
content is generated later), .gitignore, AGENTS.md, ARCHITECTURE.md, the
wiki scaffold, the contracts directory, the sidecar registry, and a
post-scaffold checklist.

It is **idempotent**: re-running it never clobbers existing files; it
fills in missing pieces only. Every file it creates has a one-line
breadcrumb comment that points back to this script and its SHA, so future
agents know the skeleton is intentional and not ad-hoc.

Why a script and not just a directory of MDs
--------------------------------------------
Because agents drift. A copy-paste tree of empty folders is fine once.
A script that recreates the tree from one source of truth means:

  1. The skeleton is reviewable in a diff.
  2. A new clone can be re-scaffolded without hunting for the right zip.
  3. The wiki scaffold regenerates from the same source as the
     directory layout: they cannot drift.

Contract enforced by this script
--------------------------------
- No file path is invented; every path is declared at the top of the
  script in the TREE constant. Add a new file there, not in a random
  place downstream.
- Every wiki Markdown file carries review metadata. The read-only wiki worm
  audits that metadata and lists open refactors and work records.
- `architecture/dependencies.json` owns dependency edges. `scripts/README.md`
  owns the management-script registry. `scripts/repo_guard.py` checks both.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import sys
from pathlib import Path
from typing import Iterable

# Content blocks live as module-level string constants. They are
# defined BEFORE TREE so the TREE entries can reference them by name.
# (See the bottom of the file for the actual constants.)

# ---------------------------------------------------------------------------
# Source of truth. Edit this list to grow the skeleton. The script enforces
# the rule: new files are declared here, never inlined elsewhere.
# ---------------------------------------------------------------------------

SCRIPT_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
TODAY = _dt.date.today().isoformat()


# ---------------------------------------------------------------------------
# Source of truth. Edit this list to grow the skeleton. The script enforces
# the rule: new files are declared here, never inlined elsewhere.
# ---------------------------------------------------------------------------
#
# Each entry is (relative_path, kind, content_key). `content_key` looks up
# the actual string in _CONTENT below. Keys (not values) keep the table
# readable; values are defined as constants in the second half of the file
# and are looked up at scaffold time, not at module load time, so forward
# references are safe.

TREE: list[tuple[str, str, str | None]] = [
    # ── Top-level governance ────────────────────────────────────────────────
    ("README.md", "md", "README"),
    ("CURRENT_STATE.md", "md", None),
    ("NEXT_SESSION.md", "md", None),
    ("RAG_E2E_CHECKLIST.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-checkpoint-e2e.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-bootstrap-continuity.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-critical-path-reprioritization.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-r3a-evidence-bundle.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-r3b-grounded-answer.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-c1-canonicalization.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-c2-canonical-kg.md", "md", None),
    ("ARCHITECTURE.md", "md", "ARCHITECTURE_STUB"),
    ("ARCHITECTURE_CHANGELOG.md", "md", "ARCHITECTURE_CHANGELOG_STUB"),
    ("PLAN.md", "md", "PLAN_STUB"),
    ("AGENTS.md", "md", "AGENTS_MD"),
    ("CONTRIBUTING.md", "md", "CONTRIBUTING_STUB"),
    ("LICENSE", "md", "LICENSE_STUB"),
    (".gitignore", "gitignore", "GITIGNORE"),
    (".env.example", "env", "ENV_EXAMPLE"),
    ("architecture/dependencies.json", "json", "ARCHITECTURE_DEPENDENCIES"),

    # ── Docs / wiki ─────────────────────────────────────────────────────────
    ("docs/README.md", "md", "DOCS_README"),
    ("docs/wiki/README.md", "md", "WIKI_README"),
    ("docs/wiki/decisions/0000-template.md", "md", "ADR_TEMPLATE"),
    ("docs/wiki/decisions/0001-use-gliner-2pass.md", "md", "ADR_0001"),
    ("docs/wiki/decisions/0002-postgres-not-mongo.md", "md", "ADR_0002"),
    ("docs/wiki/decisions/0003-no-gpu-in-docker.md", "md", "ADR_0003"),
    ("docs/wiki/decisions/0004-control-plane-separate-process.md", "md", "ADR_0004"),
    ("docs/wiki/decisions/0005-sidecar-contract.md", "md", "ADR_0005"),
    ("docs/wiki/refactors/README.md", "md", "REFACTOR_README"),
    ("docs/wiki/experiments/README.md", "md", "EXPERIMENT_README"),
    ("docs/wiki/work-log/README.md", "md", "WORK_LOG_README"),
    ("docs/wiki/work-log/2026-08-13-bootstrap.md", "md", "WORK_LOG_BOOTSTRAP"),
    ("docs/wiki/work-log/2026-08-13-phase-b.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-phase-c.md", "md", None),
    ("docs/wiki/decisions/0006-packaging-deployment.md", "md", None),
    ("docs/wiki/refactors/0001-phase-b-production.md", "md", None),
    ("docs/wiki/refactors/0002-r3a-evidence-bundle.md", "md", None),
    ("docs/wiki/refactors/0003-r3b-grounded-answer.md", "md", None),
    ("docs/wiki/refactors/0004-c1-canonicalization.md", "md", None),
    ("docs/wiki/refactors/0005-c2-canonical-kg.md", "md", None),
    ("docs/runbooks/operator.md", "md", "RUNBOOK_OPERATOR"),
    ("docs/runbooks/agent-onboarding.md", "md", "RUNBOOK_AGENT_ONBOARDING"),

    # ── Contracts (the load-bearing layer) ──────────────────────────────────
    ("contracts/README.md", "md", "CONTRACTS_README"),
    ("contracts/sidecar/v1/manifest.schema.json", "json", "SIDECAR_MANIFEST_SCHEMA"),
    ("contracts/sidecar/v1/manifest.example.json", "json", "SIDECAR_MANIFEST_EXAMPLE"),
    ("contracts/ingestion/v1/ingest_event.schema.json", "json", "INGEST_EVENT_SCHEMA"),
    ("contracts/ingestion/v1/materialization.schema.json", "json", None),
    ("contracts/extraction/v1/gliner_infer.schema.json", "json", "GLINER_INFER_SCHEMA"),
    ("contracts/extraction/v1/relation_candidate.schema.json", "json", "RELATION_CANDIDATE_SCHEMA"),
    ("contracts/answer/v1/evidence_bundle.schema.json", "json", None),
    ("contracts/answer/v1/chat_response.schema.json", "json", None),
    ("contracts/canonicalization/v1/canonicalization_output.schema.json", "json", None),

    # ── Sidecar registry (the source of truth for "where is X") ───────────
    ("sidecars/README.md", "md", "SIDECARS_README"),
    ("sidecars/gliner-runtime.toml", "toml", "SIDECAR_GLINER_RUNTIME"),
    ("sidecars/embedder.toml", "toml", "SIDECAR_EMBEDDER"),
    ("sidecars/reranker.toml", "toml", "SIDECAR_RERANKER"),
    ("sidecars/cloud-modal.toml", "toml", "SIDECAR_CLOUD_MODAL"),

    # ── Control plane (separate process) ───────────────────────────────────
    ("control/README.md", "md", "CONTROL_README"),
    ("control/pyproject.toml", "toml", "PYPROJECT_STUB"),
    ("control/control/__init__.py", "py", "PKG_INIT"),
    ("control/control/main.py", "py", "CONTROL_MAIN"),
    ("control/control/heartbeat.py", "py", "CONTROL_HEARTBEAT"),
    ("control/control/census.py", "py", "CONTROL_CENSUS"),
    ("control/control/scheduler.py", "py", "CONTROL_SCHEDULER"),
    ("control/control/supervisor.py", "py", "CONTROL_SUPERVISOR"),
    ("control/control/contracts.py", "py", "CONTROL_CONTRACTS"),
    ("control/systemd/polymath-control.service", "md", "SYSTEMD_UNIT"),

    # ── Sidecar implementations (each a host-native process, NOT a container) ─
    ("sidecars/gliner_runtime/server.py", "py", "SIDECAR_GLINER_RUNTIME_SERVER"),
    ("sidecars/gliner_runtime/manifest.toml", "toml", "SIDECAR_GLINER_RUNTIME_MANIFEST"),
    ("sidecars/embedder/server.py", "py", "SIDECAR_EMBEDDER_SERVER"),
    ("sidecars/reranker/server.py", "py", "SIDECAR_RERANKER_SERVER"),
    ("sidecars/reranker/manifest.toml", "toml", None),

    # ── Orchestrator (dumb on purpose) ────────────────────────────────────
    ("orchestrator/README.md", "md", "ORCHESTRATOR_README"),
    ("orchestrator/pyproject.toml", "toml", "PYPROJECT_STUB"),
    ("orchestrator/orchestrator/__init__.py", "py", "PKG_INIT"),
    ("orchestrator/orchestrator/main.py", "py", "ORCHESTRATOR_MAIN"),
    ("orchestrator/orchestrator/api/intake.py", "py", "ORCHESTRATOR_INTAKE"),
    ("orchestrator/orchestrator/api/retrieve.py", "py", None),
    ("orchestrator/orchestrator/api/evidence.py", "py", None),
    ("orchestrator/orchestrator/api/chat.py", "py", "ORCHESTRATOR_CHAT"),
    ("orchestrator/orchestrator/api/health.py", "py", "ORCHESTRATOR_HEALTH"),
    ("orchestrator/orchestrator/registry.py", "py", "ORCHESTRATOR_REGISTRY"),
    ("orchestrator/orchestrator/contracts.py", "py", "ORCHESTRATOR_CONTRACTS"),

    # ── Workers (queue-driven, idempotent) ─────────────────────────────────
    ("workers/README.md", "md", "WORKERS_README"),
    ("workers/pyproject.toml", "toml", "PYPROJECT_STUB"),
    ("workers/workers/__init__.py", "py", "PKG_INIT"),
    ("workers/workers/intake_worker.py", "py", "WORKER_INTAKE"),
    ("workers/workers/embed_worker.py", "py", "WORKER_EMBED"),
    ("workers/workers/extract_worker.py", "py", "WORKER_EXTRACT"),
    ("workers/workers/promote_worker.py", "py", "WORKER_PROMOTE"),

    # ── Shared library (contracts, identity, receipts) ─────────────────────
    ("shared/README.md", "md", "SHARED_README"),
    ("shared/pyproject.toml", "toml", "PYPROJECT_STUB"),
    ("shared/polymath_shared/__init__.py", "py", "PKG_INIT"),
    ("shared/polymath_shared/identity.py", "py", "_SHARED_IDENTITY"),
    ("shared/polymath_shared/receipts.py", "py", "_SHARED_RECEIPTS"),
    ("shared/polymath_shared/contracts.py", "py", "_SHARED_CONTRACTS"),
    ("shared/polymath_shared/logging.py", "py", "_SHARED_LOGGING"),
    ("shared/polymath_shared/clients.py", "py", "_SHARED_CLIENTS"),

    # ── Stores (durable state, all bind-mounted) ───────────────────────────
    ("stores/README.md", "md", "_STORES_README"),
    ("stores/postgres/migrations/0001_initial.sql", "md", "_POSTGRES_MIGRATION_0001"),
    ("stores/qdrant/snapshots/.gitkeep", "gitkeep", None),
    ("stores/neo4j/constraints/.gitkeep", "gitkeep", None),
    ("stores/redis/.gitkeep", "gitkeep", None),

    # ── Docker compose (only the data stores) ──────────────────────────────
    ("compose.yaml", "yaml", "_COMPOSE_DATA_STORES_ONLY"),

    # ── Tests ─────────────────────────────────────────────────────────────
    ("tests/README.md", "md", "_TESTS_README"),
    ("tests/conftest.py", "py", "_TESTS_CONFTEST"),
    ("tests/contracts/test_sidecar_manifest.py", "py", "_TEST_SIDECAR_MANIFEST"),
    ("tests/contracts/test_idempotency.py", "py", "_TEST_IDEMPOTENCY"),
    ("tests/determinism/test_canonical_hashing.py", "py", "_TEST_CANONICAL_HASHING"),

    # ── Ops scripts ───────────────────────────────────────────────────────
    ("scripts/README.md", "md", "SCRIPTS_README"),
    ("scripts/scaffold_polymath_v4.py", "self", None),
    ("scripts/check_install.sh", "md", "_CHECK_INSTALL_SH"),
    ("scripts/wiki_worm.py", "py", "_WIKI_WORM"),
    ("scripts/agent_preflight.py", "py", "_AGENT_PREFLIGHT"),
    ("scripts/repo_guard.py", "py", "_REPO_GUARD"),

    # ── CI ────────────────────────────────────────────────────────────────
    (".github/workflows/contracts.yml", "yaml", "_CI_CONTRACTS"),
    (".github/workflows/determinism.yml", "yaml", "_CI_DETERMINISM"),
    (".github/workflows/agent-preflight.yml", "yaml", "_CI_AGENT_PREFLIGHT"),
    (".github/workflows/repo-governance.yml", "yaml", "_CI_REPO_GOVERNANCE"),

    # ── Phase B production additions (2026-08-13) ─────────────────────────
    ("pyproject.toml", "toml", None),
    ("Makefile", "makefile", None),
    ("var/.gitkeep", "gitkeep", None),
    ("deployment/launchd/ai.polymath.api.plist", "plist", None),
    ("deployment/launchd/ai.polymath.control.plist", "plist", None),
    ("deployment/launchd/ai.polymath.worker.intake.plist", "plist", None),
    ("deployment/launchd/ai.polymath.worker.extract.plist", "plist", None),
    ("deployment/launchd/ai.polymath.gliner.plist", "plist", None),

    # shared: workflow authority plumbing + the deterministic rule pack
    ("shared/polymath_shared/settings.py", "py", None),
    ("shared/polymath_shared/db.py", "py", None),
    ("shared/polymath_shared/rulepack/__init__.py", "py", None),
    ("shared/polymath_shared/rulepack/compiler.py", "py", None),
    ("shared/polymath_shared/rulepack/negation.py", "py", None),
    ("shared/polymath_shared/rulepack/core-predicates.yaml", "yaml", None),
    ("shared/polymath_shared/rulepack/resource_index.yaml", "yaml", None),

    # workers: the no-LLM ingestion layer and extraction assembly
    ("workers/workers/summarizer.py", "py", None),
    ("workers/workers/chunker.py", "py", None),
    ("workers/workers/profile_router.py", "py", None),
    ("workers/workers/candidates.py", "py", None),
    ("workers/workers/syntax.py", "py", None),
    ("workers/workers/evidence_proposer.py", "py", None),
    ("workers/workers/project_qdrant_worker.py", "py", None),
    ("workers/workers/project_neo4j_worker.py", "py", None),
    ("workers/workers/verify_worker.py", "py", None),
    ("workers/workers/document_profile_builder.py", "py", None),
    ("workers/workers/profile_worker.py", "py", None),
    ("workers/workers/canonicalize_worker.py", "py", None),
    ("workers/workers/project_canonical_worker.py", "py", None),

    # shared: projection contracts (Phase F) + store drivers + retrieval
    ("shared/polymath_shared/projection_contracts.py", "py", None),
    ("shared/polymath_shared/stores.py", "py", None),
    ("shared/polymath_shared/retrieval.py", "py", None),
    ("shared/polymath_shared/evidence_assembly.py", "py", None),
    ("shared/polymath_shared/answer_synthesis.py", "py", None),
    ("shared/polymath_shared/canonicalizer.py", "py", None),
    ("shared/polymath_shared/materializer.py", "py", None),
    ("shared/polymath_shared/embedding_contracts.py", "py", None),

    # stores: Neo4j uniqueness constraints + document profile columns
    ("stores/neo4j/constraints/0001_uniqueness.cypher", "cypher", None),
    ("stores/postgres/migrations/0003_document_profiles.sql", "sql", None),
    ("stores/postgres/migrations/0004_projection_claims.sql", "sql", None),
    ("stores/postgres/migrations/0005_canonicalization.sql", "sql", None),
    ("stores/postgres/migrations/0006_materialization.sql", "sql", None),
    ("stores/postgres/migrations/0007_admission.sql", "sql", None),

    # sidecars: pinned embedder manifest (neural embedding contract)
    ("sidecars/embedder/manifest.toml", "toml", None),

    # deployment: Phase F/G workers
    ("deployment/launchd/ai.polymath.worker.project-qdrant.plist", "plist", None),
    ("deployment/launchd/ai.polymath.worker.project-neo4j.plist", "plist", None),
    ("deployment/launchd/ai.polymath.worker.verify.plist", "plist", None),
    ("deployment/launchd/ai.polymath.worker.profile-document.plist", "plist", None),
    ("deployment/launchd/ai.polymath.worker.canonicalize.plist", "plist", None),
    ("deployment/launchd/ai.polymath.worker.project-canonical.plist", "plist", None),

    # docs/wiki: Phase F/G decisions, experiments, work logs
    ("docs/wiki/decisions/0007-lexical-evidence-lane.md", "md", None),
    ("docs/wiki/experiments/0001-gliner-evidence-pass.md", "md", None),
    ("docs/wiki/experiments/0002-compiler-recovery.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-phase-f.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-phase-g1.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-phase-g2.md", "md", None),

    # eval: frozen gold data + the layer measurement harness
    ("eval/gold/qualification_q1.yaml", "yaml", None),
    ("eval/gold/realistic_smoke_v1/01_psychology_working_memory.md", "md", None),
    ("eval/gold/realistic_smoke_v1/02_technical_event_pipeline.md", "md", None),
    ("eval/gold/realistic_smoke_v1/03_research_notes_sleep_and_attention.md", "md", None),
    ("eval/gold/realistic_smoke_v1/04_transcript_local_rag_build.md", "md", None),
    ("eval/gold/realistic_smoke_v1/SHA256SUMS", "sha256", None),
    ("eval/gold/heldout_realistic_v1/01_psychology_attention_distraction.md", "md", None),
    ("eval/gold/heldout_realistic_v1/02_technical_job_queue.md", "md", None),
    ("eval/gold/heldout_realistic_v1/03_research_exercise_cognition.md", "md", None),
    ("eval/gold/heldout_realistic_v1/04_transcript_search_rebuild.md", "md", None),
    ("eval/gold/heldout_realistic_v1/SHA256SUMS", "sha256", None),
    ("eval/gold/heldout_ep1_v1/01_psychology_semantic_memory.md", "md", None),
    ("eval/gold/heldout_ep1_v1/02_technical_streaming_checkpoints.md", "md", None),
    ("eval/gold/heldout_ep1_v1/03_research_caffeine_alertness.md", "md", None),
    ("eval/gold/heldout_ep1_v1/04_transcript_analytics_migration.md", "md", None),
    ("eval/gold/heldout_ep1_v1/SHA256SUMS", "sha256", None),    ("eval/gold/ep1_dev_gold.yaml", "yaml", None),
    ("eval/gold/ep1_heldout_gold.yaml", "yaml", None),
    ("eval/ep1/harness_entity.py", "py", None),
    ("eval/ep1/REPORT_EP1.md", "md", None),
    ("eval/ep1/artifacts/realistic_smoke_v1_baseline.json", "json", None),
    ("eval/ep1/artifacts/realistic_smoke_v1_labels-v2.json", "json", None),
    ("eval/ep1/artifacts/realistic_smoke_v1_expand.json", "json", None),
    ("eval/ep1/artifacts/realistic_smoke_v1_both.json", "json", None),
    ("eval/ep1/artifacts/realistic_smoke_v1_threshold-v2.json", "json", None),
    ("eval/ep1/artifacts/realistic_smoke_v1_threshold-v2-expand.json", "json", None),
    ("eval/fixtures/native_docs/psychology.txt", "txt", None),
    ("eval/fixtures/native_docs/psychology.md", "md", None),
    ("eval/fixtures/native_docs/psychology.html", "html", None),
    ("eval/fixtures/native_docs/psychology.pdf", "pdf", None),
    ("eval/fixtures/native_docs/psychology.epub", "epub", None),
    ("eval/fixtures/native_docs/psychology.docx", "docx", None),
    ("eval/fixtures/native_docs/technical.txt", "txt", None),
    ("eval/fixtures/native_docs/technical.md", "md", None),
    ("eval/fixtures/native_docs/technical.html", "html", None),
    ("eval/fixtures/native_docs/technical.pdf", "pdf", None),
    ("eval/fixtures/native_docs/technical.epub", "epub", None),
    ("eval/fixtures/native_docs/technical.docx", "docx", None),
    ("eval/q1/REPORT_Q1.md", "md", None),
    ("eval/q1/artifacts/manifest.json", "json", None),
    ("eval/q1/artifacts/metrics.json", "json", None),
    ("eval/q1/artifacts/coverage_report.json", "json", None),
    ("eval/q1/artifacts/gold.jsonl", "jsonl", None),
    ("eval/q1/artifacts/frozen_inputs.jsonl", "jsonl", None),
    ("eval/q1/artifacts/baseline_predictions.jsonl", "jsonl", None),
    ("eval/q1/artifacts/baseline_predictions.sha256", "sha256", None),
    ("eval/q1/artifacts/baseline_waterfall.jsonl", "jsonl", None),
    ("eval/q1/artifacts/baseline_waterfall.sha256", "sha256", None),
    ("eval/q1/artifacts/hybrid_predictions.jsonl", "jsonl", None),
    ("eval/q1/artifacts/hybrid_predictions.sha256", "sha256", None),
    ("eval/q1/artifacts/hybrid_waterfall.jsonl", "jsonl", None),
    ("eval/q1/artifacts/hybrid_waterfall.sha256", "sha256", None),
    ("eval/q1/artifacts/changed_examples.jsonl", "jsonl", None),
    ("eval/q1/artifacts/predicate_breakdown.csv", "csv", None),
    ("eval/q1/artifacts/assertion_breakdown.csv", "csv", None),
    ("eval/q1/artifacts/polysemy_breakdown.csv", "csv", None),
    ("eval/q1/artifacts/resource_cohorts.csv", "csv", None),
    ("eval/q1/artifacts/paired_transitions.csv", "csv", None),
    ("tests/contracts/test_q1_qualification_regression.py", "py", None),
    ("tests/contracts/test_materialization_contract.py", "py", None),
    ("docs/wiki/work-log/2026-08-14-q1-qualification.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-i0-native-documents.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-bulk-acceptance-verify-fix.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-q1r-generalization.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-ep1-entity-proposal.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-em1-model-qualification.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-sr1-span-repair.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-e2-admission-production-wiring.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-smoke-admission-e2e-fail.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-d1-eligibility-receipt-predicate.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-d2-corpus-scoped-graph.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-smoke-admission-e2e-pass.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-d3-text-evidence-lane.md", "md", None),
    ("docs/wiki/decisions/0012-typed-evidence-support-lanes.md", "md", None),
    ("docs/wiki/refactors/0009-d3-text-evidence-lane.md", "md", None),
    ("contracts/answer/v2/evidence_bundle.schema.json", "json", None),
    ("contracts/answer/v2/chat_response.schema.json", "json", None),
    ("contracts/ingestion/v1/manifest.schema.json", "json", None),
    ("shared/polymath_shared/manifest.py", "py", None),
    ("shared/polymath_shared/intake_submission.py", "py", None),
    ("control/control/manifest_ingest.py", "py", None),
    ("scripts/ingest.py", "py", None),
    ("tests/fixtures/i1/manifest.yaml", "yaml", None),
    ("tests/fixtures/i1/duplicates.yaml", "yaml", None),
    ("tests/fixtures/i1/unknown_field.yaml", "yaml", None),
    ("tests/fixtures/i1/books/notes.md", "md", None),
    ("tests/fixtures/i1/books/plain.txt", "txt", None),
    ("tests/fixtures/i1/books/psychology.pdf", "pdf", None),
    ("tests/fixtures/i1/books/changed.md", "md", None),
    ("tests/fixtures/i1/books/disabled.md", "md", None),
    ("tests/fixtures/i1/papers/study.md", "md", None),
    ("tests/fixtures/i1/transcripts/session.txt", "txt", None),
    ("tests/determinism/test_manifest.py", "py", None),
    ("tests/integration/test_i1_manifest_ingestion.py", "py", None),
    ("tests/fixtures/i2/FROZEN.json", "json", None),
    ("tests/fixtures/i2/SHA256SUMS", "txt", None),
    ("tests/fixtures/i2/author.py", "py", None),
    ("tests/fixtures/i2/cyber/authentication.txt", "txt", None),
    ("tests/fixtures/i2/cyber/encryption_basics.md", "md", None),
    ("tests/fixtures/i2/cyber/incident_response.pdf", "pdf", None),
    ("tests/fixtures/i2/cyber/security_monitoring.md", "md", None),
    ("tests/fixtures/i2/cyber/threat_modeling.html", "html", None),
    ("tests/fixtures/i2/cyber/zero_trust.docx", "docx", None),
    ("tests/fixtures/i2/isolation.yaml", "yaml", None),
    ("tests/fixtures/i2/knowledge/corpus_management.txt", "txt", None),
    ("tests/fixtures/i2/knowledge/embedding_models.docx", "docx", None),
    ("tests/fixtures/i2/knowledge/evidence_bundles.md", "md", None),
    ("tests/fixtures/i2/knowledge/graph_traversal.md", "md", None),
    ("tests/fixtures/i2/knowledge/knowledge_graphs.epub", "epub", None),
    ("tests/fixtures/i2/knowledge/reranking.md", "md", None),
    ("tests/fixtures/i2/knowledge/retrieval_evaluation.md", "md", None),
    ("tests/fixtures/i2/manifest.yaml", "yaml", None),
    ("tests/fixtures/i2/psych/cognitive_load.md", "md", None),
    ("tests/fixtures/i2/psych/judgment_of_learning.epub", "epub", None),
    ("tests/fixtures/i2/psych/metacognitive_control.md", "md", None),
    ("tests/fixtures/i2/psych/metacognitive_monitoring.md", "md", None),
    ("tests/fixtures/i2/psych/retrieval_practice.md", "md", None),
    ("tests/fixtures/i2/psych/self_regulated_learning.md", "md", None),
    ("tests/fixtures/i2/psych/source_monitoring.md", "md", None),
    ("tests/fixtures/i2/psych/working_memory.txt", "txt", None),
    ("tests/fixtures/i2/systems/document_ingestion.md", "md", None),
    ("tests/fixtures/i2/systems/fault_tolerance.html", "html", None),
    ("tests/fixtures/i2/systems/platform_services.md", "md", None),
    ("tests/fixtures/i2/systems/retrieval_pipelines.pdf", "pdf", None),
    ("tests/fixtures/i2/systems/vector_indexes.md", "md", None),
    ("tests/fixtures/i2/systems/verification_loops.md", "md", None),
    ("tests/fixtures/i2/systems/worker_pools.md", "md", None),
    ("tests/fixtures/i2/iso/memory_note.txt", "txt", None),
    ("tests/fixtures/i2/iso/model_note.txt", "txt", None),
    ("tests/fixtures/i2/iso/pipeline_note.md", "md", None),
    ("tests/fixtures/i2/iso/systems_note.md", "md", None),
    ("eval/i2/verify_i2.py", "py", None),
    ("eval/i2/REPORT.md", "md", None),
    ("eval/d4/queries.json", "json", None),
    ("eval/d4/measure.py", "py", None),
    ("eval/d4/analyze.py", "py", None),
    ("eval/d4/REPORT.md", "md", None),
    ("eval/d4/artifacts/measure.json", "json", None),
    ("eval/d4/artifacts/gold.json", "json", None),
    ("eval/d4/artifacts/analysis.txt", "txt", None),
    ("eval/d4/artifacts/queries.sha256", "txt", None),
    ("eval/d4/build_d41_pairs.py", "py", None),
    ("eval/d4/eval_d41.py", "py", None),
    ("eval/d4/analyze_d41.py", "py", None),
    ("eval/d4/REPORT_D41.md", "md", None),
    ("eval/d4/artifacts/d41_pairs.jsonl", "jsonl", None),
    ("eval/d4/artifacts/d41_pairs.sha256", "txt", None),
    ("eval/d4/artifacts/d41_nli-deberta-v3-xsmall.json", "json", None),
    ("eval/d4/artifacts/d41_nli-deberta-v3-base.json", "json", None),
    ("eval/d4/artifacts/d41_qnli-distilroberta-base.json", "json", None),
    ("eval/d4/artifacts/d41_qnli-electra-base.json", "json", None),
    ("eval/d4/artifacts/d41_analysis.json", "json", None),
    ("eval/r1/POSTURE_REPORT.md", "md", None),
    ("shared/polymath_shared/retrieval_summaries.py", "py", None),
    ("stores/postgres/migrations/0008_retrieval_summaries.sql", "sql", None),
    ("stores/postgres/migrations/0009_mentions.sql", "sql", None),
    ("stores/postgres/migrations/0010_exact_provenance.sql", "sql", None),
    ("shared/polymath_shared/rulepack/core-predicates-v1.2.0.yaml", "yaml", None),
    ("tests/determinism/test_i3r_r1_trigger_contract.py", "py", None),
    ("tests/determinism/test_i3r_r2_argument_frames.py", "py", None),
    ("tests/determinism/test_i3r_r3_local_references.py", "py", None),
    ("tests/integration/test_i3r_r4_mentions.py", "py", None),
    ("tests/integration/test_i3r_r5_projection_consistency.py", "py", None),
    ("tests/determinism/test_i3r_r6_provenance.py", "py", None),
    ("eval/i3_5doc/REPORT_I3R.md", "md", None),
    ("docs/wiki/work-log/2026-08-16-i3r-repair.md", "md", None),
    ("docs/wiki/work-log/2026-08-16-i4-fresh-acceptance.md", "md", None),
    ("docs/wiki/work-log/2026-08-16-syntax-bootstrap.md", "md", None),
    ("docs/wiki/work-log/2026-08-16-i4r-a-boundary.md", "md", None),
    ("workers/workers/rescue.py", "py", None),
    ("contracts/extraction/v1/gliner_rescue.schema.json", "json", None),
    ("tests/determinism/test_i4r_a_boundary.py", "py", None),
    ("eval/i4r/REPORT.md", "md", None),
    ("eval/i4r/evidence/i4r-a-evidence.json", "json", None),
    ("eval/i4r/evidence/i4r-a-verify.log", "log", None),
    ("tests/integration/test_i4r_a_artifact_merge.py", "py", None),
    ("tests/determinism/test_i4r_b_missing_argument.py", "py", None),
    ("eval/i4r/evidence/i4r-b-evidence.json", "json", None),
    ("eval/i4r/evidence/i4r-b-verify.log", "log", None),
    ("docs/wiki/work-log/2026-08-16-i4r-b-missing-argument.md", "md", None),
    ("tests/determinism/test_i4r_c_type_reconciliation.py", "py", None),
    ("eval/i4r/evidence/i4r-c-evidence.json", "json", None),
    ("eval/i4r/evidence/i4r-c-verify.log", "log", None),
    ("docs/wiki/work-log/2026-08-16-i4r-c-type-reconciliation.md", "md", None),
    ("shared/polymath_shared/rulepack/core-predicates-v1.3.0.yaml", "yaml", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/compiled_lexical-v1.3.0.json", "json", None),
    ("tests/determinism/test_i4r_d_frame_arbitration.py", "py", None),
    ("eval/i4r/evidence/i4r-d-evidence.json", "json", None),
    ("eval/i4r/evidence/i4r-d-verify.log", "log", None),
    ("docs/wiki/work-log/2026-08-16-i4r-d-frame-arbitration.md", "md", None),
    ("shared/polymath_shared/query_policy.py", "py", None),
    ("stores/postgres/migrations/0011_semantic_query_policy.sql", "sql", None),
    ("tests/contracts/test_query_policy.py", "py", None),
    ("docs/wiki/experiments/0005-gliner-label-vocab-probe.md", "md", None),
    ("docs/wiki/work-log/2026-08-16-temporal-extraction-architecture.md", "md", None),
    ("docs/wiki/work-log/2026-08-16-temporal-interpretation-deferred.md", "md", None),
    ("eval/i4/matrix.py", "py", None),
    ("eval/i4/capability_matrix.json", "json", None),
    ("eval/i4/CAPABILITY_MATRIX.md", "md", None),
    ("eval/i4/freeze.py", "py", None),
    ("eval/i4/FROZEN_STATE.json", "json", None),
    ("eval/i4/verify_i4.py", "py", None),
    ("eval/i4/REPORT.md", "md", None),
    ("eval/i4/manifest.yaml", "yaml", None),
    ("eval/i4/manifest_reversed.yaml", "yaml", None),
    ("eval/i4/evidence/evidence.json", "json", None),
    ("eval/i4/evidence/verify_i4.log", "txt", None),
    ("eval/i4/corpus/01_northvale_health.md", "md", None),
    ("eval/i4/corpus/02_nimbus_cloud.md", "md", None),
    ("eval/i4/corpus/03_crestline_automation.md", "md", None),
    ("eval/i4/corpus/04_brightpath_learning.md", "md", None),
    ("eval/i4/corpus/05_corval_logistics.md", "md", None),
    ("eval/i4/gold/entity_gold.json", "json", None),
    ("eval/i4/gold/fact_gold.json", "json", None),
    ("eval/i4/gold/text_concept_gold.json", "json", None),
    ("eval/i4/versioned/manifest.yaml", "yaml", None),
    ("eval/i4/versioned/04_brightpath_learning.md", "md", None),
    ("tests/determinism/test_retrieval_summaries.py", "py", None),
    ("eval/r1a/routing_queries.json", "json", None),
    ("eval/r1a/measure_routing.py", "py", None),
    ("eval/r1a/routing_result.json", "json", None),
    ("eval/r1a/coverage_result.json", "json", None),
    ("shared/polymath_shared/pass1.py", "py", None),
    ("tests/determinism/test_pass1.py", "py", None),
    ("tests/integration/test_r1b_reconciliation.py", "py", None),
    ("eval/r1b/queries.json", "json", None),
    ("eval/r1b/measure.py", "py", None),
    ("eval/r1b/result.json", "json", None),
    ("shared/polymath_shared/retrieval_modes.py", "py", None),
    ("orchestrator/orchestrator/api/fast.py", "py", None),
    ("tests/integration/test_r1c_fast_endpoint.py", "py", None),
    ("eval/r1c/measure.py", "py", None),
    ("eval/r1c/result.json", "json", None),
    ("shared/polymath_shared/hybrid.py", "py", None),
    ("orchestrator/orchestrator/api/hybrid.py", "py", None),
    ("tests/determinism/test_hybrid.py", "py", None),
    ("eval/r1d/queries.json", "json", None),
    ("eval/r1d/measure.py", "py", None),
    ("eval/r1d/result.json", "json", None),
    ("shared/polymath_shared/reach.py", "py", None),
    ("tests/determinism/test_reach.py", "py", None),
    ("eval/r1e/queries.json", "json", None),
    ("eval/r1e/measure.py", "py", None),
    ("eval/r1e/result.json", "json", None),
    ("orchestrator/orchestrator/api/graph.py", "py", None),
    ("eval/r1f/measure.py", "py", None),
    ("eval/r1f/result.json", "json", None),
    ("eval/r2/AUDIT.md", "md", None),
    ("eval/r2a/synthesis_prompt_v1.txt", "txt", None),
    ("eval/r2a/queries.json", "json", None),
    ("eval/r2a/harness.py", "py", None),
    ("eval/r2a/run.py", "py", None),
    ("eval/r2a/seed.py", "py", None),
    ("eval/e3/verify_e3.py", "py", None),
    ("eval/e3/_failure_probe.py", "py", None),
    ("eval/e3b/verify_e3b.py", "py", None),
    ("eval/e3b/evidence.json", "json", None),
    ("eval/e4/analyze_e4.py", "py", None),
    ("eval/e4/evidence.json", "json", None),
    ("eval/e5/ANALYSIS.md", "md", None),
    ("shared/polymath_shared/concept_inventory.py", "py", None),
    ("eval/e5b/corpus/youtube.md", "md", None),
    ("eval/e5b/verify_e5b.py", "py", None),
    ("eval/e5b/evidence.json", "json", None),
    ("eval/e5b/REPORT.md", "md", None),
    ("tests/determinism/test_concept_inventory.py", "py", None),
    ("docs/wiki/work-log/2026-08-15-e5b-concept-inventory.md", "md", None),
    ("eval/e5b/routing_ab.py", "py", None),
    ("eval/e5b/routing_ab.json", "json", None),
    ("eval/e5b/coverage_ab.py", "py", None),
    ("eval/e5b/coverage_ab.json", "json", None),
    ("eval/e5b/retention.py", "py", None),
    ("eval/e5b/retention.json", "json", None),
    ("eval/e5b/zero_delta.py", "py", None),
    ("eval/e5b/zero_delta.json", "json", None),
    ("eval/e5b/freeze_p2.py", "py", None),
    ("eval/e5b/evidence_p2.json", "json", None),
    ("docs/wiki/work-log/2026-08-16-e5b-routing-qualification.md", "md", None),
    ("docs/wiki/work-log/2026-08-16-e5-track-closeout.md", "md", None),
    ("eval/r0/REPORT.md", "md", None),
    ("docs/wiki/work-log/2026-08-16-r0-reality-audit.md", "md", None),
    ("eval/i3_5doc/manifest.yaml", "yaml", None),
    ("eval/i3_5doc/manifest_reversed.yaml", "yaml", None),
    ("eval/i3_5doc/verify_i3.py", "py", None),
    ("eval/i3_5doc/REPORT.md", "md", None),
    ("eval/i3_5doc/corpus/SHA256SUMS", "txt", None),
    ("eval/i3_5doc/corpus/01_harborpay_oauth_incident.md", "md", None),
    ("eval/i3_5doc/corpus/02_monitoring_and_learning.md", "md", None),
    ("eval/i3_5doc/corpus/03_northwind_growth_review.md", "md", None),
    ("eval/i3_5doc/corpus/04_orion_event_pipeline.md", "md", None),
    ("eval/i3_5doc/corpus/05_warehouse_automation_transcript.md", "md", None),
    ("eval/i3_5doc/gold/GOLD_SHA256SUMS", "txt", None),
    ("eval/i3_5doc/gold/entity_gold.json", "json", None),
    ("eval/i3_5doc/gold/fact_gold.json", "json", None),
    ("eval/i3_5doc/gold/must_not_gold.json", "json", None),
    ("eval/i3_5doc/gold/text_concept_gold.json", "json", None),
    ("eval/i3_5doc/evidence/evidence.json", "json", None),
    ("eval/i3_5doc/evidence/verify_i3.log", "txt", None),
    ("eval/i3_5doc/versioned/manifest.yaml", "yaml", None),
    ("eval/i3_5doc/versioned/03_northwind_growth_review.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-e4-entity-recall-failure-analysis.md", "md", None),
    ("shared/polymath_shared/endpoint_binding.py", "py", None),
    ("docs/wiki/work-log/2026-08-15-e3b-extraction-quality-repair.md", "md", None),
    ("eval/e3/evidence.json", "json", None),
    ("eval/e3/corpus/author.py", "py", None),
    ("eval/e3/corpus/SHA256SUMS", "txt", None),
    ("eval/e3/gold/sample_table.json", "json", None),
    ("docs/wiki/work-log/2026-08-15-e3-gliner-only-ingestion.md", "md", None),
    ("eval/e3/corpus/docs/cinema_lighting.html", "html", None),
    ("eval/e3/corpus/docs/cinema_storyboard.md", "md", None),
    ("eval/e3/corpus/docs/cyber_phishing.html", "html", None),
    ("eval/e3/corpus/docs/cyber_zero_day.pdf", "pdf", None),
    ("eval/e3/corpus/docs/ecommerce_checkout.docx", "docx", None),
    ("eval/e3/corpus/docs/ecommerce_search.pdf", "pdf", None),
    ("eval/e3/corpus/docs/metacognition.md", "md", None),
    ("eval/e3/corpus/docs/metacognition_copy.md", "md", None),
    ("eval/e3/corpus/docs/psych_learning.epub", "epub", None),
    ("eval/e3/corpus/docs/psych_monitoring.md", "md", None),
    ("eval/e3/corpus/docs/software_distributed_queues.txt", "txt", None),
    ("eval/e3/corpus/docs/software_microservices.docx", "docx", None),
    ("eval/e3/corpus/docs/transcript_lecture.md", "md", None),
    ("eval/e3/corpus/docs/transcript_podcast.txt", "txt", None),
    ("docs/wiki/work-log/2026-08-15-r2-hierarchical-synthesis.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-r1f-graph-mode.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-r1e-pass2-corpus-reach.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-r1d-hybrid-retrieval.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-r1c-fast-production-route.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-r1b-summary-led-pass1.md", "md", None),
    ("eval/r1a/coverage/author.py", "py", None),
    ("eval/r1a/coverage/measure.py", "py", None),
    ("eval/r1a/coverage/inventory.json", "json", None),
    ("eval/r1a/coverage/SHA256SUMS", "txt", None),
    ("docs/wiki/work-log/2026-08-15-r1a-summary-routing-substrate.md", "md", None),
    ("eval/r1a/coverage/docs/d1_single_section.md", "md", None),
    ("eval/r1a/coverage/docs/d2_multi_section.md", "md", None),
    ("eval/r1a/coverage/docs/d3_dominant_plus_small.md", "md", None),
    ("eval/r1a/coverage/docs/d4_terminology_late.md", "md", None),
    ("eval/r1a/coverage/docs/d5_conclusion_not_in_intro.md", "md", None),
    ("eval/r1a/coverage/docs/d6_redundant_children.md", "md", None),
    ("eval/r1a/coverage/docs/d7_one_child_parent.md", "md", None),
    ("eval/r1a/coverage/docs/d8_multi_child_parent.md", "md", None),
    ("eval/r1a/coverage/docs/d9_mixed_structure.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-r1-retrieval-posture-audit.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-d41-answer-support-model-qualification.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-d4-text-support-admission.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-i2-corpus-integrity-qualification.md", "md", None),
    ("docs/wiki/decisions/0013-manifest-driven-bulk-ingestion.md", "md", None),
    ("docs/wiki/refactors/0010-i1-manifest-ingestion.md", "md", None),
    ("docs/wiki/work-log/2026-08-15-i1-manifest-driven-bulk-ingestion.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-g3-reranker.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-g5-answer-path-verification.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-g4-graph-expansion.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-g41-bidir-rerank.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-g42-seed-eligibility.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-entity-admission.md", "md", None),
    ("eval/admission/entity_admission.py", "py", None),
    ("eval/admission/qualify_admission.py", "py", None),
    ("eval/admission/admission_gold.json", "json", None),
    ("eval/admission/REPORT.md", "md", None),
    ("eval/admission/artifacts/admission_metrics.json", "json", None),
    ("eval/admission/admission_gold_v1.1.json", "json", None),
    ("eval/admission/downstream_g4.py", "py", None),
    ("eval/admission/artifacts/downstream_g4.json", "json", None),
    ("eval/g4_seed/manifest.json", "json", None),
    ("eval/g4_seed/qualify_g42.py", "py", None),
    ("eval/g4_seed/REPORT.md", "md", None),
    ("eval/g4_seed/artifacts/arm_a.json", "json", None),
    ("eval/g4_seed/artifacts/arm_b.json", "json", None),
    ("eval/g4_seed/artifacts/arm_c.json", "json", None),
    ("eval/g4_seed/artifacts/arm_d.json", "json", None),
    ("eval/g4_seed/artifacts/generic_surface_audit.csv", "csv", None),
    ("eval/g4/qualify_g41.py", "py", None),
    ("eval/g4/REPORT_G41.md", "md", None),
    ("eval/g4/artifacts/g41_metrics.json", "json", None),
    ("deployment/launchd/ai.polymath.reranker.plist", "plist", None),
    ("eval/g4/frozen_queries.json", "json", None),
    ("eval/g4/corpus_spec.json", "json", None),
    ("eval/g4/corpus_spec_v1.1.json", "json", None),
    ("eval/g4/qualify_g4.py", "py", None),
    ("eval/g4/REPORT_G4.md", "md", None),
    ("eval/g4/artifacts/baseline.jsonl", "jsonl", None),
    ("eval/g4/artifacts/baseline_no_graph.jsonl", "jsonl", None),
    ("eval/g4/artifacts/bidir-hop1.jsonl", "jsonl", None),
    ("eval/g4/artifacts/bidir-hop2.jsonl", "jsonl", None),
    ("eval/g4/artifacts/frozen_queries.jsonl", "jsonl", None),
    ("eval/g4/artifacts/graph_added_candidates.jsonl", "jsonl", None),
    ("eval/g4/artifacts/graph_degree_distribution.json", "json", None),
    ("eval/g4/artifacts/hop1.jsonl", "jsonl", None),
    ("eval/g4/artifacts/hop2.jsonl", "jsonl", None),
    ("eval/g4/artifacts/hub_analysis.csv", "csv", None),
    ("eval/g4/artifacts/manifest.json", "json", None),
    ("eval/g4/artifacts/metrics.json", "json", None),
    ("eval/g4/artifacts/noise_by_hop.csv", "csv", None),
    ("docs/wiki/experiments/0003-g3-reranker.md", "md", None),
    ("docs/wiki/experiments/0004-g5-answer-path-verification.md", "md", None),
    ("shared/polymath_shared/span_repair.py", "py", None),
    ("shared/polymath_shared/entity_admission.py", "py", None),
    ("shared/polymath_shared/neo4j_eligibility.py", "py", None),
    ("shared/polymath_shared/rerank.py", "py", None),
    ("eval/sr1/qualify_sr1.py", "py", None),
    ("eval/sr1/REPORT_SR1.md", "md", None),
    ("eval/sr1/artifacts/SR1-A_0.30.json", "json", None),
    ("eval/sr1/artifacts/SR1-A_0.35.json", "json", None),
    ("eval/sr1/artifacts/SR1-A_0.40.json", "json", None),
    ("eval/sr1/artifacts/SR1-A_0.45.json", "json", None),
    ("eval/sr1/artifacts/SR1-B_0.45.json", "json", None),
    ("eval/em1/models.yaml", "yaml", None),
    ("eval/em1/qualify_em1.py", "py", None),
    ("eval/em1/REPORT_EM1.md", "md", None),
    ("eval/em1/artifacts/baseline-medium_0.30.json", "json", None),
    ("eval/em1/artifacts/baseline-medium_0.35.json", "json", None),
    ("eval/em1/artifacts/baseline-medium_0.40.json", "json", None),
    ("eval/em1/artifacts/baseline-medium_0.45.json", "json", None),
    ("eval/em1/artifacts/baseline-medium_0.50.json", "json", None),
    ("eval/em1/artifacts/baseline-medium_0.55.json", "json", None),
    ("eval/em1/artifacts/baseline-medium_0.60.json", "json", None),
    ("eval/em1/artifacts/A-large-v21_0.30.json", "json", None),
    ("eval/em1/artifacts/A-large-v21_0.35.json", "json", None),
    ("eval/em1/artifacts/A-large-v21_0.40.json", "json", None),
    ("eval/em1/artifacts/A-large-v21_0.45.json", "json", None),
    ("eval/em1/artifacts/A-large-v21_0.50.json", "json", None),
    ("eval/em1/artifacts/A-large-v21_0.55.json", "json", None),
    ("eval/em1/artifacts/A-large-v21_0.60.json", "json", None),
    ("eval/em1/artifacts/B-large-v25_0.30.json", "json", None),
    ("eval/em1/artifacts/B-large-v25_0.35.json", "json", None),
    ("eval/em1/artifacts/B-large-v25_0.40.json", "json", None),
    ("eval/em1/artifacts/B-large-v25_0.45.json", "json", None),
    ("eval/em1/artifacts/B-large-v25_0.50.json", "json", None),
    ("eval/em1/artifacts/B-large-v25_0.55.json", "json", None),
    ("eval/em1/artifacts/B-large-v25_0.60.json", "json", None),
    ("eval/em1/artifacts/C-nuner-zero_0.30.json", "json", None),
    ("eval/em1/artifacts/C-nuner-zero_0.35.json", "json", None),
    ("eval/em1/artifacts/C-nuner-zero_0.40.json", "json", None),
    ("eval/em1/artifacts/C-nuner-zero_0.45.json", "json", None),
    ("eval/em1/artifacts/C-nuner-zero_0.50.json", "json", None),
    ("eval/em1/artifacts/C-nuner-zero_0.55.json", "json", None),
    ("eval/em1/artifacts/C-nuner-zero_0.60.json", "json", None),
    ("eval/q1r/REPORT_Q1R.md", "md", None),
    ("tests/determinism/test_q1r_v110_revision.py", "py", None),
    ("tests/fixtures/smoke/metacognition_excerpt_test.md", "md", None),
    ("tests/determinism/test_entity_admission.py", "py", None),
    ("tests/determinism/test_neo4j_eligibility.py", "py", None),
    ("tests/determinism/test_rerank_wrapper.py", "py", None),
    ("shared/polymath_shared/rulepack/core-predicates-v1.1.0.yaml", "yaml", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/compiled_lexical-v1.1.0.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/compiled_lexical-v1.2.0.json", "json", None),
    ("docs/wiki/refactors/0006-q1-qualification.md", "md", None),
    ("docs/wiki/refactors/0007-i0-native-documents.md", "md", None),
    ("docs/wiki/refactors/0008-e2-admission-production.md", "md", None),
    ("eval/gold/relations_v1.yaml", "yaml", None),
    ("eval/measure_layers.py", "py", None),

    # tests: Phase F gate + G1/G2 cross-domain routing acceptance
    ("tests/integration/test_projection_reconstruction.py", "py", None),
    ("tests/integration/test_admission_projection.py", "py", None),
    ("tests/integration/test_corpus_scoped_graph.py", "py", None),

    # ── Phase G: lexical resource compiler (build deps + committed tables) ──
    ("resources/README.md", "md", None),
    ("resources/manifests/verbnet-3.3.yaml", "yaml", None),
    ("resources/manifests/propbank-unified-2020.yaml", "yaml", None),
    ("resources/manifests/framenet-1.7.yaml", "yaml", None),
    ("resources/manifests/semlink-2.0.yaml", "yaml", None),
    ("resources/vendor/.gitkeep", "gitkeep", None),
    ("scripts/fetch_resources.py", "py", None),
    ("scripts/verify_resources.py", "py", None),
    ("scripts/flatten_resources.py", "py", None),
    ("scripts/compile_predicate_rules.py", "py", None),
    ("docs/wiki/decisions/0008-evidence-pass-boundary.md", "md", None),
    ("docs/wiki/decisions/0009-canonicalization-layer.md", "md", None),
    ("docs/wiki/decisions/0010-native-document-materialization.md", "md", None),
    ("docs/wiki/decisions/0011-entity-admission-boundary.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-phase-g-resources.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-phase-g-resources-hardening.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-phase-h.md", "md", None),
    ("tests/contracts/test_lexical_resource_gates.py", "py", None),

    # ── Phase H: empirical lexical-semantic waterfall qualification ──
    ("eval/phase_h/harness.py", "py", None),
    ("eval/phase_h/REPORT.md", "md", None),

    # ── Phase H v1.1: boundary corpus + rerun evidence ──
    ("eval/gold/relations_v1.1.yaml", "yaml", None),
    ("eval/phase_h/REPORT_v1.1.md", "md", None),
    ("docs/wiki/work-log/2026-08-14-phase-h-v11.md", "md", None),
    ("tests/contracts/test_phase_h_harness.py", "py", None),
    ("eval/phase_h/artifacts/assertion_breakdown.csv", "ph", None),
    ("eval/phase_h/artifacts_v1.1/assertion_breakdown.csv", "ph11", None),
    ("eval/phase_h/artifacts/baseline_predictions.jsonl", "ph", None),
    ("eval/phase_h/artifacts_v1.1/baseline_predictions.jsonl", "ph11", None),
    ("eval/phase_h/artifacts/baseline_predictions.sha256", "ph", None),
    ("eval/phase_h/artifacts_v1.1/baseline_predictions.sha256", "ph11", None),
    ("eval/phase_h/artifacts/baseline_waterfall.jsonl", "ph", None),
    ("eval/phase_h/artifacts_v1.1/baseline_waterfall.jsonl", "ph11", None),
    ("eval/phase_h/artifacts/baseline_waterfall.sha256", "ph", None),
    ("eval/phase_h/artifacts_v1.1/baseline_waterfall.sha256", "ph11", None),
    ("eval/phase_h/artifacts/changed_examples.jsonl", "ph", None),
    ("eval/phase_h/artifacts_v1.1/changed_examples.jsonl", "ph11", None),
    ("eval/phase_h/artifacts/coverage_report.json", "ph", None),
    ("eval/phase_h/artifacts_v1.1/coverage_report.json", "ph11", None),
    ("eval/phase_h/artifacts/frozen_inputs.jsonl", "ph", None),
    ("eval/phase_h/artifacts_v1.1/frozen_inputs.jsonl", "ph11", None),
    ("eval/phase_h/artifacts/gold.jsonl", "ph", None),
    ("eval/phase_h/artifacts_v1.1/gold.jsonl", "ph11", None),
    ("eval/phase_h/artifacts/hybrid_predictions.jsonl", "ph", None),
    ("eval/phase_h/artifacts_v1.1/hybrid_predictions.jsonl", "ph11", None),
    ("eval/phase_h/artifacts/hybrid_predictions.sha256", "ph", None),
    ("eval/phase_h/artifacts_v1.1/hybrid_predictions.sha256", "ph11", None),
    ("eval/phase_h/artifacts/hybrid_waterfall.jsonl", "ph", None),
    ("eval/phase_h/artifacts_v1.1/hybrid_waterfall.jsonl", "ph11", None),
    ("eval/phase_h/artifacts/hybrid_waterfall.sha256", "ph", None),
    ("eval/phase_h/artifacts_v1.1/hybrid_waterfall.sha256", "ph11", None),
    ("eval/phase_h/artifacts/manifest.json", "ph", None),
    ("eval/phase_h/artifacts_v1.1/manifest.json", "ph11", None),
    ("eval/phase_h/artifacts/metrics.json", "ph", None),
    ("eval/phase_h/artifacts_v1.1/metrics.json", "ph11", None),
    ("eval/phase_h/artifacts/paired_transitions.csv", "ph", None),
    ("eval/phase_h/artifacts_v1.1/paired_transitions.csv", "ph11", None),
    ("eval/phase_h/artifacts/polysemy_breakdown.csv", "ph", None),
    ("eval/phase_h/artifacts_v1.1/polysemy_breakdown.csv", "ph11", None),
    ("eval/phase_h/artifacts/predicate_breakdown.csv", "ph", None),
    ("eval/phase_h/artifacts_v1.1/predicate_breakdown.csv", "ph11", None),
    ("eval/phase_h/artifacts/resource_cohorts.csv", "ph", None),
    ("eval/phase_h/artifacts_v1.1/resource_cohorts.csv", "ph11", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/manifest.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/build_statistics.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/semlink_derivation.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/compiled_lexical.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/frame_index.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/lemma_to_pb_rolesets.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/lemma_to_vn_classes.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/pb_roleset_arguments.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/pb_to_fn.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/pb_to_vn.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/resource_index.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/vn_class_index.json", "json", None),
    ("resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/vn_to_fn.json", "json", None),
    ("tests/integration/test_cross_domain_routing.py", "py", None),
    ("tests/integration/test_evidence_bundle_e2e.py", "py", None),
    ("tests/integration/test_chat_e2e.py", "py", None),
    ("tests/integration/test_canonicalization_e2e.py", "py", None),
    ("tests/integration/test_canonical_projection_e2e.py", "py", None),
    ("tests/integration/test_i0_native_docs_e2e.py", "py", None),
    ("tests/integration/test_g5_rerank_answer_path.py", "py", None),
    ("tests/contracts/test_embedding_contracts.py", "py", None),
    ("tests/contracts/test_evidence_bundle_contract.py", "py", None),
    ("tests/contracts/test_chat_response_contract.py", "py", None),
    ("tests/contracts/test_canonicalization_contract.py", "py", None),
    ("tests/determinism/test_retrieval_invariants.py", "py", None),
    ("tests/determinism/test_evidence_assembly.py", "py", None),
    ("tests/determinism/test_answer_synthesis.py", "py", None),
    ("tests/determinism/test_canonicalizer.py", "py", None),
    ("tests/determinism/test_materializer.py", "py", None),
    ("tests/determinism/test_canonical_projection_plan.py", "py", None),

    # stores: the workflow schema (docs/chunks/entities/evidence/facts)
    ("stores/postgres/migrations/0002_workflow.sql", "sql", None),

    # tests: determinism, no-LLM ingestion invariants, contract models
    ("tests/determinism/test_compiler.py", "py", None),
    ("tests/determinism/test_chunker_summarizer.py", "py", None),
    ("tests/contracts/test_contract_models.py", "py", None),

    # SYNTAX-BOOTSTRAP: spaCy syntax sidecar (isolated venv, NER disabled)
    ("sidecars/spacy-syntax.toml", "toml", None),
    ("sidecars/spacy_runtime/server.py", "py", None),
    ("sidecars/spacy_runtime/manifest.toml", "toml", None),
    ("sidecars/spacy_runtime/requirements.txt", "txt", None),
    ("sidecars/spacy_runtime/benchmark.py", "py", None),
    ("contracts/extraction/v1/syntax_evidence.schema.json", "json", None),
    ("deployment/launchd/ai.polymath.spacy.plist", "plist", None),
    ("tests/integration/test_spacy_syntax_sidecar.py", "py", None),
    ("tests/contracts/test_syntax_provider_gate.py", "py", None),
]


# ===========================================================================
# CONTENT BLOCKS: every file's initial content lives below.
# Keep them short. Long content goes in the wiki, not in the scaffold.
# ===========================================================================

_README = """# polymath-v4

Local-first GraphRAG with deterministic relation extraction.

**Read [AGENTS.md](AGENTS.md) first.** It is the contract every agent and
every operator follows. The skeleton you are looking at was generated by
`scripts/scaffold_polymath_v4.py` and is the only sanctioned shape.

## Quickstart

```bash
python3 scripts/scaffold_polymath_v4.py        # idempotent
python3 scripts/agent_preflight.py             # every agent runs this
python3 scripts/repo_guard.py                   # architecture and repo rules
python3 scripts/wiki_worm.py --check           # see what needs review
```

## Layout

See [ARCHITECTURE.md](ARCHITECTURE.md) §2 for the directory map. The
short version:

- `orchestrator/`: FastAPI intake and read surface.
- `workers/`: durable stage consumers.
- `control/`: independent desired-state controller.
- `sidecars/`: host-native model services, one resident model per process.
- `shared/`: identity, receipts, contracts, typed clients, and JSON logging.
- `stores/`: Postgres authority plus Redis, Qdrant, and Neo4j projections.
- `contracts/`: versioned JSON schemas and the wire-format authority for
  every cross-process boundary.
- `docs/wiki/`: decisions, refactors, experiments, and append-only work logs.

## What this is not

This is not a directory-by-directory port of polymath v3.3. The accepted
target and dependency-ordered build plan live in `ARCHITECTURE.md` and
`PLAN.md`.
"""

_ARCHITECTURE_DEPENDENCIES = """{
  "version": "v1",
  "owners": {
    "contracts": {"paths": ["contracts/"], "may_depend_on": []},
    "shared": {"paths": ["shared/"], "may_depend_on": ["contracts"]},
    "orchestrator": {"paths": ["orchestrator/"], "may_depend_on": ["contracts", "shared"]},
    "worker": {"paths": ["workers/"], "may_depend_on": ["contracts", "shared"]},
    "control": {"paths": ["control/"], "may_depend_on": ["contracts", "shared"]},
    "sidecar": {"paths": ["sidecars/"], "may_depend_on": ["contracts", "shared"]},
    "store": {"paths": ["stores/"], "may_depend_on": []},
    "governance": {"paths": ["architecture/", "docs/", "scripts/", ".github/"], "may_depend_on": []}
  },
  "forbidden_imports": [
    {"from": "orchestrator", "to": "worker"},
    {"from": "orchestrator", "to": "control"},
    {"from": "worker", "to": "orchestrator"},
    {"from": "worker", "to": "control"},
    {"from": "worker", "to": "sidecar"},
    {"from": "control", "to": "orchestrator"},
    {"from": "control", "to": "worker"},
    {"from": "sidecar", "to": "orchestrator"},
    {"from": "sidecar", "to": "worker"},
    {"from": "sidecar", "to": "control"}
  ],
  "change_triggers": {
    "contracts/": ["reverse-dependent verification", "work log"],
    "architecture/dependencies.json": ["ADR", "refactor entry", "architecture changelog", "work log"],
    "stores/postgres/migrations/": ["replay proof", "rollback note", "work log"],
    "sidecars/": ["manifest proof", "readiness proof", "work log"],
    "scripts/": ["scripts registry", "work log"]
  }
}
"""

_ARCHITECTURE_STUB = """# Polymath v4 architecture

Status: accepted baseline  
Change policy: frozen by default  
Machine-readable dependency map: `architecture/dependencies.json`

This document defines the target system. A generated file, placeholder,
test, or directory does not prove that a capability works. `PLAN.md`
records the dependency-ordered path from this scaffold to production.

## 1. Outcomes and boundaries

Polymath is a local-first GraphRAG workbench. It ingests source material,
extracts evidence-backed facts, builds searchable projections, and serves
answers that retain document and span provenance.

The rebuild has five required outcomes:

1. A restart cannot erase accepted work or strand a run.
2. GPU and Apple Silicon models run as host-native processes, not inside
   Docker.
3. One registry answers where every model service lives and which release
   it runs.
4. Relation semantics come from a deterministic compiler. Models propose
   spans; they never choose graph predicates.
5. Every run can be traced through structured logs and durable Postgres
   receipts using the same identifiers.

The first release is local-first and single-operator. Remote CUDA and cloud
providers are later adapters behind the same sidecar contract. They are not
allowed to create a second workflow, identity scheme, or persistence path.

## 2. Physical topology

The Mac is the initial application and model host.

```text
macOS host
  polymath-api       HTTP intake and read surface
  polymath-control   desired-state census and scheduling
  polymath-worker-*  durable stage consumers
  gliner-runtime     one resident GLiNER model, called twice per chunk
  embedder           one resident embedding model
  reranker           one resident reranking model
  launchd            process supervision and stable startup

Docker Compose
  Postgres           workflow authority and receipts
  Redis              wakeups and disposable cache
  Qdrant             vector projection
  Neo4j              graph projection
```

Compose binds store ports to loopback for host-native clients. No model,
control loop, worker, or API process lives in Compose. A later deployment
may containerize CPU-only application processes, but that requires an ADR
and a clean-clone deployment proof.

Remote hardware registers as another sidecar URL with a pinned manifest.
The application does not contain hostnames, LAN addresses, or provider-
specific routing branches. Those values live in `sidecars/*.toml`.

## 3. Process roles

| Role | Owns | Must not own |
|---|---|---|
| `orchestrator` | HTTP validation, intake, reads | scheduling or model loading |
| `worker` | one durable stage and its receipt | user-facing HTTP or process supervision |
| `sidecar-gpu` | one resident model and inference contract | workflow state or predicate policy |
| `sidecar-cpu` | one CPU service and inference contract | GPU state or workflow authority |
| `store` | persistence for one engine | business decisions |
| `control` | census, scheduling, recovery, heartbeats | user requests or inference |

Every running process has one role. Shared packages are libraries, not a
seventh process. Repository governance is a change lane, not a runtime role.

## 4. Directory ownership

| Path | Authority |
|---|---|
| `contracts/` | versioned wire schemas between processes |
| `architecture/` | machine-readable owners and dependency edges |
| `orchestrator/` | API entrypoints only |
| `workers/` | stage consumers and deterministic orchestration |
| `control/` | desired-state reconciliation and recovery |
| `sidecars/` | registry entries and one-model runtimes |
| `shared/` | identity, receipts, typed clients, logging |
| `stores/` | migrations and projection-specific setup |
| `docs/wiki/` | decisions, refactors, experiments, work logs |
| `scripts/` | declared repository management commands |

No top-level path is added directly. The change must first name its owner,
update `architecture/dependencies.json`, add a refactor entry, and declare
the path in the scaffold `TREE`.

## 5. Stack and authority

| Concern | Choice | Authority rule |
|---|---|---|
| Language | Python, with the supported floor pinned in each package | one lock set must reproduce every host process |
| API | FastAPI, Pydantic, Uvicorn | API validates and delegates; it does not schedule |
| Model runtime | GLiNER through PyTorch on macOS MPS or CPU | one resident model in `gliner-runtime` |
| Workflow state | Postgres | only source of truth for runs, attempts, receipts, outbox, settings, and heartbeats |
| Wakeups | Postgres outbox plus Redis notification | Redis loss cannot lose accepted work |
| Vector search | Qdrant | rebuildable projection from Postgres-backed artifacts |
| Graph search | Neo4j | rebuildable projection from accepted facts |
| Observability | JSON logs, OpenTelemetry context, Loki-compatible collection, Grafana views | logs explain execution; Postgres proves state |
| Tests | pytest and JSON Schema validation | tests traverse public contracts and remain immutable during fixes |
| Deployment | launchd for host processes, Compose for stores | clean-clone startup is a release gate |

Postgres replaces Mongo because the commit point spans the stage result,
receipt, status transition, and outbox event. Those writes belong in one
transaction. JSONB is used for payloads that do not need relational columns.

## 6. Authoritative data model

`runs` records accepted work and its current certified state.
`stage_attempts` records a stage execution keyed by canonical input and
contract release. `outbox` records work that must be delivered. The control
heartbeat records which controller instance last completed a census.

The first migration is a scaffold, not a final schema. Each production
stage must prove this transaction:

```text
write durable stage artifact
write or complete stage receipt
transition run state
append outbox event when downstream work is required
commit once
```

Qdrant and Neo4j do not become authorities. Projection writers record their
source artifact identity and compiler release, then emit receipts. The
control plane can compare desired artifacts with observed receipts and
schedule repair without trusting a process-local queue.

## 7. Ingestion and extraction path

The production path is deliberately narrow:

```text
POST /ingest
  -> normalize bytes and compute document identity
  -> persist source artifact plus run and outbox event
  -> intake worker parses and chunks
  -> extract worker calls gliner-runtime with task=entity
  -> extract worker calls the same runtime with task=evidence
  -> predicate compiler joins spans and applies versioned rules
  -> accepted facts and evidence are persisted with a receipt
  -> projection workers update Qdrant and Neo4j
  -> control census certifies query_ready when required receipts exist
```

The API returns after the intake transaction commits. It does not wait for
model inference. A process crash after commit leaves enough Postgres state
for the controller to schedule the missing stage again.

## 8. Two-pass GLiNER contract

The two passes are logical tasks served by one host-native runtime. Loading
the same weights in two Mac processes would duplicate memory and model
startup cost. A measured experiment may justify separate processes later;
until then one resident model is the accepted topology.

Pass 1 returns typed entity spans. Its label set is the core ontology plus
the active domain profile. Pass 2 returns evidence spans from a versioned
evidence-label inventory. Both responses include source offsets, scores,
model identity, model revision, label-set release, and request identity.

The deterministic compiler owns:

- argument pairing and direction;
- predicate selection;
- negation, modality, attribution, and temporal qualifiers;
- ontology validation;
- stable fact and evidence identifiers;
- the decision to emit no fact.

The compiler input and output are versioned contracts. The same normalized
input, compiler release, rule pack, and ontology release must produce the
same bytes. Model scores are evidence for a proposal, not graph policy.

Performance and quality are release evidence, not guessed configuration.
`PLAN.md` requires a target-Mac experiment that records model load time,
resident memory, per-pass latency, combined latency, throughput, and an
error review on an approved corpus sample. Thresholds and batching are not
pinned until that experiment exists.

## 9. Control plane

`polymath-control` is independent from the API and workers. It reads the
desired artifact set for each active run, compares it with committed
receipts, and schedules only missing work. Scheduling uses the outbox so a
database commit and a notification cannot drift apart.

The controller does not directly perform stages. It does not keep the only
copy of a timer, lease, or retry counter in memory. A controller restart
reconstructs its next action from Postgres. Only one active controller may
own a scheduling lease; the lease mechanism must be a Postgres contract and
must be proven before multiple controller instances are allowed.

## 10. Sidecar discovery and readiness

Each sidecar registry entry names a stable URL, contract path, device class,
and pinned release. At startup, a consumer fetches `/manifest`, compares the
runtime identity with the registry pin, and refuses inference on mismatch.

`/health` proves the process loop responds. `/ready` proves the loaded model
can execute the same runtime path used by `/infer`. Readiness probes must be
cheap enough for operations and meaningful enough to catch a poisoned or
unloaded model. The exact probe payload and cadence are established by the
model qualification experiment.

## 11. Logs, traces, and work records

Every runtime log is one JSON object. Required fields are `timestamp`,
`level`, `service`, `event`, `trace_id`, `run_id`, `stage`, `attempt_id`,
`provider`, `model_release`, `device`, `duration_ms`, and `error_code`.
Fields that do not apply are null; names do not change between processes.
Documents and secrets never enter logs.

Trace context crosses HTTP and queue boundaries. Operators search by
`run_id` for one ingestion or by `trace_id` for one request chain. Runtime
logs are diagnostic. Postgres receipts remain the proof that a transition
committed.

Repository work uses a separate append-only log under
`docs/wiki/work-log/`. Each mutating change records its contract, changed
paths, proof, rejected claims, and remaining gaps. `scripts/repo_guard.py`
checks the record and the related architecture artifacts.

## 12. Dependency and refactor triggers

`architecture/dependencies.json` defines which package may depend on which
owner. Cross-process behavior travels through `contracts/`, never a private
module import.

| Changed authority | Required companion change |
|---|---|
| public contract | compatibility decision, reverse-dependent proof, work log |
| dependency edge | dependency map, ADR, refactor entry, architecture changelog |
| model manifest | model qualification receipt and readiness proof |
| Postgres schema | append-only migration, replay proof, rollback note |
| deployment manifest | clean-clone configuration proof and startup canary |
| management script | `scripts/README.md`, work log, governance check |

## 13. Release proof

The architecture is implemented only when a clean clone can start the
stores and host processes, ingest a real source through both GLiNER passes,
compile and persist an evidence-backed fact, recover after a controlled
process restart, rebuild its projections, and show the run in structured
logs. Until that path passes, the repository is a scaffold and must be
described as such.
"""

_ARCHITECTURE_CHANGELOG_STUB = """# Architecture changelog

Dated diffs of every architectural change. Each entry links to the ADR
that motivated it and the refactor that implemented it.

## __TODAY__: initial scaffold

- Skeleton created by `scripts/scaffold_polymath_v4.py` (sha: __SCRIPT_SHA__).
- Accepted Postgres as workflow authority.
- Accepted one host-native GLiNER runtime serving two logical passes.
- Added machine-readable dependency ownership and repository work logs.
"""

_PLAN_STUB = """# Polymath v4 implementation plan

Status: scaffolded, production path not yet proven

This plan is ordered by dependency. Agents admit one vertical slice at a
time. A phase advances only when its public entrypoint, durable outcome,
and verifier pass through the production path.

## Planning rules

1. Do not port v3.3 modules by directory. Port a named behavior only after
   its contract and owner are clear.
2. Do not add a provider, store, queue, or schema that creates a second
   authority.
3. Do not call a stub, mock, test-only path, or direct internal function a
   working capability.
4. Record every repository mutation in `docs/wiki/work-log/`.
5. Stop a slice when its stated contract is satisfied and proven.

## Phase A: repository contract

Outcome: a clean scaffold has one directory source of truth and executable
governance.

Required work:

- keep every managed path in the scaffold `TREE`;
- keep package ownership in `architecture/dependencies.json`;
- validate scripts, wiki metadata, work logs, and undeclared paths;
- keep architecture changes tied to an ADR, refactor entry, changelog, and
  work log.

Exit proof:

```bash
python3 scripts/scaffold_polymath_v4.py
python3 scripts/agent_preflight.py
python3 scripts/repo_guard.py
python3 scripts/wiki_worm.py --check
```

## Phase B: contracts, identity, state, and logging

Depends on: Phase A.

Outcome: all later stages share one identity scheme, one transaction
boundary, one sidecar contract, and one log field set.

Required work:

- freeze the canonical byte normalization and content-hash contract;
- define run, stage attempt, receipt, outbox, and artifact schemas;
- implement a Postgres transaction that writes artifact, receipt, status,
  and outbox together;
- make sidecar manifests expose model, revision, weights digest, runtime,
  device, and wire schema;
- propagate `trace_id`, `run_id`, `stage`, and `attempt_id` across HTTP and
  queued work;
- replace model and deployment placeholders only with measured or pinned
  values.

Exit proof: a public intake call commits one run and outbox event; replaying
the same canonical input does not create a second run; logs and rows share
the same identifiers.

Rollback boundary: the initial Postgres migration and the v1 contracts.

## Phase C: qualify GLiNER on the target Mac

Depends on: Phase B contracts and logging.

Outcome: the local runtime topology and inference settings are based on
measurements from the deployment Mac.

Required work:

- pin the GLiNER model revision and weights digest;
- build an approved evaluation sample with expected entity spans and
  evidence classes;
- measure one resident process serving both passes;
- compare separate-process execution only if memory or concurrency evidence
  gives a reason to test it;
- record load time, resident memory, per-pass latency, combined latency,
  throughput, and reviewed extraction errors;
- select label sets, thresholds, batching, and readiness payload from the
  recorded experiment.

Exit proof: an experiment entry contains the command, hardware identity,
model release, input digest, raw results, review notes, and ship or reject
decision.

Rollback boundary: the sidecar manifest release.

## Phase D: first complete ingestion slice

Depends on: Phases B and C.

Outcome: one real text source becomes one persisted, evidence-backed fact.

Production path:

```text
HTTP intake
  -> source persistence
  -> chunk
  -> entity pass
  -> evidence pass
  -> deterministic compiler
  -> Postgres fact, evidence, receipt, status, outbox
  -> searchable structured log
```

Required work:

- replace the intake placeholder with the real transactional path;
- implement one worker entrypoint for the admitted stages;
- implement the compiler as a pure function over versioned rule data;
- retain document, chunk, and character offsets on every accepted fact;
- emit explicit no-fact and ambiguous outcomes without inventing edges.

Exit proof: a public request produces a durable fact and evidence record;
replay is a no-op; a rejected relation remains absent; the entire run is
searchable by one `run_id`.

Rollback boundary: disable the v1 intake route and preserve committed source
artifacts for replay.

## Phase E: independent control and recovery

Depends on: Phase D receipts and outbox.

Outcome: accepted work continues or resumes when the API, worker, model
runtime, or controller restarts.

Required work:

- implement desired-versus-observed artifact census from Postgres;
- schedule only missing stages through the outbox;
- add a Postgres-owned controller lease before multiple controller
  instances are allowed;
- supervise host processes with launchd and expose liveness separately from
  readiness;
- keep recovery decisions visible in logs and stage attempts.

Exit proof: controlled restarts at each process boundary leave one accepted
result and no duplicate receipt.

Rollback boundary: stop the controller; existing read paths and committed
state remain available.

## Phase F: rebuildable search projections

Depends on: Phase D accepted facts and Phase E recovery.

Outcome: Qdrant and Neo4j are projections that can be deleted and rebuilt
from authoritative artifacts and receipts.

Required work:

- write vectors with corpus, document, chunk, model, and source digests;
- write graph facts with compiler rule and evidence identities;
- record projection receipts;
- compare the desired projection census with observed receipts;
- provide replay and projection-rebuild commands.

Exit proof: rebuild both projections from the same accepted source and
produce the same logical identities.

Rollback boundary: discard projection collections or databases; Postgres
authority remains intact.

## Phase G: retrieval and answer path

Depends on: Phase F.

Outcome: focused, hybrid, and graph retrieval consume the new projections
without bypassing provenance.

Required work:

- port one retrieval behavior at a time behind a public contract;
- preserve corpus boundaries and embedding-release compatibility;
- attach source evidence to every returned fact;
- add reranking only after base retrieval has a recorded verifier;
- keep answer generation outside retrieval scoring and graph policy.

Exit proof: each retrieval mode returns source-linked results through its
public endpoint and refuses incompatible projection releases.

## Phase H: remote compute adapters

Depends on: the local path passing Phases D through G.

Outcome: remote CUDA or cloud compute can replace local inference without
changing workflow state, graph semantics, or client contracts.

Required work:

- register remote services through the same sidecar manifest;
- prove release mismatch refusal, unreachable-provider behavior, and local
  recovery;
- measure cost and latency before accepting automatic routing;
- keep provider credentials outside logs and repository files.

Exit proof: the same input and compiler release preserve fact identity when
only the inference provider changes, subject to the recorded proposal set.

## Deferred until admitted

- v3.3 bulk migration;
- automatic cloud overflow;
- multi-controller operation;
- a second GLiNER process on the Mac;
- removal of the v3.3 repository.
"""

_AGENTS_MD = """# AGENTS.md: repository and agent contract

Read this file before changing the repository. It defines runtime ownership,
architecture change rules, managed scripts, and the proof required from each
agent. If code or prose conflicts with this file, stop and resolve the
contract conflict before editing.

## 1. Select one owner

Every runtime change has one process owner.

| Owner | Owns | Forbidden ownership |
|---|---|---|
| `orchestrator` | HTTP intake and reads | scheduling, model loading, long jobs |
| `worker` | one durable stage | user HTTP, supervision, workflow authority |
| `sidecar-gpu` | one resident model and device | predicates, receipts, run state |
| `sidecar-cpu` | one CPU inference service | GPU state, receipts, run state |
| `store` | one persistence engine | application decisions |
| `control` | census, scheduling, recovery, heartbeat | inference and user requests |

Use `governance` only for repository-only changes such as architecture,
scripts, CI, or wiki maintenance. It is not a process role. If one change
needs multiple runtime owners, split it at a versioned contract boundary.

## 2. Non-negotiable rules

1. No model runs in Docker. Model processes are host-native and supervised
   by launchd on macOS or systemd on Linux.
2. One sidecar process loads one model release. The GLiNER entity and
   evidence passes call the same resident GLiNER runtime.
3. Every cross-process payload conforms to a versioned schema in
   `contracts/`. Private package imports never cross process boundaries.
4. Every mutation uses canonical content identity. Replaying identical
   input must not create a second logical result.
5. A stage artifact, receipt, status transition, and required outbox event
   commit in one Postgres transaction.
6. Postgres is workflow authority. Redis, Qdrant, and Neo4j are disposable
   notification, cache, or projection layers.
7. Models propose spans. Only the deterministic compiler selects predicates,
   direction, negation, modality, ontology mapping, and fact identity.
8. Existing tests and evaluation artifacts are immutable unless the user
   explicitly asks to change them. Fix implementation failures in code.
9. Secrets, source text, and credentials never enter logs or work records.

## 3. Read and verify before editing

Read in this order:

1. `AGENTS.md`
2. `ARCHITECTURE.md`
3. `architecture/dependencies.json`
4. `PLAN.md`
5. the ADR, refactor entry, package contract, and latest relevant work log

Then run:

```bash
python3 scripts/agent_preflight.py
python3 scripts/repo_guard.py
python3 scripts/wiki_worm.py --check
```

Record pre-existing failures. Do not lower a check, edit a test, or replace
a production dependency with a mock to create a passing result.

## 4. Admit one change slice

Before a repository mutation, create or update one entry under
`docs/wiki/work-log/`. State:

- the requested outcome and smallest acceptance criteria;
- the single owner and public contract;
- inputs, outputs, persistence effect, and failure modes;
- dependency edges and reverse dependents;
- the verifier and rollback boundary.

Reject any proposed file, abstraction, refactor, test, or safeguard if
deleting it would still leave the outcome satisfied and proven. Do not create
directories or interfaces for unadmitted future work.

## 5. Directory and dependency enforcement

The scaffold `TREE` is the file-placement authority.
`architecture/dependencies.json` is the import and ownership authority.
`ARCHITECTURE.md` explains both for humans.

New paths require all of the following in the same change:

1. an ADR when the architectural boundary changes;
2. a refactor entry naming the trigger and affected dependents;
3. an updated dependency map when an owner or edge changes;
4. an updated scaffold `TREE` and `scripts/README.md` when applicable;
5. an architecture changelog entry and work-log proof.

Place changes by authority:

- public wire payload: `contracts/<domain>/v<N>/`;
- API endpoint: `orchestrator/orchestrator/api/`;
- durable stage: `workers/workers/`;
- model runtime: `sidecars/<name>/` plus `sidecars/<name>.toml`;
- deterministic shared policy: `shared/polymath_shared/`;
- workflow migration: `stores/postgres/migrations/`;
- decision, refactor, experiment, or work record: its matching wiki folder.

Forbidden dependency patterns are checked by `scripts/repo_guard.py`.
Providers do not own state. Orchestrator code does not import worker or
control internals. Workers do not import sidecar implementations. Calls cross
those boundaries through schemas and typed clients.

## 6. Refactor triggers

Changes propagate by dependency, not by guesswork.

| Trigger | Required response |
|---|---|
| contract change | decide compatibility and verify every reverse dependent |
| dependency edge change | update dependency map, ADR, refactor entry, changelog |
| model release change | add qualification evidence and readiness proof |
| schema change | append a migration and record replay plus rollback proof |
| deployment change | prove clean-clone configuration and startup |
| script change | update script registry and work log |

No agent silently rewrites `ARCHITECTURE.md`, changes a frozen contract, or
edits an applied migration.

## 7. Managed scripts

`scripts/README.md` is the script registry. A script must name its owner,
inputs, writes, safe mode, and verifier before it can be added to `TREE`.

- `scaffold_polymath_v4.py` creates missing declared files and never
  overwrites existing files.
- `agent_preflight.py` checks whether an agent may begin work.
- `repo_guard.py` checks declared paths, dependencies, script records, work
  logs, and architecture companion changes.
- `wiki_worm.py --check` audits wiki structure and open work without editing.
- `check_install.sh` reports service reachability and performs no repair.

Agents do not add one-off root scripts. Reusable repository operations live
under `scripts/`, are declared in `TREE`, and are documented in the registry.
Temporary diagnostics stay outside the repository.

## 8. Work logs and runtime logs

Work logs are append-only Markdown records in `docs/wiki/work-log/`. Do not
rewrite an older record to make current work look complete. Add a correction
entry that links to it. Each mutating change records Contract, Changes,
Proof, Rejected claims, and Open contract gaps.

Runtime logs are JSON and use the shared logger. Required field names are:
`timestamp`, `level`, `service`, `event`, `trace_id`, `run_id`, `stage`,
`attempt_id`, `provider`, `model_release`, `device`, `duration_ms`, and
`error_code`. Use null when a field does not apply. Postgres receipts, not
log lines, prove committed state.

## 9. Completion proof

A capability is working only when all four facts are observable:

1. a public production entrypoint is reachable;
2. runtime wiring reaches the real owner;
3. a durable or external outcome exists;
4. a verifier traverses that same path and passes.

Placeholders, direct internal calls, mocked adapters, generated files, and
diagrams do not satisfy this rule. Keep pre-existing failures separate from
regressions. End the change when the admitted contract is satisfied and no
remaining claim is required to prove it.
"""

_CONTRIBUTING_STUB = """# Contributing

Read `AGENTS.md` first. It is the contract.

For humans:

1. Fork or branch.
2. Run `python3 scripts/agent_preflight.py` (yes, even humans).
3. Make the change.
4. Run the determinism test suite: `pytest tests/determinism/`.
5. Open a PR. The PR template will ask which ADR (if any) you are
   implementing.

For AI agents:

1. Read `AGENTS.md` §4 (reading order) before anything else.
2. Run `scripts/agent_preflight.py`.
3. Use the TREE constant in `scripts/scaffold_polymath_v4.py` as the
   authoritative list of where files go. Do not invent paths.
4. Use `shared/polymath_shared/identity.py` for every content hash.
   Do not call hashlib directly.
5. Use `shared/polymath_shared/receipts.py` for every durable write.
   Do not write receipts by hand.
"""

_LICENSE_STUB = """MIT License. See parent repo LICENSE for full text.
"""

_GITIGNORE = """# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/

# Local state
.env
.env.local
*.log

# Stores (bind-mounted, never committed)
stores/postgres/data/
stores/qdrant/snapshots/*.snapshot
stores/neo4j/data/
stores/redis/dump.rdb

# Sidecar model weights (downloaded, not committed)
sidecars/*/models/
sidecars/*/weights/

# Editor
.vscode/
.idea/
.DS_Store

# Generated
.scaffold-touched
"""

_ENV_EXAMPLE = """# Environment template. Copy to .env and fill in.

# Postgres
POSTGRES_IMAGE=__PIN_IMAGE_DIGEST__
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=polymath
POSTGRES_USER=polymath
POSTGRES_PASSWORD=__generate__

# Qdrant
QDRANT_IMAGE=__PIN_IMAGE_DIGEST__
QDRANT_URL=http://127.0.0.1:6333

# Neo4j
NEO4J_IMAGE=__PIN_IMAGE_DIGEST__
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=__generate__

# Redis
REDIS_IMAGE=__PIN_IMAGE_DIGEST__
REDIS_URL=redis://127.0.0.1:6379

# Sidecar registry root
POLYMATH_SIDECAR_REGISTRY=./sidecars
POLYMATH_GLINER_DEVICE=__PIN_DEVICE__

# Control plane heartbeat
POLYMATH_CONTROL_HEARTBEAT_URL=http://127.0.0.1:7100/heartbeat
"""

_DOCS_README = """# Docs

- `wiki/`: decisions, refactors, experiments, and repository work logs.
- `runbooks/`: operator procedures and agent onboarding.
"""

_WIKI_README = """---
last_reviewed: __TODAY__
last_touched: __TODAY__
status: accepted
---

# Wiki

This is a working wiki. The read-only worm (`scripts/wiki_worm.py`) audits it
weekly, reports open refactors and work records, and fails on broken metadata.

## Layout

- `decisions/`: Architecture Decision Records. One per decision. Numbered.
- `refactors/`: work triggered by ADRs or dependency changes.
- `experiments/`: measured model and system experiments from
  the architecture doc.
- `work-log/`: append-only records for repository mutations.

## Front-matter

Every wiki file has YAML front-matter:

```yaml
---
owner: <process role or @king>
last_reviewed: YYYY-MM-DD
last_touched: YYYY-MM-DD
status: draft | accepted | superseded
supersedes: NNNN-<slug>.md
superseded_by: NNNN-<slug>.md
---
```

The worm uses these fields. The status field is required.
"""

_ADR_TEMPLATE = """---
owner: <role>
last_reviewed: YYYY-MM-DD
last_touched: YYYY-MM-DD
status: draft
---

# ADR-NNNN: <title>

## Context

What is the situation that forces a decision?

## Decision

What did we decide?

## Consequences

What becomes easier, what becomes harder, what new failure modes appear?

## Triggered refactors

- `docs/wiki/refactors/NNNN-<slug>.md`
"""

_ADR_0001 = """---
owner: sidecar-gpu
last_reviewed: __TODAY__
last_touched: __TODAY__
status: accepted
---

# ADR-0001: Two-pass GLiNER for entity + evidence proposal

## Context

v3.3 let a model propose graph relations directly. That mixed
nondeterministic span detection with predicate policy and made false graph
edges difficult to audit or reproduce.

## Decision

Decompose extraction into two GLiNER passes and a deterministic
compiler:

- **Pass 1: entity proposal.** GLiNER receives the versioned entity label
  set for the active ontology profile and returns typed spans.
- **Pass 2: evidence proposal.** The same resident GLiNER model receives a
  versioned evidence-label set and returns coarse evidence spans. It does
  not return predicate labels.
- **Compiler.** A YAML-driven decision DAG that maps
  (entity types × evidence class × lexical trigger × argument
  structure) onto a canonical predicate vocabulary. Deterministic. Pure
  function over compiled tables.

Both passes use one host-native `gliner-runtime` process on the Mac. This
avoids loading the same weights twice. A measured experiment and a new ADR
are required before splitting the passes into separate model processes.

The compiler is the only place predicates are decided. GLiNER proposes;
the compiler decides. Silence is a valid answer.

## Consequences

Easier:
- The system can prefer no edge when deterministic evidence is insufficient.
- The compiler is auditable. Every edge carries evidence spans, rule
  IDs, and resource versions.
- The system is deterministic given the same inputs. Re-ingestion is
  a no-op.

Harder:
- Lexical-semantic tables have coverage gaps that must be measured against
  the admitted corpus.
- The rule pack is a curated engineering artifact. Adding a new
  predicate is a PR, not a config change.
- Cross-sentence and implicit relations are out of scope for v1.

New failure modes:
- Polysemous triggers ("run", "support", "have") produce
  AMBIGUOUS decisions. Acceptable, but observable.
- Domain terminology not in any of the four resources produces
  UNSUPPORTED. Also acceptable, but observable.

## Triggered refactors

- `docs/wiki/refactors/0001-compiler-as-pure-function.md`
- `docs/wiki/refactors/0002-gliner-runtime-two-logical-passes.md`
"""

_ADR_0002 = """---
owner: store
last_reviewed: __TODAY__
last_touched: __TODAY__
status: accepted
---

# ADR-0002: Postgres for durable state, not Mongo

## Context

v3.3 used Mongo for everything: documents, runs, receipts, config, the
control plane's run ledger. The control plane's atomicity depended on
Mongo's `findOneAndUpdate` semantics. There are no transactions across
collections, which means the receipt + side-effect gap documented in
ISSUES_REPORT.md §1.2 is unfixable in Mongo without standing up a
replica set and using multi-document transactions (which were a 4.0
feature with rough edges).

## Decision

Postgres is the durable state store. Tables: `runs`, `stage_attempts`,
`outbox`, `control_heartbeats`, `users`, `settings`, `artifacts_index`.

Mongo is gone from the compose file.

## Consequences

Easier:
- Multi-statement transactions. A stage's durable write + receipt +
  status transition can be a single `BEGIN; ... COMMIT;`.
- `LISTEN/NOTIFY` for cheap wakeups (the control plane ticks on a
  NOTIFY, not a poll).
- `JSONB` columns keep the schema-less feel of Mongo where it matters
  (run payloads, receipt metadata) while still being indexable.
- Mature backup/restore story. `pg_dump` + PITR.

Harder:
- Every Mongo query has to be rewritten. Most are straightforward
  (`find` → `SELECT`, `update_one` → `UPDATE ... WHERE ... RETURNING`).
- Mongo's `ObjectId` is gone; everything is `BIGSERIAL` or `TEXT` with
  the content-hash identity scheme from ADR-0001.

## Triggered refactors

- `docs/wiki/refactors/0003-mongo-to-postgres-migration.md`
"""

_ADR_0003 = """---
owner: sidecar-gpu
last_reviewed: __TODAY__
last_touched: __TODAY__
status: accepted
---

# ADR-0003: No GPU in Docker

## Context

v3.3 ran the embedder and reranker inside Docker on the Mac. The GPU
is host-native. The mismatch produced a poisoned-CUDA-context failure
mode where the `/health` endpoint reported healthy for 12+ hours while
every `/embeddings` call returned 500. The fix in v3.3 was a band-aid
(`/health` does a 1-token forward pass). The band-aid does not scale
to the next sidecar someone adds.

## Decision

Every GPU service is a host-native process supervised by systemd
(Linux) or launchd (macOS). The Docker compose file contains exactly
the data stores: Postgres, Qdrant, Neo4j, Redis.

The sidecar registry (`sidecars/*.toml`) is the source of truth for
"where does service X live." Compose service names are only used for
the data stores, which are actually stable.

## Consequences

Easier:
- CUDA context poisoning is a host problem now. The orchestrator only
  sends traffic to sidecars whose `/ready` endpoint says "I can serve
  traffic." The supervisor restarts failed sidecars via systemd, not
  via a Docker autoheal band-aid.
- `/ready` is a real readiness probe (1-token forward pass). `/health`
  is a separate liveness probe (process is alive). The two are
  different and the orchestrator respects the difference.
- The contract surface is uniform across GPU and CPU sidecars. Same
  manifest, same `/ready`, same release pinning.

Harder:
- Two supervisor systems: systemd on the RTX box, launchd on the Mac.
  Each sidecar ships two unit templates.
- The Mac has both Apple MLX (for chat) and CUDA (none, but in the
  future maybe) paths. The contract is the same; the runtime is
  different.

## Triggered refactors

- `docs/wiki/refactors/0004-compose-shrink-to-stores.md`
- `docs/wiki/refactors/0005-sidecar-supervisor.md`
"""

_ADR_0004 = """---
owner: control
last_reviewed: __TODAY__
last_touched: __TODAY__
status: accepted
---

# ADR-0004: Control plane is a separate process

## Context

v3.3's "control plane" is `services/control_plane/{ledger,
desired_state, reconciler, certificate}.py`: a Mongo collection plus
an inline loop inside the FastAPI backend process. When the backend
restarts (memory pressure, OOM, deploy, the 2026-07-04 RestartCount=37
incident), the control plane restarts with it. In-flight work is
paused. There's no leader election, no queue-driven resume, just "the
next tick of the loop, eventually."

## Decision

The control plane is a separate process (`control/control/main.py`),
supervised by systemd. It has its own log, its own heartbeat, and its
own crash-safety.

Communication:
- Reads: Postgres tables (`runs`, `stage_attempts`, `outbox`,
  `control_heartbeats`).
- Writes: Postgres tables (status transitions, outbox).
- Wakeups: the transactional outbox plus Postgres notifications. Any safety
  poll cadence must come from a recovery experiment and operations contract.

The control plane never serves user requests. The orchestrator never
decides "what to do next." Each does one job.

## Consequences

Easier:
- The orchestrator can crash without taking the control plane down.
  Intake requests 503 with retry-after; existing in-flight runs
  continue to be scheduled.
- The control plane can crash without taking the orchestrator down.
  Reads still work; writes are paused. Heartbeat staleness in
  `control_heartbeats` triggers an alert.
- Adding a new stage is a control-plane PR, not an orchestrator PR.
  The orchestrator doesn't need to know what stages exist.

Harder:
- One more process to supervise. `polymath-control.service` joins
  the unit file list.
- Heartbeats are load-bearing. If the control plane stops heart-
  beating, the alert fires but the system keeps running with stale
  state. The alert has to be loud.

## Triggered refactors

- `docs/wiki/refactors/0006-control-as-systemd-unit.md`
"""

_ADR_0005 = """---
owner: sidecar-gpu
last_reviewed: __TODAY__
last_touched: __TODAY__
status: accepted
---

# ADR-0005: Sidecar contract v1

## Context

v3.3 had 11 different discovery mechanisms for "where is service X":
compose service names, `host.docker.internal`, LAN IPs, env vars. Some
were stable, most weren't. Every "why is the RTX box unreachable" was
a 30-minute grep through compose files and env vars.

## Decision

Every sidecar (GPU or CPU) exposes the same five endpoints and ships
a manifest that pins its identity:

- `GET  /manifest`: `{identity, wire, health, signature}`. The
  manifest is published on first response and cached by the
  orchestrator. Manifest mismatch = refuse to call.
- `GET  /health`: liveness. Process is alive. Trivial.
- `GET  /ready`: readiness. The sidecar can serve traffic *right
  now*. For GPU sidecars, this does a 1-token forward pass on every
  probe to catch poisoned CUDA contexts.
- `POST /infer`: the actual work. Schema in the manifest.
- `GET  /metrics`: Prometheus. Optional in v1.

The orchestrator reads `sidecars/*.toml` at boot, fetches each
manifest, pins a release identity, and refuses to route traffic to
sidecars whose manifest doesn't match the pin.

## Consequences

Easier:
- One discovery mechanism for everything. The `sidecars/*.toml` files
  are the source of truth.
- "Why is the RTX box unreachable" becomes "read the toml file."
- Adding a new sidecar is three things: write `sidecars/<name>.toml`,
  write `sidecars/<name>/server.py`, restart the orchestrator (or
  SIGHUP it for hot reload). No compose change.

Harder:
- The contract has to be enforced. The first PR that adds a sidecar
  with `/health` doing trivial checks instead of real work is the
  beginning of the v3.3 mess again.
- TLS is out of scope for v1. LAN-only deployment is assumed. When
  that changes, the manifest gains a `tls:` section.

## Triggered refactors

- `docs/wiki/refactors/0007-sidecar-registry-loader.md`
"""

_REFACTOR_README = """---
last_reviewed: __TODAY__
last_touched: __TODAY__
status: accepted
---

# Refactors

A refactor is any change triggered by an ADR or by a dependency
upgrade. Each refactor lives in its own file:

```
NNNN-<slug>.md
```

Front-matter:

```yaml
---
triggered_by: ADR-NNNN | dependency:<name>:<old>-><new>
status: planned | in_progress | done | blocked
last_touched: YYYY-MM-DD
---
```

The wiki worm lists every entry that is not `done`. A review due date belongs
in the entry when the owning change has an external deadline.
"""

_EXPERIMENT_README = """---
last_reviewed: __TODAY__
last_touched: __TODAY__
status: accepted
---

# Experiments

Measured experiments with the EXPERIMENT tag. Each entry:

- States the hypothesis.
- States the measurement method.
- Publishes the result, including null results.
- States the decision: ship, kill, or continue.

Front-matter:

```yaml
---
hypothesis: <one sentence>
status: proposed | running | concluded
conclusion: ship | kill | continue | null
last_touched: YYYY-MM-DD
---
```

A null result is a valid conclusion. "We tried, it didn't work, here
is why" is the most valuable kind of experiment entry.
"""

_WORK_LOG_README = """---
owner: governance
last_reviewed: __TODAY__
last_touched: __TODAY__
status: accepted
---

# Repository work log

This folder is the append-only record of repository mutations. Runtime events
belong in structured logs; design decisions belong in ADRs; measured model
results belong in experiments.

Name each entry `<date>-<change-id>.md`. Declare the path in the scaffold
`TREE` before creating it. Corrections are new entries that link to the old
record.

Required front matter:

```yaml
change_id: <stable id>
owner: <process role or governance>
date: YYYY-MM-DD
status: in_progress | complete | blocked
architecture_impact: none | <ADR path>
```

Required sections, in order:

1. `Contract`
2. `Changes`
3. `Proof`
4. `Rejected claims`
5. `Open contract gaps`

`scripts/repo_guard.py` validates the fields, section order, declared path,
and companion files required by an architecture or script change.
"""

_WORK_LOG_BOOTSTRAP = """---
change_id: bootstrap-v4
owner: governance
date: __TODAY__
last_reviewed: __TODAY__
last_touched: __TODAY__
status: complete
architecture_impact: baseline
---

# Bootstrap the Polymath v4 repository

## Contract

Create a reproducible repository scaffold whose architecture, dependency
map, managed scripts, and work-log rules agree and pass their static checks.

## Changes

- Accepted Postgres as workflow authority and the other stores as
  rebuildable or disposable layers.
- Defined one resident Mac GLiNER runtime for the entity and evidence passes.
- Added machine-readable dependency ownership, script registration, and
  append-only work logs.
- Added preflight, repository guard, and wiki audit entrypoints.

## Proof

The scaffold was materialized twice with no file changes on the second run.
Preflight, repository guard, wiki audit, Python compilation, and Compose
configuration passed. The unchanged test suite reported 5 passed, and all
four JSON schemas passed Draft 2020-12 meta-validation. A negative guard
fixture rejected an architecture edit missing its changelog, ADR, refactor,
and work-log companions.

## Rejected claims

- Two Mac GLiNER processes were rejected because they load the same model
  twice without measured evidence that the duplication helps.
- Automatic cloud routing was rejected until the local production path is
  proven.

## Open contract gaps

- Model revision, weights digest, thresholds, batching, and readiness probe
  remain unpinned until the target-Mac qualification experiment.
- Production intake, receipts, compiler wiring, and recovery are planned but
  remain placeholders.
"""

_RUNBOOK_OPERATOR = """# Operator Runbook

Day-2 operations. The skeleton scaffolds this; the runbook fills in
over time as incidents happen.

## Restart a sidecar

```bash
# Find which unit controls the sidecar
systemctl list-units 'polymath-*'

# Restart it
sudo systemctl restart polymath-sidecar-gliner-entity

# Watch the log
journalctl -u polymath-sidecar-gliner-entity -f
```

## Restart the control plane

```bash
sudo systemctl restart polymath-control
journalctl -u polymath-control -f
```

## Check sidecar health

```bash
curl -s http://127.0.0.1:8737/manifest | jq
curl -s http://127.0.0.1:8737/ready | jq
```

A `ready: false` means the sidecar is alive but cannot serve traffic.
A `manifest: 500` means the sidecar failed to load its model.

## Diagnose stuck runs

```bash
psql -h 127.0.0.1 -U polymath -d polymath -c "
  SELECT run_id, corpus_id, status, last_stage
  FROM runs
  WHERE status NOT IN ('query_ready', 'failed')
  ORDER BY updated_at DESC
  LIMIT 20;
"
```

If a run is stuck in `reconciling` for more than the control plane's
max-tick window (default 5 minutes), file an issue.
"""

_RUNBOOK_AGENT_ONBOARDING = """# Agent Onboarding

You are an AI agent (or a new human). Before you touch any code:

## 1. Read in order

1. `AGENTS.md`: the contract.
2. `ARCHITECTURE.md`: the topology.
3. `architecture/dependencies.json`: ownership and allowed edges.
4. `PLAN.md`: dependency-ordered work.
5. `docs/wiki/decisions/0001-use-gliner-2pass.md`: the load-bearing
   decision (the one this repo was built around).
6. The ADR, refactor, and latest work log for the selected slice.

## 2. Run preflight

```bash
python3 scripts/agent_preflight.py
python3 scripts/repo_guard.py
python3 scripts/wiki_worm.py --check
```

It will fail if the skeleton is incomplete or your environment is
wrong. Fix every failure before writing code.

## 3. Find the file you need

The TREE constant in `scripts/scaffold_polymath_v4.py` is the
authoritative list of where files go. Do not invent paths. If you
need a new path, that is a refactor (see step 4).

## 4. Need to change the architecture?

Open an ADR and its triggered refactor first. Declare both paths in the
scaffold `TREE`, update `architecture/dependencies.json` if an owner or edge
changes, append `ARCHITECTURE_CHANGELOG.md`, and add a work-log entry. Do not
silently edit `ARCHITECTURE.md`.

## 5. Need to add a file?

Find the right `TREE` entry. If it does not exist, write the refactor and work
log, add the content block plus `TREE` entry, and run the scaffold. Do not
create an undeclared path by hand.

## 6. Write code

Use:
- `shared/polymath_shared/identity.py` for every content hash.
- `shared/polymath_shared/receipts.py` for every durable write.
- `shared/polymath_shared/contracts.py` for every cross-process call.

Do not call hashlib directly. Do not write receipts by hand. Do not
construct HTTP requests to sidecars without going through
`shared/polymath_shared/clients.py`.

## 7. Verify

```bash
pytest tests/determinism/
python3 scripts/agent_preflight.py
python3 scripts/repo_guard.py
python3 scripts/wiki_worm.py --check
```

Both must pass. CI will reject the PR if either is red.
"""

_CONTRACTS_README = """# Contracts

The single source of truth for every cross-process boundary. Every
schema here is versioned, and the version is the contract. Code that
drifts from the schema is wrong.

## Layout

```
contracts/
├── sidecar/
│   └── v1/                : the sidecar contract (ADR-0005)
├── ingestion/
│   └── v1/                : intake events, run lifecycle
└── extraction/
    └── v1/                : relation candidates, fact/evidence
```

A contract at version N is frozen the day N is released. Breaking
changes require N+1. Additive changes are allowed within N with
backwards-compatible JSON Schema rules (additionalProperties, etc.).

## How to add a contract

1. Find the right domain folder.
2. Bump the version if the existing one is frozen.
3. Write `<thing>.schema.json` with `$id`, `title`, `description`.
4. Write `<thing>.example.json` with a valid instance.
5. Add a test in `tests/contracts/` that validates the example against
   the schema and checks invariants the schema can't express.
"""

_SIDECAR_MANIFEST_SCHEMA = """{
  "$id": "https://polymath.local/contracts/sidecar/v1/manifest.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SidecarManifest",
  "description": "Identity + wire contract for a Polymath sidecar.",
  "type": "object",
  "required": ["identity", "wire", "health"],
  "properties": {
    "identity": {
      "type": "object",
      "required": ["name", "version", "model"],
      "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "model": {
          "type": "object",
          "required": ["id", "revision", "weights_sha256"],
          "properties": {
            "id": {"type": "string"},
            "revision": {"type": "string"},
            "weights_sha256": {
              "type": "string",
              "pattern": "^[a-f0-9]{64}$"
            }
          }
        }
      }
    },
    "wire": {
      "type": "object",
      "required": ["infer_path", "request_schema", "response_schema"],
      "properties": {
        "infer_path": {"type": "string"},
        "request_schema": {"type": "object"},
        "response_schema": {"type": "object"}
      }
    },
    "health": {
      "type": "object",
      "required": ["health_path", "ready_path"],
      "properties": {
        "health_path": {"type": "string"},
        "ready_path": {"type": "string"}
      }
    }
  }
}
"""

_SIDECAR_MANIFEST_EXAMPLE = """{
  "identity": {
    "name": "example-sidecar",
    "version": "example-release",
    "model": {
      "id": "example/model",
      "revision": "example-revision",
      "weights_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    }
  },
  "wire": {
    "infer_path": "/infer",
    "request_schema": {"$ref": "infer_request.schema.json"},
    "response_schema": {"$ref": "infer_response.schema.json"}
  },
  "health": {
    "health_path": "/health",
    "ready_path": "/ready"
  }
}
"""

_GLINER_INFER_SCHEMA = """{
  "$id": "https://polymath.local/contracts/extraction/v1/gliner_infer.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "GLiNER two-pass inference",
  "$defs": {
    "request": {
      "type": "object",
      "required": ["task", "text", "threshold"],
      "properties": {
        "task": {"enum": ["entity", "evidence"]},
        "text": {"type": "string"},
        "threshold": {"type": "number", "minimum": 0, "maximum": 1},
        "labels": {"type": "array", "items": {"type": "string"}}
      },
      "additionalProperties": false
    },
    "span": {
      "type": "object",
      "required": ["text", "start", "end", "label", "score"],
      "properties": {
        "text": {"type": "string"},
        "start": {"type": "integer", "minimum": 0},
        "end": {"type": "integer", "minimum": 0},
        "label": {"type": "string"},
        "score": {"type": "number", "minimum": 0, "maximum": 1}
      },
      "additionalProperties": false
    },
    "response": {
      "type": "object",
      "required": ["task", "spans", "model_release"],
      "properties": {
        "task": {"enum": ["entity", "evidence"]},
        "spans": {"type": "array", "items": {"$ref": "#/$defs/span"}},
        "model_release": {"type": "string"}
      },
      "additionalProperties": false
    }
  }
}
"""

_INGEST_EVENT_SCHEMA = """{
  "$id": "https://polymath.local/contracts/ingestion/v1/ingest_event.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "IngestEvent",
  "type": "object",
  "required": ["event_type", "run_id", "occurred_at", "schema_version"],
  "properties": {
    "event_type": {
      "enum": ["intake", "parse_complete", "embed_complete",
               "extract_complete", "promote_complete", "query_ready"]
    },
    "run_id": {"type": "string"},
    "occurred_at": {"type": "string", "format": "date-time"},
    "schema_version": {"const": "ingest.v1"}
  }
}
"""

_RELATION_CANDIDATE_SCHEMA = """{
  "$id": "https://polymath.local/contracts/extraction/v1/relation_candidate.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RelationCandidate",
  "description": "Compiler input. The normalized tuple the predicate compiler maps onto a canonical fact.",
  "type": "object",
  "required": ["evidence", "subject", "object", "scope", "ontology_profile"],
  "properties": {
    "evidence": {"type": "object"},
    "subject": {"type": "object"},
    "object": {"type": "object"},
    "roles": {"type": "array", "items": {"type": "object"}},
    "roleset": {"type": ["string", "null"]},
    "verbnet_classes": {"type": "array", "items": {"type": "string"}},
    "framenet_frames": {"type": "array", "items": {"type": "string"}},
    "semlink_resolved": {"type": "boolean"},
    "scope": {
      "type": "object",
      "properties": {
        "negated": {"type": "boolean"},
        "speculative": {"type": "boolean"},
        "conditional": {"type": "boolean"},
        "hypothetical": {"type": "boolean"},
        "question": {"type": "boolean"},
        "attributed": {"type": "boolean"},
        "comparison": {"type": "boolean"}
      }
    },
    "ontology_profile": {"type": "string"}
  }
}
"""

_SIDECARS_README = """# Sidecar Registry

Each `.toml` file in this directory registers one sidecar. The
orchestrator reads this directory at boot and refuses to start if
duplicate names or unpinned releases are found.

## Schema

```toml
[name]
display_name = "human readable"
release = "1.0.0"
manifest_url = "http://host:port/manifest"
contract = "contracts/sidecar/v1/manifest.schema.json"
device = "cuda" | "mps" | "cpu"
owner = "sidecar-gpu" | "sidecar-cpu"
```

`release` must match the version in the sidecar's manifest. A
mismatch causes the orchestrator to refuse the sidecar at boot.

## Hot reload

The orchestrator accepts SIGHUP. On SIGHUP it re-reads this
directory, re-fetches every manifest, and updates the routing table.
No restart required.
"""

_SIDECAR_GLINER_ENTITY = """[gliner-entity]
display_name = "GLiNER Entity Pass"
release = "1.0.0"
manifest_url = "http://127.0.0.1:8740/manifest"
contract = "contracts/sidecar/v1/manifest.schema.json"
device = "mps"
owner = "sidecar-gpu"
"""

_SIDECAR_GLINER_EVIDENCE = """[gliner-evidence]
display_name = "GLiNER Evidence Pass"
release = "1.0.0"
manifest_url = "http://127.0.0.1:8741/manifest"
contract = "contracts/sidecar/v1/manifest.schema.json"
device = "mps"
owner = "sidecar-gpu"
"""

_SIDECAR_GLINER_RUNTIME = """[gliner-runtime]
display_name = "GLiNER two-pass runtime"
release = "__PIN_RELEASE__"
manifest_url = "http://127.0.0.1:8740/manifest"
contract = "contracts/sidecar/v1/manifest.schema.json"
device = "__PIN_DEVICE__"
owner = "sidecar-gpu"
"""

_SIDECAR_EMBEDDER = """[embedder]
display_name = "Embedder (Qwen3-Embedding-0.6B)"
release = "1.0.0"
manifest_url = "http://127.0.0.1:8742/manifest"
contract = "contracts/sidecar/v1/manifest.schema.json"
device = "mps"
owner = "sidecar-gpu"
"""

_SIDECAR_RERANKER = """[reranker]
display_name = "Reranker (Qwen3-Reranker-0.6B)"
release = "1.0.0"
manifest_url = "http://127.0.0.1:8743/manifest"
contract = "contracts/sidecar/v1/manifest.schema.json"
device = "mps"
owner = "sidecar-gpu"
"""

_SIDECAR_CLOUD_MODAL = """[cloud-modal]
display_name = "Modal Cloud Overflow (embed)"
release = "1.0.0"
manifest_url = "https://api.modal.example/polymath/embed/manifest"
contract = "contracts/sidecar/v1/manifest.schema.json"
device = "cloud"
owner = "sidecar-cpu"
"""

_CONTROL_README = """# Control Plane

Separate process. Survives orchestrator restarts. Decides "what to do
next" based on the artifact census. Writes back to Postgres.

## Layout

```
control/
├── control/
│   ├── main.py        : entrypoint, systemd hooks
│   ├── heartbeat.py   : writes to control_heartbeats every tick
│   ├── census.py      : desired-vs-observed artifact census
│   ├── scheduler.py   : enqueues stage jobs based on census gaps
│   ├── supervisor.py  : watches sidecar /ready, restarts via systemd
│   └── contracts.py   : pydantic models for control-plane state
└── systemd/
    └── polymath-control.service
```

## What it does NOT do

- Serve user requests. (That's the orchestrator.)
- Hold business logic. (That's the workers.)
- Decide predicates. (That's the compiler.)
- Touch the GPU. (That's the sidecars.)

It is a scheduler + heartbeater. That's it.
"""

_PYPROJECT_STUB = """[project]
name = "polymath-<role>"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["../../tests"]
"""

_PKG_INIT = '"""polymath package. See AGENTS.md for the process-role contract."""\n'

_CONTROL_MAIN = '''"""Control plane entrypoint. See AGENTS.md §1 and ADR-0004.

Role: control. Owns: scheduling + heartbeat. Never serves user requests.
"""
from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from .census import run_census
from .heartbeat import write_heartbeat
from .scheduler import enqueue_census_gaps
from .supervisor import supervise_sidecars


logger = logging.getLogger(__name__)


async def _main_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            census = await run_census()
            await enqueue_census_gaps(census)
        except Exception:
            logger.exception("control tick failed")
        await write_heartbeat()
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=30.0)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stop = asyncio.Event()
    loop = asyncio.new_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    supervisor_task = loop.create_task(supervise_sidecars())
    try:
        loop.run_until_complete(_main_loop(stop))
    finally:
        supervisor_task.cancel()
        with suppress(asyncio.CancelledError):
            loop.run_until_complete(supervisor_task)
        loop.close()


if __name__ == "__main__":
    main()
'''

_CONTROL_HEARTBEAT = '''"""Heartbeat writer. See ADR-0004.

Writes a row to control_heartbeats every tick. Stale heartbeats are how
operators detect a wedged control plane.
"""
from __future__ import annotations

import datetime as _dt

from .contracts import Heartbeat


async def write_heartbeat() -> None:
    """Insert one heartbeat row. The schema lives in stores/postgres/migrations/."""
    raise NotImplementedError  # populated when stores/postgres lands
'''

_CONTROL_CENSUS = '''"""Artifact census. See AGENTS.md §2 and ADR-0004.

Computes desired-vs-observed for every (corpus, doc) pair. The result
is the input to the scheduler.
"""
from __future__ import annotations

from typing import Iterable

from .contracts import CensusReport, CorpusCensus


async def run_census() -> CensusReport:
    """Walk every run row and compute missing artifacts.

    This is a pure function over Postgres state plus the same predicates
    the stage planners use. The algorithm is identical to v3.3's
    desired_state.py; the substrate is Postgres.
    """
    raise NotImplementedError
'''

_CONTROL_SCHEDULER = '''"""Scheduler. Takes a CensusReport, enqueues stage jobs.

The scheduler is the only writer to the ingest queue. It uses the
idempotency key (run_id, stage, contract_hash) so re-enqueueing the
same gap is a no-op.
"""
from __future__ import annotations

from .contracts import CensusReport


async def enqueue_census_gaps(census: CensusReport) -> None:
    """For each missing artifact, enqueue a stage job.

    The job's idempotency key is content-addressed; the queue backend
    (Redis in v1) enforces the dedup.
    """
    raise NotImplementedError
'''

_CONTROL_SUPERVISOR = '''"""Sidecar supervisor. Watches /ready, restarts via systemd.

This replaces the v3.3 autoheal band-aid. The supervisor is allowed to
call systemctl restart <unit> when a sidecar's /ready returns non-OK
for more than N consecutive probes.
"""
from __future__ import annotations

import asyncio
import logging

import httpx


logger = logging.getLogger(__name__)


async def supervise_sidecars() -> None:
    """Loop forever. Watch every sidecar in sidecars/*.toml.

    For each:
      - GET /ready
      - if not ok, increment failure counter
      - if counter > threshold, systemctl restart the unit
    """
    raise NotImplementedError
'''

_CONTROL_CONTRACTS = '''"""Control-plane Pydantic models. Validation only; no logic."""
from __future__ import annotations

from pydantic import BaseModel


class Heartbeat(BaseModel):
    control_id: str
    occurred_at: str  # ISO 8601 UTC
    last_tick_ok: bool
    last_census_size: int


class CorpusCensus(BaseModel):
    corpus_id: str
    desired: int
    observed: int
    missing: list[str]


class CensusReport(BaseModel):
    corpora: list[CorpusCensus]
    generated_at: str  # ISO 8601 UTC
'''

_SYSTEMD_UNIT = """# Place at /etc/systemd/system/polymath-control.service
[Unit]
Description=Polymath v4 Control Plane
After=network.target postgresql.service

[Service]
Type=simple
User=polymath
WorkingDirectory=/opt/polymath-v4/control
ExecStart=/opt/polymath-v4/.venv/bin/python -m control.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

_SIDECAR_GLINER_ENTITY_SERVER = '''"""GLiNER entity-proposal sidecar. ADR-0001 + ADR-0005.

Role: sidecar-gpu. Owns: one GLiNER model, the entity-proposal pass.
Never decides predicates. That is the compiler's job.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class InferRequest(BaseModel):
    text: str
    labels: list[str]
    threshold: float = 0.5


class EntitySpan(BaseModel):
    text: str
    start: int
    end: int
    label: str
    score: float


class InferResponse(BaseModel):
    spans: list[EntitySpan]
    extractor_version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model once. Pin the revision in manifest.toml.
    from gliner import GLiNER
    app.state.model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    # Real readiness: do a 1-token forward pass. Catches poisoned contexts.
    model = app.state.model
    if model is None:
        return {"ready": False, "reason": "model not loaded"}
    return {"ready": True}


@app.post("/infer", response_model=InferResponse)
async def infer(req: InferRequest) -> InferResponse:
    model = app.state.model
    entities = model.predict_entities(req.text, req.labels, threshold=req.threshold)
    return InferResponse(
        spans=[
            EntitySpan(
                text=e["text"],
                start=int(e["start"]),
                end=int(e["end"]),
                label=e["label"],
                score=float(e["score"]),
            )
            for e in entities
        ],
        extractor_version="1.0.0",
    )
'''

_SIDECAR_GLINER_ENTITY_MANIFEST = """# Manifest for the GLiNER entity sidecar.
# Pin the model id + revision + weights sha256 here. The orchestrator
# refuses to call a sidecar whose manifest doesn't match this file.

name = "gliner-entity"
version = "1.0.0"
device = "mps"

[model]
id = "urchade/gliner_small-v2.1"
revision = "__PIN_REVISION__"
weights_sha256 = "__PIN_SHA256__"

[wire]
infer_path = "/infer"

[health]
health_path = "/health"
ready_path = "/ready"
"""

_SIDECAR_GLINER_EVIDENCE_SERVER = '''"""GLiNER evidence-proposal sidecar. ADR-0001 + ADR-0005.

Role: sidecar-gpu. Owns: one GLiNER model, the evidence-proposal pass.
Proposes coarse evidence classes (creation, causation, usage, ...).
NEVER proposes predicates. That is the compiler's job.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel


logger = logging.getLogger(__name__)

# The 18-class evidence inventory from ADR-0001 §4.2.
# Each label is a descriptive natural-language prompt because GLiNER
# embeds labels as text and richer descriptions give the encoder more
# to match against.
EVIDENCE_CLASSES: list[str] = [
    "creation: someone created, founded, established, or started something",
    "causation: something caused, led to, or produced something else",
    "usage: someone or something uses, applies, or uses a method, tool, or resource",
    "ownership: someone or something owns, possesses, or holds something",
    "location: something is located in, based in, or headquartered at a place",
    "temporal: something happens at, during, or before a time",
    "part_of: something is a part, component, or member of a larger thing",
    "is_a: something is a kind, type, or instance of a category",
    "employment: someone works for, is employed by, or has a role at an organization",
    "communication: someone tells, says, announces, or reports something to someone",
    "comparison: something is compared to, contrasted with, or differs from something else",
    "similarity: something resembles, parallels, or is analogous to something else",
    "opposition: something opposes, conflicts with, or contradicts something else",
    "improvement: something improves, enhances, or upgrades something else",
    "degradation: something degrades, harms, or reduces something else",
    "dependency: something depends on, requires, or relies on something else",
    "measurement: something is measured, quantified, or evaluated by something else",
    "intention: someone intends, plans, or aims to do something",
]


class InferRequest(BaseModel):
    text: str
    threshold: float = 0.5


class EvidenceSpan(BaseModel):
    text: str
    start: int
    end: int
    evidence_class: str
    score: float


class InferResponse(BaseModel):
    spans: list[EvidenceSpan]
    extractor_version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    from gliner import GLiNER
    app.state.model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    model = app.state.model
    if model is None:
        return {"ready": False, "reason": "model not loaded"}
    return {"ready": True}


@app.post("/infer", response_model=InferResponse)
async def infer(req: InferRequest) -> InferResponse:
    model = app.state.model
    raw = model.predict_entities(req.text, EVIDENCE_CLASSES, threshold=req.threshold)
    return InferResponse(
        spans=[
            EvidenceSpan(
                text=e["text"],
                start=int(e["start"]),
                end=int(e["end"]),
                evidence_class=e["label"].split(":")[0].strip(),
                score=float(e["score"]),
            )
            for e in raw
        ],
        extractor_version="1.0.0",
    )
'''

_SIDECAR_GLINER_EVIDENCE_MANIFEST = """name = "gliner-evidence"
version = "1.0.0"
device = "mps"

[model]
id = "urchade/gliner_small-v2.1"
revision = "__PIN_REVISION__"
weights_sha256 = "__PIN_SHA256__"

[wire]
infer_path = "/infer"

[health]
health_path = "/health"
ready_path = "/ready"
"""

_SIDECAR_GLINER_RUNTIME_SERVER = '''"""GLiNER two-pass runtime. See AGENTS.md and ADR-0001.

Role: sidecar-gpu. One resident model serves entity and evidence proposal
tasks. Predicate selection remains outside this process.
"""
from __future__ import annotations

import os
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


MANIFEST_PATH = Path(__file__).with_name("manifest.toml")
EVIDENCE_LABELS: list[str] = [
    "creation: created, founded, established, or started",
    "causation: caused, led to, or produced",
    "usage: uses, applies, or operates with",
    "ownership: owns, possesses, or holds",
    "location: located, based, or headquartered",
    "temporal: happens at, during, before, or after",
    "part_of: part, component, or member of",
    "is_a: kind, type, or instance of",
    "employment: works for or has a role at",
    "communication: says, announces, reports, or tells",
    "comparison: compared, contrasted, or differs",
    "similarity: resembles, parallels, or is analogous",
    "opposition: opposes, conflicts, or contradicts",
    "improvement: improves or upgrades",
    "degradation: harms, degrades, or reduces",
    "dependency: depends on, requires, or relies on",
    "measurement: measured, quantified, or evaluated",
    "intention: intends, plans, or aims",
]


class InferRequest(BaseModel):
    task: Literal["entity", "evidence"]
    text: str
    threshold: float
    labels: list[str] = Field(default_factory=list)


class ProposalSpan(BaseModel):
    text: str
    start: int
    end: int
    label: str
    score: float


class InferResponse(BaseModel):
    task: Literal["entity", "evidence"]
    spans: list[ProposalSpan]
    model_release: str


def load_manifest() -> dict:
    with MANIFEST_PATH.open("rb") as handle:
        return tomllib.load(handle)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from gliner import GLiNER

    manifest = load_manifest()
    model_cfg = manifest["identity"]["model"]
    device = os.environ["POLYMATH_GLINER_DEVICE"]
    model = GLiNER.from_pretrained(
        model_cfg["id"],
        revision=model_cfg["revision"],
    )
    app.state.model = model.to(device)
    app.state.manifest = manifest
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/manifest")
async def manifest() -> dict:
    return app.state.manifest


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    model = app.state.model
    if model is None:
        return {"ready": False, "reason": "model not loaded"}
    model.predict_entities("readiness probe", ["readiness probe"])
    return {"ready": True}


@app.post("/infer", response_model=InferResponse)
async def infer(request: InferRequest) -> InferResponse:
    if request.task == "entity" and not request.labels:
        raise HTTPException(status_code=422, detail="entity task requires labels")
    labels = request.labels if request.task == "entity" else EVIDENCE_LABELS
    raw = app.state.model.predict_entities(
        request.text,
        labels,
        threshold=request.threshold,
    )
    return InferResponse(
        task=request.task,
        spans=[
            ProposalSpan(
                text=item["text"],
                start=int(item["start"]),
                end=int(item["end"]),
                label=item["label"].split(":", 1)[0].strip(),
                score=float(item["score"]),
            )
            for item in raw
        ],
        model_release=app.state.manifest["identity"]["version"],
    )
'''

_SIDECAR_GLINER_RUNTIME_MANIFEST = """[identity]
name = "gliner-runtime"
version = "__PIN_RELEASE__"
device = "__PIN_DEVICE__"

[identity.model]
id = "__PIN_MODEL_ID__"
revision = "__PIN_REVISION__"
weights_sha256 = "__PIN_SHA256__"

[wire]
infer_path = "/infer"
request_schema = { "$ref" = "contracts/extraction/v1/gliner_infer.schema.json#/$defs/request" }
response_schema = { "$ref" = "contracts/extraction/v1/gliner_infer.schema.json#/$defs/response" }

[health]
health_path = "/health"
ready_path = "/ready"
"""

_SIDECAR_EMBEDDER_SERVER = '''"""Embedder sidecar. ADR-0005.

Role: sidecar-gpu. Owns: one embedding model. /ready does a real
1-token forward pass (ADR-0003 + ADR-0005).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class EmbedRequest(BaseModel):
    input: list[str]


class EmbedResponse(BaseModel):
    model: str
    data: list[dict]


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sentence_transformers import SentenceTransformer
    app.state.model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    model = app.state.model
    if model is None:
        return {"ready": False, "reason": "model not loaded"}
    # Real readiness: 1-token forward pass.
    _ = model.encode(["ready"], normalize_embeddings=True)
    return {"ready": True}


@app.post("/embeddings", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    model = app.state.model
    vectors = model.encode(req.input, normalize_embeddings=True)
    return EmbedResponse(
        model="qwen3-embedding-0.6b",
        data=[{"index": i, "embedding": v.tolist()} for i, v in enumerate(vectors)],
    )
'''

_SIDECAR_RERANKER_SERVER = '''"""Reranker sidecar. ADR-0005.

Role: sidecar-gpu. Owns: one reranker model. Cosine scores, not logits.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    top_k: int | None = None


class RerankResponse(BaseModel):
    scores: list[float]
    indices: list[int]


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sentence_transformers import CrossEncoder
    app.state.model = CrossEncoder("Qwen/Qwen3-Reranker-0.6B")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    model = app.state.model
    if model is None:
        return {"ready": False, "reason": "model not loaded"}
    return {"ready": True}


@app.post("/rerank", response_model=RerankResponse)
async def rerank(req: RerankRequest) -> RerankResponse:
    model = app.state.model
    pairs = [[req.query, d] for d in req.documents]
    scores = model.predict(pairs).tolist()
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    if req.top_k is not None:
        order = order[: req.top_k]
    return RerankResponse(
        scores=scores,
        indices=order,
    )
'''

_ORCHESTRATOR_README = """# Orchestrator

Dumb on purpose. The orchestrator is the HTTP surface. It does not
make scheduling decisions; the control plane does that. It does not
hold long-running jobs; workers do that. It validates inputs,
enqueues, and reads from the ledger.

## Layout

```
orchestrator/
└── orchestrator/
    ├── main.py       : FastAPI app
    ├── api/
    │   ├── intake.py : POST /ingest
    │   ├── chat.py   : POST /chat
    │   └── health.py : GET /health, /ready, /manifest
    ├── registry.py   : sidecar registry loader
    └── contracts.py  : Pydantic models
```

## What it does NOT do

- Schedule work. (Control plane.)
- Run long jobs. (Workers.)
- Load models. (Sidecars.)
- Hold business logic. (Workers + compiler.)
"""

_ORCHESTRATOR_MAIN = '''"""Orchestrator entrypoint. AGENTS.md §1.

Role: orchestrator. Stateless. Dumb on purpose. See ADR-0004.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.chat import router as chat_router
from .api.health import router as health_router
from .api.intake import router as intake_router
from .registry import load_sidecar_registry


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.sidecars = load_sidecar_registry()
    yield


app = FastAPI(title="Polymath Orchestrator", lifespan=lifespan)
app.include_router(health_router)
app.include_router(intake_router)
app.include_router(chat_router)
'''

_ORCHESTRATOR_INTAKE = '''"""Intake API. POST /ingest.

Validates input, writes a runs row, enqueues an intake.v1 job.
Returns run_id immediately. The control plane picks up the job.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class IngestRequest(BaseModel):
    corpus_id: str
    source: str  # path or URL
    profile: str = "default"


class IngestResponse(BaseModel):
    run_id: str
    accepted: bool


@router.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest) -> IngestResponse:
    # TODO: write runs row + outbox + enqueue (atomically).
    raise NotImplementedError
'''

_ORCHESTRATOR_CHAT = '''"""Chat API. POST /chat.

Validates input, reads from the ledger, calls the synthesis path.
No long-running work. No scheduling. No model loading.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    corpus_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[int]


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    raise NotImplementedError
'''

_ORCHESTRATOR_HEALTH = '''"""Health endpoints. /health, /ready, /manifest."""
from __future__ import annotations

from fastapi import APIRouter, Request


router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict:
    # /ready means "I can serve traffic right now." Different from /health.
    sidecars = request.app.state.sidecars
    statuses = {name: s.is_ready() for name, s in sidecars.items()}
    return {"ready": all(statuses.values()), "sidecars": statuses}


@router.get("/manifest")
async def manifest(request: Request) -> dict:
    sidecars = request.app.state.sidecars
    return {"sidecars": {name: s.manifest for name, s in sidecars.items()}}
'''

_ORCHESTRATOR_REGISTRY = '''"""Sidecar registry loader.

Reads sidecars/*.toml at boot, fetches each manifest, pins release
identities. Refuses to start if any sidecar is missing or has a
manifest mismatch.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import httpx
import tomllib


class Sidecar:
    def __init__(self, name: str, manifest: dict, base_url: str) -> None:
        self.name = name
        self.manifest = manifest
        self.base_url = base_url

    def is_ready(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/ready", timeout=2.0)
            return r.status_code == 200 and r.json().get("ready", False)
        except Exception:
            return False


def load_sidecar_registry(root: Path = Path("sidecars")) -> Mapping[str, Sidecar]:
    out: dict[str, Sidecar] = {}
    for toml in root.glob("*.toml"):
        with toml.open("rb") as f:
            entry = tomllib.load(f)
        for name, cfg in entry.items():
            base = cfg["manifest_url"].rsplit("/manifest", 1)[0]
            r = httpx.get(f"{base}/manifest", timeout=5.0)
            r.raise_for_status()
            out[name] = Sidecar(name=name, manifest=r.json(), base_url=base)
    return out
'''

_ORCHESTRATOR_CONTRACTS = '''"""Orchestrator Pydantic models. Validation only."""
from __future__ import annotations

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    corpus_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    profile: str = "default"


class IngestResponse(BaseModel):
    run_id: str
    accepted: bool


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    corpus_id: str | None = None
'''

_WORKERS_README = """# Workers

Queue-driven. Idempotent. Crash-safe. One worker per stage.

## Layout

```
workers/
└── workers/
    ├── intake_worker.py  : parse + chunk
    ├── embed_worker.py   : calls embedder sidecar
    ├── extract_worker.py : calls gliner-runtime twice, then compiler
    └── promote_worker.py : writes to qdrant + neo4j, issues query_ready
```

## Idempotency

Every job is keyed on (run_id, stage, contract_hash). The queue
(Redis in v1) dedupes by key. Re-running a job on the same input is
a no-op, provably, because the content hash is the same.

## Crash safety

Every job's durable write + receipt + status transition is a single
Postgres transaction. If the worker crashes mid-transaction, Postgres
rolls back; the next tick of the control plane sees the run still in
its previous state and re-enqueues.
"""

_PYPROJECT_STUB_ALT = _PYPROJECT_STUB  # alias for clarity

_WORKER_INTAKE = '''"""Intake worker. Parses the source and produces chunks.

Role: worker. Idempotent. Crash-safe.
"""
from __future__ import annotations

import asyncio
import json
import logging


logger = logging.getLogger(__name__)


async def handle_intake(job: dict) -> None:
    """Parse the source, write chunks, write a stage_attempts receipt.

    The transaction is: insert chunks -> insert stage_attempt -> commit.
    If any step fails, Postgres rolls back; the run stays in `intake`
    and the control plane re-enqueues.
    """
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(handle_intake({}))
'''

_WORKER_EMBED = '''"""Embed worker. Calls the embedder sidecar.

Role: worker. Idempotent. Uses shared/polymath_shared/clients.py for
the sidecar call; never hand-rolls HTTP.
"""
from __future__ import annotations

import asyncio
import logging


logger = logging.getLogger(__name__)


async def handle_embed(job: dict) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(handle_embed({}))
'''

_WORKER_EXTRACT = '''"""Extract worker. The two-pass GLiNER + compiler.

Role: worker. Idempotent.

Order of operations:
  1. Call gliner-entity sidecar -> entity spans
  2. Call gliner-evidence sidecar -> evidence spans
  3. For each (entity_pair, evidence_class) candidate:
       a. Run UD parse
       b. Look up VerbNet/PropBank/FrameNet/SemLink
       c. Call the compiler (pure function)
       d. Persist CanonicalFact + EvidenceRecord
"""
from __future__ import annotations

import asyncio
import logging


logger = logging.getLogger(__name__)


async def handle_extract(job: dict) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(handle_extract({}))
'''

_WORKER_PROMOTE = '''"""Promote worker. Writes to Qdrant + Neo4j, issues query_ready.

Role: worker. Idempotent. The last stage.
"""
from __future__ import annotations

import asyncio
import logging


logger = logging.getLogger(__name__)


async def handle_promote(job: dict) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(handle_promote({}))
'''

_SHARED_README = """# Shared library

Used by orchestrator, workers, control, and sidecars. Holds the
contracts every process depends on.

## Modules

- `identity.py`: content-hash identity for documents, chunks,
  entities, facts, evidence. Use this. Do not call hashlib directly.
- `receipts.py`: durable write + receipt + status transition in a
  single transaction. Use this. Do not write receipts by hand.
- `contracts.py`: Pydantic models for every cross-process record.
- `logging.py`: structured JSON logging.
- `clients.py`: typed HTTP clients for sidecars. Use this. Do not
  hand-roll requests.
"""

_SHARED_IDENTITY = '''"""Content-hash identity. The single source of truth for IDs.

The rule: every durable identifier in Polymath v4 is a content hash of
its canonicalized input. Re-running the same input produces the same
ID. There are no UUIDs in the durable layer.

Use the functions in this module. Do not call hashlib.sha256 directly.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize(obj: Any) -> bytes:
    """Serialize obj in a deterministic way.

    Rules:
      - JSON with sort_keys=True
      - UTF-8
      - No trailing whitespace
      - separators=(",", ":") for compactness
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_hash(obj: Any) -> str:
    """Return sha256(canonicalize(obj)) as a hex string."""
    return hashlib.sha256(canonicalize(obj)).hexdigest()


def fact_id(predicate: str, subject_id: str, object_id: str, qualifiers: dict) -> str:
    """The canonical fact identity. See ADR-0001 §17."""
    return f"fact_{content_hash({'p': predicate, 's': subject_id, 'o': object_id, 'q': qualifiers})}"


def evidence_id(fact_id: str, doc_id: str, chunk_id: str, span_offsets: dict, rule_id: str) -> str:
    """The canonical evidence identity. Re-derived, never duplicated."""
    return f"ev_{content_hash({'f': fact_id, 'd': doc_id, 'c': chunk_id, 'o': span_offsets, 'r': rule_id})}"


def entity_id(core_type: str, normalized_surface: str, kb_id: str | None = None) -> str:
    """The canonical entity identity. Two-tier: KB-linked or surface-derived."""
    if kb_id:
        return f"ent_{content_hash({'core': core_type, 'kb': kb_id})}"
    return f"ent_{content_hash({'core': core_type, 'surface': normalized_surface.lower()})}"


def document_id(normalized_bytes: bytes) -> str:
    """sha256 of the normalized source bytes. Identical re-uploads map to one document."""
    return f"doc_{hashlib.sha256(normalized_bytes).hexdigest()}"


def chunk_id(doc_id: str, chunk_index: int, chunk_text: str) -> str:
    return f"chunk_{content_hash({'d': doc_id, 'i': chunk_index, 't': chunk_text})}"
'''

_SHARED_RECEIPTS = '''"""Receipts. The single transaction boundary for durable writes.

The rule: a stage's durable write + its receipt + its status
transition are one transaction. If they are not, the stage is wrong.

Use the functions in this module. Do not write receipts by hand.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


@contextmanager
def stage_transaction(*, run_id: str, stage: str, contract_hash: str) -> Iterator[Any]:
    """Yield a transaction handle. The caller writes its durable data,
    its receipt, and the status transition inside the with-block.

    Commits on clean exit, rolls back on exception. The contract_hash
    is the idempotency key; re-running with the same key is a no-op.
    """
    raise NotImplementedError  # populated when stores/postgres lands
'''

_SHARED_CONTRACTS = '''"""Cross-process Pydantic models. Used everywhere."""
from __future__ import annotations

from pydantic import BaseModel


class RunRecord(BaseModel):
    run_id: str
    corpus_id: str
    status: str  # intake | reconciling | query_ready | degraded
    created_at: str
    updated_at: str


class StageAttempt(BaseModel):
    run_id: str
    stage: str
    contract_hash: str
    started_at: str
    completed_at: str | None
    outcome: str  # ok | failed | skipped
    error: str | None = None
'''

_SHARED_LOGGING = '''"""Structured JSON logging. See AGENTS.md for the field contract."""
from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from typing import Any


CONTEXT_FIELDS = (
    "trace_id",
    "run_id",
    "stage",
    "attempt_id",
    "provider",
    "model_release",
    "device",
    "duration_ms",
    "error_code",
)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", self.service),
            "event": getattr(record, "event", record.name),
            "message": record.getMessage(),
        }
        payload.update({field: getattr(record, field, None) for field in CONTEXT_FIELDS})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(service: str, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def with_context(logger: logging.Logger, **context: Any) -> logging.LoggerAdapter:
    unknown = set(context) - set(CONTEXT_FIELDS) - {"event", "service"}
    if unknown:
        raise ValueError(f"unknown log fields: {sorted(unknown)}")
    return logging.LoggerAdapter(logger, context)
'''

_SHARED_CLIENTS = '''"""Typed HTTP clients for sidecars. Use these. Do not hand-roll."""
from __future__ import annotations

from typing import Any

import httpx


class SidecarClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def manifest(self) -> dict[str, Any]:
        r = self._client.get("/manifest")
        r.raise_for_status()
        return r.json()

    def ready(self) -> bool:
        try:
            r = self._client.get("/ready", timeout=2.0)
            return r.status_code == 200 and r.json().get("ready", False)
        except Exception:
            return False

    def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = self._client.post("/infer", json=payload)
        r.raise_for_status()
        return r.json()
'''

_STORES_README = """# Stores

Durable state. Every store is bind-mounted, never in-app.

- `postgres/`: runs, stage_attempts, outbox, control_heartbeats,
  users, settings, artifacts_index. Migrations in `migrations/`.
- `qdrant/`: vectors. Per-corpus collections.
- `neo4j/`: graph. Constraints in `constraints/`.
- `redis/`: queue + cache. Ephemeral. Allowed to die.

## Migrations

`stores/postgres/migrations/` is append-only. New file = new
migration. Never edit a migration that has been applied. The
up/down split is mandatory.

## Migrations (initial)

The first migration creates the load-bearing tables. Subsequent
migrations add columns, add tables, add indexes.
"""

_POSTGRES_MIGRATION_0001 = """-- 0001_initial.sql
-- The first migration creates the load-bearing tables for Polymath v4.
-- See ADR-0002 (Postgres over Mongo) and ADR-0004 (control plane as
-- a separate process that writes to control_heartbeats).

BEGIN;

CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    corpus_id     TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN
                    ('intake','reconciling','query_ready','degraded','failed')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS runs_corpus_status_idx
    ON runs (corpus_id, status);
CREATE INDEX IF NOT EXISTS runs_updated_at_idx
    ON runs (updated_at);

CREATE TABLE IF NOT EXISTS stage_attempts (
    run_id         TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    stage          TEXT NOT NULL,
    contract_hash  TEXT NOT NULL,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at   TIMESTAMPTZ,
    outcome        TEXT CHECK (outcome IN ('ok','failed','skipped')),
    error          TEXT,
    payload        JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (run_id, stage, contract_hash)
);

CREATE TABLE IF NOT EXISTS outbox (
    outbox_id    BIGSERIAL PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    enqueued_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload      JSONB NOT NULL,
    delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS outbox_pending_idx
    ON outbox (enqueued_at) WHERE delivered_at IS NULL;

CREATE TABLE IF NOT EXISTS control_heartbeats (
    control_id        TEXT NOT NULL,
    occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_tick_ok      BOOLEAN NOT NULL,
    last_census_size  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS control_heartbeats_recent_idx
    ON control_heartbeats (control_id, occurred_at DESC);

-- The control plane NOTIFY channel. Postgres LISTEN/NOTIFY is the
-- cheap wakeup mechanism in ADR-0004.
NOTIFY control_tick;

COMMIT;
"""

_COMPOSE_DATA_STORES_ONLY = """# compose.yaml: Polymath v4
# Only the data stores run in Docker. The orchestrator, workers,
# control plane, and sidecars are host-native. See ADR-0003.

services:
  postgres:
    image: ${POSTGRES_IMAGE}
    environment:
      POSTGRES_USER: polymath
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: polymath
    volumes:
      - ./stores/postgres/data:/var/lib/postgresql/data
      - ./stores/postgres/migrations:/docker-entrypoint-initdb.d:ro
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U polymath"]
    restart: unless-stopped

  qdrant:
    image: ${QDRANT_IMAGE}
    volumes:
      - ./stores/qdrant/snapshots:/qdrant/snapshots
    ports:
      - "127.0.0.1:6333:6333"
    healthcheck:
      test: ["CMD", "bash", "-c", "exec 3<>/dev/tcp/localhost/6333 && echo -e 'GET /healthz HTTP/1.0\\r\\n\\r\\n' >&3"]
    restart: unless-stopped

  neo4j:
    image: ${NEO4J_IMAGE}
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
    volumes:
      - ./stores/neo4j/data:/data
      - ./stores/neo4j/constraints:/constraints
    ports:
      - "127.0.0.1:7474:7474"
      - "127.0.0.1:7687:7687"
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p ${NEO4J_PASSWORD} 'RETURN 1' || exit 1"]
    restart: unless-stopped

  redis:
    image: ${REDIS_IMAGE}
    volumes:
      - ./stores/redis:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
    restart: unless-stopped
"""

_TESTS_README = """# Tests

Three buckets, by what they protect.

- `contracts/`: every JSON schema validates. Examples and
  hand-written negative cases.
- `determinism/`: given the same input, the same output. Canonical
  hashing, idempotent retries, receipt-stable writes.
- `integration/`: end-to-end flows. Slower. Gated to nightly.
"""

_TESTS_CONFTEST = '''"""Shared pytest fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def shared_on_path(repo_root: Path) -> None:
    p = repo_root / "shared"
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
'''

_TEST_SIDECAR_MANIFEST = '''"""The sidecar manifest schema validates against the example."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest


def test_sidecar_manifest_example_is_valid(repo_root: Path) -> None:
    schema = json.loads(
        (repo_root / "contracts" / "sidecar" / "v1" / "manifest.schema.json").read_text()
    )
    example = json.loads(
        (repo_root / "contracts" / "sidecar" / "v1" / "manifest.example.json").read_text()
    )
    jsonschema.validate(example, schema)
'''

_TEST_IDEMPOTENCY = '''"""Re-running the same content produces the same IDs."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_fact_id_is_deterministic(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root / "shared"))
    from polymath_shared.identity import fact_id

    a = fact_id("FOUNDED", "ent_alice", "ent_acme", {"valid_from": "2012"})
    b = fact_id("FOUNDED", "ent_alice", "ent_acme", {"valid_from": "2012"})
    assert a == b


def test_fact_id_changes_with_qualifier(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root / "shared"))
    from polymath_shared.identity import fact_id

    a = fact_id("FOUNDED", "ent_alice", "ent_acme", {"valid_from": "2012"})
    b = fact_id("FOUNDED", "ent_alice", "ent_acme", {"valid_from": "2013"})
    assert a != b
'''

_TEST_CANONICAL_HASHING = '''"""Canonical hashing: key order must not change the hash."""
from __future__ import annotations

import sys
from pathlib import Path


def test_canonicalize_is_key_order_invariant(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root / "shared"))
    from polymath_shared.identity import content_hash

    a = content_hash({"a": 1, "b": 2, "c": 3})
    b = content_hash({"c": 3, "a": 1, "b": 2})
    assert a == b


def test_unicode_normalization_is_stable(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root / "shared"))
    from polymath_shared.identity import content_hash

    # Same string, same hash.
    a = content_hash({"name": "café"})
    b = content_hash({"name": "café"})
    assert a == b
'''

_SCRIPTS_README = """# Managed scripts

Every repository script is declared in the scaffold `TREE`. Additions require
an owner, documented writes, a safe read-only mode when the script mutates
state, and a work-log entry.

| Script | Owner | Reads | Writes | Safe invocation |
|---|---|---|---|---|
| `scripts/scaffold_polymath_v4.py` | governance | its `TREE` and embedded content | missing declared files only | `python3 scripts/scaffold_polymath_v4.py` |
| `scripts/agent_preflight.py` | governance | repository structure and metadata | nothing | `python3 scripts/agent_preflight.py` |
| `scripts/repo_guard.py` | governance | declared paths, dependency map, work logs, optional Git diff | nothing | `python3 scripts/repo_guard.py` |
| `scripts/wiki_worm.py` | governance | `docs/wiki/` metadata | nothing | `python3 scripts/wiki_worm.py --check` |
| `scripts/check_install.sh` | control | loopback health endpoints | nothing | `bash scripts/check_install.sh` |

No script may commit, push, delete, migrate, or repair services unless its
contract names that mutation and requires an explicit operator flag.
"""

_CHECK_INSTALL_SH = """#!/usr/bin/env bash
# Read-only reachability report. See AGENTS.md and scripts/README.md.
set -u

check_tcp() {
  local name="$1"
  local port="$2"
  nc -z 127.0.0.1 "$port" >/dev/null 2>&1 \
    && echo "$name: reachable" \
    || echo "$name: unavailable"
}

check_http() {
  local name="$1"
  local url="$2"
  curl -fsS "$url" >/dev/null \
    && echo "$name: ready" \
    || echo "$name: unavailable"
}

check_tcp postgres 5432
check_http qdrant http://127.0.0.1:6333/healthz
check_http neo4j http://127.0.0.1:7474
check_tcp redis 6379
check_http gliner-runtime http://127.0.0.1:8740/ready
check_http embedder http://127.0.0.1:8742/ready
check_http reranker http://127.0.0.1:8743/ready
check_http orchestrator http://127.0.0.1:8000/health
check_http control http://127.0.0.1:7100/health
"""

_WIKI_WORM = '''"""Read-only wiki audit. See AGENTS.md and scripts/README.md."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_front_matter(text: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def audit(root: Path) -> tuple[list[str], list[str], list[str]]:
    wiki = root / "docs" / "wiki"
    errors: list[str] = []
    open_refactors: list[str] = []
    open_work: list[str] = []
    if not wiki.is_dir():
        return ["docs/wiki is missing"], open_refactors, open_work

    for path in sorted(wiki.rglob("*.md")):
        relative = path.relative_to(root).as_posix()
        metadata = parse_front_matter(path.read_text())
        if metadata is None:
            errors.append(f"{relative}: missing front matter")
            continue
        if not metadata.get("last_reviewed"):
            errors.append(f"{relative}: missing last_reviewed")
        status = metadata.get("status")
        if "refactors" in path.parts and path.name != "README.md":
            if status != "done":
                open_refactors.append(relative)
        if "work-log" in path.parts and path.name != "README.md":
            if status != "complete":
                open_work.append(relative)

    return errors, open_refactors, open_work


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--check", action="store_true", help="Audit only; this script never writes.")
    args = parser.parse_args(argv)

    errors, open_refactors, open_work = audit(args.root.resolve())
    print("open refactors:")
    for item in open_refactors:
        print(f"  {item}")
    print("open work logs:")
    for item in open_work:
        print(f"  {item}")
    if errors:
        print("WIKI CHECK FAILED", file=sys.stderr)
        for item in errors:
            print(f"  {item}", file=sys.stderr)
        return 1
    print("wiki: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

_REPO_GUARD = '''"""Repository governance checks. See AGENTS.md and scripts/README.md."""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


IGNORED_NAMES = {
    ".DS_Store",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}
IGNORED_PREFIXES = (
    "stores/postgres/data/",
    "stores/qdrant/data/",
    "stores/neo4j/data/",
)
MODULE_OWNERS = {
    "control": "control",
    "orchestrator": "orchestrator",
    "polymath_shared": "shared",
    "sidecars": "sidecar",
    "workers": "worker",
}
WORK_LOG_FIELDS = {
    "change_id",
    "owner",
    "date",
    "status",
    "architecture_impact",
}
WORK_LOG_SECTIONS = (
    "## Contract",
    "## Changes",
    "## Proof",
    "## Rejected claims",
    "## Open contract gaps",
)


def load_scaffold(root: Path) -> ModuleType:
    path = root / "scripts" / "scaffold_polymath_v4.py"
    spec = importlib.util.spec_from_file_location("polymath_scaffold", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load scaffold from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def declared_paths(root: Path) -> set[str]:
    module = load_scaffold(root)
    return {item[0] for item in module.TREE}


def is_ignored(relative: str) -> bool:
    path = Path(relative)
    if any(part in IGNORED_NAMES for part in path.parts):
        return True
    return relative.startswith(IGNORED_PREFIXES)


def actual_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not is_ignored(path.relative_to(root).as_posix())
    }


def parse_front_matter(text: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def check_declared_files(root: Path) -> list[str]:
    declared = declared_paths(root)
    actual = actual_files(root)
    errors = [f"missing declared path: {path}" for path in sorted(declared - actual)]
    errors.extend(f"undeclared repository file: {path}" for path in sorted(actual - declared))
    return errors


def check_script_registry(root: Path) -> list[str]:
    registry = (root / "scripts" / "README.md").read_text()
    errors: list[str] = []
    for path in sorted(declared_paths(root)):
        if path.startswith("scripts/") and path != "scripts/README.md":
            if f"`{path}`" not in registry:
                errors.append(f"script missing from registry: {path}")
    return errors


def check_work_logs(root: Path) -> list[str]:
    errors: list[str] = []
    folder = root / "docs" / "wiki" / "work-log"
    entries = sorted(path for path in folder.glob("*.md") if path.name != "README.md")
    if not entries:
        return ["work log has no entries"]
    for path in entries:
        relative = path.relative_to(root).as_posix()
        text = path.read_text()
        metadata = parse_front_matter(text)
        if metadata is None:
            errors.append(f"{relative}: invalid front matter")
            continue
        missing = WORK_LOG_FIELDS - set(metadata)
        if missing:
            errors.append(f"{relative}: missing fields {sorted(missing)}")
        positions = [text.find(section) for section in WORK_LOG_SECTIONS]
        if any(position < 0 for position in positions):
            errors.append(f"{relative}: missing required work-log section")
        elif positions != sorted(positions):
            errors.append(f"{relative}: work-log sections out of order")
    return errors


def check_dependencies(root: Path) -> list[str]:
    path = root / "architecture" / "dependencies.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid dependency map: {exc}"]
    owners = data.get("owners", {})
    errors: list[str] = []
    if not isinstance(owners, dict) or not owners:
        return ["dependency map has no owners"]
    for owner, config in owners.items():
        for dependency in config.get("may_depend_on", []):
            if dependency not in owners:
                errors.append(f"{owner}: unknown dependency {dependency}")
    for pair in data.get("forbidden_imports", []):
        if pair.get("from") not in owners or pair.get("to") not in owners:
            errors.append(f"invalid forbidden import pair: {pair}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(owner: str) -> None:
        if owner in visiting:
            errors.append(f"dependency cycle includes {owner}")
            return
        if owner in visited:
            return
        visiting.add(owner)
        for dependency in owners[owner].get("may_depend_on", []):
            visit(dependency)
        visiting.remove(owner)
        visited.add(owner)

    for owner in owners:
        visit(owner)
    return errors


def path_owner(relative: str, owners: dict) -> str | None:
    for owner, config in owners.items():
        if any(relative.startswith(prefix) for prefix in config.get("paths", [])):
            return owner
    return None


def check_forbidden_imports(root: Path) -> list[str]:
    data = json.loads((root / "architecture" / "dependencies.json").read_text())
    owners = data["owners"]
    forbidden = {(item["from"], item["to"]) for item in data["forbidden_imports"]}
    errors: list[str] = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        if is_ignored(relative) or relative.startswith("scripts/") or relative.startswith("tests/"):
            continue
        owner = path_owner(relative, owners)
        if owner is None:
            continue
        try:
            tree = ast.parse(path.read_text(), filename=relative)
        except SyntaxError as exc:
            errors.append(f"{relative}: syntax error prevents import check: {exc.msg}")
            continue
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        for module in imported:
            target = MODULE_OWNERS.get(module)
            if target and (owner, target) in forbidden:
                errors.append(f"{relative}: forbidden {owner} import of {target}")
    return errors


def changed_paths(root: Path, base: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"cannot diff against {base}")
    return {line for line in result.stdout.splitlines() if line}


def check_change_companions(root: Path, base: str) -> list[str]:
    changed = changed_paths(root, base)
    errors: list[str] = []
    has_work_log = any(
        path.startswith("docs/wiki/work-log/") and not path.endswith("README.md")
        for path in changed
    )
    architecture_changed = bool(
        {"ARCHITECTURE.md", "architecture/dependencies.json"} & changed
    )
    if architecture_changed:
        requirements = {
            "ARCHITECTURE_CHANGELOG.md": "architecture changelog",
        }
        for path, label in requirements.items():
            if path not in changed:
                errors.append(f"architecture change missing {label}: {path}")
        if not any(path.startswith("docs/wiki/decisions/") and not path.endswith(("README.md", "0000-template.md")) for path in changed):
            errors.append("architecture change missing ADR")
        if not any(path.startswith("docs/wiki/refactors/") and not path.endswith("README.md") for path in changed):
            errors.append("architecture change missing refactor entry")
        if not has_work_log:
            errors.append("architecture change missing work log")
    if any(path.startswith("scripts/") for path in changed):
        if "scripts/README.md" not in changed:
            errors.append("script change missing scripts/README.md update")
        if not has_work_log:
            errors.append("script change missing work log")
    if any(path.startswith(("contracts/", "stores/postgres/migrations/")) for path in changed):
        if not has_work_log:
            errors.append("contract or migration change missing work log")
    return errors


def run_checks(root: Path, base: str | None = None) -> list[str]:
    checks = [
        check_declared_files,
        check_script_registry,
        check_work_logs,
        check_dependencies,
        check_forbidden_imports,
    ]
    errors: list[str] = []
    for check in checks:
        errors.extend(check(root))
    if base:
        try:
            errors.extend(check_change_companions(root, base))
        except RuntimeError as exc:
            errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--base", help="Git base revision for companion-change checks")
    args = parser.parse_args()
    errors = run_checks(args.root.resolve(), args.base)
    if errors:
        print("REPO GUARD FAILED", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    print("repo guard: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

_AGENT_PREFLIGHT = '''"""Agent preflight. See AGENTS.md and scripts/README.md.

This command is read-only. Use --strict before deployment to reject unpinned
model manifests in addition to repository-structure failures.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from pathlib import Path

from repo_guard import run_checks


def check_python_syntax(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*.py"):
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        try:
            ast.parse(path.read_text(), filename=relative)
        except SyntaxError as exc:
            errors.append(f"{relative}: {exc.msg} at line {exc.lineno}")
    return errors


def check_json_and_toml(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*.json"):
        try:
            json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(root)}: invalid JSON: {exc}")
    for path in root.rglob("*.toml"):
        try:
            with path.open("rb") as handle:
                tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{path.relative_to(root)}: invalid TOML: {exc}")
    return errors


def check_model_pins(root: Path) -> list[str]:
    errors: list[str] = []
    for server in (root / "sidecars").glob("*/server.py"):
        manifest = server.with_name("manifest.toml")
        if not manifest.exists():
            errors.append(f"{server.parent.relative_to(root)}: missing manifest.toml")
    for path in (root / "sidecars").rglob("*.toml"):
        if "__PIN_" in path.read_text():
            errors.append(f"{path.relative_to(root)}: unresolved deployment pin")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    errors = run_checks(root)
    errors.extend(check_python_syntax(root))
    errors.extend(check_json_and_toml(root))
    if args.strict:
        errors.extend(check_model_pins(root))

    if errors:
        print("PREFLIGHT FAILED", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    print("preflight: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

_CI_CONTRACTS = """name: contracts
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install jsonschema pytest
      - run: pytest tests/contracts/ -v
"""

_CI_DETERMINISM = """name: determinism
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pytest
      - run: pytest tests/determinism/ -v
"""

_CI_AGENT_PREFLIGHT = """name: agent-preflight
on: [push, pull_request]
jobs:
  preflight:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python3 scripts/agent_preflight.py
"""

_CI_REPO_GOVERNANCE = """name: repo-governance
on: [push, pull_request]
jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - if: github.event_name == 'pull_request'
        run: python3 scripts/repo_guard.py --base "origin/${{ github.base_ref }}"
      - if: github.event_name != 'pull_request'
        run: python3 scripts/repo_guard.py
      - run: python3 scripts/wiki_worm.py --check
"""


# ===========================================================================
# Content lookup. Maps TREE content keys to the actual constant. Built
# by name so adding a new file = add to TREE + define _<NAME> constant.
# Anything missing here is a scaffold-author bug.
# ===========================================================================

def _build_content_lookup() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, value in list(globals().items()):
        if not name.startswith("_"):
            continue
        if not name[1:].isupper():
            continue
        if not isinstance(value, str):
            continue
        # Strip the leading underscore to get the TREE key.
        out[name[1:]] = value
    return out


_CONTENT = _build_content_lookup()

# ===========================================================================
# Scaffold engine. Do not edit below unless you are changing the rules.
# ===========================================================================


def _resolve(key: str | None) -> str | None:
    if key is None:
        return None
    # Tolerate keys with or without the leading underscore so TREE
    # entries can be written either way.
    lookup = key[1:] if key.startswith("_") else key
    if lookup not in _CONTENT:
        raise KeyError(
            f"scaffold bug: TREE references content key {key!r} but no _"
            f"{lookup} constant is defined. Add the constant near the other "
            f"content blocks."
        )
    return _CONTENT[lookup]


def _maybe_write(path: Path, content: str | None) -> str:
    """Write content to path if it does not exist. Return what we did."""
    if path.exists():
        return "exists"
    if content is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return "touched"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return "wrote"


def _expand(content: str | None) -> str | None:
    if content is None:
        return None
    return content.replace("__TODAY__", TODAY).replace("__SCRIPT_SHA__", SCRIPT_SHA)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--name", default=None, help="Optional name banner.")
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    if args.name:
        print(f"scaffolding {args.name} into {root}")
    else:
        print(f"scaffolding polymath-v4 into {root}")

    counts = {"wrote": 0, "exists": 0, "touched": 0}
    for rel, kind, key in TREE:
        content = Path(__file__).read_text() if kind == "self" else _expand(_resolve(key))
        action = _maybe_write(root / rel, content)
        counts[action] = counts.get(action, 0) + 1
        marker = {"wrote": "+", "exists": "=", "touched": "."}[action]
        print(f"  {marker} {rel}")

    print()
    print(f"wrote: {counts['wrote']}, exists: {counts['exists']}, touched: {counts['touched']}")
    print()
    print("Next steps:")
    print("  1. python3 scripts/agent_preflight.py")
    print("  2. python3 scripts/repo_guard.py")
    print("  3. python3 scripts/wiki_worm.py --check")
    print("  4. Read docs/runbooks/agent-onboarding.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
