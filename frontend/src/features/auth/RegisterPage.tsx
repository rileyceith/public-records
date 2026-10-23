import { useState, type FormEvent } from "react";
import { UserPlus } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "./AuthContext";

export function RegisterPage({ onDone }: { onDone(): void }) {
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
      onDone();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Unable to create your account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-intro"><div><p className="eyebrow">Citizen account</p><h1>Create an account</h1><p className="page-subtitle">Register to request access to restricted records. An administrator verifies your identity before requests are accepted.</p></div></div>
      <div className="admin-layout">
        <section className="admin-panel">
          <div className="panel-heading"><span className="panel-icon"><UserPlus size={17} /></span><div><h2>Your details</h2><p>Use an email address you can access.</p></div></div>
          <form className="form-stack" onSubmit={(event) => void submit(event)}>
            <label>Full name<input value={fullName} maxLength={120} minLength={2} onChange={(event) => setFullName(event.target.value)} required /></label>
            <label>Email address<input type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            <label>Password<input type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} /><small className="field-help">At least 12 characters.</small></label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button button-primary" disabled={busy}><UserPlus size={15} />{busy ? "Creating account…" : "Register"}</button>
          </form>
        </section>
      </div>
    </>
  );
}
