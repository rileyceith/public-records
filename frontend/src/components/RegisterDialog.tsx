import { useState, type FormEvent } from "react";
import { UserPlus, X } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";

export function RegisterDialog({ onClose, onSignIn }: { onClose(): void; onSignIn(): void }) {
  const { signIn } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.register({ full_name: fullName, email, password });
      await signIn(email, password);
      onClose();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Unable to create your account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="register-title">
        <div className="dialog-heading">
          <div><p className="eyebrow">Citizen account</p><h2 id="register-title">Create an account</h2></div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close registration"><X size={18} /></button>
        </div>
        <p className="muted">Register to browse records and request access. An administrator verifies your identity before requests are accepted.</p>
        <form onSubmit={(event) => void submit(event)} className="form-stack">
          <label>Full name<input value={fullName} maxLength={120} minLength={2} onChange={(event) => setFullName(event.target.value)} required autoFocus /></label>
          <label>Email address<input type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label>Password<input type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} /><small className="field-help">At least 12 characters.</small></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button-primary" disabled={busy}><UserPlus size={15} />{busy ? "Creating account…" : "Register"}</button>
        </form>
        <p className="setup-hint">Already registered? <button type="button" className="text-button" onClick={onSignIn}>Sign in</button></p>
      </section>
    </div>
  );
}
