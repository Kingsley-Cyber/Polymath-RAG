import { useState } from "react";
import { copyText } from "../lib/auth";
import { Icon } from "./icons";

/** ONE-PROFILE (the owner, 2026-09-28: "copy and paste should work") — text to copy with a VISIBLE Copy button: a one-line
 *  command, or (`block`) a longer text in a scrollable preview with the button in its corner. The button says "Copied" for two
 *  seconds; when the browser refuses the clipboard it says how to copy by hand. */
export function CopyField({ value, what, block = false, primary = false }: {
  value: string;
  what: string;
  block?: boolean;
  primary?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  const copy = () => {
    void copyText(value).then((ok) => {
      setFailed(!ok);
      if (ok) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    });
  };
  const label = copied ? "Copied" : `Copy ${what}`;
  const button = (
    <button type="button" className={`btn copyfield__btn${primary ? " btn--primary" : ""}`} aria-label={label} title={label}
            disabled={!value} onClick={copy}>
      <Icon name={copied ? "check" : "copy"} size={15} />
      <span>{copied ? "Copied" : block ? `Copy ${what}` : "Copy"}</span>
    </button>
  );
  const fail = failed && <p className="copyfield__fail" role="alert">The browser blocked copying: select the text and press ⌘C.</p>;
  if (block) {
    return (
      <div className="copyfield copyfield--block">
        {button}
        <pre className="copyfield__text" tabIndex={0} aria-label={what}>{value}</pre>
        {fail}
      </div>
    );
  }
  return (
    <div className="copyfield">
      <code className="copyfield__text" aria-label={what}>{value}</code>
      {button}
      {fail}
    </div>
  );
}
