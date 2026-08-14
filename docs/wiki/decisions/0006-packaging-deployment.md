---
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: accepted
---

# ADR-0006: Packaging and deployment boundary

Status: accepted
Date: 2026-08-13

## Context

Phase B admits production code into the four declared owners. Something
must make the packages installable, the venv reproducible, and the host
processes supervised. v3.3 buried deployment decisions in an 881-line
compose file (ISSUES_REPORT §4.5).

## Decision

1. A root `pyproject.toml` is the uv workspace; the four packages
   (`polymath-shared`, `polymath-workers`, `polymath-orchestrator`,
   `polymath-control`) are its members with editable installs.
2. Docker Compose carries ONLY the four data stores (ADR-0003 unchanged).
   Every application process — API, control, workers, GLiNER runtime —
   is host-native and supervised by launchd via
   `deployment/launchd/*.plist` (systemd units remain for Linux under
   `control/systemd/`).
3. The `Makefile` is the operator surface: `make setup`, `make db-up`,
   `make db-migrate`, `make dev-*`, `make test`, `make guards`,
   `make install-launchd`.
4. All non-secret settings are typed (`shared/polymath_shared/settings.py`);
   `.env` holds secrets only.

## Consequences

- Clean-clone startup is: `make setup && cp .env.example .env && make db-up && make dev`.
- Runtime logs go to `var/log/` (gitignored).
- A change to the deployment topology requires a refactor entry + a
  clean-clone deployment proof (AGENTS.md §6).
