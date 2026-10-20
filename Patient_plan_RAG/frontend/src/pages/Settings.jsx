import React, { useState } from "react";
import { api } from "../services/api";
import { useAuth } from "../auth/AuthContext";
import { navigate } from "../utils/route";

const clean = (msg) => msg.replace(/^\d+: /, "");

function Section({ title, children, danger = false }) {
  return (
    <section className={`bg-white rounded-lg shadow p-5 ${danger ? "border border-red-200" : ""}`}>
      <h3 className={`font-semibold mb-3 ${danger ? "text-red-700" : ""}`}>{title}</h3>
      {children}
    </section>
  );
}

/** Account settings for individuals. */
export default function Settings() {
  const { user, refresh, signOut } = useAuth();
  const [profile, setProfile] = useState({ fullName: user.full_name || "", phone: user.phone || "" });
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);

  const act = async (fn, done) => {
    setError("");
    setMsg("");
    try {
      await fn();
      if (done) setMsg(done);
    } catch (e) {
      setError(clean(e.message));
    }
  };

  const download = () => act(async () => {
    const data = await api.exportMyData();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "my-patient-plan-data.json";
    a.click();
    URL.revokeObjectURL(url);
  }, "Your data was downloaded.");

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-2xl font-bold">Settings</h2>
      {msg && <p role="status" className="text-sm text-green-700">{msg}</p>}
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

      <Section title="Profile">
        <form onSubmit={(e) => {
          e.preventDefault();
          act(async () => {
            await api.updateProfile(profile.fullName.trim(), profile.phone.trim());
            await refresh();
          }, "Profile saved.");
        }} className="space-y-3 text-sm">
          <label className="block">
            <span className="text-gray-700">Full name</span>
            <input maxLength={120} value={profile.fullName}
                   onChange={(e) => setProfile({ ...profile, fullName: e.target.value })}
                   className="mt-1 w-full border rounded px-3 py-1.5" />
          </label>
          <label className="block">
            <span className="text-gray-700">Phone</span>
            <input maxLength={30} value={profile.phone}
                   onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                   className="mt-1 w-full border rounded px-3 py-1.5" />
          </label>
          <p className="text-gray-500">Email (used to sign in): {user.username}</p>
          <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700">Save profile</button>
        </form>
      </Section>

      <Section title="Security">
        <div className="space-y-3 text-sm">
          <button onClick={() => navigate("/account/password")} className="text-blue-700 hover:underline block">
            Change password
          </button>
          <div>
            <button onClick={() => act(async () => {
              await api.signOutEverywhere();
              await signOut();
            })} className="text-blue-700 hover:underline">
              Sign out on all devices
            </button>
            <p className="text-xs text-gray-500">Ends every session, including this one.</p>
          </div>
        </div>
      </Section>

      <Section title="Your data">
        <p className="text-sm text-gray-600 mb-3">
          Download everything we hold about you: profile, policy details, providers and who you share with.
        </p>
        <button onClick={download} className="border px-4 py-1.5 rounded text-sm hover:bg-gray-50">
          Download my data
        </button>
      </Section>

      <Section title="Delete account" danger>
        <p className="text-sm text-gray-600 mb-3">
          This permanently deletes your profile, your uploaded policies and providers, and stops all
          sharing: hospitals lose access immediately. It can't be undone. A record that the account
          existed and was deleted stays in the security log.
        </p>
        {deleting ? (
          <form onSubmit={(e) => {
            e.preventDefault();
            act(async () => {
              await api.deleteAccount(confirm);
              await signOut().catch(() => {});
            });
          }} className="space-y-2 text-sm">
            <label className="block">
              <span className="text-gray-700">Type your email address to confirm</span>
              <input value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off"
                     className="mt-1 w-full border rounded px-3 py-1.5" />
            </label>
            <button type="submit" disabled={confirm.trim().toLowerCase() !== user.username}
                    className="bg-red-600 text-white px-4 py-1.5 rounded hover:bg-red-700 disabled:opacity-50">
              Permanently delete my account
            </button>{" "}
            <button type="button" onClick={() => { setDeleting(false); setConfirm(""); }}
                    className="text-gray-500 hover:underline">Cancel</button>
          </form>
        ) : (
          <button onClick={() => setDeleting(true)} className="border border-red-300 text-red-700 px-4 py-1.5 rounded text-sm hover:bg-red-50">
            Delete my account…
          </button>
        )}
      </Section>
    </div>
  );
}
