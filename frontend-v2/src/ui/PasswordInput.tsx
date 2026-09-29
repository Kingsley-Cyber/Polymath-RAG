import { useState } from "react";
import { Icon } from "./icons";

/** ONE-PROFILE — a password field with a Show / Hide eye button (one field is enough when you can see what you typed). */
export function PasswordInput({ id, value, onChange, autoComplete, placeholder, autoFocus }: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const [show, setShow] = useState(false);
  return (
    <span className="pw">
      <input id={id} type={show ? "text" : "password"} className="pw__input" autoComplete={autoComplete} value={value}
             placeholder={placeholder} autoFocus={autoFocus} autoCapitalize="none" autoCorrect="off" spellCheck={false}
             onChange={(e) => onChange(e.target.value)} />
      <button type="button" className="pw__eye" aria-label={show ? "Hide password" : "Show password"} aria-pressed={show}
              title={show ? "Hide password" : "Show password"} onClick={() => setShow((s) => !s)}>
        <Icon name={show ? "eyeOff" : "eye"} size={16} />
      </button>
    </span>
  );
}
