import { useEffect, useState, type FormEvent } from "react";
import { Shield, UserPlus, Users } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { Agency, Role, User } from "../../lib/types";

const ROLES: Role[] = ["citizen", "clerk", "admin", "auditor"];

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("citizen");
  const [agencyId, setAgencyId] = useState("");
  const [verified, setVerified] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setUsers(await api.listUsers());
  }

  useEffect(() => {
    refresh().catch((cause: unknown) => {
      setError(cause instanceof ApiError ? cause.message : "Unable to load team accounts.");
    });
    api.listAgencies().then(setAgencies).catch(() => setAgencies([]));
  }, []);

  async function update(user: User, change: Parameters<typeof api.updateUser>[1]) {
    setError("");
    try {
      await api.updateUser(user.id, change);
      await refresh();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Unable to update this account.");
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.createUser({ full_name: fullName, email, password, role, agency_id: agencyId ? Number(agencyId) : null, is_verified: verified });
      setFullName("");
      setEmail("");
      setPassword("");
      setRole("citizen");
      setAgencyId("");
      setVerified(false);
      await refresh();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Unable to create this account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-intro">
        <div><p className="eyebrow">Workspace access</p><h1>People & permissions</h1><p className="page-subtitle">Add staff and choose which administrative tools they can use.</p></div>
      </div>
      <div className="admin-layout">
        <section className="admin-panel">
          <div className="panel-heading"><span className="panel-icon"><UserPlus size={17} /></span><div><h2>Add a teammate</h2><p>Create an account for someone who needs workspace access.</p></div></div>
          <form className="form-stack" onSubmit={submit}>
            <label>Full name<input value={fullName} maxLength={120} onChange={(event) => setFullName(event.target.value)} required minLength={2} /></label>
            <label>Email address<input type="email" autoComplete="off" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            <label>Temporary password<input type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} /><small className="field-help">At least 12 characters. Share it securely and ask the user to change it.</small></label>
            <label>Role<select value={role} onChange={(event) => setRole(event.target.value as Role)}>{ROLES.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
            <label>Agency<select value={agencyId} onChange={(event) => setAgencyId(event.target.value)}><option value="">No agency</option>{agencies.map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}</select><small className="field-help">Clerks must belong to an agency.</small></label>
            <label className="checkbox-label"><input type="checkbox" checked={verified} onChange={(event) => setVerified(event.target.checked)} /> Identity verified</label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button button-primary" disabled={busy}><UserPlus size={15} />{busy ? "Creating account…" : "Create account"}</button>
          </form>
        </section>

        <section className="admin-panel">
          <div className="panel-heading"><span className="panel-icon"><Users size={17} /></span><div><h2>Workspace accounts</h2><p>{users.length} {users.length === 1 ? "account" : "accounts"} · passwords are never displayed</p></div></div>
          {error && users.length === 0 ? <div className="state-inline">{error}</div> : users.length === 0 ? <div className="state-inline">No accounts found.</div> : (
            <ul className="user-list">
              {users.map((user) => <li key={user.id}><span className="avatar">{user.full_name.slice(0, 1).toUpperCase()}</span><span className="user-copy"><strong>{user.full_name}</strong><small>{user.email}{user.is_active ? "" : " · disabled"}</small></span>
                <span className={`role-badge ${user.role === "admin" ? "role-admin" : ""}`}><Shield size={12} />{user.is_verified ? "verified" : "unverified"}</span>
                <span className="inline-actions">
                  <select aria-label={`Role for ${user.full_name}`} value={user.role} onChange={(event) => void update(user, { role: event.target.value as Role })}>{ROLES.map((value) => <option key={value} value={value}>{value}</option>)}</select>
                  <select aria-label={`Agency for ${user.full_name}`} value={user.agency_id ?? ""} onChange={(event) => void update(user, { agency_id: event.target.value ? Number(event.target.value) : null })}><option value="">No agency</option>{agencies.map((value) => <option key={value.id} value={value.id}>{value.code}</option>)}</select>
                  <button className="button button-secondary button-small" onClick={() => void update(user, { is_verified: !user.is_verified })}>{user.is_verified ? "Unverify" : "Verify"}</button>
                  <button className="button button-secondary button-small" onClick={() => void update(user, { is_active: !user.is_active })}>{user.is_active ? "Deactivate" : "Activate"}</button>
                </span></li>)}
            </ul>
          )}
        </section>
      </div>
      <p className="catalog-note">Administrator actions are recorded in the audit history. User passwords are stored as salted hashes.</p>
    </>
  );
}
