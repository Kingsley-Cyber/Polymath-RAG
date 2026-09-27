import { useEffect, useId, useState } from "react";
import { PUBLIC_MODES, type PublicMode, type Synthesizer } from "../lib/contracts";
import { useComposerSettings } from "../lib/composerSettings";
import { IconButton } from "../ui/icons";
import { ModelPicker } from "./ModelPicker";

/**
 * HEADER-CONTROLS (owner, 2026-09-27: "only deep research should be in the chatbox and reasoning; everything else should
 * be in the header top next to corpus selector"). The chat's Retrieval mode, Model and Corpus Explore switch, in the top
 * bar right after the library while the Chat screen is active. They read and write the per-browser store
 * (lib/composerSettings) that the composer reads when it sends, so a request carries the same fields as before.
 *
 * On a desktop the three sit inline. Below 1100 px (app.css: the shell's tablet and phone widths) they go behind ONE
 * "Chat options" button and open in a panel under the bar: a disclosure (aria-expanded + aria-controls), closed by Escape,
 * a click outside, or the button again. The controls are rendered once; only the CSS moves them.
 */
export function ChatControls({ models, corpusExploreAvailable }: {
  /** The `/synthesizers` catalog (App reads it once). */
  models: Synthesizer[];
  /** CORPUS-EXPLORER-V1: the toggle shows only when the server advertises the capability (its deployment kill switch). */
  corpusExploreAvailable: boolean;
}) {
  const [settings, update] = useComposerSettings();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const modelLabelId = useId();

  // A stored model the catalog no longer offers would send a synthesizer the backend cannot run: back to the default.
  useEffect(() => {
    if (models.length && settings.model && !models.some((s) => (s.id ?? s.name) === settings.model)) update({ model: "" });
  }, [models, settings.model]);

  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent && e.key !== "Escape") return;
      if (e instanceof MouseEvent && (e.target as HTMLElement | null)?.closest(".topbar__chat")) return;
      setOpen(false);
    };
    window.addEventListener("keydown", close);
    window.addEventListener("mousedown", close);
    return () => { window.removeEventListener("keydown", close); window.removeEventListener("mousedown", close); };
  }, [open]);

  return (
    <div className="topbar__chat">
      <IconButton className="topbar__chat-btn" icon="sliders" label="Chat options" aria-expanded={open} aria-controls={panelId}
                  onClick={() => setOpen((o) => !o)} />
      <div id={panelId} className={`topbar__controls${open ? " topbar__controls--open" : ""}`} role="group" aria-label="Chat options">
        <label className="chip-field" title="How the library is searched">
          <span className="label">Retrieval</span>
          <select value={settings.mode} onChange={(e) => update({ mode: e.target.value as PublicMode })}>
            {PUBLIC_MODES.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <div className="chip-field chip-field--model" role="group" aria-labelledby={modelLabelId}>
          <span className="label" id={modelLabelId}>Model</span>
          <ModelPicker synthesizers={models} value={settings.model} onChange={(model) => update({ model })} />
        </div>
        {corpusExploreAvailable && (
          <label className="chip-field chip-field--toggle"
                 title="Bounded, corpus-grounded exploration: activate related concepts from your library and retrieve through a few grounded sub-questions.">
            <input type="checkbox" checked={settings.corpusExplore} onChange={(e) => update({ corpusExplore: e.target.checked })} />
            <span className="label">Corpus Explore</span>
          </label>
        )}
      </div>
    </div>
  );
}
