import React from "react";
import { useHashPath, navigate } from "./utils/route";
import ErrorBoundary from "./components/ErrorBoundary";
import { useAuth } from "./auth/AuthContext";
import SignIn from "./pages/SignIn";
import ChangePassword from "./pages/ChangePassword";
import Admin from "./pages/Admin";
import Dashboard from "./pages/Dashboard";
import PolicyViewer from "./pages/PolicyViewer";
import ChatAssistant from "./pages/ChatAssistant";
import CoverageAssessment from "./pages/CoverageAssessment";
import PriorAuth from "./pages/PriorAuth";
import Patients from "./pages/Patients";
import SharedWithUs from "./pages/SharedWithUs";
import Staff from "./pages/Staff";
import MyAccount from "./pages/MyAccount";
import SharingAccess from "./pages/SharingAccess";
import Settings from "./pages/Settings";

const ASK = [
  { path: "/chat", label: "Ask a Question", icon: "💬" },
  { path: "/coverage", label: "Coverage Check", icon: "🔍" },
  { path: "/auth", label: "Prior Auth", icon: "📝" },
];

/** Navigation for each kind of account. */
const NAV = {
  individual: [
    { path: "/", label: "My Account", icon: "🏠" },
    { path: "/policies", label: "My Policies", icon: "📋" },
    { path: "/chat", label: "Ask a Question", icon: "💬" },
    { path: "/coverage", label: "Coverage Check", icon: "🔍" },
    { path: "/sharing", label: "Sharing & Access", icon: "🔐" },
    { path: "/settings", label: "Settings", icon: "⚙️" },
  ],
  hospital_staff: [
    { path: "/patients", label: "Patients", icon: "🏥" },
    { path: "/shared", label: "Shared with us", icon: "📨" },
    ...ASK,
  ],
  hospital_admin: [
    { path: "/patients", label: "Patients", icon: "🏥" },
    { path: "/shared", label: "Shared with us", icon: "📨" },
    ...ASK,
    { path: "/staff", label: "Staff", icon: "👥" },
  ],
  platform_admin: [
    { path: "/", label: "Dashboard", icon: "📊" },
    { path: "/admin", label: "Hospitals & Accounts", icon: "🏛️" },
    { path: "/policies", label: "Sample Policies", icon: "📋" },
    { path: "/chat", label: "Ask a Question", icon: "💬" },
  ],
};

const ACCOUNT_LABELS = {
  individual: "Personal account",
  hospital_staff: "Hospital staff",
  hospital_admin: "Hospital admin",
  platform_admin: "Platform admin",
};

export function Disclaimer() {
  return (
    <div className="bg-amber-50 border-l-4 border-amber-400 p-3 text-sm text-amber-800">
      <strong>Demonstration Only:</strong> This tool provides AI-generated
      interpretations of synthetic insurance policy language. It does not
      constitute coverage determinations, legal advice, or guarantees of
      benefits. Always verify with your actual plan administrator.
    </div>
  );
}

function UserMenu({ user, onSignOut }) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="opacity-90" title={ACCOUNT_LABELS[user.role]}>
        {user.username}
      </span>
      <button onClick={() => navigate("/account/password")} className="hover:underline opacity-90">
        Change password
      </button>
      <button onClick={onSignOut} className="bg-white/15 hover:bg-white/25 px-3 py-1 rounded">
        Sign out
      </button>
    </div>
  );
}

function Shell({ children }) {
  return (
    <div className="min-h-screen flex flex-col">
      <Disclaimer />
      {children}
      <footer className="text-center text-xs text-gray-400 py-4">
        Patient Plan RAG v0.1.0 — Synthetic data only — Not for clinical use
      </footer>
    </div>
  );
}

export default function App() {
  const path = useHashPath();
  const { user, loading, signOut } = useAuth();

  if (loading) return <Shell><p className="text-center text-gray-500 mt-16">Loading...</p></Shell>;
  if (!user) return <Shell><SignIn /></Shell>;
  if (user.must_change_password) return <Shell><ChangePassword forced /></Shell>;

  const nav = NAV[user.role] || [];
  const allowed = (prefix) => nav.some((n) => n.path === prefix);
  const denied = <p role="alert">Not permitted.</p>;

  const page = (() => {
    if (path.startsWith("/policies")) return <PolicyViewer />;
    if (path.startsWith("/chat")) return <ChatAssistant />;
    if (path === "/coverage") return <CoverageAssessment />;
    if (path === "/auth") return allowed("/auth") ? <PriorAuth /> : denied;
    if (path === "/sharing") return allowed("/sharing") ? <SharingAccess /> : denied;
    if (path === "/settings") return allowed("/settings") ? <Settings /> : denied;
    if (path === "/account/password") return <ChangePassword />;
    if (path.startsWith("/patients")) return allowed("/patients") ? <Patients /> : denied;
    if (path === "/shared") return allowed("/shared") ? <SharedWithUs /> : denied;
    if (path === "/staff") return allowed("/staff") ? <Staff /> : denied;
    if (path === "/admin") return allowed("/admin") ? <Admin /> : denied;
    // hospital accounts start on their patient list; individuals on their account
    if (!allowed("/")) return <Patients />;
    if (user.role === "individual") return <MyAccount />;
    return <Dashboard />;
  })();

  return (
    <div className="min-h-screen flex flex-col">
      <Disclaimer />
      <header className="bg-brand-800 text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
          <h1
            className="text-lg font-bold cursor-pointer"
            onClick={() => navigate("/")}
          >
            Patient Plan RAG
          </h1>
          <nav className="flex gap-1">
            {nav.map((n) => (
              <button
                key={n.path}
                onClick={() => navigate(n.path)}
                className={`px-3 py-1.5 rounded text-sm transition ${
                  path === n.path || (n.path !== "/" && path.startsWith(n.path))
                    ? "bg-white/20 font-semibold"
                    : "hover:bg-white/10"
                }`}
              >
                {n.icon} {n.label}
              </button>
            ))}
          </nav>
          <UserMenu user={user} onSignOut={signOut} />
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        {/* keyed on path: navigating away from a crashed page resets it */}
        <ErrorBoundary key={path} onHome={() => navigate("/")}>
          {page}
        </ErrorBoundary>
      </main>
      <footer className="text-center text-xs text-gray-400 py-4">
        Patient Plan RAG v0.1.0 — Synthetic data only — Not for clinical use
      </footer>
    </div>
  );
}
