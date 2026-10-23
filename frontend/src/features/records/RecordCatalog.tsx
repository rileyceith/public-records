import { useEffect, useState } from "react";
import { ArrowDownWideNarrow, ArrowUpRight, FileText, Lock, MapPin, Navigation, Plus, Search, SlidersHorizontal } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { AccessLevel, Agency, PublicRecord, RecordStatus, RecordType } from "../../lib/types";

interface RecordCatalogProps {
  canManage: boolean;
  onCreate(): void;
  onSelect(record: PublicRecord): void;
  initialQuery?: string;
}

const STATUSES: RecordStatus[] = ["draft", "pending", "published", "archived", "redacted"];
const ACCESS_LEVELS: AccessLevel[] = ["public", "restricted", "confidential"];

export function RecordCatalog({ canManage, onCreate, onSelect, initialQuery = "" }: RecordCatalogProps) {
  const [query, setQuery] = useState(initialQuery);
  const [search, setSearch] = useState(initialQuery);
  const [recordType, setRecordType] = useState("");
  const [agency, setAgency] = useState("");
  const [status, setStatus] = useState("");
  const [access, setAccess] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [tag, setTag] = useState("");
  const [tagQuery, setTagQuery] = useState("");
  const [near, setNear] = useState<{ lat: number; lng: number } | null>(null);
  const [nearError, setNearError] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [offset, setOffset] = useState(0);
  const [records, setRecords] = useState<PublicRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [recordTypes, setRecordTypes] = useState<RecordType[]>([]);
  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [facetError, setFacetError] = useState("");

  useEffect(() => {
    Promise.all([api.listRecordTypes(), api.listAgencies()])
      .then(([types, list]) => {
        setRecordTypes(types);
        setAgencies(list);
      })
      .catch((cause: unknown) => {
        setFacetError(cause instanceof ApiError ? cause.message : "Unable to load record filters.");
      });
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(search);
      setTag(tagQuery.trim().toLowerCase());
      setOffset(0);
    }, 220);
    return () => window.clearTimeout(timer);
  }, [search, tagQuery]);

  useEffect(() => {
    const prefix = search.trim();
    if (prefix.length < 2) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      api.suggest(prefix, controller.signal)
        .then((result) => setSuggestions(result.suggestions))
        .catch(() => setSuggestions([]));
    }, 200);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [search]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: "25", offset: String(offset) });
    if (query.trim()) params.set("q", query.trim());
    if (recordType) params.set("record_type_id", recordType);
    if (agency) params.set("agency_id", agency);
    if (status) params.set("status", status);
    if (access) params.set("access_level", access);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (tag) params.set("tag", tag);
    if (near) {
      params.set("near_lat", String(near.lat));
      params.set("near_lng", String(near.lng));
      params.set("radius_km", "10");
    }
    setLoading(true);
    setError("");
    api.listRecords(params, controller.signal)
      .then((page) => {
        setRecords(page.items);
        setTotal(page.total);
      })
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError") return;
        setError(cause instanceof ApiError ? cause.message : "Unable to load public records.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [query, recordType, agency, status, access, dateFrom, dateTo, tag, near, offset]);

  function toggleNear() {
    setNearError("");
    if (near) {
      setNear(null);
      setOffset(0);
      return;
    }
    if (!navigator.geolocation) {
      setNearError("Location is not available in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setNear({ lat: position.coords.latitude, lng: position.coords.longitude });
        setOffset(0);
      },
      () => setNearError("Unable to determine your location."),
    );
  }

  function pick<T>(setter: (value: T) => void, value: T) {
    setter(value);
    setOffset(0);
  }

  return (
    <>
      <div className="page-intro">
        <div>
          <p className="eyebrow">Public archive</p>
          <h1>Records, made easier to find.</h1>
          <p className="page-subtitle">Search public documents and browse official record details in one place.</p>
        </div>
        {canManage && <button className="button button-primary" onClick={onCreate}><Plus size={16} /> Add record</button>}
      </div>

      <section className="search-panel" aria-label="Search public records">
        <label className="search-field">
          <Search size={17} aria-hidden="true" />
          <span className="sr-only">Search records</span>
          <input type="search" list="record-suggestions" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search title, number, tag, text…" />
          <datalist id="record-suggestions">{suggestions.map((value) => <option key={value} value={value} />)}</datalist>
          <kbd>Enter</kbd>
        </label>
        <div className="filter-field"><SlidersHorizontal size={16} aria-hidden="true" />
          <label className="sr-only" htmlFor="record-type">Record type</label>
          <select id="record-type" value={recordType} onChange={(event) => pick(setRecordType, event.target.value)}>
            <option value="">All record types</option>
            {recordTypes.map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}
          </select>
        </div>
        <div className="filter-field">
          <label className="sr-only" htmlFor="agency">Agency</label>
          <select id="agency" value={agency} onChange={(event) => pick(setAgency, event.target.value)}>
            <option value="">All agencies</option>
            {agencies.map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}
          </select>
        </div>
        <div className="filter-field">
          <label className="sr-only" htmlFor="status-filter">Status</label>
          <select id="status-filter" value={status} onChange={(event) => pick(setStatus, event.target.value)}>
            <option value="">Any status</option>
            {STATUSES.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
        <div className="filter-field">
          <label className="sr-only" htmlFor="access-filter">Access level</label>
          <select id="access-filter" value={access} onChange={(event) => pick(setAccess, event.target.value)}>
            <option value="">Any access level</option>
            {ACCESS_LEVELS.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
        <div className="filter-field">
          <label className="sr-only" htmlFor="date-from">From date</label>
          <input id="date-from" className="filter-input" type="date" title="From date" value={dateFrom} onChange={(event) => pick(setDateFrom, event.target.value)} />
        </div>
        <div className="filter-field">
          <label className="sr-only" htmlFor="date-to">To date</label>
          <input id="date-to" className="filter-input" type="date" title="To date" value={dateTo} onChange={(event) => pick(setDateTo, event.target.value)} />
        </div>
        <div className="filter-field">
          <label className="sr-only" htmlFor="tag-filter">Tag</label>
          <input id="tag-filter" className="filter-input" placeholder="Tag" maxLength={40} value={tagQuery} onChange={(event) => setTagQuery(event.target.value)} />
        </div>
        <div className="filter-field">
          <button type="button" className={`button button-small ${near ? "button-primary" : "button-secondary"}`} onClick={toggleNear}><Navigation size={14} />{near ? "Near me: on" : "Near me"}</button>
        </div>
      </section>
      {facetError && <p className="form-error" role="status">{facetError}</p>}
      {nearError && <p className="form-error" role="status">{nearError}</p>}

      <div className="results-heading">
        <div><h2>Public records</h2><span>{loading ? "Updating results…" : `${total} ${total === 1 ? "record" : "records"}`}</span></div>
        <span className="results-sort"><ArrowDownWideNarrow size={15} /> Most recent</span>
      </div>

      {error && <div className="state-card state-error" role="alert"><strong>We couldn’t load the records.</strong><span>{error}</span></div>}
      {!error && loading && <div className="state-card">Loading the public archive…</div>}
      {!error && !loading && records.length === 0 && (
        <div className="state-card empty-state">
          <span className="empty-icon"><FileText size={21} /></span>
          <strong>No matching records yet</strong>
          <span>Try another search or adjust your filters.{canManage && " You can also add the first record."}</span>
          {canManage && <button className="button button-secondary" onClick={onCreate}><Plus size={15} /> Add the first record</button>}
        </div>
      )}
      {!error && records.length > 0 && (
        <div className="record-grid">
          {records.map((record) => (
            <article className="record-card" key={record.id}>
              <div className="record-card-top">
                <span className="record-type"><FileText size={14} /> {record.record_type.name}</span>
                <span className="record-date">{record.date_filed ? new Date(`${record.date_filed}T12:00:00`).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "Date not listed"}</span>
              </div>
              <h3>{record.title}</h3>
              <p className="record-description">{record.can_access ? record.summary || "No summary has been added to this record." : "This record is restricted. Request access to see its details."}</p>
              <div className="record-card-meta">
                <span><MapPin size={14} />{record.agency.name}</span>
                <span className="record-reference">{record.record_number}</span>
              </div>
              <div className="record-card-meta">
                <span className={`status-badge status-${record.status}`}>{record.status}</span>
                <span className="role-badge">{record.access_level !== "public" && <Lock size={11} />}{record.access_level}</span>
                {record.tags.slice(0, 3).map((value) => <span className="role-badge" key={value}>#{value}</span>)}
              </div>
              <div className="record-card-bottom">
                <span>{record.can_access ? (record.attachments.length ? `${record.attachments.length} ${record.attachments.length === 1 ? "file" : "files"}` : "No attachments") : "Access required"}</span>
                <button className="text-button" onClick={() => onSelect(record)}>View record <ArrowUpRight size={15} /></button>
              </div>
            </article>
          ))}
        </div>
      )}
      {!error && total > 25 && <nav className="pagination" aria-label="Record pages">
        <button className="button button-secondary button-small" disabled={offset === 0 || loading} onClick={() => setOffset((current) => Math.max(0, current - 25))}>Previous</button>
        <span>Showing {offset + 1}–{Math.min(offset + records.length, total)} of {total}</span>
        <button className="button button-secondary button-small" disabled={offset + 25 >= total || loading} onClick={() => setOffset((current) => current + 25)}>Next</button>
      </nav>}
      <p className="catalog-note">Published public records are visible to everyone. Restricted and confidential records require verified access.</p>
    </>
  );
}
