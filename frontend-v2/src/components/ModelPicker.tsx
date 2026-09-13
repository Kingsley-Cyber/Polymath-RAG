import { useEffect, useMemo, useRef, useState } from "react";
import type { Synthesizer } from "../lib/contracts";

/**
 * MODEL-PICKER-V2 (owner request 2026-09-12: "style of model selections" — the
 * legacy /ui grouped picker, ported to V2).
 *
 * A flat `<select>` of every synthesizer is unreadable once the catalog passes a
 * couple of dozen entries (it is currently 24). This groups by PROVIDER using the
 * catalog's own `provider` / `provider_label` / `model` fields — never by parsing
 * ids — collapses each provider section, opens the one holding the current
 * selection, and shows a filter box once the catalog is long. Open/closed state
 * per provider persists in localStorage.
 */

const OPEN_KEY = "polymath-v2.model-picker.open";
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

function idOf(s: Synthesizer): string {
  return s.id ?? s.name ?? "";
}

export function ModelPicker({
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

  const groups = useMemo(() => groupBy(synthesizers), [synthesizers]);
  const current = synthesizers.find((s) => idOf(s) === value);
  const q = filter.trim().toLowerCase();

  const shown = useMemo(
    () =>
      q
        ? groups
            .map((g) => ({
              ...g,
              items: g.items.filter(
                (s) =>
                  (s.model || s.label || idOf(s)).toLowerCase().includes(q) ||
                  g.label.toLowerCase().includes(q),
              ),
            }))
            .filter((g) => g.items.length > 0)
        : groups,
    [groups, q],
  );

  useEffect(() => {
    localStorage.setItem(OPEN_KEY, JSON.stringify(expanded));
  }, [expanded]);

  // close on outside click / Escape
  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // the group holding the current selection starts open
  const currentGroup = current ? current.provider || current.kind || "other" : null;
  function isExpanded(gid: string): boolean {
    return expanded[gid] ?? (gid === currentGroup);
  }

  function pick(id: string) {
    onChange(id);
    setOpen(false);
    setFilter("");
  }

  return (
    <div className="mp" ref={rootRef}>
      <button
        type="button"
        className="mp__button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {current ? (
          <span>
            <span className="mp__provider">{current.provider_label || current.kind}</span>{" "}
            <span className="mp__model">{current.model || idOf(current)}</span>
          </span>
        ) : (
          <span className="mp__model">backend default</span>
        )}
        <span aria-hidden="true" className="faint">▾</span>
      </button>

      {open && (
        <div className="mp__menu" role="listbox">
          {synthesizers.length >= FILTER_AT && (
            <input
              className="mp__filter"
              placeholder="Filter models…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              autoFocus
            />
          )}

          <button
            type="button"
            className="mp__item"
            aria-selected={value === ""}
            onClick={() => pick("")}
          >
            backend default
          </button>

          {shown.map((g) => (
            <div key={g.id}>
              <button
                type="button"
                className="mp__group"
                onClick={() => setExpanded((x) => ({ ...x, [g.id]: !isExpanded(g.id) }))}
              >
                {isExpanded(g.id) || q ? "▾" : "▸"} {g.label} ({g.items.length})
              </button>
              {(isExpanded(g.id) || q) &&
                g.items.map((s) => {
                  const id = idOf(s);
                  return (
                    <button
                      key={id}
                      type="button"
                      className="mp__item"
                      role="option"
                      aria-selected={id === value}
                      title={s.description}
                      onClick={() => pick(id)}
                    >
                      <span>{s.model || s.label || id}</span>
                      {s.default && <span className="faint">default</span>}
                    </button>
                  );
                })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
