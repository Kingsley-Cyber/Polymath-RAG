"""TRUE-CORPUS-DELETE-V1 (2026-11-20): give the disk space of deleted rows back to the machine.

Owner: "I SHOULD BE ABLE TO TRULY DELETE A CORPUS AND IT DOES WHAT ITS SUPPOSE TO DO ON MY MACHINE AND GIVES ME STORAGE."

A Postgres DELETE leaves the row's space inside the table file; the file never shrinks. `VACUUM FULL` writes a compact copy
of the table and then removes the old file, so for a moment the disk holds both: the copy needs free space about the size of
what the table keeps. Measured 2026-11-20: the disk had 9.3 GB free of 460 GB, and Postgres was 20 GB. A full disk stops
Postgres, so a table is compacted only when the disk has room for its estimated copy plus a reserve; otherwise it is skipped
and the result says why. Only the tables a delete removed rows from are compacted.

`VACUUM FULL` locks the table while it runs (reads and writes wait), and it cannot run inside a transaction: this module
opens its own autocommit connection.
"""
from __future__ import annotations

import os
import pathlib
import shutil
from collections.abc import Callable, Mapping

from psycopg import sql

#: free disk the compaction always leaves untouched
RESERVE_BYTES = 2 * 1024 ** 3
#: the copy's estimate is scaled by this margin (row and index overheads the estimate does not see)
COPY_MARGIN = 1.25

_REPO = pathlib.Path(__file__).resolve().parents[2]


def postgres_data_dir() -> pathlib.Path:
    """The host folder that holds the Postgres files (compose bind-mounts ./stores/postgres/data)."""
    return pathlib.Path(os.environ.get("POLYMATH_PG_DATA_DIR") or (_REPO / "stores" / "postgres"))


def _table_exists(conn, table: str) -> bool:
    return conn.execute("SELECT to_regclass(%s)", (f"public.{table}",)).fetchone()[0] is not None


def _total_bytes(conn, table: str) -> int:
    return int(conn.execute("SELECT pg_total_relation_size(%s::regclass)", (f"public.{table}",)).fetchone()[0])


def reclaim(conn, deleted_rows: Mapping[str, int], *, data_dir: pathlib.Path | str | None = None,
            reserve_bytes: int = RESERVE_BYTES,
            free_bytes: Callable[[pathlib.Path], int] | None = None) -> dict:
    """Compact every table in `deleted_rows` (table -> rows the delete removed) that the disk has room for.

    `conn` must be an AUTOCOMMIT connection. Returns {"tables": [...], "freed_bytes", "free_before", "free_after"}; each
    table row says compacted (with bytes before and after) or skipped (with the reason)."""
    folder = pathlib.Path(data_dir) if data_dir else postgres_data_dir()
    free_of = free_bytes or (lambda p: shutil.disk_usage(p).free)
    free_before = free_of(folder)
    rows: list[dict] = []
    candidates = []
    for table, removed in deleted_rows.items():
        if not isinstance(removed, int) or removed <= 0 or not _table_exists(conn, table):
            continue
        candidates.append((table, removed, _total_bytes(conn, table)))
    # largest first: the biggest file frees the most room for the ones after it
    for table, removed, before in sorted(candidates, key=lambda c: (-c[2], c[0])):
        kept_rows = int(conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0])
        kept_fraction = kept_rows / max(1, kept_rows + removed)
        copy_bytes = int(before * kept_fraction * COPY_MARGIN)
        free = free_of(folder)
        row = {"table": table, "rows_deleted": removed, "rows_kept": kept_rows, "bytes_before": before,
               "copy_bytes_estimate": copy_bytes, "free_bytes": free}
        if copy_bytes + reserve_bytes > free:
            row.update(status="skipped", reason=(
                f"not enough free disk: the compact copy needs about {copy_bytes} bytes plus the {reserve_bytes}-byte "
                f"reserve, {free} bytes are free"))
        else:
            conn.execute(sql.SQL("VACUUM (FULL, ANALYZE) {}").format(sql.Identifier(table)))
            after = _total_bytes(conn, table)
            row.update(status="compacted", bytes_after=after, freed_bytes=max(0, before - after))
        rows.append(row)
    return {"tables": rows, "freed_bytes": sum(r.get("freed_bytes", 0) for r in rows),
            "free_before": free_before, "free_after": free_of(folder)}
