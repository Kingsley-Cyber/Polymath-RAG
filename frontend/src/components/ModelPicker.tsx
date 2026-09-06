import { useEffect, useMemo, useRef, useState } from "react";
import type { Synthesizer } from "../types";

/** MODEL-PICKER-V1 (owner request 2026-09-06): the model dropdown grouped into
 * collapsible provider sections, so the list stays short as providers and keys
 * grow. Grouping comes from the catalog rows (provider / provider_label / model),
 * never from parsing ids. The section holding the selected model opens by
 * default; open/closed state per provider is remembered in localStorage. A
 * filter box appears once the catalog is longer than one screen. */

const OPEN_KEY = "pm-model-picker-open";
const FILTER_AT = 12;

type Group = { id: string; label: string; items: Synthesizer[] };

function loadOpen(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(OPEN_KEY) || "{}") as Record<string, boolean>;
  } catch {
    return {};
  }
}

function groupBy(synths: Synthesizer[]): Group[] {
  const map = new Map<string, Group>();
  for (const s of synths) {
    const id = s.provider || s.kind || "other";
    const label = s.provider_label || (s.kind === "ollama" ? "Ollama" : id);
    if (!map.has(id)) map.set(id, { id, label, items: [] });
    map.get(id)!.items.push(s);
  }
  return [...map.values()];
}

export default function ModelPicker({
  synthesizers,
  value,
  onChange,
}: {
  synthesizers: Synthesizer[];
  value: string;
  onChange: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>(loadOpen);
  const rootRef = useRef<HTMLDivElement>(null);
  const filterRef = useRef<HTMLInputElement>(null);

  const current = synthesizers.find((s) => s.id === value) || synthesizers[0];
  const groups = useMemo(() => groupBy(synthesizers), [synthesizers]);
  const q = filter.trim().toLowerCase();
  const shown = useMemo(
    () =>
      q
        ? groups
            .map((g) => ({
              ...g,
              items: g.items.filter(
                (s) =>
                  (s.model || s.label).toLowerCase().includes(q) ||
                  g.label.toLowerCase().includes(q),
              ),
            }))
            .filter((g) => g.items.length > 0)
        : groups,
    [groups, q],
  );

  // close on outside click / Escape
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (open && synthesizers.length > FILTER_AT) filterRef.current?.focus();
    if (!open) setFilter("");
  }, [open, synthesizers.length]);

  const isOpen = (g: Group) =>
    q ? true : expanded[g.id] ?? g.items.some((s) => s.id === current?.id);

  const toggle = (g: Group) => {
    const next = { ...expanded, [g.id]: !isOpen(g) };
    setExpanded(next);
    try {
      localStorage.setItem(OPEN_KEY, JSON.stringify(next));
    } catch {
      /* per-viewer convenience only */
    }
  };

  const pick = (s: Synthesizer) => {
    onChange(s.id);
    setOpen(false);
  };

  return (
    <div className="model-picker" ref={rootRef}>
      <button
        type="button"
        className={`model-picker-btn${open ? " open" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={current?.description || "Choose the chat model"}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="model-picker-provider">{current?.provider_label || current?.kind || "model"}</span>
        <span className="model-picker-model">{current?.model || current?.label || "— none —"}</span>
        <span className="model-picker-caret" aria-hidden>
          {open ? "▴" : "▾"}
        </span>
      </button>
      {open && (
        <div className="model-picker-pop" role="listbox" aria-label="Chat model">
          {synthesizers.length > FILTER_AT && (
            <input
              ref={filterRef}
              className="model-picker-filter"
              placeholder={`Filter ${synthesizers.length} models…`}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          )}
          {shown.length === 0 && <div className="model-picker-empty">No model matches “{filter}”.</div>}
          {shown.map((g) => {
            const openG = isOpen(g);
            const holdsCurrent = g.items.some((s) => s.id === current?.id);
            return (
              <div className={`model-group${openG ? " open" : ""}`} key={g.id}>
                <button
                  type="button"
                  className="model-group-head"
                  aria-expanded={openG}
                  onClick={() => toggle(g)}
                >
                  <span className="model-group-caret" aria-hidden>
                    {openG ? "▾" : "▸"}
                  </span>
                  <span className="model-group-label">{g.label}</span>
                  <span className="model-group-count">
                    {g.items.length}
                    {holdsCurrent && !openG ? " · current" : ""}
                  </span>
                </button>
                {openG && (
                  <div className="model-group-items">
                    {g.items.map((s) => (
                      <button
                        type="button"
                        key={s.id}
                        role="option"
                        aria-selected={s.id === current?.id}
                        className={`model-item${s.id === current?.id ? " selected" : ""}${s.available === false ? " unavailable" : ""}`}
                        title={s.description}
                        onClick={() => pick(s)}
                      >
                        <span className="model-item-name">{s.model || s.label}</span>
                        {s.default && <span className="model-item-tag">default</span>}
                        {s.available === false && <span className="model-item-tag warn">not pulled</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
