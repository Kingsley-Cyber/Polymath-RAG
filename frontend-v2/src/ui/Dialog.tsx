import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

/** FRONTEND-REFRESH-V1 §5 — a modal built on the native <dialog>: the browser traps focus, Esc closes it, and the page behind
 *  is inert. Replaces window.prompt / confirm / alert. */
export function Dialog({ open, title, onClose, children, actions }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; actions: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    if (open && d && !d.open) {
      if (typeof d.showModal === "function") d.showModal(); else d.setAttribute("open", "");
    }
  }, [open]);
  if (!open) return null;                     // a closed dialog is not in the page at all (no stray text, no stale state)
  return (
    <dialog ref={ref} className="dialog" aria-labelledby={titleId} onCancel={(e) => { e.preventDefault(); onClose(); }}>
      <h2 className="dialog__title" id={titleId}>{title}</h2>
      <div className="dialog__body">{children}</div>
      <div className="dialog__actions">{actions}</div>
    </dialog>
  );
}

/** A destructive action the user confirms by typing its name (the backend requires the same token). */
export function ConfirmByName({ open, title, name, what, action, onConfirm, onClose }: {
  open: boolean; title: string; name: string; what: ReactNode; action: string;
  onConfirm: () => Promise<void> | void; onClose: () => void;
}) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inputId = useId();
  useEffect(() => { if (open) { setTyped(""); setError(""); setBusy(false); } }, [open]);
  const match = typed === name;
  async function confirm() {
    if (!match || busy) return;
    setBusy(true); setError("");
    try { await onConfirm(); onClose(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  return (
    <Dialog open={open} title={title} onClose={onClose} actions={<>
      <button type="button" className="btn" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn--danger-solid" disabled={!match || busy} onClick={() => void confirm()}>
        {busy ? "Deleting…" : action}
      </button>
    </>}>
      <p className="dialog__text">{what}</p>
      <label className="field" htmlFor={inputId}>
        <span className="label">Type <strong className="mono">{name}</strong> to confirm</span>
        <input id={inputId} type="text" value={typed} autoComplete="off" spellCheck={false}
               onChange={(e) => setTyped(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter") void confirm(); }} />
      </label>
      {error && <p className="banner banner--bad">{error}</p>}
    </Dialog>
  );
}

export interface ConfirmOptions { title: string; body: ReactNode; action: string; danger?: boolean }

/** `const [confirm, confirmDialog] = useConfirm()`; render `confirmDialog`, then `if (!(await confirm({…}))) return;`.
 *  The promise answers true only for the action button; Cancel, Esc and the backdrop answer false. */
export function useConfirm(): [(o: ConfirmOptions) => Promise<boolean>, ReactNode] {
  const [pending, setPending] = useState<{ o: ConfirmOptions; resolve: (ok: boolean) => void } | null>(null);
  const confirm = useCallback((o: ConfirmOptions) => new Promise<boolean>((resolve) => setPending({ o, resolve })), []);
  const answer = (ok: boolean) => { pending?.resolve(ok); setPending(null); };
  const element = (
    <Dialog open={!!pending} title={pending?.o.title ?? ""} onClose={() => answer(false)} actions={<>
      <button type="button" className="btn" onClick={() => answer(false)}>Cancel</button>
      <button type="button" className={`btn ${pending?.o.danger ? "btn--danger-solid" : "btn--primary"}`} onClick={() => answer(true)}>
        {pending?.o.action}
      </button>
    </>}>
      <p className="dialog__text">{pending?.o.body}</p>
    </Dialog>
  );
  return [confirm, element];
}
