-- 0067: CORPUS-ACCESS-PARITY (the owner, 2026-11-01: "the corpus it uses it should be able to use any corpus, idk why we have
-- corpus false error its just a lot of dumb bugs").
--
-- The owner's real libraries were created by uploads while the column default was purpose='probe', query_enabled=false
-- (0035), so EVERY one of them is 'probe' and "all libraries" (ALL_AUTHORIZED: purpose='production' AND query_enabled AND
-- query-ready) resolved to nothing. This reclassifies exactly those libraries — by an explicit corpus_id list, never a pattern —
-- as what they are: production, query-enabled.
--
-- Readers of corpora.purpose / corpora.query_enabled checked before writing this (2026-11-01): ALL_AUTHORIZED
-- (shared/polymath_shared/query_scope.py), GET /corpora + PATCH /corpora/{id}/query_enabled (orchestrator api/ui.py), MCP
-- list_corpora (passes GET /corpora through), the legacy UI (CorporaView / FilesView display + toggle) and frontend-v2 Overview
-- (display), tests/determinism/test_killchain_gates.py (picks one production corpus for a read-only check). The control plane,
-- fleet autopilot, census, medic, scheduler and workers read neither column: nothing changes there.
--
-- The column DEFAULTS stay 'probe' / false on purpose: a raw INSERT (a test fixture, an eval harness) is not user material and
-- must not join "all libraries". The user creation paths classify explicitly instead — the intake worker for an upload into a
-- new corpus_id and web_accounts for a friend's private library (polymath_shared.query_scope.new_corpus_classification).
--
-- Idempotent: a second run matches no row (the WHERE excludes rows already production + query-enabled) and changes nothing.
-- Rollback: UPDATE corpora SET purpose='probe', query_enabled=<previous value>, updated_at=now() WHERE corpus_id IN (<list>);
-- (previous values 2026-11-01: query_enabled false for cinema, commerce-v1, mythos; true for the other four).

UPDATE corpora
   SET purpose = 'production', query_enabled = true, updated_at = now()
 WHERE corpus_id IN (
   'cinema',
   'commerce-v1',
   'mythos',
   'social-media-taste',
   'video-rules',
   'video-taste',
   'video-technique')
   AND (purpose IS DISTINCT FROM 'production' OR query_enabled IS DISTINCT FROM true);
