"""QDRANT-PERSISTENT-STORAGE-V1 (2026-11-19): every durable store keeps its data in a host folder, as stores/README.md
says ("Every store is bind-mounted, never in-app").

Measured live 2026-11-19: compose.yaml gave Qdrant only its snapshots folder, so its collections lived inside the
container. A fleet restart (`scripts/boot_polymath.sh` runs `docker compose up -d` for the stores) recreated the
containers and every vector collection was lost; Postgres and Neo4j, bind-mounted, kept their data.
"""
from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
#: durable store service -> its data directory inside the container
DURABLE = {"postgres": "/var/lib/postgresql/data", "qdrant": "/qdrant/storage", "neo4j": "/data"}


def _services() -> dict:
    return yaml.safe_load((ROOT / "compose.yaml").read_text())["services"]


def test_every_durable_store_keeps_its_data_in_a_host_folder():
    services = _services()
    for name, target in DURABLE.items():
        mounts = [str(v) for v in services[name].get("volumes") or []]
        bound = [m for m in mounts if m.split(":")[1:2] == [target]]
        assert bound, f"{name}: no host folder is mounted at {target} (mounts: {mounts})"
        assert bound[0].startswith("./stores/"), f"{name}: its data must live under ./stores/ ({bound[0]})"


def test_the_qdrant_data_folder_is_never_committed():
    assert "stores/qdrant/storage/" in (ROOT / ".gitignore").read_text().splitlines()
