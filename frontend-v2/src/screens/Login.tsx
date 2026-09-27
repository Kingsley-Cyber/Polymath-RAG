import { useState, type FormEvent } from "react";
import { Icon } from "../ui/icons";
import { ApiError } from "../lib/api";
import { auth, type Me } from "../lib/auth";

/** FRIENDS-ACCESS-V1 — the sign-in screen (rag.kingsleylab.xyz). The server decides; this only asks. INVITE-SIGNUP: the same
 *  page offers "Create your account" (username, password, the owner's invite code); a success is a signed-in friend. */
export function Login({ onSignedIn }: { onSignedIn: (me: Me) => void }) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSignedIn(await auth.login(username.trim(), password));
    } catch (err) {
      const code = err instanceof ApiError ? err.code : null;
      setError(
        code === "BAD_LOGIN" ? "Wrong username or password."
          : code === "TOO_MANY_ATTEMPTS" ? "Too many failed sign-ins. Wait 15 minutes and try again."
          : code === "LOGIN_NOT_CONFIGURED" ? "Sign-in is not set up on the server yet."
          : `Sign-in failed: ${err instanceof ApiError ? err.detailMessage : String(err)}`,
      );
    } finally {
      setBusy(false);
      setPassword("");
    }
  }

  if (mode === "signup") return <CreateAccount onSignedIn={onSignedIn} onBack={() => setMode("signin")} />;
  return (
    <div className="auth">
      <form className="card auth__card stack" onSubmit={(e) => void submit(e)}>
        <div className="auth__mark" aria-hidden="true"><Icon name="research" size={22} /></div>
        <h1 className="screen__title">Polymath</h1>
        <p className="screen__sub">Sign in to continue.</p>
        {error && <div className="banner banner--bad" role="alert">{error}</div>}
        <label className="field">
          <span className="label">Username</span>
          <input type="text" autoComplete="username" autoFocus value={username}
                 onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label className="field">
          <span className="label">Password</span>
          <input type="password" autoComplete="current-password" value={password}
                 onChange={(e) => setPassword(e.target.value)} />
        </label>
        <button className="btn btn--primary" type="submit" disabled={busy || !username.trim() || !password}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <button className="linklike" type="button" onClick={() => setMode("signup")}>New here? Create your account</button>
      </form>
    </div>
  );
}

/** The backend's refusal, in the app's words (the codes /auth/register answers). */
function signUpProblem(err: unknown): string {
  const code = err instanceof ApiError ? err.code : null;
  switch (code) {
    case "INVITE_INVALID": return "The invite code is wrong.";
    case "USERNAME_TAKEN": return "That username is taken.";
    case "USERNAME_INVALID": return "Usernames are 2–32 characters: lowercase letters, digits, - or _.";
    case "WEAK_PASSWORD": return "Choose a password.";
    case "INVITES_OFF": return "Sign-ups are not open yet. Ask King for an invite code.";
    case "TOO_MANY_ATTEMPTS": return "Too many failed tries. Wait 15 minutes and try again.";
    case "LOGIN_NOT_CONFIGURED": return "Sign-in is not set up on the server yet.";
    default: return `Could not create the account: ${err instanceof ApiError ? err.detailMessage : String(err)}`;
  }
}

/** INVITE-SIGNUP — Create your account: username, password (twice), the invite code King sent. On success the person is
 *  signed in as a friend at once: they chose the password, so there is no first-password step. */
function CreateAccount({ onSignedIn, onBack }: { onSignedIn: (me: Me) => void; onBack: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mismatch = again.length > 0 && again !== password;
  const ready = username.trim().length > 0 && password.length > 0 && again === password && code.trim().length > 0;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSignedIn(await auth.register(username.trim(), password, code.trim()));
    } catch (err) {
      setError(signUpProblem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <form className="card auth__card stack" onSubmit={(e) => void submit(e)}>
        <div className="auth__mark" aria-hidden="true"><Icon name="research" size={22} /></div>
        <h1 className="screen__title">Polymath</h1>
        <p className="screen__sub">Create your account with the invite code King sent you.</p>
        {error && <div className="banner banner--bad" role="alert">{error}</div>}
        <label className="field">
          <span className="label">Username</span>
          <input type="text" autoComplete="username" autoCapitalize="none" spellCheck={false} autoFocus value={username}
                 onChange={(e) => setUsername(e.target.value)} />
          <span className="faint">Lowercase letters, digits, - or _ (2–32 characters).</span>
        </label>
        <label className="field">
          <span className="label">Password</span>
          <input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <label className="field">
          <span className="label">Type it again</span>
          <input type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
        </label>
        {mismatch && <div className="faint">The two passwords differ.</div>}
        <label className="field">
          <span className="label">Invite code</span>
          <input type="text" autoComplete="off" autoCapitalize="none" spellCheck={false} value={code}
                 onChange={(e) => setCode(e.target.value)} />
        </label>
        <button className="btn btn--primary" type="submit" disabled={busy || !ready}>
          {busy ? "Creating…" : "Create account"}
        </button>
        <button className="linklike" type="button" onClick={onBack}>Back to sign in</button>
      </form>
    </div>
  );
}

/** Change my password. `forced`: the first sign-in with a password the owner generated (nothing else opens until done). */
export function ChangePassword({ me, forced, onChanged, onSignOut }: {
  me: Me;
  forced?: boolean;
  onChanged: (me: Me) => void;
  onSignOut?: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const mismatch = again.length > 0 && again !== next;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const updated = await auth.changePassword(current, next);
      setDone(true);
      setCurrent(""); setNext(""); setAgain("");
      onChanged(updated);
    } catch (err) {
      const code = err instanceof ApiError ? err.code : null;
      setError(code === "BAD_PASSWORD" ? "The current password is wrong."
        : err instanceof ApiError ? err.detailMessage : String(err));
    } finally {
      setBusy(false);
    }
  }

  const form = (
    <form className="stack" onSubmit={(e) => void submit(e)}>
      {forced && (
        <div className="banner banner--info">
          Welcome, {me.display_name}. Choose your own password to continue.
        </div>
      )}
      {error && <div className="banner banner--bad" role="alert">{error}</div>}
      {done && !forced && <div className="banner banner--ok">Password changed. Other devices are signed out.</div>}
      <label className="field">
        <span className="label">{forced ? "The password you were given" : "Current password"}</span>
        <input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
      </label>
      <label className="field">
        <span className="label">New password</span>
        <input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
      </label>
      <label className="field">
        <span className="label">New password again</span>
        <input type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
      </label>
      {mismatch && (
        <div className="faint">The two new passwords differ.</div>
      )}
      <div className="row">
        <button className="btn btn--primary" type="submit"
                disabled={busy || !current || next.length === 0 || next !== again}>
          {busy ? "Saving…" : "Change password"}
        </button>
        {forced && onSignOut && <button className="btn" type="button" onClick={onSignOut}>Sign out</button>}
      </div>
    </form>
  );

  if (!forced) return form;
  return (
    <div className="auth">
      <div className="card auth__card stack">
        <h1 className="screen__title">Polymath</h1>
        {form}
      </div>
    </div>
  );
}
