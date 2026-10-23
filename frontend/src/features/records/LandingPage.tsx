import { useEffect, useState } from "react";
import { ArrowRight, FileSearch, KeyRound, ShieldCheck } from "lucide-react";
import { api } from "../../lib/api";

interface LandingPageProps {
  onSignIn(): void;
  onRegister(): void;
}

export function LandingPage({ onSignIn, onRegister }: LandingPageProps) {
  const [total, setTotal] = useState<number | null>(null);
  const [agencies, setAgencies] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.listRecords(new URLSearchParams({ limit: "1" })), api.listAgencies()])
      .then(([page, list]) => {
        if (!active) return;
        setTotal(page.total);
        setAgencies(list.length);
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  return (
    <div className="landing">
      <div className="landing-orb landing-orb-sun" aria-hidden="true" />
      <div className="landing-orb landing-orb-stone" aria-hidden="true" />
      <main className="landing-board">
        <section className="landing-card landing-intro">
          <span className="landing-eyebrow">Public records</span>
          <h1>Open records, made simple</h1>
          <p>Search published documents from every agency, request access to restricted files and follow every change in an audit trail.</p>
          <button className="landing-pill landing-pill-orange" onClick={onSignIn}>Sign in to continue<ArrowRight size={16} /></button>
        </section>

        <section className="landing-card landing-stat">
          <strong>{total ?? "–"}</strong>
          <span>published records across {agencies ?? "–"} agencies</span>
          <i className="landing-gem" aria-hidden="true"><ShieldCheck size={18} /></i>
        </section>

        <section className="landing-card landing-feature">
          <h2>How it works</h2>
          <ul>
            <li><FileSearch size={16} />Search by type, agency, date, tag or place</li>
            <li><KeyRound size={16} />Verified citizens request restricted access</li>
            <li><ShieldCheck size={16} />Every view and download is logged</li>
          </ul>
        </section>

        <section className="landing-card landing-search">
          <h2>Your account</h2>
          <p>An account is required to enter the app.</p>
          <button className="landing-pill landing-pill-orange wide" onClick={onSignIn}>Sign in</button>
          <div className="landing-links">
            <button onClick={onRegister}>Create account</button>
          </div>
        </section>

        <section className="landing-card landing-cta">
          <h2>New here?</h2>
          <p>Register in a minute, then browse and request access to records.</p>
          <button className="landing-pill landing-pill-ghost" onClick={onRegister}>Create an account</button>
        </section>
      </main>
    </div>
  );
}
