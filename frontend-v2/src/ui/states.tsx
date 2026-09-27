import type { ReactNode } from "react";
import { Icon } from "./icons";

/** FRONTEND-REFRESH-V1 §5 — the three states every data view needs, so "still loading", "nothing here" and "failed" never look
 *  alike (problem P4: Files said "0 documents" and "not reachable" while it was still loading). */

export function Skeleton({ rows = 4, label = "Loading…" }: { rows?: number; label?: string }) {
  return (
    <div className="skeleton" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton__row" style={{ width: `${92 - (i % 3) * 14}%` }} />)}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="state">
      <p className="state__title">{title}</p>
      {children && <p className="state__text">{children}</p>}
      {action && <div className="state__action">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <p className="state__title"><Icon name="alert" /> Couldn't load this</p>
      <p className="state__text">{message}</p>
      {onRetry && <div className="state__action"><button type="button" className="btn" onClick={onRetry}>Retry</button></div>}
    </div>
  );
}
