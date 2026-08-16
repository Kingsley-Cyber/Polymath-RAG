# Polymath v4 — local-first deployment (macOS host + Docker for stores only).
#
# Stores live in Compose (ADR-0003). Every model process is host-native and
# supervised by launchd. `make dev` runs the whole stack in the foreground
# for development; `make install-launchd` installs the stable units.

PY     ?= .venv/bin/python
UV     ?= uv
COMPOSE = docker compose

.PHONY: setup db-up db-down db-migrate migrate dev test guards install-launchd uninstall-launchd clean

## setup — create the venv and install the workspace (editable)
setup:
	$(UV) venv --python 3.11 .venv
	$(UV) pip install -e shared -e workers -e orchestrator -e control
	$(UV) pip install pytest

## db-up — start the data stores (Postgres, Qdrant, Neo4j, Redis)
db-up:
	$(COMPOSE) up -d --wait

## db-down — stop the data stores
db-down:
	$(COMPOSE) down

## db-migrate — apply unapplied Postgres migrations in order
db-migrate:
	@for f in stores/postgres/migrations/*.sql; do \
		echo "applying $$f"; \
		$(COMPOSE) exec -T postgres psql -U polymath -d polymath -v ON_ERROR_STOP=1 -f - < $$f || exit 1; \
	done

## migrate — alias for db-migrate
migrate: db-migrate

## ingest-plan — read-only manifest ingestion plan (I1)
ingest-plan:
	$(PY) scripts/ingest.py plan --manifest $(MANIFEST)

## ingest-run — submit required manifest intake work (I1)
ingest-run:
	$(PY) scripts/ingest.py run --manifest $(MANIFEST)

## ingest-status — manifest reconciliation report (I1)
ingest-status:
	$(PY) scripts/ingest.py status --manifest $(MANIFEST)

## dev-api — orchestrator in the foreground
dev-api:
	cd orchestrator && ../$(PY) -m uvicorn orchestrator.main:app --host 127.0.0.1 --port 7200

## dev-control — control plane in the foreground
dev-control:
	$(PY) -m control.main

## dev-worker-intake — intake worker in the foreground
dev-worker-intake:
	$(PY) -m workers.intake_worker

## dev-worker-extract — extract worker in the foreground
dev-worker-extract:
	$(PY) -m workers.extract_worker

## dev-gliner — GLiNER runtime in the foreground (first boot downloads the pinned model)
dev-gliner:
	cd sidecars/gliner_runtime && ../../$(PY) -m uvicorn server:app --host 127.0.0.1 --port 8740

## dev — run api + control + workers + gliner in one tmux session
dev:
	tmux new-session -d -s polymath 'make dev-api' \; \
		split-window 'make dev-control' \; \
		split-window 'make dev-worker-intake' \; \
		split-window 'make dev-worker-extract' \; \
		split-window 'make dev-gliner' \; \
		select-layout tiled \; attach

## test — unit + determinism + contract tests (no live services required)
test:
	$(PY) -m pytest tests

## guards — repository governance checks (preflight, repo guard, wiki worm)
guards:
	$(PY) scripts/agent_preflight.py
	$(PY) scripts/repo_guard.py
	$(PY) scripts/wiki_worm.py --check

## install-launchd — install host-native supervision units
install-launchd:
	@for f in deployment/launchd/*.plist; do \
		dest=$$HOME/Library/LaunchAgents/$$(basename $$f); \
		sed "s|__REPO__|$(shell pwd)|g; s|__PY__|$(shell pwd)/.venv/bin/python|g" $$f > $$dest; \
		launchctl load $$dest && echo "loaded $$dest"; \
	done

## uninstall-launchd — remove supervision units
uninstall-launchd:
	@for f in deployment/launchd/*.plist; do \
		dest=$$HOME/Library/LaunchAgents/$$(basename $$f); \
		launchctl unload $$dest 2>/dev/null || true; rm -f $$dest; echo "removed $$dest"; \
	done

## clean — remove venv and caches
clean:
	rm -rf .venv .pytest_cache **/__pycache__ **/**/__pycache__

## dev-worker-project-qdrant — Qdrant projector in the foreground
dev-worker-project-qdrant:
	$(PY) -m workers.project_qdrant_worker

## dev-worker-project-neo4j — Neo4j projector in the foreground
dev-worker-project-neo4j:
	$(PY) -m workers.project_neo4j_worker

## dev-worker-verify — projection verifier in the foreground
dev-worker-verify:
	$(PY) -m workers.verify_worker

## dev-worker-profile — document retrieval-profile worker in the foreground
dev-worker-profile:
	$(PY) -m workers.profile_worker

## dev-worker-canonicalize — corpus canonicalization worker in the foreground
dev-worker-canonicalize:
	$(PY) -m workers.canonicalize_worker

## dev-worker-project-canonical — canonical graph projector in the foreground
dev-worker-project-canonical:
	$(PY) -m workers.project_canonical_worker

## dev-reranker — G3 reranker sidecar in the foreground (first boot downloads the pinned model)
dev-reranker:
	$(PY) -m uvicorn server:app --host 127.0.0.1 --port 8743 --app-dir sidecars/reranker

## setup-spacy — create the ISOLATED spaCy syntax sidecar venv (never the root venv)
setup-spacy:
	cd sidecars/spacy_runtime && $(UV) venv --python 3.11 .venv && \
		$(UV) pip install --python .venv/bin/python -r requirements.txt -e ../../shared

## dev-spacy — spaCy syntax sidecar in the foreground (own venv, port 8744)
dev-spacy:
	cd sidecars/spacy_runtime && .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8744
