import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { navigate } from "../utils/route";

const clean = (msg) => msg.replace(/^\d+: /, "");

/** Which providers can see which of my policies; share, stop sharing, remove a provider. */
export default function SharingAccess() {
  const [sharing, setSharing] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [form, setForm] = useState({ documentId: "", orgId: "" });
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([api.sharingOverview(), api.hospitalDirectory(), api.listPolicies()])
      .then(([s, h, p]) => {
        setSharing(s);
        setHospitals(h);
        setPolicies(p.filter((d) => d.owner)); // only my own documents can be shared
      })
      .catch((e) => setError(clean(e.message)));
  useEffect(() => { load(); }, []);

  const act = async (fn) => {
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(clean(e.message));
    }
  };

  const label = (d) => d.display_name || d.plan_name || d.filename;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Sharing & access</h2>
      <p className="text-sm text-gray-600">
        Providers can only see the policies you share with them, and lose access the moment you
        stop sharing.
      </p>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

      <section className="bg-white rounded-lg shadow p-5">
        <h3 className="font-semibold mb-3">Share a policy</h3>
        {policies.length === 0 ? (
          <p className="text-sm text-gray-500">
            Upload a policy under <button onClick={() => navigate("/policies")} className="text-blue-700 hover:underline">My policies</button> first.
          </p>
        ) : hospitals.length === 0 ? (
          <p className="text-sm text-gray-500">No providers are on the platform yet.</p>
        ) : (
          <div className="flex flex-wrap gap-2 text-sm">
            <select aria-label="Policy to share" value={form.documentId}
                    onChange={(e) => setForm({ ...form, documentId: e.target.value })} className="border rounded px-2 py-1">
              <option value="">Choose a policy…</option>
              {policies.map((d) => <option key={d.document_id} value={d.document_id}>{label(d)}</option>)}
            </select>
            <select aria-label="Provider to share with" value={form.orgId}
                    onChange={(e) => setForm({ ...form, orgId: e.target.value })} className="border rounded px-2 py-1">
              <option value="">Choose a provider…</option>
              {hospitals.map((h) => <option key={h.org_id} value={h.org_id}>{h.name}{h.category_label ? ` (${h.category_label})` : ""}{h.city ? ` — ${h.city}` : ""}</option>)}
            </select>
            <button disabled={!form.documentId || !form.orgId}
                    onClick={() => act(async () => {
                      await api.share(form.documentId, form.orgId);
                      setForm({ documentId: "", orgId: "" });
                    })}
                    className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50">
              Share
            </button>
          </div>
        )}
      </section>

      <section className="bg-white rounded-lg shadow">
        <h3 className="font-semibold p-4 border-b">Providers with access</h3>
        {sharing.length === 0 ? (
          <p className="p-4 text-sm text-gray-500">No provider can see your policies.</p>
        ) : (
          <ul className="divide-y">
            {sharing.map((h) => (
              <li key={h.org_id} className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <strong className="text-sm">{h.org_name}</strong>
                  <button onClick={() => act(() => api.removeHospitalAccess(h.org_id))}
                          className="text-xs text-red-700 hover:underline">
                    Remove all access
                  </button>
                </div>
                <ul className="text-sm space-y-1">
                  {h.policies.map((p) => (
                    <li key={p.share_id} className="flex items-center gap-3">
                      {p.name}
                      <button onClick={() => act(() => api.unshare(p.share_id))}
                              className="text-xs text-red-700 hover:underline">
                        Stop sharing
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-xs text-gray-500">
        A provider may also keep its own copy of your policy (for example from your insurance
        card at registration). Those are the provider's records: stopping sharing or deleting your
        account here doesn't remove them, so ask the provider directly.
      </p>
    </div>
  );
}
