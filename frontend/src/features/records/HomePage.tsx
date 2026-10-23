import { useEffect, useState, type FormEvent } from "react";
import { Building2, FileSearch, KeyRound, Search, ShieldCheck } from "lucide-react";
import { api } from "../../lib/api";
import type { Agency, PublicRecord, RecordType } from "../../lib/types";

interface HomePageProps {
  signedIn: boolean;
  onSearch(query: string): void;
  onBrowse(): void;
  onSelect(record: PublicRecord): void;
  onRegister(): void;
  onSignIn(): void;
}

export function HomePage({ signedIn, onSearch, onBrowse, onSelect, onRegister, onSignIn }: HomePageProps) {
  const [query, setQuery] = useState("");
  const [latest, setLatest] = useState<PublicRecord[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [types, setTypes] = useState<RecordType[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({ limit: "5" });
    Promise.all([api.listRecords(params), api.listAgencies(), api.listRecordTypes()])
      .then(([page, agencyList, typeList]) => {
        if (!active) return;
        setLatest(page.items);
        setTotal(page.total);
        setAgencies(agencyList);
        setTypes(typeList);
      })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    onSearch(query.trim());
  }

  return (
    <div className="home">
      <section className="home-hero">
        <h1>Find and request public records</h1>
        <p>Search published records from {agencies.length || "your"} agencies. Restricted records show their details once an access request is approved.</p>
        <form className="home-search" onSubmit={submit} role="search">
          <Search size={18} />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by title, record number or tag" aria-label="Search records" />
          <button className="button button-primary" type="submit">Search</button>
        </form>
        <div className="home-actions">
          <button className="text-button" onClick={onBrowse}>Browse all records</button>
          {!signedIn && <><button className="text-button" onClick={onRegister}>Create an account</button><button className="text-button" onClick={onSignIn}>Sign in</button></>}
        </div>
      </section>

      {failed && <div className="state-card state-error">The records service is not reachable right now.</div>}

      <section className="home-stats" aria-label="Overview">
        <div><strong>{total ?? "–"}</strong><span>Published records</span></div>
        <div><strong>{agencies.length || "–"}</strong><span>Agencies</span></div>
        <div><strong>{types.length || "–"}</strong><span>Record types</span></div>
      </section>

      <section className="home-steps">
        <article><FileSearch size={20} /><strong>1. Search</strong><span>Filter by type, agency, date, tag or location.</span></article>
        <article><KeyRound size={20} /><strong>2. Request access</strong><span>Verified citizens can ask to view or get a certified copy of restricted records.</span></article>
        <article><ShieldCheck size={20} /><strong>3. Stay accountable</strong><span>Every view, download and change is written to the audit history.</span></article>
      </section>

      <section className="home-latest">
        <h2><Building2 size={16} /> Latest records</h2>
        {latest.length === 0 && !failed && <div className="state-card">No published records yet.</div>}
        <ul>
          {latest.map((record) => (
            <li key={record.id}>
              <button className="home-record" onClick={() => onSelect(record)}>
                <strong>{record.title}</strong>
                <span>{record.record_number} · {record.record_type.name} · {record.agency.name}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
