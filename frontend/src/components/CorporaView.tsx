import { useCallback, useEffect, useState } from "react";
import { fetchCorpora, renameCorpus } from "../api";
import type { Corpus } from "../types";

/** Corpus manager: every corpus in the store, with single and bulk
 * deletion through the verified DELETE cascade. Deletion is guarded by
 * a typed confirmation naming the survivors, mirroring the owner rule
 * that a purge must state what it keeps. */
export default function CorporaView({
  onChanged,
}: {
  onChanged?: () => void;
}) {
  const [corpora, setCorpora] = useState<Corpus[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);

  const refresh = useCallback(async () => {
    try {
      setCorpora(await fetchCorpora(true));
    } catch {
      setCorpora([]);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 15_000);
    return () => clearInterval(t);
  }, [refresh]);

  const toggle = (id: string) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  const deleteOne = async (id: string): Promise<boolean> => {
    const r = await fetch(
      `/corpora/${encodeURIComponent(id)}?confirm=${encodeURIComponent(id)}`,
      { method: "DELETE" },
    );
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      const why = body?.detail?.error_code === "runs_in_flight"
        ? "extraction in flight — retry after ingestion completes"
        : body?.detail?.message ?? r.status;
      setLog((l) => [`✗ ${id}: ${why}`, ...l].slice(0, 20));
      window.alert(`Delete failed: ${why}`);
      return false;
    }
    setLog((l) => [`✓ deleted ${id}`, ...l].slice(0, 20));
    return true;
  };

  const renameOne = async (c: Corpus) => {
    const typed = window.prompt(
      `Rename corpus (display name only — the id ${c.corpus_id} is immutable):`,
      c.name || c.corpus_id,
    );
    if (typed === null) return;
    try {
      const r = await renameCorpus(c.corpus_id, typed);
      setLog((l) => [`✓ renamed ${c.corpus_id} → "${r.name}"`, ...l].slice(0, 20));
    } catch (e) {
      setLog((l) => [`✗ rename ${c.corpus_id}: ${e}`, ...l].slice(0, 20));
    }
    await refresh();
    onChanged?.();
  };

  const confirmAndDelete = async (ids: string[]) => {
    if (ids.length === 0) return;
    const survivors = corpora
      .map((c) => c.corpus_id)
      .filter((id) => !ids.includes(id));
    const typed = window.prompt(
      `Delete ${ids.length} corpus${ids.length === 1 ? "" : "es"} permanently?\n\n` +
        `DELETING:\n${ids.slice(0, 12).join("\n")}${ids.length > 12 ? `\n…and ${ids.length - 12} more` : ""}\n\n` +
        `KEEPING: ${survivors.length ? survivors.slice(0, 8).join(", ") : "NOTHING — the store will be empty"}\n\n` +
        `Type DELETE to proceed:`,
    );
    if (typed !== "DELETE") return;
    for (const id of ids) {
      setBusy(id);
      await deleteOne(id);
    }
    setBusy(null);
    setSelected(new Set());
    await refresh();
    onChanged?.();
  };

  return (
    <div className="files">
      <div className="files-inner">
        <div className="panel">
          <h3>Corpora ({corpora.length})</h3>
          <div className="readiness" style={{ marginBottom: 10 }}>
            A corpus is the isolation unit: its own vectors, graph
            slice, documents and query scope. Deleting one removes it
            everywhere — there is no undo.
          </div>
          <table className="doc-table">
            <thead>
              <tr>
                <th></th>
                <th>Corpus</th>
                <th>Purpose</th>
                <th>Docs</th>
                <th>Queryable</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {corpora.map((c) => (
                <tr key={c.corpus_id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(c.corpus_id)}
                      onChange={() => toggle(c.corpus_id)}
                    />
                  </td>
                  <td>
                    <b>{c.name || c.corpus_id}</b>
                    {c.name && c.name !== c.corpus_id && (
                      <div className="mono" style={{ opacity: 0.6 }}>
                        {c.corpus_id}
                      </div>
                    )}
                    {busy === c.corpus_id && (
                      <span className="mono"> deleting…</span>
                    )}
                  </td>
                  <td className="mono">{c.purpose}</td>
                  <td>{c.documents}</td>
                  <td>
                    <span
                      className={`status-pill ${
                        c.query_enabled ? "st-query_ready" : "st-reconciling"
                      }`}
                    >
                      {c.query_enabled ? "enabled" : "not enabled"}
                    </span>
                  </td>
                  <td>
                    <button
                      className="chunk-chip"
                      onClick={() => renameOne(c)}
                    >
                      ✎ rename
                    </button>{" "}
                    <button
                      className="chunk-chip"
                      onClick={() => confirmAndDelete([c.corpus_id])}
                    >
                      ✕ delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {selected.size > 0 && (
          <div className="panel danger">
            <h3>Bulk delete</h3>
            <div className="readiness" style={{ marginBottom: 10 }}>
              {selected.size} selected. The confirmation will name what
              is kept before anything is removed.
            </div>
            <button
              className="btn-danger"
              onClick={() => confirmAndDelete([...selected])}
            >
              Delete {selected.size} selected
            </button>{" "}
            <button
              className="chunk-chip"
              onClick={() =>
                setSelected(
                  new Set(corpora.map((c) => c.corpus_id)),
                )
              }
            >
              select all
            </button>{" "}
            <button className="chunk-chip" onClick={() => setSelected(new Set())}>
              clear
            </button>
          </div>
        )}

        {log.length > 0 && (
          <div className="panel">
            <h3>Recent deletions</h3>
            {log.map((line, i) => (
              <div key={i} className="chunk-row mono">
                {line}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
