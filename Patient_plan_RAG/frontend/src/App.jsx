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

const NAV = [
  { path: "/", label: "Dashboard", icon: "📊" },
  { path: "/policies", label: "Policies", icon: "📋" },
  { path: "/chat", label: "Ask a Question", icon: "💬" },
  { path: "/coverage", label: "Coverage Check", icon: "🔍" },
  { path: "/auth", label: "Prior Auth", icon: "📝" },
];

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
      <span className="opacity-90" title={user.role === "admin" ? "Staff account" : "Member account"}>
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

  const isAdmin = user.role === "admin";
  const nav = isAdmin ? [...NAV, { path: "/admin", label: "Admin", icon: "👥" }] : NAV;

  const page = (() => {
    if (path.startsWith("/policies")) return <PolicyViewer />;
    if (path === "/chat") return <ChatAssistant />;
    if (path === "/coverage") return <CoverageAssessment />;
    if (path === "/auth") return <PriorAuth />;
    if (path === "/account/password") return <ChangePassword />;
    if (path === "/admin") return isAdmin ? <Admin /> : <p role="alert">Not permitted.</p>;
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
