import { useEffect, useState } from "react";

export interface Async<T> { data: T | null; error: string | null; loading: boolean }

/** Minimal fetch-on-mount hook with abort. Deps decide when it refetches. */
export function useAsync<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[]): Async<T> {
  const [state, setState] = useState<Async<T>>({ data: null, error: null, loading: true });
  useEffect(() => {
    const ac = new AbortController();
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn(ac.signal)
      .then((d) => { if (live) setState({ data: d, error: null, loading: false }); })
      .catch((e: unknown) => {
        if (!live || ac.signal.aborted) return;
        setState({ data: null, error: e instanceof Error ? e.message : String(e), loading: false });
      });
    return () => { live = false; ac.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
