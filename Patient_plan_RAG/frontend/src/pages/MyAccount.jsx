import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { navigate } from "../utils/route";

const KINDS = ["doctor", "hospital", "clinic", "pharmacy", "laboratory", "imaging", "dental", "other"];
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
const same = (a, b) => a.trim().toLowerCase() === b.trim().toLowerCase();

function Badge({ on }) {
  return on
    ? <span className="bg-green-100 text-green-800 px-2 py-0.5 rounded text-xs">On the platform</span>
    : <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs">Not on the platform</span>;
}

/** After connecting: offer to share policies with that provider (never automatic). */
function SharePrompt({ provider, policies, alreadyShared, onDone, act }) {
  const available = policies.filter((p) => !alreadyShared.has(p.document_id));
  const [chosen, setChosen] = useState([]);
  const toggle = (id) => setChosen(chosen.includes(id) ? chosen.filter((c) => c !== id) : [...chosen, id]);
  return (
    <div role="region" aria-label={`Share with ${provider.name}`} className="border rounded p-3 bg-blue-50 text-sm space-y-2">
      <p>
        <strong>{provider.name}</strong> can see your name and email, but none of your policies.
        {available.length > 0 ? " Share a policy with them?" : ""}
      </p>
      {available.length === 0 ? (
        <p className="text-gray-600">
          {policies.length === 0 ? "Upload a policy first to share it." : "All your policies are already shared with them."}
        </p>
      ) : (
        <ul className="space-y-1">
          {available.map((p) => (
            <li key={p.document_id}>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={chosen.includes(p.document_id)} onChange={() => toggle(p.document_id)} />
                {p.name}
              </label>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-3">
        {available.length > 0 && (
          <button disabled={chosen.length === 0}
                  onClick={() => act(async () => {
                    for (const id of chosen) await api.share(id, provider.org_id);
                    onDone();
                  })}
                  className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50">
            Share selected
          </button>
        )}
        <button onClick={onDone} className="text-gray-600 hover:underline">
          {available.length > 0 ? "Not now" : "Close"}
        </button>
      </div>
    </div>
  );
}

/** Find a provider on the platform; or add one by hand. */
function AddProvider({ directory, linkedOrgs, onConnected, act, onCancel }) {
  const [query, setQuery] = useState("");
  const [manual, setManual] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const q = query.trim().toLowerCase();
  const matches = directory.filter((h) => !linkedOrgs.has(h.org_id) &&
    (!q || [h.name, h.city, h.category_label].some((v) => (v || "").toLowerCase().includes(q))));

  if (manual)
    return (
      <form onSubmit={(e) => { e.preventDefault(); act(() => api.addProvider(form)); }} className="space-y-2">
        <ProviderFields form={form} setForm={setForm} />
        <button type="submit" className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700">Add provider</button>{" "}
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:underline">Cancel</button>
      </form>
    );
  return (
    <div className="space-y-2 text-sm">
      <input aria-label="Find a provider" placeholder="Find your provider by name, city or type" maxLength={100}
             value={query} onChange={(e) => setQuery(e.target.value)} className="border rounded px-2 py-1 w-full" />
      {matches.length === 0 ? (
        <p className="text-gray-500">No providers on the platform match.</p>
      ) : (
        <ul className="divide-y border rounded max-h-56 overflow-y-auto">
          {matches.map((h) => (
            <li key={h.org_id} className="flex items-center justify-between gap-2 px-2 py-1.5">
              <span>
                {h.name}
                <span className="text-gray-500"> · {h.category_label}{h.city ? ` · ${h.city}` : ""}</span>
              </span>
              <button onClick={() => act(async () => onConnected(await api.addProvider({ org_id: h.org_id })))}
                      aria-label={`Add ${h.name}`} className="text-blue-700 hover:underline text-xs">
                Add
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-gray-500">
        Adding a provider on the platform lets them see your name and email, so they can match
        you to their records. They see your policies only if you share them.
      </p>
      <div className="flex gap-3">
        <button onClick={() => setManual(true)} className="text-blue-700 hover:underline">Not listed? Add it by hand</button>
        <button onClick={onCancel} className="text-gray-500 hover:underline">Cancel</button>
      </div>
    </div>
  );
}

function ProviderFields({ form, setForm, linked = false }) {
  return (
    <div className="flex flex-wrap gap-2 items-end text-sm">
      {!linked && (
        <>
          <input aria-label="Provider name" placeholder="Name" required maxLength={120} value={form.name}
                 onChange={(e) => setForm({ ...form, name: e.target.value })} className="border rounded px-2 py-1" />
          <select aria-label="Provider type" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}
                  className="border rounded px-2 py-1 capitalize">
            {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </>
      )}
      <input aria-label="Provider phone" placeholder="Phone" maxLength={30} value={form.phone}
             onChange={(e) => setForm({ ...form, phone: e.target.value })} className="border rounded px-2 py-1 w-32" />
      <input aria-label="Provider notes" placeholder="Notes" maxLength={500} value={form.notes}
             onChange={(e) => setForm({ ...form, notes: e.target.value })} className="border rounded px-2 py-1" />
    </div>
  );
}

function Providers({ providers, sharing, policies, onChange }) {
  const [directory, setDirectory] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [adding, setAdding] = useState(false);
  const [prompt, setPrompt] = useState(null);     // provider to offer sharing with
  const [removing, setRemoving] = useState(null); // linked provider with shared policies
  const [error, setError] = useState("");

  useEffect(() => { api.hospitalDirectory().then(setDirectory).catch(() => setDirectory([])); }, []);

  const act = async (fn) => {
    setError("");
    try {
      await fn();
      setForm(EMPTY);
      setEditing(null);
      setAdding(false);
      setRemoving(null);
      onChange();
    } catch (e) {
      setError(clean(e.message));
    }
  };

  const linkedOrgs = new Set(providers.filter((p) => p.org_id).map((p) => p.org_id));
  const sharedWith = (orgId) => sharing.find((h) => h.org_id === orgId)?.policies || [];
  const matchFor = (p) => !p.org_id && directory.find((h) => same(h.name, p.name) && !linkedOrgs.has(h.org_id));
  const remove = (p) => (p.org_id && sharedWith(p.org_id).length > 0
    ? setRemoving(p.provider_id)
    : act(() => api.deleteProvider(p.provider_id)));

  return (
    <>
      {providers.length === 0 && !adding && (
        <p className="text-sm text-gray-500 mb-2">Add the doctors, clinics and pharmacies you use.</p>
      )}
      <ul className="space-y-2 text-sm mb-3">
        {providers.map((p) => {
          const match = matchFor(p);
          const shared = p.org_id ? sharedWith(p.org_id) : [];
          return (
            <li key={p.provider_id} className="space-y-1">
              {editing === p.provider_id ? (
                <form onSubmit={(e) => { e.preventDefault(); act(() => api.updateProvider(p.provider_id, form)); }}
                      className="space-y-2">
                  <ProviderFields form={form} setForm={setForm} linked={Boolean(p.org_id)} />
                  <button type="submit" className="text-blue-700 hover:underline">Save</button>{" "}
                  <button type="button" onClick={() => setEditing(null)} className="text-gray-500 hover:underline">Cancel</button>
                </form>
              ) : (
                <div className="flex flex-wrap gap-2 items-center">
                  <strong>{p.name}</strong>
                  <span className="text-gray-500 capitalize">{p.category_label || p.kind}</span>
                  {p.city && <span className="text-gray-500">· {p.city}</span>}
                  <Badge on={p.on_platform} />
                  {p.phone && <span className="text-gray-500">· {p.phone}</span>}
                  {p.notes && <span className="text-gray-500">· {p.notes}</span>}
                  {p.on_platform && (
                    <span className="text-gray-500 text-xs">
                      {shared.length ? `· ${shared.length} polic${shared.length > 1 ? "ies" : "y"} shared` : "· no policies shared"}
                    </span>
                  )}
                  {p.on_platform && (
                    <button onClick={() => setPrompt(p)} className="text-blue-700 hover:underline text-xs">Share a policy</button>
                  )}
                  <button onClick={() => { setEditing(p.provider_id); setForm({ name: p.name, kind: p.kind, phone: p.phone, notes: p.notes }); }}
                          className="text-blue-700 hover:underline text-xs">Edit</button>
                  <button onClick={() => remove(p)} className="text-red-700 hover:underline text-xs">Remove</button>
                </div>
              )}
              {match && (
                <p className="text-xs">
                  <span className="text-gray-600">{match.name} is on the platform. </span>
                  <button onClick={() => act(async () => setPrompt(await api.updateProvider(p.provider_id,
                                       { phone: p.phone, notes: p.notes, org_id: match.org_id })))}
                          className="text-blue-700 hover:underline">
                    Link to {match.name}
                  </button>
                </p>
              )}
              {removing === p.provider_id && (
                <div role="alertdialog" aria-label={`Remove ${p.name}`} className="border border-red-200 rounded p-2 bg-red-50 text-xs space-y-2">
                  <p>You share {shared.length} polic{shared.length > 1 ? "ies" : "y"} with {p.name}. Stop sharing {shared.length > 1 ? "them" : "it"} too?</p>
                  <div className="flex flex-wrap gap-3">
                    <button onClick={() => act(async () => { await api.removeHospitalAccess(p.org_id); await api.deleteProvider(p.provider_id); })}
                            className="text-red-700 font-medium hover:underline">Remove and stop sharing</button>
                    <button onClick={() => act(() => api.deleteProvider(p.provider_id))}
                            className="text-gray-700 hover:underline">Remove, keep sharing</button>
                    <button onClick={() => setRemoving(null)} className="text-gray-500 hover:underline">Cancel</button>
                  </div>
                </div>
              )}
              {prompt?.provider_id === p.provider_id && (
                <SharePrompt provider={p} policies={policies}
                             alreadyShared={new Set(shared.map((s) => s.document_id))}
                             onDone={() => { setPrompt(null); onChange(); }} act={act} />
              )}
            </li>
          );
        })}
      </ul>
      {adding ? (
        <AddProvider directory={directory} linkedOrgs={linkedOrgs} act={act}
                     onConnected={(p) => setPrompt(p)} onCancel={() => { setAdding(false); setForm(EMPTY); }} />
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
          <Providers providers={providers} sharing={sharing} onChange={load}
                     policies={insurance.flatMap((g) => g.plans)} />
        </Card>
      </div>

      <Card
        title="Who can see my policies"
        action={<button onClick={() => navigate("/sharing")} className="text-sm text-blue-700 hover:underline">Manage</button>}
      >
        <p className="text-sm text-gray-600">
          {sharedWith === 0
            ? "Only you. You haven't shared any policies with a provider."
            : `${sharedWith} provider${sharedWith > 1 ? "s" : ""} can see some of your policies: ${sharing.map((h) => h.org_name).join(", ")}.`}
        </p>
      </Card>
    </div>
  );
}
