import { useState, type FormEvent } from "react";
import { ArrowLeft, CalendarDays, Download, FileText, Lock, MapPin, Paperclip, Pencil, ScanText, Trash2, Upload, UserPlus, X } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import type { PartyInput, PartyRole, PartyType, PublicRecord, RequestType } from "../../lib/types";

const EMPTY_PARTY: PartyInput = { full_name: "", party_type: "person", id_number: "", address: "", role: "owner" };

export function RecordDetail({
  record,
  canDelete,
  onBack,
  onEdit,
  onChanged,
  onDelete,
}: {
  record: PublicRecord;
  canDelete: boolean;
  onBack(): void;
  onEdit(): void;
  onChanged(): Promise<void>;
  onDelete(): Promise<void>;
}) {
  const { user, isVerifiedCitizen } = useAuth();
  const canManage = record.can_edit;
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [party, setParty] = useState<PartyInput>(EMPTY_PARTY);
  const [requestType, setRequestType] = useState<RequestType>("view");
  const [purpose, setPurpose] = useState("");

  async function run(action: () => Promise<unknown>, success: string, failure: string) {
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await action();
      setMessage(success);
      await onChanged();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : failure);
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File | undefined) {
    if (!file) return;
    await run(() => api.uploadAttachment(record.id, file), "File uploaded.", "Unable to upload this file.");
  }

  async function transition(action: "submit" | "publish" | "archive") {
    await run(() => api.recordAction(record.id, action), `Record ${action === "submit" ? "submitted for review" : action === "publish" ? "published" : "archived"}.`, `Unable to ${action} this record.`);
  }

  async function redact() {
    if (!window.confirm("Redact the summary, location and parties of this record? This cannot be undone.")) return;
    await run(() => api.redactRecord(record.id, ["summary", "location_address", "parties"], record.attachments.map((item) => item.id)), "Record redacted.", "Unable to redact this record.");
  }

  async function download(id: string) {
    const attachment = record.attachments.find((item) => item.id === id);
    if (!attachment) return;
    setError("");
    try {
      await api.downloadAttachment(attachment);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Unable to download this file.");
    }
  }

  async function removeAttachment(id: string) {
    if (!window.confirm("Delete this attachment? This cannot be undone.")) return;
    await run(() => api.deleteAttachment(id), "Attachment deleted.", "Unable to delete this attachment.");
  }

  async function ocr(id: string) {
    await run(() => api.runOcr(id), "Text recognition finished.", "Unable to run OCR on this file.");
  }

  async function addParty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: PartyInput = { ...party, id_number: party.id_number?.trim() || null };
    await run(async () => {
      await api.addParty(record.id, payload);
      setParty(EMPTY_PARTY);
    }, "Party added.", "Unable to add this party.");
  }

  async function removeParty(linkId: number) {
    if (!window.confirm("Remove this party from the record?")) return;
    await run(() => api.removeParty(record.id, linkId), "Party removed.", "Unable to remove this party.");
  }

  async function requestAccess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await api.createAccessRequest({ record_id: record.id, request_type: requestType, purpose });
      setPurpose("");
    }, "Access request sent. You can follow it under Access requests.", "Unable to send your request.");
  }

  async function removeRecord() {
    if (!window.confirm(`Delete “${record.title}” and its attachments? This cannot be undone.`)) return;
    setBusy(true);
    setError("");
    try {
      await onDelete();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Unable to delete this record.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="detail-page">
      <button className="back-button" onClick={onBack}><ArrowLeft size={16} /> All records</button>
      <article className="detail-card">
        <div className="detail-actions">
          <span><span className={`status-badge status-${record.status}`}>{record.status}</span> <span className="role-badge">{record.access_level !== "public" && <Lock size={11} />}{record.access_level}</span></span>
          {canManage && <div className="inline-actions">
            {record.status === "draft" && <button className="button button-secondary button-small" onClick={() => void transition("submit")} disabled={busy}>Submit</button>}
            {record.status !== "published" && record.status !== "redacted" && <button className="button button-primary button-small" onClick={() => void transition("publish")} disabled={busy}>Publish</button>}
            {record.status !== "archived" && <button className="button button-secondary button-small" onClick={() => void transition("archive")} disabled={busy}>Archive</button>}
            {record.status !== "archived" && <button className="button button-secondary button-small" onClick={() => void redact()} disabled={busy}>Redact</button>}
            <button className="button button-secondary button-small" onClick={onEdit}><Pencil size={14} /> Edit</button>
            {canDelete && <button className="button button-danger button-small" onClick={removeRecord} disabled={busy}><Trash2 size={14} /> Delete</button>}
          </div>}
        </div>
        <p className="eyebrow">{record.record_type.name} <span aria-hidden="true">·</span> {record.record_number} <span aria-hidden="true">·</span> v{record.version}</p>
        <h1>{record.title}</h1>
        {record.can_access
          ? <p className="detail-description">{record.summary || "No summary has been added to this record."}</p>
          : <p className="detail-description">Details of this record are restricted.</p>}
        <div className="detail-meta">
          <span><MapPin size={16} />{record.agency.name} ({record.agency.code})</span>
          {record.can_access && record.location_address && <span><MapPin size={16} />{record.location_address}</span>}
          <span><CalendarDays size={16} />Filed {record.date_filed ? new Date(`${record.date_filed}T12:00:00`).toLocaleDateString(undefined, { dateStyle: "long" }) : "date not listed"}</span>
          {record.date_of_event && <span><CalendarDays size={16} />Event {new Date(`${record.date_of_event}T12:00:00`).toLocaleDateString(undefined, { dateStyle: "long" })}</span>}
          {record.date_published && <span><CalendarDays size={16} />Published {new Date(record.date_published).toLocaleDateString()}</span>}
          <span><FileText size={16} />Updated {new Date(record.last_modified).toLocaleDateString()} · {record.language.toUpperCase()}</span>
        </div>
        {record.tags.length > 0 && <div className="tag-list">{record.tags.map((value) => <span className="role-badge" key={value}>#{value}</span>)}</div>}
        {message && <p className="form-success" role="status">{message}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </article>

      {!record.can_access && (
        <section className="attachments-section restricted-notice">
          <div className="section-title"><div><p className="eyebrow">Restricted record</p><h2><Lock size={16} /> Access is required</h2></div></div>
          {!user && <p className="supporting-note">Sign in with a verified citizen account to request access to this record.</p>}
          {user && user.role !== "citizen" && <p className="supporting-note">Your role does not grant access to this record.</p>}
          {user?.role === "citizen" && !isVerifiedCitizen && <p className="supporting-note">Your identity must be verified before you can request restricted records. Contact an administrator.</p>}
          {isVerifiedCitizen && (
            <form className="form-stack" onSubmit={(event) => void requestAccess(event)}>
              <label>Request type<select value={requestType} onChange={(event) => setRequestType(event.target.value as RequestType)}><option value="view">View the record</option><option value="certified_copy">Certified copy (fee may apply)</option></select></label>
              <label>Purpose<textarea rows={3} minLength={5} maxLength={2000} required value={purpose} onChange={(event) => setPurpose(event.target.value)} placeholder="Why do you need this record?" /></label>
              <button className="button button-primary" disabled={busy}>{busy ? "Sending…" : "Request access"}</button>
            </form>
          )}
        </section>
      )}

      {record.can_access && (
      <section className="attachments-section">
        <div className="section-title"><div><p className="eyebrow">Supporting documents</p><h2>Attachments <span className="count-chip">{record.attachments.length}</span></h2></div>
          {canManage && <label className={`button button-secondary button-small upload-button ${busy ? "is-disabled" : ""}`}><Upload size={15} />{busy ? "Working…" : "Upload file"}<input type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,.csv" disabled={busy} onChange={(event) => { void upload(event.target.files?.[0]); event.currentTarget.value = ""; }} /></label>}
        </div>
        <p className="supporting-note">PDF, image, text, and CSV files up to 10 MB.</p>
        {record.attachments.length === 0 ? <div className="attachment-empty"><Paperclip size={18} /><span>No supporting files are attached to this record.</span></div> : (
          <ul className="attachment-list">
            {record.attachments.map((attachment) => (
              <li key={attachment.id}>
                <span className="file-icon"><FileText size={17} /></span>
                <span className="file-copy"><strong>{attachment.original_name}</strong><small>{(attachment.size_bytes / 1024).toFixed(0)} KB{attachment.page_count ? ` · ${attachment.page_count} pages` : ""} · Added {new Date(attachment.created_at).toLocaleDateString()}{attachment.is_redacted ? " · Redacted" : ""}<br />SHA-256 <span className="monospace">{attachment.checksum_sha256.slice(0, 16) || "n/a"}</span></small></span>
                <button className="icon-button" onClick={() => void download(attachment.id)} aria-label={`Download ${attachment.original_name}`}><Download size={16} /></button>
                {canManage && <button className="icon-button" onClick={() => void ocr(attachment.id)} disabled={busy} title="Run OCR" aria-label={`Run OCR on ${attachment.original_name}`}><ScanText size={16} /></button>}
                {canManage && <button className="icon-button icon-danger" onClick={() => void removeAttachment(attachment.id)} aria-label={`Delete ${attachment.original_name}`}><Trash2 size={16} /></button>}
              </li>
            ))}
          </ul>
        )}
      </section>
      )}

      {record.can_access && (
      <section className="attachments-section">
        <div className="section-title"><div><p className="eyebrow">People and organisations</p><h2>Parties <span className="count-chip">{record.parties.length}</span></h2></div></div>
        {record.parties.length === 0 ? <div className="attachment-empty"><UserPlus size={18} /><span>No parties are linked to this record.</span></div> : (
          <ul className="attachment-list">
            {record.parties.map((link) => (
              <li key={link.id}>
                <span className="file-icon"><UserPlus size={17} /></span>
                <span className="file-copy"><strong>{link.party.full_name}</strong><small>{link.role} · {link.party.party_type}{link.party.address ? ` · ${link.party.address}` : ""}</small></span>
                {canManage && <button className="icon-button icon-danger" onClick={() => void removeParty(link.id)} disabled={busy} aria-label={`Remove ${link.party.full_name}`}><X size={16} /></button>}
              </li>
            ))}
          </ul>
        )}
        {canManage && (
          <form className="form-stack" onSubmit={(event) => void addParty(event)}>
            <div className="form-grid">
              <label>Full name<input required minLength={2} maxLength={160} value={party.full_name} onChange={(event) => setParty({ ...party, full_name: event.target.value })} /></label>
              <label>Role<select value={party.role} onChange={(event) => setParty({ ...party, role: event.target.value as PartyRole })}><option value="owner">Owner</option><option value="applicant">Applicant</option><option value="witness">Witness</option><option value="official">Official</option></select></label>
              <label>Type<select value={party.party_type} onChange={(event) => setParty({ ...party, party_type: event.target.value as PartyType })}><option value="person">Person</option><option value="company">Company</option><option value="agency">Agency</option></select></label>
              <label>ID number<input autoComplete="off" maxLength={64} value={party.id_number ?? ""} onChange={(event) => setParty({ ...party, id_number: event.target.value })} /><small className="field-help">Hashed on receipt and never shown.</small></label>
              <label className="form-span">Address<input maxLength={255} value={party.address} onChange={(event) => setParty({ ...party, address: event.target.value })} /></label>
            </div>
            <button className="button button-secondary button-small" disabled={busy}><UserPlus size={14} /> Add party</button>
          </form>
        )}
      </section>
      )}
    </section>
  );
}
