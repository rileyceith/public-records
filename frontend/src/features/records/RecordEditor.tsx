import { useEffect, useState, type FormEvent } from "react";
import { X } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { Agency, PublicRecord, RecordInput, RecordType } from "../../lib/types";
import { useAuth } from "../auth/AuthContext";

export function RecordEditor({
  record,
  onClose,
  onSaved,
}: {
  record: PublicRecord | null;
  onClose(): void;
  onSaved(record: PublicRecord): void;
}) {
  const { user, isAdmin } = useAuth();
  const [types, setTypes] = useState<RecordType[]>([]);
  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [tagText, setTagText] = useState(record?.tags.join(", ") ?? "");
  const [form, setForm] = useState<RecordInput>({
    record_number: record?.record_number ?? "",
    title: record?.title ?? "",
    summary: record?.summary ?? "",
    record_type_id: record?.record_type.id ?? 0,
    agency_id: record?.agency.id ?? user?.agency_id ?? 0,
    access_level: record?.access_level ?? null,
    date_of_event: record?.date_of_event ?? null,
    date_filed: record?.date_filed ?? null,
    language: record?.language ?? "en",
    location_address: record?.location_address ?? "",
    latitude: record?.latitude ?? null,
    longitude: record?.longitude ?? null,
    tags: record?.tags ?? [],
    retention_until: record?.retention_until ?? null,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.listRecordTypes(), api.listAgencies()])
      .then(([typeList, agencyList]) => {
        setTypes(typeList);
        setAgencies(agencyList);
        setForm((current) => ({
          ...current,
          record_type_id: current.record_type_id || typeList[0]?.id || 0,
          agency_id: current.agency_id || agencyList[0]?.id || 0,
        }));
      })
      .catch((cause: unknown) => {
        setError(cause instanceof ApiError ? cause.message : "Unable to load record types and agencies.");
      });
  }, []);

  function update<K extends keyof RecordInput>(field: K, value: RecordInput[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function coordinate(value: string): number | null {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const payload: RecordInput = {
      ...form,
      tags: tagText.split(",").map((value) => value.trim()).filter(Boolean),
    };
    try {
      const result = record
        ? await api.updateRecord(record.id, payload)
        : await api.createRecord(payload);
      onSaved(result);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Unable to save this record.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="dialog-card dialog-wide" role="dialog" aria-modal="true" aria-labelledby="record-editor-title">
        <div className="dialog-heading">
          <div><p className="eyebrow">Records administration</p><h2 id="record-editor-title">{record ? "Edit record" : "Add a record"}</h2></div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close record editor"><X size={18} /></button>
        </div>
        <form onSubmit={submit} className="form-stack">
          <div className="form-grid">
            <label className="form-span">Record title<input maxLength={180} value={form.title} onChange={(event) => update("title", event.target.value)} required minLength={3} /></label>
            <label>Record type<select value={form.record_type_id} onChange={(event) => update("record_type_id", Number(event.target.value))} required>{types.map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>
            <label>Record number<input maxLength={80} value={form.record_number} onChange={(event) => update("record_number", event.target.value)} required /></label>
            <label>Agency<select value={form.agency_id} onChange={(event) => update("agency_id", Number(event.target.value))} disabled={!isAdmin && Boolean(user?.agency_id)} required>{agencies.map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>
            <label>Access level<select value={form.access_level ?? ""} onChange={(event) => update("access_level", (event.target.value || null) as RecordInput["access_level"])}><option value="">Record type default</option><option value="public">Public</option><option value="restricted">Restricted</option><option value="confidential">Confidential</option></select></label>
            <label>Date filed<input type="date" value={form.date_filed ?? ""} onChange={(event) => update("date_filed", event.target.value || null)} /></label>
            <label>Date of event<input type="date" value={form.date_of_event ?? ""} onChange={(event) => update("date_of_event", event.target.value || null)} /></label>
            <label>Retain until<input type="date" value={form.retention_until ?? ""} onChange={(event) => update("retention_until", event.target.value || null)} /></label>
            <label>Language<input maxLength={16} minLength={2} value={form.language} onChange={(event) => update("language", event.target.value)} required /></label>
            <label className="form-span">Location address<input maxLength={255} value={form.location_address} onChange={(event) => update("location_address", event.target.value)} /></label>
            <label>Latitude<input type="number" step="any" min={-90} max={90} value={form.latitude ?? ""} onChange={(event) => update("latitude", coordinate(event.target.value))} /></label>
            <label>Longitude<input type="number" step="any" min={-180} max={180} value={form.longitude ?? ""} onChange={(event) => update("longitude", coordinate(event.target.value))} /></label>
            <label className="form-span">Tags<input value={tagText} placeholder="Comma separated, e.g. zoning, permit" onChange={(event) => setTagText(event.target.value)} /></label>
            <label className="form-span">Summary<textarea rows={4} maxLength={5000} value={form.summary} onChange={(event) => update("summary", event.target.value)} /></label>
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="dialog-actions"><button className="button button-secondary" type="button" onClick={onClose}>Cancel</button><button className="button button-primary" disabled={busy}>{busy ? "Saving…" : record ? "Save changes" : "Create record"}</button></div>
        </form>
      </section>
    </div>
  );
}
