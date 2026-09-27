import { useState } from "react";
import { copyText } from "../lib/auth";
import { Icon } from "./icons";

/** A secret shown once (an API key, a first password) or a long prompt, with the same hover copy button the chat's answers have
 *  (`icon-btn icon-btn--sm`, the check fades after two seconds). The button is visible on hover or keyboard focus, and always on a
 *  touch screen. `what` names the thing in the button's label ("Copy key"). */
export function Secret({ value, what, block = false, rows = 10 }: { value: string; what: string; block?: boolean; rows?: number }) {
  const [copied, setCopied] = useState(false);
  const copy = () => { void copyText(value).then((ok) => { if (ok) { setCopied(true); setTimeout(() => setCopied(false), 2000); } }); };
  const label = copied ? "Copied" : `Copy ${what}`;
  return (
    <div className={`secret${block ? " secret--block" : ""}`}>
      {block ? <textarea className="mono settings__prompt" readOnly rows={rows} value={value} aria-label={what} />
             : <code className="mono settings__secret">{value}</code>}
      <button type="button" className="icon-btn icon-btn--sm secret__copy" aria-label={label} title={label} onClick={copy}>
        <Icon name={copied ? "check" : "copy"} size={15} />
      </button>
    </div>
  );
}
