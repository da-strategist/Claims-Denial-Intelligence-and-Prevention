import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { navigate } from "../utils/route";

const KINDS = ["doctor", "hospital", "clinic", "pharmacy", "other"];
const clean = (msg) => msg.replace(/^\d+: /, "");
const fmt = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString() : "");

function Card({ title, action, children }) {
  return (
    <section className="bg-white rounded-lg shadow p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function Insurance({ groups }) {
  if (groups.length === 0)
    return (
      <p className="text-sm text-gray-500">
        No policies yet.{" "}
        <button onClick={() => navigate("/policies")} className="text-blue-700 hover:underline">
          Upload your insurance policy
        </button>{" "}
        to see your plans here.
      </p>
    );
  return (
    <div className="space-y-4">
      {groups.map((g) => (
        <div key={g.insurer}>
          <p className="text-sm font-medium text-gray-700 mb-1">{g.insurer}</p>
          <ul className="space-y-1">
            {g.plans.map((p) => (
              <li key={p.document_id} className="text-sm flex flex-wrap items-center gap-2">
                <button onClick={() => navigate(`/policies/${p.document_id}`)} className="text-blue-700 hover:underline">
                  {p.name}
                </button>
                {p.plan_id && <span className="text-gray-500">· {p.plan_id}</span>}
                {(p.effective_date || p.expiration_date) && (
                  <span className="text-gray-500">· {fmt(p.effective_date)} – {fmt(p.expiration_date)}</span>
                )}
                {p.expired && (
                  <span className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded text-xs">Ended</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

const EMPTY = { name: "", kind: "doctor", phone: "", notes: "" };

function Providers({ providers, hospitals, onChange }) {
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  const act = async (fn) => {
    setError("");
    try {
      await fn();
      setForm(EMPTY);
      setEditing(null);
      setAdding(false);
      onChange();
    } catch (e) {
      setError(clean(e.message));
    }
  };

  const fields = (
    <div className="flex flex-wrap gap-2 items-end text-sm">
      <input aria-label="Provider name" placeholder="Name" required maxLength={120} value={form.name}
             onChange={(e) => setForm({ ...form, name: e.target.value })} className="border rounded px-2 py-1" />
      <select aria-label="Provider type" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}
              className="border rounded px-2 py-1 capitalize">
        {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
      </select>
      <input aria-label="Provider phone" placeholder="Phone" maxLength={30} value={form.phone}
             onChange={(e) => setForm({ ...form, phone: e.target.value })} className="border rounded px-2 py-1 w-32" />
      <input aria-label="Provider notes" placeholder="Notes" maxLength={500} value={form.notes}
             onChange={(e) => setForm({ ...form, notes: e.target.value })} className="border rounded px-2 py-1" />
    </div>
  );

  return (
    <>
      {hospitals.length > 0 && (
        <p className="text-sm mb-2">
          <span className="text-gray-500">Hospitals you share policies with: </span>
          {hospitals.map((h) => h.org_name).join(", ")}
        </p>
      )}
      {providers.length === 0 && !adding && (
        <p className="text-sm text-gray-500 mb-2">Add the doctors, clinics and pharmacies you use, for quick reference.</p>
      )}
      <ul className="space-y-2 text-sm mb-3">
        {providers.map((p) => (
          <li key={p.provider_id}>
            {editing === p.provider_id ? (
              <form onSubmit={(e) => { e.preventDefault(); act(() => api.updateProvider(p.provider_id, form)); }}
                    className="space-y-2">
                {fields}
                <button type="submit" className="text-blue-700 hover:underline">Save</button>{" "}
                <button type="button" onClick={() => setEditing(null)} className="text-gray-500 hover:underline">Cancel</button>
              </form>
            ) : (
              <div className="flex flex-wrap gap-2 items-center">
                <strong>{p.name}</strong>
                <span className="text-gray-500 capitalize">{p.kind}</span>
                {p.phone && <span className="text-gray-500">· {p.phone}</span>}
                {p.notes && <span className="text-gray-500">· {p.notes}</span>}
                <button onClick={() => { setEditing(p.provider_id); setForm({ name: p.name, kind: p.kind, phone: p.phone, notes: p.notes }); }}
                        className="text-blue-700 hover:underline text-xs">Edit</button>
                <button onClick={() => act(() => api.deleteProvider(p.provider_id))}
                        className="text-red-700 hover:underline text-xs">Remove</button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {adding ? (
        <form onSubmit={(e) => { e.preventDefault(); act(() => api.addProvider(form)); }} className="space-y-2">
          {fields}
          <button type="submit" className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700">Add provider</button>{" "}
          <button type="button" onClick={() => { setAdding(false); setForm(EMPTY); }} className="text-sm text-gray-500 hover:underline">Cancel</button>
        </form>
      ) : (
        editing === null && (
          <button onClick={() => { setAdding(true); setForm(EMPTY); }} className="text-sm text-blue-700 hover:underline">
            + Add a provider
          </button>
        )
      )}
      {error && <p role="alert" className="text-sm text-red-600 mt-2">{error}</p>}
    </>
  );
}

/** An individual's home page. */
export default function MyAccount() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const load = () => api.overview().then(setData).catch((e) => setError(clean(e.message)));
  useEffect(() => { load(); }, []);

  if (error) return <p role="alert" className="text-red-600 text-sm">Couldn't load your account: {error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;

  const { profile, insurance, providers, sharing, policy_count } = data;
  const sharedWith = sharing.length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">{profile.full_name ? `Hello, ${profile.full_name}` : "My account"}</h2>
          <p className="text-sm text-gray-500">
            {profile.username}
            {profile.phone && <> · {profile.phone}</>}
            {!profile.full_name && (
              <> · <button onClick={() => navigate("/settings")} className="text-blue-700 hover:underline">add your name</button></>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => navigate("/policies")} className="border px-4 py-1.5 rounded text-sm hover:bg-gray-50">
            Upload a policy
          </button>
          <button onClick={() => navigate("/chat")} disabled={policy_count === 0}
                  className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50">
            Ask about my coverage
          </button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="My insurance">
          <Insurance groups={insurance} />
        </Card>
        <Card title="My providers">
          <Providers providers={providers} hospitals={sharing} onChange={load} />
        </Card>
      </div>

      <Card
        title="Who can see my policies"
        action={<button onClick={() => navigate("/sharing")} className="text-sm text-blue-700 hover:underline">Manage</button>}
      >
        <p className="text-sm text-gray-600">
          {sharedWith === 0
            ? "Only you. You haven't shared any policies with a hospital."
            : `${sharedWith} hospital${sharedWith > 1 ? "s" : ""} can see some of your policies: ${sharing.map((h) => h.org_name).join(", ")}.`}
        </p>
      </Card>
    </div>
  );
}
