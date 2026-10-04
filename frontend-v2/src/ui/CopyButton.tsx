import { useEffect, useRef, useState } from "react";
import { copyText } from "../lib/auth";
import { Icon } from "./icons";

/** COPY-ON-HOVER-V1 (the owner, 2026-10-04: "there should be an input and output simple button that shows up when I hover
 *  with mouse to simply copy"): one small copy button for a chat message — the question (input) and the answer (output).
 *  The stylesheet hides it until the pointer is over the message (`.copy-btn--hover`); it is always shown on a touch screen
 *  (no hover), when it has keyboard focus, and for the two seconds after a copy ("Copied" with a check). */
export function CopyButton({ text, label, className = "" }: { text: string; label: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current != null) window.clearTimeout(timer.current); }, []);
  const words = copied ? "Copied" : label;
  return (
    <button type="button" className={`icon-btn icon-btn--sm copy-btn copy-btn--hover${copied ? " copy-btn--done" : ""} ${className}`.trim()}
            aria-label={words} title={words}
            onClick={() => {
              void copyText(text).then((ok) => {
                if (!ok) return;
                setCopied(true);
                if (timer.current != null) window.clearTimeout(timer.current);
                timer.current = window.setTimeout(() => setCopied(false), 2000);
              });
            }}>
      <Icon name={copied ? "check" : "copy"} size={15} />
    </button>
  );
}
