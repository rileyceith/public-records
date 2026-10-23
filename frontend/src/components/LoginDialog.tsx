import { useState, type FormEvent } from "react";
import { X } from "lucide-react";
import { ApiError } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";

export function LoginDialog({ onClose }: { onClose(): void }) {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signIn(email, password);
      onClose();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Unable to sign in right now.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="login-title">
        <div className="dialog-heading">
          <div>          <p className="eyebrow">Account access</p><h2 id="login-title">Welcome back</h2></div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close sign-in"><X size={18} /></button>
        </div>
                  <p className="muted">Sign in to manage records, request access, or view the audit history.</p>
        <form onSubmit={submit} className="form-stack">
          <label>Email address<input autoComplete="username" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoFocus /></label>
          <label>Password<input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button-primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
        <p className="setup-hint">First time here? Create an administrator from the backend setup command in the README.</p>
      </section>
    </div>
  );
}
