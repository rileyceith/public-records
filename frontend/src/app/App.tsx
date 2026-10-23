import { useEffect, useState } from "react";
import { Archive, BookOpen, ChevronRight, CircleHelp, FileText, Fingerprint, Home, Inbox, LogIn, LogOut, ShieldCheck, UserRound, Users } from "lucide-react";
import { LoginDialog } from "../components/LoginDialog";
import { RegisterDialog } from "../components/RegisterDialog";
import { useAuth } from "../features/auth/AuthContext";
import { AuditPage } from "../features/audit/AuditPage";
import { AccessRequestsPage } from "../features/records/AccessRequestsPage";
import { HomePage } from "../features/records/HomePage";
import { LandingPage } from "../features/records/LandingPage";
import { RecordCatalog } from "../features/records/RecordCatalog";
import { RecordDetail } from "../features/records/RecordDetail";
import { RecordEditor } from "../features/records/RecordEditor";
import { UsersPage } from "../features/users/UsersPage";
import { api, ApiError } from "../lib/api";
import type { PublicRecord, WorkspaceSection } from "../lib/types";

export function App() {
  const { user, isAdmin, isStaff, canAudit, signOut } = useAuth();
  const [section, setSection] = useState<WorkspaceSection>("home");
  const [registerOpen, setRegisterOpen] = useState(false);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [selected, setSelected] = useState<PublicRecord | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<PublicRecord | null>(null);
  const [loginOpen, setLoginOpen] = useState(false);
  const [revision, setRevision] = useState(0);
  const [flash, setFlash] = useState("");
  const [serviceState, setServiceState] = useState<"checking" | "online" | "offline">("checking");
  const canRequest = user?.role === "citizen" || isStaff;
  const roleLabels = { citizen: "Citizen", clerk: "Clerk", admin: "Administrator", auditor: "Auditor" } as const;
  const sectionAllowed =
    section === "home" ||
    section === "records" ||
    (section === "register" && !user) ||
    (section === "requests" && canRequest) ||
    (section === "audit" && canAudit) ||
    (section === "users" && isAdmin);
  const sectionTitle = { home: "Home", records: "Public records", requests: "Access requests", register: "Create account", audit: "Audit history", users: "People & permissions" }[section];

  useEffect(() => {
    setSelected(null);
  }, [user?.id]);

  useEffect(() => {
    let active = true;
    const check = () => {
      api.health()
        .then(() => { if (active) setServiceState("online"); })
        .catch(() => { if (active) setServiceState("offline"); });
    };
    check();
    const timer = window.setInterval(check, 30_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  async function refreshSelected() {
    if (!selected) return;
    setSelected(await api.getRecord(selected.id));
  }

  function editRecord(record: PublicRecord | null) {
    setEditingRecord(record);
    setEditorOpen(true);
  }

  function savedRecord(record: PublicRecord) {
    setEditorOpen(false);
    setSelected(record);
    setRevision((current) => current + 1);
    setSection("records");
  }

  async function deleteRecord() {
    if (!selected) return;
    await api.deleteRecord(selected.id);
    setSelected(null);
    setRevision((current) => current + 1);
  }

  async function logout() {
    let message = "";
    try {
      await signOut();
    } catch (cause) {
      message = cause instanceof ApiError ? cause.message : "Unable to contact the server while signing out.";
    } finally {
      setSelected(null);
      setSection("home");
      setFlash(message);
    }
  }

  function navigate(destination: WorkspaceSection) {
    setSection(destination);
    setSelected(null);
    setCatalogQuery("");
  }

  function searchFromHome(query: string) {
    setCatalogQuery(query);
    setSection("records");
    setSelected(null);
    setRevision((current) => current + 1);
  }

  function openFromHome(record: PublicRecord) {
    setSection("records");
    setSelected(record);
  }

  if (!user) {
    return (
      <>
        <LandingPage onSignIn={() => { setRegisterOpen(false); setLoginOpen(true); }} onRegister={() => { setLoginOpen(false); setRegisterOpen(true); }} />
        {loginOpen && <LoginDialog onClose={() => setLoginOpen(false)} />}
        {registerOpen && <RegisterDialog onClose={() => setRegisterOpen(false)} onSignIn={() => { setRegisterOpen(false); setLoginOpen(true); }} />}
      </>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event) => {         event.preventDefault(); navigate("home"); }}>
          <span className="brand-icon"><Archive size={20} /></span>
          <span className="brand-copy"><strong>Public records</strong><small>Records workspace</small></span>
        </a>
        <div className="sidebar-label">Workspace</div>
        <nav className="primary-nav" aria-label="Main navigation">
                  <button className={`nav-link ${section === "home" ? "active" : ""}`} onClick={() => navigate("home")}><Home size={17} />Home<ChevronRight className="nav-chevron" size={15} /></button>
          <button className={`nav-link ${section === "records" ? "active" : ""}`} onClick={() => navigate("records")}><BookOpen size={17} />Records<ChevronRight className="nav-chevron" size={15} /></button>
          {canRequest && <button className={`nav-link ${section === "requests" ? "active" : ""}`} onClick={() => navigate("requests")}><Inbox size={17} />Access requests<ChevronRight className="nav-chevron" size={15} /></button>}
          {(isAdmin || canAudit) && <span className="sidebar-label sidebar-label-spaced">Administration</span>}
          {isAdmin && <button className={`nav-link ${section === "users" ? "active" : ""}`} onClick={() => navigate("users")}><Users size={17} />People & permissions<ChevronRight className="nav-chevron" size={15} /></button>}
          {canAudit && <button className={`nav-link ${section === "audit" ? "active" : ""}`} onClick={() => navigate("audit")}><Fingerprint size={17} />Audit history<ChevronRight className="nav-chevron" size={15} /></button>}
        </nav>
        <div className="sidebar-bottom">
          <div className="help-card"><span className="help-icon"><CircleHelp size={16} /></span><strong>Need a hand?</strong><span>Explore records or use search to find a reference.</span></div>
          {user ? <>
          <div className="account-card">
            <span className="account-avatar">{user.full_name.slice(0, 1).toUpperCase()}</span>
            <span className="account-copy"><strong>{user.full_name}</strong><small>{user.role === "admin" ? <ShieldCheck size={12} /> : <UserRound size={12} />} {roleLabels[user.role]}{user.role === "citizen" && !user.is_verified ? " (unverified)" : ""}</small></span>
          </div>
          <button className="button button-secondary sign-in-button" onClick={() => void logout()}><LogOut size={16} />Sign out</button>
          </> : <button className="button button-secondary sign-in-button" onClick={() => setLoginOpen(true)}><LogIn size={16} />Sign in</button>}
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar"><div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} /><strong>{selected ? "Record details" : sectionTitle}</strong></div><div className="topbar-right"><span className="service-status" data-state={serviceState} role="status"><i />{serviceState === "checking" ? "Checking API…" : serviceState === "online" ? "API connected" : "API offline"}</span><span className="topbar-user">{user?.full_name ?? "Public access"}</span></div></header>
        <div className="content-area">
          {flash && <div className="notice" role="alert"><span>{flash}</span><button className="text-button" onClick={() => setFlash("")}>Dismiss</button></div>}
          {section === "home" && <HomePage signedIn onSearch={searchFromHome} onBrowse={() => navigate("records")} onSelect={openFromHome} onRegister={() => navigate("records")} onSignIn={() => navigate("records")} />}
          {section === "records" && (selected
            ? <RecordDetail key={`${selected.id}-${user?.id ?? "anon"}`} record={selected} canDelete={isAdmin} onBack={() => setSelected(null)} onEdit={() => editRecord(selected)} onChanged={refreshSelected} onDelete={deleteRecord} />
            : <RecordCatalog key={`${revision}-${user?.id ?? "anon"}`} canManage={isStaff} initialQuery={catalogQuery} onCreate={() => editRecord(null)} onSelect={setSelected} />)}
          {section === "requests" && canRequest && <AccessRequestsPage />}
          {section === "audit" && canAudit && <AuditPage />}
          {section === "users" && isAdmin && <UsersPage />}
          {!sectionAllowed && <div className="state-card state-error">You do not have access to this section.</div>}
        </div>
        <footer className="app-footer"><span><span className="footer-mark"><FileText size={13} /></span>Public Records Workspace</span><span>Private records stay private. Every change is logged.</span></footer>
      </main>
      {loginOpen && <LoginDialog onClose={() => setLoginOpen(false)} />}
      {editorOpen && <RecordEditor key={editingRecord?.id ?? "new"} record={editingRecord} onClose={() => setEditorOpen(false)} onSaved={savedRecord} />}
    </div>
  );
}
