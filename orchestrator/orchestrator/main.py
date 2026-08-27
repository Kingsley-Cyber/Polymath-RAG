"""Orchestrator entrypoint. AGENTS.md §1.

Role: orchestrator. Stateless. Dumb on purpose. See ADR-0004.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.ask import router as ask_router
from .api.chat import router as chat_router
from .api.evidence import router as evidence_router
from .api.health import router as health_router
from .api.intake import router as intake_router
from .api.retrieve import router as retrieve_router
from .api.ui import router as ui_router
from .registry import load_sidecar_registry


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.sidecars = load_sidecar_registry()
    yield


app = FastAPI(title="Polymath Orchestrator", lifespan=lifespan)

# POLYMATH-UI-V1: dev-server origin only; production serves the built
# UI from this same process (below), so no cross-origin traffic exists.
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# FLEET-AUTOPILOT-V1: record query activity so the supervisor's demand
# policy can keep retrieval models warm while the app is in use and
# park them when it is not. Fire-and-forget; a signal write must never
# fail a query.
@app.middleware("http")
async def _query_activity_signal(request, call_next):
    response = await call_next(request)
    if request.url.path in ("/chat", "/chat/stream", "/retrieve", "/ask",
                            "/fast", "/hybrid", "/graph"):
        try:
            from polymath_shared.db import tx
            with tx() as conn:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS runtime_signals (
                         key text PRIMARY KEY,
                         updated_at timestamptz NOT NULL)""")
                conn.execute(
                    """INSERT INTO runtime_signals VALUES
                         ('last_query', now())
                       ON CONFLICT (key) DO UPDATE
                         SET updated_at = now()""")
        except Exception:
            pass
    return response


app.include_router(health_router)
app.include_router(intake_router)
app.include_router(retrieve_router)
app.include_router(evidence_router)
app.include_router(chat_router)
app.include_router(ask_router)
app.include_router(ui_router)

# Serve the built web UI at /ui when a build exists (single-port product).
from pathlib import Path  # noqa: E402

_UI_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _UI_DIST.exists():
    from fastapi.staticfiles import StaticFiles  # noqa: E402

    from pathlib import Path as _P
    import os as _os
    _GEN_DIR = _P(_os.environ.get(
        "POLYMATH_GENERATED_DIR",
        str(_P.home() / "PolymathRuntime" / "polymath-v4" / "generated")))
    _GEN_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/generated", StaticFiles(directory=str(_GEN_DIR), html=True),
              name="generated")
    app.mount("/ui", StaticFiles(directory=str(_UI_DIST), html=True),
              name="ui")
