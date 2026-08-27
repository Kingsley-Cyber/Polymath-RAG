"""Projection store driver factories (Phase F/G).

Drivers live in shared so both workers (writers) and the orchestrator
(reads) open stores without crossing the worker boundary. The stores
remain disposable projections; these factories never touch workflow
state.
"""
from __future__ import annotations

from functools import lru_cache

from neo4j import Driver as Neo4jDriver
from neo4j import GraphDatabase
from qdrant_client import QdrantClient

from polymath_shared.settings import get_settings


class GraphBackendUnavailable(RuntimeError):
    """Typed graph-store failure (FAILURE-TRANSPARENCY-V1).

    A Neo4j exception must NEVER be returned as an empty expansion —
    an outage is not an absence of knowledge. Query routes translate
    this into a 502 graph_backend_unavailable; a valid zero-relationship
    result stays an ordinary empty list."""


def neo4j_driver() -> Neo4jDriver:
    settings = get_settings()
    return GraphDatabase.driver(
        settings.stores.neo4j_uri,
        auth=(settings.stores.neo4j_user, settings.stores.neo4j_password),
    )


def qdrant_client(timeout: float = 60.0) -> QdrantClient:
    return QdrantClient(url=get_settings().stores.qdrant_url, timeout=timeout)
