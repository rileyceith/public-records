import { useEffect, useState } from "react";
import { Activity, Search } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { AuditEvent } from "../../lib/types";

function describeEvent(event: AuditEvent): string {
  const title = event.details.title;
  const filename = event.details.filename;
  const label = typeof title === "string" ? `“${title}”` : typeof filename === "string" ? filename : event.entity_id;
  return `${event.action} ${event.entity_type} · ${label}`;
}

export function AuditPage() {
  const [query, setQuery] = useState("");
  const [recordId, setRecordId] = useState("");
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: "50" });
    if (query.trim()) params.set("q", query.trim());
    if (recordId.trim()) params.set("record_id", recordId.trim());
    setLoading(true);
    setError("");
    api.listAuditEvents(params, controller.signal)
      .then((page) => {
        setEvents(page.items);
        setTotal(page.total);
      })
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError") return;
        setError(cause instanceof ApiError ? cause.message : "Unable to load audit history.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [query, recordId]);

  return (
    <>
      <div className="page-intro"><div><p className="eyebrow">Accountability</p><h1>Audit history</h1><p className="page-subtitle">A chronological log of record, account, and document changes.</p></div><span className="activity-total"><Activity size={15} />{total} events</span></div>
      <label className="search-field audit-search"><Search size={17} /><span className="sr-only">Search audit history</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter by action, record, or account…" /></label>
      <label className="search-field audit-search"><Search size={17} /><span className="sr-only">Filter by record ID</span><input type="search" maxLength={36} value={recordId} onChange={(event) => setRecordId(event.target.value)} placeholder="Filter by record ID…" /></label>
      {error && <div className="state-card state-error" role="alert">{error}</div>}
      {!error && loading && <div className="state-card">Loading audit history…</div>}
      {!error && !loading && events.length === 0 && <div className="state-card empty-state"><span className="empty-icon"><Activity size={21} /></span><strong>No activity found</strong><span>Changes made in this workspace will appear here.</span></div>}
      {!error && !loading && events.length > 0 && (
        <div className="audit-table-wrap">
          <table className="audit-table">
            <thead><tr><th scope="col">Action</th><th scope="col">User</th><th scope="col">IP address</th><th scope="col">Date and time</th><th scope="col">Event ID</th></tr></thead>
            <tbody>{events.map((event) => <tr key={event.id}>
              <td><span className={`action-dot action-${event.action}`} />{describeEvent(event)}</td>
              <td>{event.actor_email || "System"}</td>
              <td className="monospace">{event.ip_address || "—"}</td>
              <td>{new Date(event.created_at).toLocaleString()}</td>
              <td className="monospace">{event.id}</td>
            </tr>)}</tbody>
          </table>
        </div>
      )}
    </>
  );
}
