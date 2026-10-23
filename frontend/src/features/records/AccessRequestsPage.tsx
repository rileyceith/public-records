import { useCallback, useEffect, useState } from "react";
import { Check, Inbox, X } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { AccessRequest } from "../../lib/types";
import { useAuth } from "../auth/AuthContext";

export function AccessRequestsPage() {
  const { isStaff } = useAuth();
  const [items, setItems] = useState<AccessRequest[]>([]);
  const [filter, setFilter] = useState("");
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setItems(await api.listAccessRequests(filter || undefined));
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    setError("");
    refresh()
      .catch((cause: unknown) => setError(cause instanceof ApiError ? cause.message : "Unable to load access requests."))
      .finally(() => setLoading(false));
  }, [refresh]);

  async function act(id: string, action: () => Promise<unknown>, failure: string) {
    setBusyId(id);
    setError("");
    try {
      await action();
      await refresh();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : failure);
    } finally {
      setBusyId("");
    }
  }

  return (
    <>
      <div className="page-intro">
        <div><p className="eyebrow">Record access</p><h1>Access requests</h1><p className="page-subtitle">{isStaff ? "Review requests for restricted records." : "Track the requests you have made for restricted records."}</p></div>
        <div className="filter-field">
          <label className="sr-only" htmlFor="request-status">Status</label>
          <select id="request-status" value={filter} onChange={(event) => setFilter(event.target.value)}>
            <option value="">All requests</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="denied">Denied</option>
          </select>
        </div>
      </div>
      {error && <div className="state-card state-error" role="alert">{error}</div>}
      {!error && loading && <div className="state-card">Loading requests…</div>}
      {!error && !loading && items.length === 0 && <div className="state-card empty-state"><span className="empty-icon"><Inbox size={21} /></span><strong>No requests found</strong><span>Requests for restricted records will appear here.</span></div>}
      {!loading && items.length > 0 && (
        <ul className="user-list request-list">
          {items.map((item) => (
            <li key={item.id}>
              <span className="user-copy">
                <strong>{item.record_number} · {item.record_title}</strong>
                <small>{item.request_type === "certified_copy" ? "Certified copy" : "View"} · {item.requester_email} · {new Date(item.requested_at).toLocaleString()}</small>
                <small>Purpose: {item.purpose}</small>
                {Number(item.fee_amount) > 0 && <small>Fee {Number(item.fee_amount).toFixed(2)} · {item.payment_status}</small>}
                {item.decision_reason && <small>Decision: {item.decision_reason}</small>}
              </span>
              <span className={`status-badge status-request-${item.status}`}>{item.status}</span>
              {isStaff && item.status === "pending" && (
                <span className="inline-actions">
                  <input className="reason-input" placeholder="Reason" maxLength={2000} value={reasons[item.id] ?? ""} onChange={(event) => setReasons({ ...reasons, [item.id]: event.target.value })} aria-label="Decision reason" />
                  <button className="button button-primary button-small" disabled={busyId === item.id} onClick={() => void act(item.id, () => api.approveAccessRequest(item.id, reasons[item.id] ?? ""), "Unable to approve this request.")}><Check size={14} /> Approve</button>
                  <button className="button button-danger button-small" disabled={busyId === item.id || !(reasons[item.id] ?? "").trim()} title="A reason is required to deny" onClick={() => void act(item.id, () => api.denyAccessRequest(item.id, reasons[item.id] ?? ""), "Unable to deny this request.")}><X size={14} /> Deny</button>
                </span>
              )}
              {isStaff && item.status === "approved" && item.payment_status !== "paid" && (
                <button className="button button-secondary button-small" disabled={busyId === item.id} onClick={() => void act(item.id, () => api.markAccessRequestPaid(item.id), "Unable to record the payment.")}>Mark paid</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
